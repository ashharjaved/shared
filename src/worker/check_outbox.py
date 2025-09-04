# check_outbox.py
# Usage:
#   python check_outbox.py 481a9d49-71e0-43f5-a0c4-44ec4c077d69
# Optional:
#   python check_outbox.py <msg_id> --tenant 00000000-0000-0000-0000-000000000000
#   python check_outbox.py <msg_id> --pg "postgresql+asyncpg://user:pass@localhost:5432/yourdb" --redis "redis://localhost:6379/0"

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone

import asyncpg
import redis.asyncio as aioredis

DEFAULT_PG = os.getenv("DATABASE_URL", "postgresql://postgres:123456@localhost:5432/centralize_api")
DEFAULT_REDIS = os.getenv("REDIS_URL", "redis://localhost:6379/0")

REDIS_KEY_TEMPLATE = "outbox:msg:{id}:{suffix}"

SQL_FIND_EVENT = """
SELECT id, aggregate_type, aggregate_id, event_type, payload_jsonb, created_at, processed_at
FROM outbox_events
WHERE aggregate_id = $1
ORDER BY created_at DESC
LIMIT 5
"""

SQL_SET_GUC = "SELECT set_config('app.jwt_tenant', $1, true)"

SQL_SELECT_MESSAGE = """
SELECT id, tenant_id, channel_id, direction, status, retry_count,
       whatsapp_message_id, error_code, created_at, status_updated_at, from_phone, to_phone
FROM messages
WHERE id = $1
"""

def ts(i):
    try:
        return datetime.fromtimestamp(float(i), tz=timezone.utc).isoformat()
    except Exception:
        return None

async def fetch_outbox_events(conn, msg_id):
    rows = await conn.fetch(SQL_FIND_EVENT, msg_id)
    events = []
    for r in rows:
        payload = r["payload_jsonb"]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                pass
        events.append({
            "id": str(r["id"]),
            "aggregate_type": r["aggregate_type"],
            "aggregate_id": str(r["aggregate_id"]),
            "event_type": r["event_type"],
            "payload": payload,
            "created_at": r["created_at"].isoformat(),
            "processed_at": r["processed_at"].isoformat() if r["processed_at"] else None,
        })
    return events

def derive_tenant_from_events(events):
    for ev in events:
        p = ev.get("payload") or {}
        # try typical fields
        tid = p.get("tenant_id") or p.get("tenantId")
        if tid:
            return tid
    return None

async def fetch_message(conn, msg_id):
    row = await conn.fetchrow(SQL_SELECT_MESSAGE, msg_id)
    return dict(row) if row else None

async def check_redis(r, msg_id):
    keys = {
        "attempts": REDIS_KEY_TEMPLATE.format(id=msg_id, suffix="attempts"),
        "not_before_ts": REDIS_KEY_TEMPLATE.format(id=msg_id, suffix="not_before_ts"),
        "lock": REDIS_KEY_TEMPLATE.format(id=msg_id, suffix="lock"),
        "last_error": REDIS_KEY_TEMPLATE.format(id=msg_id, suffix="last_error"),
    }
    out = {}
    for name, key in keys.items():
        val = await r.get(key)
        ttl = await r.ttl(key)
        out[name] = {"key": key, "value": val, "ttl": ttl}
    return out

def print_section(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

def recommendation(msg, redisinfo):
    reasons = []

    if not msg:
        return "Message not found (or RLS blocked it). Ensure the correct tenant is set."

    # Status-based skip
    st = msg.get("status")
    if st and st != "QUEUED":
        reasons.append(f"- Message status is '{st}', not 'QUEUED' → worker will skip.")

    # Backoff related
    nbt = redisinfo.get("not_before_ts", {}).get("value")
    if nbt:
        iso = ts(nbt)
        reasons.append(f"- Backoff active: not_before_ts={nbt} ({iso}). Worker will skip until then.")

    # Lock
    lockv = redisinfo.get("lock", {}).get("value")
    if lockv:
        reasons.append("- Lock key present → another worker/process may be handling it.")

    # Attempts
    attempts = redisinfo.get("attempts", {}).get("value")
    if attempts and attempts.isdigit() and int(attempts) > 0:
        reasons.append(f"- Attempts so far: {attempts}")

    if not reasons:
        reasons.append("- No obvious blocker found. If still skipped, check RLS GUC and event payload shape.")

    return "\n".join(reasons)

async def main():
    ap = argparse.ArgumentParser(description="Inspect WhatsApp outbox message state.")
    ap.add_argument("message_id", help="UUID of the message")
    ap.add_argument("--tenant", help="Tenant UUID to set as app.jwt_tenant (optional)")
    ap.add_argument("--pg", default=DEFAULT_PG, help=f"Postgres DSN (default: {DEFAULT_PG})")
    ap.add_argument("--redis", default=DEFAULT_REDIS, help=f"Redis URL (default: {DEFAULT_REDIS})")
    args = ap.parse_args()

    # Connect Redis
    r = aioredis.from_url(args.redis, decode_responses=True)

    # Connect Postgres (asyncpg)
    conn = await asyncpg.connect(args.pg)

    try:
        print_section("OUTBOX EVENTS (latest 5)")
        events = await fetch_outbox_events(conn, args.message_id)
        for ev in events:
            print(json.dumps(ev, indent=2, default=str))
        if not events:
            print("(no outbox_events found for this message id)")

        # Determine tenant_id to set GUC
        tenant_id = args.tenant or derive_tenant_from_events(events)
        if tenant_id:
            print_section("SETTING RLS CONTEXT (GUC)")
            await conn.execute(SQL_SET_GUC, tenant_id)
            print(f"app.jwt_tenant set to {tenant_id}")
        else:
            print_section("RLS CONTEXT (GUC) NOT SET")
            print("Could not derive tenant_id from events payload. Pass --tenant <UUID> if needed.")
        
        print_section("MESSAGE ROW")
        msg = await fetch_message(conn, args.message_id)
        if msg:
            # Convert datetimes to iso strings for pretty print
            for k in ("created_at", "status_updated_at"):
                if msg.get(k) and hasattr(msg[k], "isoformat"):
                    msg[k] = msg[k].isoformat()
            print(json.dumps(msg, indent=2, default=str))
        else:
            print("(message not found or RLS prevented access)")

        print_section("REDIS KEYS")
        rinfo = await check_redis(r, args.message_id)
        printable = {}
        for k, v in rinfo.items():
            vv = v["value"]
            if k == "not_before_ts" and vv:
                printable[k] = {**v, "iso": ts(vv)}
            else:
                printable[k] = v
        print(json.dumps(printable, indent=2))

        print_section("DIAGNOSIS")
        print(recommendation(msg, rinfo))

        print("\nTips:")
        print("- If status != QUEUED, set it back to QUEUED (only if safe) or create a fresh message.")
        print("- If backoff is set (not_before_ts), wait until that time or clear cautiously for testing:")
        print(f"    redis-cli DEL {REDIS_KEY_TEMPLATE.format(id=args.message_id, suffix='not_before_ts')}")
        print("- Ensure the worker sets the tenant GUC before selecting/updating messages.")
    finally:
        await conn.close()
        await r.close()

if __name__ == "__main__":
    asyncio.run(main())
