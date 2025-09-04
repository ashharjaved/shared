# src/worker/outbox_worker.py
from __future__ import annotations

import asyncio
import json
import os
import signal
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine, async_sessionmaker

# =========================
# Config
# =========================

DB_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:123456@localhost:5432/centralize_api")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Polling cadence
POLL_INTERVAL_SECONDS = float(os.getenv("OUTBOX_POLL_INTERVAL_SECONDS", "1.0"))
BATCH_SIZE = int(os.getenv("OUTBOX_BATCH_SIZE", "20"))

# Retry/backoff
MAX_RETRIES = int(os.getenv("OUTBOX_MAX_RETRIES", "5"))
BACKOFF_BASE_SECONDS = float(os.getenv("OUTBOX_BACKOFF_BASE_SECONDS", "2.0"))
BACKOFF_MAX_SECONDS = float(os.getenv("OUTBOX_BACKOFF_MAX_SECONDS", "60.0"))

# WhatsApp API (replace/extend as needed)
WHATSAPP_GRAPH_BASE = os.getenv("WHATSAPP_GRAPH_BASE", "https://graph.facebook.com/v21.0")

# =========================
# Utilities
# =========================

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def backoff_seconds(attempts: int) -> float:
    # simple exponential backoff with cap
    delay = BACKOFF_BASE_SECONDS * (2 ** max(0, attempts - 1))
    return min(delay, BACKOFF_MAX_SECONDS)

def redis_keys_for_message(message_id: str) -> Dict[str, str]:
    base = f"msg:{message_id}"
    return {
        "attempts": f"{base}:attempts",
        "not_before": f"{base}:not_before",
        "dlq": f"{base}:dlq",
    }

# =========================
# Data models (event shape)
# =========================

@dataclass
class OutboxEvent:
    id: str
    tenant_id: Optional[str]
    aggregate_type: str
    event_type: str
    payload: Any
    created_at: Optional[str]

# =========================
# Worker core
# =========================

