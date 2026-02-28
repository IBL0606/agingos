#!/usr/bin/env python3
import os
import json
import subprocess
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any, List

import psycopg2
import psycopg2.extras


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_ts(s: str) -> datetime:
    # Expect ISO 8601 or RFC3339 with Z/offset
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def db_connect():
    # Prefer DATABASE_URL if set, else default to local docker-compose postgres exposure
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        host = os.getenv("PGHOST", "localhost")
        port = os.getenv("PGPORT", "5432")
        user = os.getenv("PGUSER", "agingos")
        pwd = os.getenv("PGPASSWORD", "agingos")
        db = os.getenv("PGDATABASE", "agingos")
        dsn = f"postgresql://{user}:{pwd}@{host}:{port}/{db}"
    return psycopg2.connect(dsn)


def get_scope_via_api() -> Dict[str, str]:
    base_url = os.getenv("BASE_URL")
    api_key = os.getenv("API_KEY")
    if not base_url or not api_key:
        raise RuntimeError(
            "BASE_URL and API_KEY must be set to fetch scope via /debug/scope"
        )

    # Use existing wrapper if present, else raw curl
    wrapper = os.path.join(os.path.dirname(__file__), "curl_api.sh")
    if os.path.exists(wrapper):
        cmd = [wrapper, f"{base_url}/debug/scope"]
        out = subprocess.check_output(cmd)
    else:
        cmd = ["curl", "-sS", f"{base_url}/debug/scope", "-H", f"X-API-Key: {api_key}"]
        out = subprocess.check_output(cmd)

    scope = json.loads(out.decode("utf-8"))
    for k in ("org_id", "home_id", "subject_id"):
        if k not in scope or not scope[k]:
            raise RuntimeError(f"Scope missing {k}: {scope}")
    return {
        "org_id": scope["org_id"],
        "home_id": scope["home_id"],
        "subject_id": scope["subject_id"],
    }


def ensure_state_row(
    cur, org_id: str, home_id: str, subject_id: str, builder_name: str
) -> None:
    cur.execute(
        """
        INSERT INTO episode_builder_state (org_id, home_id, subject_id, builder_name)
        VALUES (%s,%s,%s,%s)
        ON CONFLICT (org_id, home_id, subject_id, builder_name) DO NOTHING
        """,
        (org_id, home_id, subject_id, builder_name),
    )


def read_watermark_for_update(
    cur, org_id: str, home_id: str, subject_id: str, builder_name: str
) -> Tuple[Optional[datetime], Optional[int]]:
    cur.execute(
        """
        SELECT last_event_ts, last_event_row_id
        FROM episode_builder_state
        WHERE org_id=%s AND home_id=%s AND subject_id=%s AND builder_name=%s
        FOR UPDATE
        """,
        (org_id, home_id, subject_id, builder_name),
    )
    row = cur.fetchone()
    if not row:
        return (None, None)
    return (row["last_event_ts"], row["last_event_row_id"])


def fetch_events(
    cur,
    org_id: str,
    home_id: str,
    subject_id: str,
    wm_ts: Optional[datetime],
    wm_id: Optional[int],
    since: Optional[datetime],
    until: Optional[datetime],
    batch: int,
) -> List[Dict[str, Any]]:
    # Presence-only v1 (deterministisk med room+state)
    params = [org_id, home_id, subject_id, os.getenv("AGINGOS_STREAM_ID", "prod")]
    where = [
        "org_id=%s",
        "home_id=%s",
        "subject_id=%s",
        "stream_id=%s",
        "category='presence'",
    ]

    if since is not None:
        where.append('"timestamp" >= %s')
        params.append(since)
    if until is not None:
        where.append('"timestamp" < %s')
        params.append(until)

    if since is None and until is None:
        # incremental watermark filtering
        if wm_ts is not None:
            where.append('("timestamp" > %s OR ("timestamp" = %s AND id > %s))')
            params.extend([wm_ts, wm_ts, (wm_id or 0)])

    sql = f"""
        SELECT id, event_id, "timestamp" AS ts, payload
        FROM events
        WHERE {" AND ".join(where)}
        ORDER BY "timestamp" ASC, id ASC
        LIMIT %s
    """
    params.append(batch)
    cur.execute(sql, params)
    return list(cur.fetchall())


def payload_get(payload_json) -> Dict[str, Any]:
    # events.payload is json (psycopg2 returns Python dict if using RealDictCursor with json adaptation,
    # but be defensive)
    if isinstance(payload_json, dict):
        return payload_json
    if isinstance(payload_json, str):
        return json.loads(payload_json)
    # psycopg2 may return as Python object already, else fallback
    try:
        return dict(payload_json)
    except Exception:
        return {}


