#!/usr/bin/env python3
"""
Notification outbox delivery worker for AgingOS (P0-4-2 + P0-4-3).

Implements:
- claim (FOR UPDATE SKIP LOCKED)
- retry with exponential backoff + jitter
- dead-letter after max_attempts
- idempotent delivery via notification_deliveries unique index
- route_type='db' (no external side-effect; writes delivery receipt + ack)
- policy: NORMAL / QUIET / NIGHT + override_until + bypass_policy
"""

import os
import sys
import json
import time
import random
import socket
from datetime import datetime, timedelta, timezone

import psycopg2
import psycopg2.extras

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None


def utcnow():
    return datetime.now(timezone.utc)


def get_db_dsn() -> str:
    host = os.getenv("PGHOST", "localhost")
    port = int(os.getenv("PGPORT", "5432"))
    user = os.getenv("PGUSER", "agingos")
    password = os.getenv("PGPASSWORD", "agingos")
    dbname = os.getenv("PGDATABASE", "agingos")
    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"


def backoff_seconds(attempt_n: int, base: float = 2.0, cap: float = 300.0) -> float:
    raw = min(cap, base * (2 ** max(0, attempt_n - 1)))
    jitter = random.uniform(0, raw * 0.25)
    return raw + jitter


def get_policy(cur, org_id: str, home_id: str, subject_id: str):
    cur.execute(
        """
        SELECT mode, quiet_start_local, quiet_end_local, tz, override_until
        FROM notification_policy
        WHERE org_id=%s AND home_id=%s AND subject_id=%s
        """,
        (org_id, home_id, subject_id),
    )
    return cur.fetchone()


def in_quiet_window(now_local, start_t, end_t) -> bool:
    """
    True if now_local.time() is within [start,end).
    Handles wrap-around windows like 22:00-07:00.
    """
    if start_t is None or end_t is None:
        return False
    t = now_local.time()
    if start_t < end_t:
        return start_t <= t < end_t
    return t >= start_t or t < end_t


def compute_next_allowed_local(now_local, end_t):
    """Compute next local datetime at end_t (today or tomorrow)."""
    if end_t is None:
        return now_local
    candidate = now_local.replace(
        hour=end_t.hour,
        minute=end_t.minute,
        second=end_t.second,
        microsecond=0,
    )
    if candidate <= now_local:
        candidate = candidate + timedelta(days=1)
    return candidate


def defer_due_to_policy(cur, outbox_id: int, next_attempt_at_utc: datetime, reason: str):
    # Important: do NOT bump attempt_n for policy deferrals.
    cur.execute(
        """
        UPDATE notification_outbox
        SET status='RETRY',
            next_attempt_at=%s,
            last_error=%s,
            locked_at=NULL,
            locked_by=NULL,
            updated_at=now()
        WHERE id=%s;
        """,
        (next_attempt_at_utc, reason, outbox_id),
    )


def claim_one(cur, worker_id: str):
    cur.execute(
        """
        WITH candidate AS (
          SELECT id
          FROM notification_outbox
          WHERE status IN ('PENDING','RETRY')
            AND next_attempt_at <= now()
            AND (locked_at IS NULL OR locked_at < (now() - interval '15 minutes'))
          ORDER BY next_attempt_at ASC, id ASC
          FOR UPDATE SKIP LOCKED
          LIMIT 1
        )
        UPDATE notification_outbox o
        SET status = 'IN_FLIGHT',
            locked_at = now(),
            locked_by = %s,
            updated_at = now()
        FROM candidate
        WHERE o.id = candidate.id
        RETURNING
          o.id, o.org_id, o.home_id, o.subject_id,
          o.route_type, o.route_key, o.destination,
          o.message_type, o.severity, o.idempotency_key, o.payload,
          o.bypass_policy,
          o.status, o.attempt_n, o.max_attempts,
          o.next_attempt_at, o.last_attempt_at,
          o.delivered_at, o.acked_at;
        """,
        (worker_id,),
    )
    return cur.fetchone()


def mark_dead(cur, outbox_id: int, reason: str):
    cur.execute(
        """
        UPDATE notification_outbox
        SET status='DEAD',
            dead_letter_reason=%s,
            last_error=%s,
            locked_at=NULL,
            locked_by=NULL,
            updated_at=now()
        WHERE id=%s;
        """,
        (reason, reason, outbox_id),
    )


def schedule_retry(cur, outbox_id: int, attempt_n: int, err: str):
    delay = backoff_seconds(attempt_n)
    cur.execute(
        """
        UPDATE notification_outbox
        SET status='RETRY',
            attempt_n=%s,
            last_attempt_at=now(),
            next_attempt_at=(now() + (%s || ' seconds')::interval),
            last_error=%s,
            locked_at=NULL,
            locked_by=NULL,
            updated_at=now()
        WHERE id=%s;
        """,
        (attempt_n, delay, err, outbox_id),
    )
    return delay


