"""
Outbox Worker
- Polls unprocessed outbox events
- For MessageChanged events where message.status == QUEUED: send via WhatsApp
- Retries with exponential backoff using Redis
- DLQs after max retries
- ALWAYS sets `SET LOCAL app.jwt_tenant = :tenant_id` before tenant-scoped DB ops
"""

import asyncio
import json
import os
import signal
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from src.shared.database import get_engine, get_session  # adjust path if different
engine = get_engine()
SessionLocal = get_session()

from dotenv import load_dotenv
load_dotenv()
# --------------------------
# Configuration
# --------------------------

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("DATABASE_URL")  # e.g. postgresql+asyncpg://...
REDIS_URL = os.getenv("REDIS_URL") or os.getenv("REDIS_URL".lower()) or "redis://localhost:6379/0"
WHATSAPP_API_BASE = os.getenv("WHATSAPP_API_BASE", "https://graph.facebook.com/v21.0")
MAX_RETRIES = int(os.getenv("OUTBOX_MAX_RETRIES", "5"))
BACKOFF_BASE_SECONDS = float(os.getenv("OUTBOX_BACKOFF_BASE_SECONDS", "2"))  # 2,4,8,16,...
BACKOFF_MAX_SECONDS = float(os.getenv("OUTBOX_BACKOFF_MAX_SECONDS", "60"))
POLL_INTERVAL_SECONDS = float(os.getenv("OUTBOX_POLL_INTERVAL_SECONDS", "1.0"))
BATCH_SIZE = int(os.getenv("OUTBOX_BATCH_SIZE", "50"))
HTTP_TIMEOUT_SECONDS = float(os.getenv("OUTBOX_HTTP_TIMEOUT_SECONDS", "15"))


# --------------------------
# Helpers
# --------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def backoff_seconds(attempt: int) -> float:
    # attempt starts at 1
    delay = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
    return min(delay, BACKOFF_MAX_SECONDS)

def redis_keys_for_message(message_id: str):
    # per-message retry bookkeeping in Redis
    return {
        "attempts": f"outbox:msg:{message_id}:attempts",
        "not_before": f"outbox:msg:{message_id}:not_before_ts",
        "dlq": f"dlq:messages"  # list
    }

@asynccontextmanager
async def lifespan_tasks():
    # graceful shutdown for worker
    stop_event = asyncio.Event()

    def _handle_sig(*_):
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_sig)
        except NotImplementedError:
            pass  # on Windows

    try:
        yield stop_event
    finally:
        stop_event.set()


# --------------------------
# Infrastructure singletons
# --------------------------


redis = aioredis.from_url(REDIS_URL, decode_responses=True)
http = httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)


# --------------------------
# WhatsApp API client
# --------------------------

async def _compose_wa_payload(message_row: dict) -> dict:
    """
    Compose a WA API payload from messages.content_jsonb.
    Supports simple text messages and raw payload passthrough.
    """
    content = message_row["content_jsonb"]
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except Exception:
            content = {"text": {"body": content}}

    # minimal support: text or ready-made object (template/media supported upstream)
    if "text" in content:
        return {
            "messaging_product": "whatsapp",
            "to": message_row["to_phone"],
            "type": "text",
            "text": {"body": content["text"]["body"]},
        }

    # if upstream already built the WA payload structure, pass it through
    base = {
        "messaging_product": "whatsapp",
        "to": message_row["to_phone"],
    }
    base.update(content)
    return base


async def send_via_whatsapp(session: AsyncSession, message_id: str) -> tuple[bool, str | None, int | None, str | None]:
    """
    Sends a queued message via WhatsApp Graph API.
    Returns: (success, wa_message_id, http_status, error_text)
    """
    # Fetch message & channel (under tenant RLS)
    # We DO NOT trust outbox payload blindly; we read normalized state from DB.
    row = (
        await session.execute(
            text(
                """
                SELECT m.id, m.channel_id, m.to_phone, m.from_phone,
                       m.content_jsonb, m.status, m.retry_count,
                       c.phone_number_id, c.business_phone, c.api_token
                FROM messages m
                JOIN whatsapp_channels c ON c.id = m.channel_id AND c.tenant_id = m.tenant_id
                WHERE m.id = :mid
                """
            ),
            {"mid": message_id},
        )
    ).mappings().first()

    if not row:
        return (False, None, 404, "message_not_found")

    if row["status"] != "QUEUED":
        return (True, None, 200, "noop_not_queued")

    # Compose request
    phone_number_id = row["phone_number_id"]
    bearer = row["api_token"]  # stored encrypted in prod; decrypt upstream if needed

    payload = await _compose_wa_payload(row)
    url = f"{WHATSAPP_API_BASE}/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {bearer}"}

    try:
        resp = await http.post(url, headers=headers, json=payload)
    except httpx.RequestError as e:
        return (False, None, None, f"network_error:{e.__class__.__name__}")

    # Parse WA response
    if resp.status_code in (200, 201):
        data = resp.json()
        wa_id = None
        try:
            wa_id = data["messages"][0]["id"]
        except Exception:
            wa_id = None
        return (True, wa_id, resp.status_code, None)

    # Common error handling cases we contract-test (429/409)
    try:
        err_json = resp.json()
        err_msg = json.dumps(err_json, separators=(",", ":"), ensure_ascii=False)
    except Exception:
        err_msg = resp.text

    return (False, None, resp.status_code, err_msg or "unknown_error")


# --------------------------
# Outbox processing
# --------------------------