def upsert_episode(
    cur,
    org_id: str,
    home_id: str,
    subject_id: str,
    episode_type: str,
    room_id: str,
    start_ts: datetime,
    end_ts: datetime,
    start_row_id: Optional[int],
    end_row_id: Optional[int],
    start_event_id: Optional[str],
    end_event_id: Optional[str],
    event_n: int,
    is_open: bool,
    meta: Dict[str, Any],
) -> None:
    cur.execute(
        """
        INSERT INTO episodes_svc (
          org_id, home_id, subject_id,
          episode_type, room_id,
          start_ts, end_ts,
          start_event_row_id, end_event_row_id,
          start_event_id, end_event_id,
          event_n, is_open, meta
        )
        VALUES (%s,%s,%s, %s,%s, %s,%s, %s,%s, %s,%s, %s,%s, %s::jsonb)
        ON CONFLICT (org_id, home_id, subject_id, episode_type, room_id, start_ts)
        DO UPDATE SET
          end_ts = EXCLUDED.end_ts,
          end_event_row_id = EXCLUDED.end_event_row_id,
          end_event_id = EXCLUDED.end_event_id,
          event_n = GREATEST(episodes_svc.event_n, EXCLUDED.event_n),
          is_open = EXCLUDED.is_open,
          meta = episodes_svc.meta || EXCLUDED.meta
        """,
        (
            org_id,
            home_id,
            subject_id,
            episode_type,
            room_id,
            start_ts,
            end_ts,
            start_row_id,
            end_row_id,
            start_event_id,
            end_event_id,
            event_n,
            is_open,
            json.dumps(meta),
        ),
    )


def update_builder_state(
    cur,
    org_id: str,
    home_id: str,
    subject_id: str,
    builder_name: str,
    last_ts: Optional[datetime],
    last_id: Optional[int],
    ok: bool,
    err_msg: Optional[str],
) -> None:
    now = datetime.now(timezone.utc)
    if ok:
        cur.execute(
            """
            UPDATE episode_builder_state
            SET last_event_ts=%s,
                last_event_row_id=%s,
                last_run_at=%s,
                last_ok_at=%s,
                last_error_at=NULL,
                last_error_msg=NULL
            WHERE org_id=%s AND home_id=%s AND subject_id=%s AND builder_name=%s
            """,
            (last_ts, last_id, now, now, org_id, home_id, subject_id, builder_name),
        )
    else:
        cur.execute(
            """
            UPDATE episode_builder_state
            SET last_run_at=%s,
                last_error_at=%s,
                last_error_msg=%s
            WHERE org_id=%s AND home_id=%s AND subject_id=%s AND builder_name=%s
            """,
            (now, now, err_msg, org_id, home_id, subject_id, builder_name),
        )