class OutboxWorker:
    def __init__(self, engine: AsyncEngine, redis: Redis):
        self.engine = engine
        self.redis = redis
        self._stop = asyncio.Event()

        self._Session = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        print("[outbox-worker] starting …", flush=True)
        try:
            while not self._stop.is_set():
                events = await self._fetch_pending_events(limit=BATCH_SIZE)
                print(f"[outbox-worker] polled; events_seen={len(events)}", flush=True)

                if not events:
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
                    continue

                handled = 0
                async with self._Session() as session:
                    for evt in events:
                        try:
                            await self._handle_event(session, evt)
                            handled += 1
                        except Exception as e:
                            # If a single event explosions, isolate it, mark processed, and push DLQ
                            print(f"[outbox-worker] error handling event={evt.id}: {e}", flush=True)
                            try:
                                await self._mark_event_processed(session, evt.id)
                            except Exception:
                                pass
                            try:
                                self.redis.lpush(
                                    "dlq:outbox_events",
                                    json.dumps(
                                        {
                                            "event_id": evt.id,
                                            "reason": "handler_exception",
                                            "error": str(e),
                                            "aggregate_type": evt.aggregate_type,
                                            "event_type": evt.event_type,
                                            "ts": _utcnow().isoformat(),
                                        }
                                    ),
                                )
                            except Exception:
                                pass
                    try:
                        await session.commit()
                    except Exception:
                        await session.rollback()
                        raise

                print(f"[outbox-worker] handled={handled}, skipped={len(events) - handled}", flush=True)
        except asyncio.CancelledError:
            pass
        finally:
            print("[outbox-worker] stopping", flush=True)

    async def _fetch_pending_events(self, limit: int) -> List[OutboxEvent]:
        # Fetch events that are not yet processed
        # IMPORTANT: Do not set jwt_tenant here; outbox_events is cross-tenant metadata.
        query = text(
            """
            SELECT id, tenant_id, aggregate_type, event_type, payload_jsonb, created_at
            FROM outbox_events
            WHERE processed_at IS NULL
            ORDER BY created_at ASC
            LIMIT :lim
            """
        )
        async with self.engine.connect() as conn:
            res = await conn.execute(query, {"lim": limit})
            rows = res.mappings().all()

        events: List[OutboxEvent] = []
        for r in rows:
            payload = r.get("payload_jsonb")
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    pass
            created_at = r.get("created_at")
            events.append(
                OutboxEvent(
                    id=str(r["id"]),
                    tenant_id=(str(r["tenant_id"]) if r.get("tenant_id") else None),
                    aggregate_type=r["aggregate_type"],
                    event_type=r["event_type"],
                    payload=payload,
                    created_at=(created_at.isoformat() if created_at is not None else None),
                )
            )
        return events

    async def _handle_event(self, session: AsyncSession, evt: OutboxEvent) -> None:
        # Dispatcher
        if evt.aggregate_type == "Message" and evt.event_type == "MessageChanged":
            await self._process_message_changed(session, evt)
            return

        # Unknown event → mark processed (don’t poison)
        await self._mark_event_processed(session, evt.id)

    async def _mark_event_processed(self, session: AsyncSession, event_id: str) -> None:
        await session.execute(
            text(
                """
                UPDATE outbox_events
                SET processed_at = NOW()
                WHERE id = :eid
                """
            ),
            {"eid": event_id},
        )

    # =========================
    # Message handler
    # =========================

    async def _process_message_changed(self, session: AsyncSession, evt: OutboxEvent) -> None:
        """
        Handle MessageChanged:
          - If message.status == QUEUED → attempt send
          - Retry with exponential backoff via Redis
          - DLQ after MAX_RETRIES
        """
        payload = evt.payload or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}

        message_id = payload.get("id") or payload.get("message_id")
        # status from payload is not trusted; DB is the source of truth.
        if not message_id:
            # malformed event; mark processed to avoid poison loop
            await self._mark_event_processed(session, evt.id)
            return

        # Backoff gate (Redis): don't attempt before "not_before"
        keys = redis_keys_for_message(message_id)
        not_before_ts = await self.redis.get(keys["not_before"])
        if not_before_ts is not None:
            try:
                nb = float(not_before_ts)
                if nb > _utcnow().timestamp():
                    eta = int(nb - _utcnow().timestamp())
                    print(f"[outbox-worker] backoff active for {message_id}; retry in ~{eta}s", flush=True)
                    return
            except ValueError:
                pass

        # Determine tenant_id for RLS (prefer event → payload)
        tenant_id = evt.tenant_id or payload.get("tenant_id")
        if not tenant_id:
            # No tenant context → log + mark processed + DLQ; do not proceed.
            try:
                print(
                    f"[outbox-worker] missing tenant_id for event={evt.id} msg={message_id}; DLQ",
                    flush=True,
                )
            except Exception:
                pass
            await self._mark_event_processed(session, evt.id)
            try:
                self.redis.lpush(
                    "dlq:outbox_events",
                    json.dumps(
                        {
                            "event_id": evt.id,
                            "reason": "missing_tenant_id",
                            "message_id": message_id,
                            "evt_payload_keys": list((payload or {}).keys()),
                            "ts": _utcnow().isoformat(),
                        }
                    ),
                )
            except Exception:
                pass
            return

        # Set tenant context (RLS)
        await session.execute(text("SELECT set_config('app.jwt_tenant', :tid, true)"), {"tid": str(tenant_id)})

        # Gate on actual DB status to keep idempotency tight
        res = await session.execute(
            text("SELECT status FROM messages WHERE id = :mid"),
            {"mid": message_id},
        )
        row = res.mappings().first()
        if not row:
            # Not visible (RLS?) or already gone → mark done
            await self._mark_event_processed(session, evt.id)
            return

        if row["status"] != "QUEUED":
            # Nothing to do for non-queued states
            await self._mark_event_processed(session, evt.id)
            return

        # ---- Attempt send via provider ----
        success, wa_id, http_status, error_text = await self._send_via_whatsapp(session, message_id)

        if success:
            # Transition → SENT and store WA id
            await session.execute(
                text(
                    """
                    UPDATE messages
                    SET status = 'SENT',
                        whatsapp_message_id = COALESCE(:waid, whatsapp_message_id),
                        status_updated_at = now(),
                        retry_count = 0
                    WHERE id = :mid
                    """
                ),
                {"mid": message_id, "waid": wa_id},
            )
            await self._mark_event_processed(session, evt.id)
            return

        # Failure path
        attempts = await self.redis.incr(keys["attempts"])
        # Treat idempotency conflict like success/no-op: do not spam
        if http_status == 409:
            await self._mark_event_processed(session, evt.id)
            return

        # Retryable?
        if http_status == 429 or (http_status is None) or (500 <= (http_status or 500) < 600):
            delay = backoff_seconds(attempts)
            not_before = _utcnow().timestamp() + delay
            await self.redis.set(keys["not_before"], str(not_before), ex=int(delay) + 5)
            # visible counter in DB (optional)
            await session.execute(
                text("UPDATE messages SET retry_count = COALESCE(retry_count,0) + 1 WHERE id = :mid"),
                {"mid": message_id},
            )
            if attempts >= MAX_RETRIES:
                await session.execute(
                    text(
                        """
                        UPDATE messages
                        SET status = 'FAILED',
                            status_updated_at = now()
                        WHERE id = :mid
                        """
                    ),
                    {"mid": message_id},
                )
                await self._mark_event_processed(session, evt.id)
                try:
                    self.redis.lpush(
                        keys["dlq"],
                        json.dumps(
                            {
                                "message_id": message_id,
                                "event_id": evt.id,
                                "tenant_id": str(tenant_id),
                                "reason": f"retry_exhausted:{http_status}",
                                "error": error_text,
                                "ts": _utcnow().isoformat(),
                            }
                        ),
                    )
                except Exception:
                    pass
            return

        # Non-retryable 4xx → mark FAILED + DLQ
        await session.execute(
            text(
                """
                UPDATE messages
                SET status = 'FAILED',
                    error_code = :ecode,
                    status_updated_at = now(),
                    retry_count = COALESCE(retry_count,0)
                WHERE id = :mid
                """
            ),
            {"mid": message_id, "ecode": f"http_{http_status}"},
        )
        await self._mark_event_processed(session, evt.id)
        try:
            self.redis.lpush(
                keys["dlq"],
                json.dumps(
                    {
                        "message_id": message_id,
                        "event_id": evt.id,
                        "tenant_id": str(tenant_id),
                        "reason": f"non_retryable:{http_status}",
                        "error": error_text,
                        "ts": _utcnow().isoformat(),
                    }
                ),
            )
        except Exception:
            pass

    # =========================
    # Provider adapter (WhatsApp Graph API)
    # =========================
    async def _send_via_whatsapp(
        self, session: AsyncSession, message_id: str
    ) -> Tuple[bool, Optional[str], Optional[int], Optional[str]]:
        """
        Actually send message via WhatsApp Graph API.
        Returns (success, wa_id, http_status, error_text).
        """

        # Fetch message + channel details
        row = (
            await session.execute(
                text(
                    """
                    SELECT m.id, m.to_phone, m.content_jsonb, m.message_type,
                           c.phone_number_id, c.access_token_ciphertext, c.tenant_id
                    FROM messages m
                    JOIN whatsapp_channels c ON m.channel_id = c.id
                    WHERE m.id = :mid
                    """
                ),
                {"mid": message_id},
            )
        ).mappings().first()

        if not row:
            return False, None, None, "message_not_found"

        # Prepare token (decrypt in real impl; here plaintext for dev)
        token = row["access_token_ciphertext"]

        # Construct request
        phone_number_id = row["phone_number_id"]
        to_phone = row["to_phone"]
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": row["message_type"].lower(),
            row["message_type"].lower(): row["content_jsonb"],
        }

        url = f"{WHATSAPP_GRAPH_BASE}/{phone_number_id}/messages"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    json=payload,
                )

            # Structured log of request + response
            log_entry = {
                "event": "whatsapp_send",
                "message_id": message_id,
                "tenant_id": str(row["tenant_id"]),
                "channel_phone_id": str(phone_number_id),
                "to": to_phone,
                "payload": payload,
                "status_code": resp.status_code,
                "resp_text": resp.text,
            }
            print(json.dumps(log_entry), flush=True)

            if resp.is_success:
                wa_id = (
                    resp.json()
                    .get("messages", [{}])[0]
                    .get("id")
                )
                return True, wa_id, resp.status_code, None
            else:
                return False, None, resp.status_code, resp.text

        except Exception as e:
            print(
                json.dumps(
                    {
                        "event": "whatsapp_send_exception",
                        "message_id": message_id,
                        "error": str(e),
                    }
                ),
                flush=True,
            )
            return False, None, None, str(e)


# =========================
# Entrypoint
# =========================

async def main() -> None:
    engine = create_async_engine(DB_URL, pool_pre_ping=True)
    redis = Redis.from_url(REDIS_URL, decode_responses=True)

    worker = OutboxWorker(engine, redis)

    # Graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, worker.stop)
        except NotImplementedError:
            # Windows
            pass

    try:
        await worker.run()
    finally:
        try:
            await redis.aclose()
        except Exception:
            pass
        try:
            await engine.dispose()
        except Exception:
            pass


if __name__ == "__main__":
    # Allow: python -m src.worker.outbox_worker
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass