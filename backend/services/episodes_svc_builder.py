from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, List

import psycopg2
import psycopg2.extras


@dataclass
class BuildResult:
    events_read: int
    episodes_upserted: int
    skipped_no_room: int
    skipped_no_state: int
    skipped_unknown_state: int
    watermark_before_ts: Optional[datetime]
    watermark_before_id: Optional[int]
    watermark_after_ts: Optional[datetime]
    watermark_after_id: Optional[int]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _payload_get(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    # psycopg2 may return JSON as string in some paths
    try:
        import json as _json
        if isinstance(payload, str):
            return _json.loads(payload)
    except Exception:
        pass
    try:
        return dict(payload)
    except Exception:
        return {}


def ensure_state_row(cur, *, org_id: str, home_id: str, subject_id: str, builder_name: str) -> None:
    cur.execute(
        """
        INSERT INTO episode_builder_state (org_id, home_id, subject_id, builder_name)
        VALUES (%s,%s,%s,%s)
        ON CONFLICT (org_id, home_id, subject_id, builder_name) DO NOTHING
        """,
        (org_id, home_id, subject_id, builder_name),
    )


def read_watermark_for_update(
    cur, *, org_id: str, home_id: str, subject_id: str, builder_name: str
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
    *,
    org_id: str,
    home_id: str,
    subject_id: str,
    wm_ts: Optional[datetime],
    wm_id: Optional[int],
    since: Optional[datetime],
    until: Optional[datetime],
    batch: int,
) -> List[Dict[str, Any]]:
    params: list[Any] = [org_id, home_id, subject_id]
    where = [
        "org_id=%s",
        "home_id=%s",
        "subject_id=%s",
        "category='presence'",
    ]

    if since is not None:
        where.append("\"timestamp\" >= %s")
        params.append(since)
    if until is not None:
        where.append("\"timestamp\" < %s")
        params.append(until)

    if since is None and until is None:
        # incremental watermark filtering
        if wm_ts is not None:
            where.append("(\"timestamp\" > %s OR (\"timestamp\" = %s AND id > %s))")
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


def upsert_episode(
    cur,
    *,
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
    import json

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
    *,
    org_id: str,
    home_id: str,
    subject_id: str,
    builder_name: str,
    last_ts: Optional[datetime],
    last_id: Optional[int],
    ok: bool,
    err_msg: Optional[str],
) -> None:
    now = _utcnow()
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


def build_presence_room_v1(
    *,
    db_dsn: str,
    org_id: str,
    home_id: str,
    subject_id: str,
    builder_name: str = "episodes_svc_v1",
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    advance_watermark: bool = False,
    batch: int = 5000,
) -> BuildResult:
    """
    Build deterministic room episodes from presence events only (payload.room + payload.state).
    Idempotent writes via episodes_svc unique key; incremental reads via episode_builder_state watermark.
    """
    conn = psycopg2.connect(db_dsn)
    conn.autocommit = False

    watermark_before_ts: Optional[datetime] = None
    watermark_before_id: Optional[int] = None
    watermark_after_ts: Optional[datetime] = None
    watermark_after_id: Optional[int] = None

    episodes_upserted = 0
    skipped_no_room = 0
    skipped_no_state = 0
    skipped_unknown_state = 0

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            ensure_state_row(cur, org_id=org_id, home_id=home_id, subject_id=subject_id, builder_name=builder_name)
            wm_ts, wm_id = read_watermark_for_update(cur, org_id=org_id, home_id=home_id, subject_id=subject_id, builder_name=builder_name)

            watermark_before_ts, watermark_before_id = wm_ts, wm_id

            events = fetch_events(
                cur,
                org_id=org_id,
                home_id=home_id,
                subject_id=subject_id,
                wm_ts=wm_ts,
                wm_id=wm_id,
                since=since,
                until=until,
                batch=batch,
            )

            open_by_room: Dict[str, Dict[str, Any]] = {}
            last_seen_ts = wm_ts
            last_seen_id = wm_id

            for e in events:
                eid_row = int(e["id"])
                ts = e["ts"]

                if last_seen_ts is None or ts > last_seen_ts or (ts == last_seen_ts and (last_seen_id is None or eid_row > last_seen_id)):
                    last_seen_ts, last_seen_id = ts, eid_row

                payload = _payload_get(e["payload"])
                room = payload.get("room")
                state = payload.get("state")

                if not room:
                    skipped_no_room += 1
                    continue
                if not state:
                    skipped_no_state += 1
                    continue

                room_id = str(room)
                st = str(state).lower().strip()

                if st not in ("on", "off"):
                    skipped_unknown_state += 1
                    continue

                episode_type = "presence_room_v1"

                if st == "on":
                    if room_id not in open_by_room:
                        open_by_room[room_id] = {
                            "start_ts": ts,
                            "start_row_id": eid_row,
                            "start_event_id": e.get("event_id"),
                            "event_n": 1,
                        }
                        upsert_episode(
                            cur,
                            org_id=org_id,
                            home_id=home_id,
                            subject_id=subject_id,
                            episode_type=episode_type,
                            room_id=room_id,
                            start_ts=ts,
                            end_ts=ts,
                            start_row_id=eid_row,
                            end_row_id=eid_row,
                            start_event_id=e.get("event_id"),
                            end_event_id=e.get("event_id"),
                            event_n=1,
                            is_open=True,
                            meta={"entity_id": payload.get("entity_id", "")},
                        )
                        episodes_upserted += 1
                    else:
                        o = open_by_room[room_id]
                        o["event_n"] += 1
                        upsert_episode(
                            cur,
                            org_id=org_id,
                            home_id=home_id,
                            subject_id=subject_id,
                            episode_type=episode_type,
                            room_id=room_id,
                            start_ts=o["start_ts"],
                            end_ts=ts,
                            start_row_id=o["start_row_id"],
                            end_row_id=eid_row,
                            start_event_id=o["start_event_id"],
                            end_event_id=e.get("event_id"),
                            event_n=o["event_n"],
                            is_open=True,
                            meta={"entity_id": payload.get("entity_id", "")},
                        )
                        episodes_upserted += 1

                else:  # off
                    if room_id in open_by_room:
                        o = open_by_room[room_id]
                        o["event_n"] += 1
                        upsert_episode(
                            cur,
                            org_id=org_id,
                            home_id=home_id,
                            subject_id=subject_id,
                            episode_type=episode_type,
                            room_id=room_id,
                            start_ts=o["start_ts"],
                            end_ts=ts,
                            start_row_id=o["start_row_id"],
                            end_row_id=eid_row,
                            start_event_id=o["start_event_id"],
                            end_event_id=e.get("event_id"),
                            event_n=o["event_n"],
                            is_open=False,
                            meta={"close_reason": "off_event", "entity_id": payload.get("entity_id", "")},
                        )
                        episodes_upserted += 1
                        del open_by_room[room_id]
                    else:
                        # off without open -> ignore
                        pass

            # watermark rules
            if since is None and until is None:
                # incremental => always advance
                watermark_after_ts, watermark_after_id = last_seen_ts, last_seen_id
                update_builder_state(
                    cur,
                    org_id=org_id,
                    home_id=home_id,
                    subject_id=subject_id,
                    builder_name=builder_name,
                    last_ts=watermark_after_ts,
                    last_id=watermark_after_id,
                    ok=True,
                    err_msg=None,
                )
            else:
                # window replay
                if advance_watermark:
                    watermark_after_ts, watermark_after_id = last_seen_ts, last_seen_id
                    update_builder_state(
                        cur,
                        org_id=org_id,
                        home_id=home_id,
                        subject_id=subject_id,
                        builder_name=builder_name,
                        last_ts=watermark_after_ts,
                        last_id=watermark_after_id,
                        ok=True,
                        err_msg=None,
                    )
                else:
                    watermark_after_ts, watermark_after_id = wm_ts, wm_id
                    update_builder_state(
                        cur,
                        org_id=org_id,
                        home_id=home_id,
                        subject_id=subject_id,
                        builder_name=builder_name,
                        last_ts=wm_ts,
                        last_id=wm_id,
                        ok=True,
                        err_msg=None,
                    )

            conn.commit()

            return BuildResult(
                events_read=len(events),
                episodes_upserted=episodes_upserted,
                skipped_no_room=skipped_no_room,
                skipped_no_state=skipped_no_state,
                skipped_unknown_state=skipped_unknown_state,
                watermark_before_ts=watermark_before_ts,
                watermark_before_id=watermark_before_id,
                watermark_after_ts=watermark_after_ts,
                watermark_after_id=watermark_after_id,
            )
    except Exception as e:
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                update_builder_state(
                    cur,
                    org_id=org_id,
                    home_id=home_id,
                    subject_id=subject_id,
                    builder_name=builder_name,
                    last_ts=None,
                    last_id=None,
                    ok=False,
                    err_msg=str(e),
                )
                conn.commit()
        except Exception:
            pass
        raise
    finally:
        conn.close()