def main():
    builder_name = os.getenv("BUILDER_NAME", "episodes_svc_v1")
    batch = int(os.getenv("BATCH", "5000"))

    # Optional window replay
    since_s = os.getenv("SINCE")
    until_s = os.getenv("UNTIL")
    since = parse_ts(since_s) if since_s else None
    until = parse_ts(until_s) if until_s else None

    # If replaying a window, default is "do not advance watermark"
    advance_watermark = os.getenv("ADVANCE_WATERMARK", "0") == "1"

    scope = get_scope_via_api()
    org_id, home_id, subject_id = scope["org_id"], scope["home_id"], scope["subject_id"]

    out = {
        "builder": builder_name,
        "scope": scope,
        "since": since_s,
        "until": until_s,
        "advance_watermark": advance_watermark,
        "started_at": utcnow(),
    }

    conn = db_connect()
    try:
        conn.autocommit = False
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            ensure_state_row(cur, org_id, home_id, subject_id, builder_name)
            wm_ts, wm_id = read_watermark_for_update(
                cur, org_id, home_id, subject_id, builder_name
            )

            out["watermark_before"] = {
                "last_event_ts": wm_ts.isoformat() if wm_ts else None,
                "last_event_row_id": wm_id,
            }

            events = fetch_events(
                cur, org_id, home_id, subject_id, wm_ts, wm_id, since, until, batch
            )

            # Simple deterministic presence-room episodes:
            # - One open episode per room at a time
            # - "on" starts (if none open); "off" closes (if open)
            open_by_room: Dict[str, Dict[str, Any]] = {}
            episodes_upserted = 0
            skipped = {"no_room": 0, "no_state": 0, "unknown_state": 0}

            last_seen_ts = wm_ts
            last_seen_id = wm_id

            for e in events:
                eid_row = int(e["id"])
                ts = e["ts"]
                if (
                    last_seen_ts is None
                    or ts > last_seen_ts
                    or (
                        ts == last_seen_ts
                        and (last_seen_id is None or eid_row > last_seen_id)
                    )
                ):
                    last_seen_ts, last_seen_id = ts, eid_row

                payload = payload_get(e["payload"])
                room = payload.get("room")
                state = payload.get("state")

                if not room:
                    skipped["no_room"] += 1
                    continue
                if not state:
                    skipped["no_state"] += 1
                    continue

                room_id = str(room)
                state = str(state).lower().strip()

                if state not in ("on", "off"):
                    skipped["unknown_state"] += 1
                    continue

                episode_type = "presence_room_v1"

                if state == "on":
                    if room_id not in open_by_room:
                        # start new
                        open_by_room[room_id] = {
                            "start_ts": ts,
                            "start_row_id": eid_row,
                            "start_event_id": e.get("event_id"),
                            "event_n": 1,
                            "end_ts": ts,
                            "end_row_id": eid_row,
                            "end_event_id": e.get("event_id"),
                        }
                        upsert_episode(
                            cur,
                            org_id,
                            home_id,
                            subject_id,
                            episode_type,
                            room_id,
                            ts,
                            ts,
                            eid_row,
                            eid_row,
                            e.get("event_id"),
                            e.get("event_id"),
                            1,
                            True,
                            {"entity_id": payload.get("entity_id", "")},
                        )
                        episodes_upserted += 1
                    else:
                        # already open; extend only counters/end markers (idempotent via upsert)
                        o = open_by_room[room_id]
                        o["event_n"] += 1
                        o["end_ts"] = ts
                        o["end_row_id"] = eid_row
                        o["end_event_id"] = e.get("event_id")
                        upsert_episode(
                            cur,
                            org_id,
                            home_id,
                            subject_id,
                            episode_type,
                            room_id,
                            o["start_ts"],
                            ts,
                            o["start_row_id"],
                            eid_row,
                            o["start_event_id"],
                            e.get("event_id"),
                            o["event_n"],
                            True,
                            {"entity_id": payload.get("entity_id", "")},
                        )
                        episodes_upserted += 1

                else:  # off
                    if room_id in open_by_room:
                        o = open_by_room[room_id]
                        o["event_n"] += 1
                        o["end_ts"] = ts
                        o["end_row_id"] = eid_row
                        o["end_event_id"] = e.get("event_id")
                        upsert_episode(
                            cur,
                            org_id,
                            home_id,
                            subject_id,
                            episode_type,
                            room_id,
                            o["start_ts"],
                            ts,
                            o["start_row_id"],
                            eid_row,
                            o["start_event_id"],
                            e.get("event_id"),
                            o["event_n"],
                            False,
                            {
                                "close_reason": "off_event",
                                "entity_id": payload.get("entity_id", ""),
                            },
                        )
                        episodes_upserted += 1
                        del open_by_room[room_id]
                    else:
                        # off without open -> ignore (still idempotent)
                        continue

            # watermark update rules
            if since is None and until is None:
                # incremental run => always advance to last processed event
                update_builder_state(
                    cur,
                    org_id,
                    home_id,
                    subject_id,
                    builder_name,
                    last_seen_ts,
                    last_seen_id,
                    True,
                    None,
                )
            else:
                # window replay => only advance if explicitly asked
                if advance_watermark:
                    update_builder_state(
                        cur,
                        org_id,
                        home_id,
                        subject_id,
                        builder_name,
                        last_seen_ts,
                        last_seen_id,
                        True,
                        None,
                    )
                else:
                    update_builder_state(
                        cur,
                        org_id,
                        home_id,
                        subject_id,
                        builder_name,
                        wm_ts,
                        wm_id,
                        True,
                        None,
                    )

            conn.commit()

            out["events_read"] = len(events)
            out["episodes_upserted"] = episodes_upserted
            out["skipped"] = skipped
            out["watermark_after"] = {
                "last_event_ts": (
                    last_seen_ts.isoformat()
                    if (since is None and until is None and last_seen_ts)
                    else (wm_ts.isoformat() if wm_ts else None)
                ),
                "last_event_row_id": (
                    last_seen_id if (since is None and until is None) else wm_id
                ),
            }
            out["finished_at"] = utcnow()

    except Exception as e:
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                update_builder_state(
                    cur,
                    org_id,
                    home_id,
                    subject_id,
                    builder_name,
                    None,
                    None,
                    False,
                    str(e),
                )
                conn.commit()
        except Exception:
            pass
        raise
    finally:
        conn.close()

    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