async def fetch_outbox_batch(session: AsyncSession):
    """
    Fetch a batch of unprocessed outbox events (skip locked) for concurrent-safe consumption.
    We keep this query *not* tenant-scoped so the worker can see all events.
    """
    res = await session.execute(
        text(
            f"""
            SELECT id, tenant_id, aggregate_type, event_type, payload_jsonb
            FROM outbox_events
            WHERE processed_at IS NULL
            ORDER BY created_at
            FOR UPDATE SKIP LOCKED
            LIMIT :lim
            """
        ),
        {"lim": BATCH_SIZE},
    )
    return [dict(r) for r in res.mappings().all()]


async def mark_event_processed(session: AsyncSession, event_id: str):
    await session.execute(
        text("UPDATE outbox_events SET processed_at = now() WHERE id = :id"),
        {"id": event_id},
    )


async def process_message_changed(session: AsyncSession, evt: dict) -> None:
    """
    Handles MessageChanged outbox event:
      - If message.status == QUEUED → attempt send
      - Retry with exponential backoff via Redis
      - DLQ after MAX_RETRIES
    """
    payload = evt.get("payload") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}

    message_id = payload.get("id") or payload.get("message_id")
    status = payload.get("status")

    if not message_id:
        # malformed event; mark processed to avoid poison loop
        await mark_event_processed(session, evt["id"])
        return

    # Backoff gate (Redis): don't attempt before "not_before"
    keys = redis_keys_for_message(message_id)
    not_before_ts = await redis.get(keys["not_before"])
    if not_before_ts is not None:
        try:
            nb = float(not_before_ts)
            if nb > _utcnow().timestamp():
                # too early — skip without marking processed (will be retried next poll)
                return
        except ValueError:
            pass

    # Only attempt if currently QUEUED (trust DB, not payload)
    # Set tenant before any tenant-scoped query
    await session.execute(text("SET LOCAL app.jwt_tenant = :tid"), {"tid": str(evt["tenant_id"])})

    success, wa_id, http_status, error_text = await send_via_whatsapp(session, message_id)

    if success:
        # Transition message → SENT and store WA id
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
        # Mark event done
        await mark_event_processed(session, evt["id"])
        return

    # Failure path: decide retry vs DLQ
    # Increment attempts in Redis
    attempts = await redis.incr(keys["attempts"])
    # contract-specific branches
    if http_status == 409:
        # Treat idempotency conflict as success/no-op in outbox (don't spam)
        await mark_event_processed(session, evt["id"])
        return

    if http_status == 429 or (http_status is None) or (500 <= (http_status or 500) < 600):
        # Retryable: schedule next attempt
        delay = backoff_seconds(attempts)
        not_before = _utcnow().timestamp() + delay
        await redis.set(keys["not_before"], str(not_before), ex=int(delay) + 5)
        # Keep the event unprocessed so we’ll pick it up later
        # Optionally increment messages.retry_count for visibility
        await session.execute(
            text("UPDATE messages SET retry_count = COALESCE(retry_count,0) + 1 WHERE id = :mid"),
            {"mid": message_id},
        )
        # DLQ if over max
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
            await mark_event_processed(session, evt["id"])
            # Push to Redis DLQ for ops visibility
            await redis.lpush(keys["dlq"], json.dumps({
                "message_id": message_id,
                "event_id": evt["id"],
                "tenant_id": str(evt["tenant_id"]),
                "reason": f"retry_exhausted:{http_status}",
                "error": error_text,
                "ts": _utcnow().isoformat(),
            }))
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
    await mark_event_processed(session, evt["id"])
    await redis.lpush(
        keys["dlq"],
        json.dumps(
            {
                "message_id": message_id,
                "event_id": evt["id"],
                "tenant_id": str(evt["tenant_id"]),
                "reason": f"non_retryable:{http_status}",
                "error": error_text,
                "ts": _utcnow().isoformat(),
            }
        ),
    )


async def handle_event(session: AsyncSession, evt: dict) -> None:
    """
    Dispatch by aggregate/event type
    """
    if evt["aggregate_type"] == "Message" and evt["event_type"] == "MessageChanged":
        await process_message_changed(session, evt)
    else:
        # Unhandled event types: mark processed to avoid pile-up
        await mark_event_processed(session, evt["id"])


# --------------------------
# Main loop
# --------------------------

async def run_once() -> int:
    """
    Run a single polling iteration. Returns number of events processed/considered.
    """
    async with SessionLocal.begin() as session:  # transactional; outbox rows are FOR UPDATE SKIP LOCKED
        events = await fetch_outbox_batch(session)
        for evt in events:
            try:
                # Each event processing uses its own nested txn boundary via the same session
                await handle_event(session, evt)
            except Exception as e:
                # Last-resort poison event handling:
                # Do NOT mark as processed; log via Redis DLQ so ops can inspect.
                try:
                    await redis.lpush(
                        "dlq:outbox_events",
                        json.dumps(
                            {
                                "event_id": evt["id"],
                                "tenant_id": str(evt.get("tenant_id")),
                                "reason": f"handler_exception:{e.__class__.__name__}",
                                "ts": _utcnow().isoformat(),
                            }
                        ),
                    )
                except Exception:
                    pass
        return len(events)


async def main():
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL is not configured", file=sys.stderr)
        sys.exit(1)

    print("[outbox-worker] starting …", flush=True)
    async with lifespan_tasks() as stop_event:
        while not stop_event.is_set():
            try:
                processed = await run_once()
                if processed == 0:
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
            except Exception as e:
                # global loop guard; don't crash the worker
                print(f"[outbox-worker] loop error: {e}", file=sys.stderr)
                await asyncio.sleep(1.0)

    print("[outbox-worker] stopping", flush=True)
    await http.aclose()
    await redis.close()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())