def mark_delivered_and_acked(cur, outbox_id: int):
    cur.execute(
        """
        UPDATE notification_outbox
        SET status='DELIVERED',
            delivered_at=COALESCE(delivered_at, now()),
            acked_at=COALESCE(acked_at, now()),
            locked_at=NULL,
            locked_by=NULL,
            updated_at=now()
        WHERE id=%s;
        """,
        (outbox_id,),
    )


def insert_delivery_receipt(cur, row) -> bool:
    cur.execute(
        """
        INSERT INTO notification_deliveries (
          outbox_id, org_id, home_id, subject_id,
          route_type, route_key, idempotency_key,
          provider_msg_id, response
        )
        VALUES (
          %(id)s, %(org_id)s, %(home_id)s, %(subject_id)s,
          %(route_type)s, %(route_key)s, %(idempotency_key)s,
          NULL, %(response)s::jsonb
        )
        ON CONFLICT (org_id, home_id, subject_id, route_type, route_key, idempotency_key)
        DO NOTHING;
        """,
        {
            "id": row["id"],
            "org_id": row["org_id"],
            "home_id": row["home_id"],
            "subject_id": row["subject_id"],
            "route_type": row["route_type"],
            "route_key": row["route_key"],
            "idempotency_key": row["idempotency_key"],
            "response": json.dumps({"route_type": row["route_type"], "ack": True}),
        },
    )
    return cur.rowcount == 1


def deliver_db(cur, row):
    inserted = insert_delivery_receipt(cur, row)
    mark_delivered_and_acked(cur, row["id"])
    return {"ok": True, "receipt_inserted": inserted}


def deliver(cur, row):
    rt = row["route_type"]
    if rt == "db":
        return deliver_db(cur, row)
    raise RuntimeError(f"Unsupported route_type: {rt}")


def apply_policy_or_none(cur, row) -> bool:
    """
    Returns True if deferred due to policy (and caller should commit+continue),
    False if delivery is allowed.
    """
    if row["bypass_policy"]:
        return False

    pol = get_policy(cur, row["org_id"], row["home_id"], row["subject_id"])
    if not pol:
        return False

    mode = pol.get("mode")
    tzname = pol.get("tz") or "Europe/Oslo"
    override_until = pol.get("override_until")

    if override_until and override_until > utcnow():
        return False

    if mode not in ("QUIET", "NIGHT"):
        return False

    if ZoneInfo is None:
        # If zoneinfo unavailable, do not block delivery.
        return False

    now_local = utcnow().astimezone(ZoneInfo(tzname))
    if in_quiet_window(now_local, pol.get("quiet_start_local"), pol.get("quiet_end_local")):
        next_local = compute_next_allowed_local(now_local, pol.get("quiet_end_local"))
        next_utc = next_local.astimezone(timezone.utc)
        defer_due_to_policy(cur, int(row["id"]), next_utc, f"policy_defer:{mode}")
        return True

    return False


def run_once(limit: int = 1) -> int:
    worker_id = os.getenv("WORKER_ID", socket.gethostname())
    dsn = os.getenv("DATABASE_URL", get_db_dsn())

    conn = psycopg2.connect(dsn)
    conn.autocommit = False

    processed = 0
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            for _ in range(limit):
                cur.execute("BEGIN;")
                row = claim_one(cur, worker_id)
                if not row:
                    conn.rollback()
                    break
                outbox_id = int(row["id"])
                max_attempts = int(row["max_attempts"])

                try:
                    # Policy gate first
                    if apply_policy_or_none(cur, row):
                        conn.commit()
                        processed += 1
                        continue

                    # Attempt delivery
                    deliver(cur, row)
                    conn.commit()
                    processed += 1

                except Exception as e:
                    err = f"{type(e).__name__}: {e}"
                    attempt_n = int(row["attempt_n"]) + 1

                    if attempt_n >= max_attempts:
                        mark_dead(cur, outbox_id, f"max_attempts_reached: {err}")
                        conn.commit()
                        processed += 1
                    else:
                        schedule_retry(cur, outbox_id, attempt_n, err)
                        conn.commit()
                        processed += 1
    finally:
        conn.close()

    return processed


def main():
    limit = 1
    if len(sys.argv) >= 2:
        limit = int(sys.argv[1])

    n = run_once(limit=limit)
    print(f"processed={n}")


if __name__ == "__main__":
    main()
