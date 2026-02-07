#!/usr/bin/env python3
"""
Build episodes from raw events.

Scope (Chat 1):
- Segment episodes per room from presence/motion (+ door context)
- Store minimal features into episodes table
- NO baseline/anomaly/proposals
- Classification = unknown (rules later)
"""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras


def parse_duration_seconds(s: str) -> int:
    s = (s or "").strip().lower()
    m = re.fullmatch(r"(\d+)\s*([smhdw])", s)
    if not m:
        raise ValueError("Invalid duration. Use like 24h, 7d, 30m, 90s, 2w")
    n = int(m.group(1))
    unit = m.group(2)
    mult = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}[unit]
    return n * mult


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def tod_bucket_utc(dt: datetime) -> str:
    h = dt.hour
    if h < 7:
        return "night"
    if h < 12:
        return "morning"
    if h < 18:
        return "day"
    return "evening"


@dataclass
class RawEvent:
    id: int
    ts: datetime
    category: str
    payload: Dict[str, Any]


@dataclass
class EpisodeDraft:
    room: str
    primary_sensor: str
    sensor_set: List[str]

    start_ts: datetime
    last_activity_ts: datetime
    end_ts: Optional[datetime] = None

    # counts
    total: int = 0
    motion: int = 0
    presence_on: int = 0
    presence_off: int = 0

    # door context (seconds)
    door_before_s: Optional[int] = None
    door_during: bool = False
    door_after_s: Optional[int] = None

    # linkage
    first_event_id: Optional[int] = None
    last_event_id: Optional[int] = None

    # state
    saw_presence_on: bool = False
    close_reason: Optional[str] = None
    timeout_s: int = 90
    quality: str = "medium"
    quality_flags: List[str] = None

    def __post_init__(self):
        if self.quality_flags is None:
            self.quality_flags = []


def db_dsn_from_env() -> str:
    # Default aligns with docker-compose env shown earlier
    host = os.getenv("PGHOST", "127.0.0.1")
    port = os.getenv("PGPORT", "5432")
    user = os.getenv("PGUSER", os.getenv("POSTGRES_USER", "agingos"))
    db = os.getenv("PGDATABASE", os.getenv("POSTGRES_DB", "agingos"))
    pw = os.getenv("PGPASSWORD", os.getenv("POSTGRES_PASSWORD", ""))
    if pw:
        return f"host={host} port={port} dbname={db} user={user} password={pw}"
    return f"host={host} port={port} dbname={db} user={user}"


def fetch_events(conn, since: datetime, until: datetime) -> List[RawEvent]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, "timestamp" as ts, category, payload
            FROM events
            WHERE "timestamp" >= %s AND "timestamp" < %s
              AND category IN ('presence','motion','door')
            ORDER BY "timestamp" ASC, id ASC
            """,
            (since, until),
        )
        rows = cur.fetchall()
    out: List[RawEvent] = []
    for r in rows:
        out.append(
            RawEvent(
                id=int(r["id"]),
                ts=r["ts"],
                category=str(r["category"]),
                payload=dict(r["payload"]),
            )
        )
    return out


def extract_room(ev: RawEvent) -> Optional[str]:
    # Most of your payloads include "room"; fallback to "area" if present.
    p = ev.payload or {}
    room = p.get("room") or p.get("area")
    if room is None:
        return None
    room = str(room).strip()
    return room or None


def extract_entity_id(ev: RawEvent) -> Optional[str]:
    p = ev.payload or {}
    eid = p.get("entity_id")
    if eid is None:
        return None
    eid = str(eid).strip()
    return eid or None


def is_presence_on(ev: RawEvent) -> bool:
    if ev.category != "presence":
        return False
    st = (ev.payload or {}).get("state")
    return str(st).lower() in ("on", "true", "1", "home", "occupied")


def is_presence_off(ev: RawEvent) -> bool:
    if ev.category != "presence":
        return False
    st = (ev.payload or {}).get("state")
    return str(st).lower() in ("off", "false", "0", "away", "clear", "not_occupied")


def is_motion(ev: RawEvent) -> bool:
    return ev.category == "motion"


def is_door(ev: RawEvent) -> bool:
    return ev.category == "door"


def build_episodes(events: List[RawEvent]) -> List[EpisodeDraft]:
    """
    Episode rules (v1, per room):
    - Start on presence_on (preferred) or motion (fallback)
    - Close on presence_off if we saw presence_on in this episode
    - Otherwise timeout-close based on inactivity gap from last_activity_ts
      - timeout 180s if saw presence_on, else 90s
    - door context:
      - door_before_s: nearest door event within 60s before start
      - door_during: any door event between start and end
      - door_after_s: nearest door event within 60s after end
    """
    # Index door events per room for context calculations
    door_by_room: Dict[str, List[RawEvent]] = {}
    for ev in events:
        if not is_door(ev):
            continue
        room = extract_room(ev)
        if not room:
            continue
        door_by_room.setdefault(room, []).append(ev)

    open_by_room: Dict[str, EpisodeDraft] = {}
    finished: List[EpisodeDraft] = []

    def close_episode(ep: EpisodeDraft, end_ts: datetime, reason: str):
        ep.end_ts = end_ts
        ep.close_reason = reason
        # duration
        # quality
        if reason == "off_event":
            ep.quality = "high" if "missing_off" not in ep.quality_flags else ep.quality
        elif reason == "timeout":
            ep.quality = "low"
            if "missing_off" not in ep.quality_flags:
                ep.quality_flags.append("missing_off")
        finished.append(ep)

    def maybe_timeout_close(now_ts: datetime, room: str):
        ep = open_by_room.get(room)
        if not ep:
            return
        if ep.saw_presence_on:
            ep.timeout_s = 180
        else:
            ep.timeout_s = 90
        gap = (now_ts - ep.last_activity_ts).total_seconds()
        if gap >= ep.timeout_s:
            close_episode(
                ep, ep.last_activity_ts + timedelta(seconds=ep.timeout_s), "timeout"
            )
            del open_by_room[room]

    # Iterate in chronological order
    for ev in events:
        room = extract_room(ev)
        if not room:
            continue

        # before processing this event, check if an open episode in this room should timeout before this event
        maybe_timeout_close(ev.ts, room)

        ep = open_by_room.get(room)

        if ep is None:
            # Start conditions
            if is_presence_on(ev) or is_motion(ev):
                primary = extract_entity_id(ev) or f"{ev.category}"
                ep = EpisodeDraft(
                    room=room,
                    primary_sensor=primary,
                    sensor_set=[primary] if primary else [],
                    start_ts=ev.ts,
                    last_activity_ts=ev.ts,
                    first_event_id=ev.id,
                    last_event_id=ev.id,
                    total=1,
                )
                if is_motion(ev):
                    ep.motion = 1
                    ep.quality = "medium"
                if is_presence_on(ev):
                    ep.presence_on = 1
                    ep.saw_presence_on = True
                    ep.quality = "high"
                open_by_room[room] = ep
            else:
                # door without episode: ignore for now (context will be attached if episode later starts)
                continue
        else:
            # Update counts/linkage
            ep.total += 1
            ep.last_event_id = ev.id

            eid = extract_entity_id(ev)
            if eid and eid not in ep.sensor_set:
                ep.sensor_set.append(eid)

            if is_motion(ev):
                ep.motion += 1
                ep.last_activity_ts = ev.ts
            elif is_presence_on(ev):
                ep.presence_on += 1
                ep.saw_presence_on = True
                ep.last_activity_ts = ev.ts
            elif is_presence_off(ev):
                ep.presence_off += 1
                # close only if we saw presence_on in this episode
                if ep.saw_presence_on:
                    close_episode(ep, ev.ts, "off_event")
                    del open_by_room[room]
            elif is_door(ev):
                ep.door_during = True
                # do not update last_activity_ts

    # Final timeout close at end of stream
    if events:
        stream_end = events[-1].ts
        for room in list(open_by_room.keys()):
            maybe_timeout_close(
                stream_end + timedelta(seconds=999999), room
            )  # force close by timeout
            # If still open (no activity at all), close at stream_end as timeout
            if room in open_by_room:
                ep = open_by_room.pop(room)
                close_episode(ep, stream_end, "timeout")

    # Attach door_before/after context (window 60s)
    window_s = 60
    for ep in finished:
        doors = door_by_room.get(ep.room, [])
        # before
        best_before = None
        for d in doors:
            if d.ts <= ep.start_ts and (ep.start_ts - d.ts).total_seconds() <= window_s:
                if best_before is None or d.ts > best_before.ts:
                    best_before = d
        if best_before is not None:
            ep.door_before_s = int((ep.start_ts - best_before.ts).total_seconds())

        # after
        if ep.end_ts is not None:
            best_after = None
            for d in doors:
                if d.ts >= ep.end_ts and (d.ts - ep.end_ts).total_seconds() <= window_s:
                    if best_after is None or d.ts < best_after.ts:
                        best_after = d
            if best_after is not None:
                ep.door_after_s = int((best_after.ts - ep.end_ts).total_seconds())

    return finished


# --- Explainable classification (rules_v1) -----------------------------------


def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def score_episode(ep: EpisodeDraft) -> tuple[str, float, float, float, list[dict], str]:
    """
    Deterministic, explainable scorer.

    Goal: separate obvious pet vs human, keep unknown as first-class when uncertain.

    Inputs available (v0 pipeline):
      - duration, event_rate, presence_on/off counts
      - close_reason/quality/timeout
      - door_before_s / door_during / door_after_s (window 60s)
    """
    assert ep.end_ts is not None
    dur_s = max(0, int((ep.end_ts - ep.start_ts).total_seconds()))
    rate = 0.0
    if dur_s > 0:
        rate = ep.total / (dur_s / 60.0)

    reasons: list[dict] = []

    # Base scores (not probabilities yet)
    s_h = 0.0
    s_p = 0.0
    s_u = 0.40  # unknown baseline so it wins when evidence is weak

    # Evidence: door near start/end strongly suggests human
    if ep.door_before_s is not None and ep.door_before_s <= 60:
        w = 0.55
        s_h += w
        reasons.append(
            {
                "code": "DOOR_BEFORE_START",
                "direction": "human",
                "weight": w,
                "evidence": {"door_before_s": ep.door_before_s, "window_s": 60},
            }
        )

    if ep.door_during:
        w = 0.35
        s_h += w
        reasons.append(
            {
                "code": "DOOR_DURING_EPISODE",
                "direction": "human",
                "weight": w,
                "evidence": {"door_during": True},
            }
        )

    if ep.door_after_s is not None and ep.door_after_s <= 60:
        w = 0.20
        s_h += w
        reasons.append(
            {
                "code": "DOOR_AFTER_END",
                "direction": "human",
                "weight": w,
                "evidence": {"door_after_s": ep.door_after_s, "window_s": 60},
            }
        )

    # Evidence: timeout close reduces confidence
    if ep.close_reason == "timeout":
        w = 0.25
        s_u += w
        reasons.append(
            {
                "code": "TIMEOUT_CLOSE",
                "direction": "unknown",
                "weight": w,
                "evidence": {"timeout_s": ep.timeout_s},
            }
        )

    # Evidence: very short episode with no door nearby + higher event-rate -> pet-weighted
    door_near = (
        (ep.door_before_s is not None and ep.door_before_s <= 60)
        or ep.door_during
        or (ep.door_after_s is not None and ep.door_after_s <= 60)
    )

    # Evidence: very short complete presence blip without door context tends to be pet
    if (not door_near) and ep.saw_presence_on and ep.presence_off >= 1 and dur_s <= 12:
        w = 0.35
        s_p += w
        reasons.append(
            {
                "code": "PRESENCE_BLIP_VERY_SHORT_NO_DOOR",
                "direction": "pet",
                "weight": w,
                "evidence": {
                    "duration_s": dur_s,
                    "presence_on": ep.presence_on,
                    "presence_off": ep.presence_off,
                    "door_near": False,
                },
            }
        )

    # Evidence: very short complete presence blip without door context tends to be pet
    if (not door_near) and ep.saw_presence_on and ep.presence_off >= 1 and dur_s <= 12:
        w = 0.35
        s_p += w
        reasons.append(
            {
                "code": "PRESENCE_BLIP_VERY_SHORT_NO_DOOR",
                "direction": "pet",
                "weight": w,
                "evidence": {
                    "duration_s": dur_s,
                    "presence_on": ep.presence_on,
                    "presence_off": ep.presence_off,
                    "door_near": False,
                },
            }
        )

    if (not door_near) and dur_s <= 45 and rate >= 6.0:
        w = 0.55
        s_p += w
        reasons.append(
            {
                "code": "SHORT_HIGH_RATE_NO_DOOR",
                "direction": "pet",
                "weight": w,
                "evidence": {
                    "duration_s": dur_s,
                    "event_rate_per_min": rate,
                    "rate_threshold": 6.0,
                    "door_near": False,
                },
            }
        )

    # Evidence: complete presence episode (on+off) gives a mild human default (prevents 'no_reasons' for common cases)
    if ep.saw_presence_on and ep.presence_off >= 1 and dur_s >= 20:
        w = 0.08
        s_h += w
        reasons.append(
            {
                "code": "COMPLETE_PRESENCE_EPISODE_DEFAULT",
                "direction": "human",
                "weight": w,
                "evidence": {
                    "duration_s": dur_s,
                    "presence_on": ep.presence_on,
                    "presence_off": ep.presence_off,
                },
            }
        )

    # Evidence: longer, stable presence episodes (on+off) mildly human-weighted
    if ep.saw_presence_on and ep.presence_off >= 1 and dur_s >= 120:
        w = 0.25
        s_h += w
        reasons.append(
            {
                "code": "LONG_PRESENCE_ON_OFF",
                "direction": "human",
                "weight": w,
                "evidence": {
                    "duration_s": dur_s,
                    "presence_on": ep.presence_on,
                    "presence_off": ep.presence_off,
                },
            }
        )

    # Evidence: presence-only with very low rate tends to be human OR unknown; keep mild human, still allow unknown to win
    if ep.presence_on >= 1 and ep.motion == 0 and rate <= 1.0 and dur_s >= 60:
        w = 0.12
        s_h += w
        reasons.append(
            {
                "code": "PRESENCE_ONLY_LOW_RATE",
                "direction": "human",
                "weight": w,
                "evidence": {"event_rate_per_min": rate, "motion": ep.motion},
            }
        )

    # Evidence: extremely high rate bursts are often pet/noise
    if rate >= 12.0 and dur_s <= 60 and not door_near:
        w = 0.25
        s_p += w
        reasons.append(
            {
                "code": "VERY_HIGH_RATE_BURST",
                "direction": "pet",
                "weight": w,
                "evidence": {
                    "event_rate_per_min": rate,
                    "duration_s": dur_s,
                    "door_near": False,
                },
            }
        )

    # Deduplicate reasons (can happen when rules overlap or code was inserted twice)
    seen = set()
    uniq = []
    for r in reasons:
        key = (
            r.get("code"),
            r.get("direction"),
            repr(r.get("evidence", {})),
        )
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    reasons = uniq

    # Deduplicate reasons (can happen when rules overlap or code was inserted twice)
    seen = set()
    uniq = []
    for r in reasons:
        key = (
            r.get("code"),
            r.get("direction"),
            repr(r.get("evidence", {})),
        )
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    reasons = uniq

    # Convert scores to probabilities (simple normalized mix)
    total = s_h + s_p + s_u
    if total <= 0:
        p_h, p_p, p_u = 0.0, 0.0, 1.0
    else:
        p_h, p_p, p_u = s_h / total, s_p / total, s_u / total

    # Choose class with guardrails: unknown wins unless one class is clearly ahead
    klass = "unknown"
    best = max(("human", p_h), ("pet", p_p), ("unknown", p_u), key=lambda x: x[1])

    # If human/pet is best and sufficiently above unknown, accept it
    if best[0] in ("human", "pet"):
        margin = best[1] - p_u
        if best[1] >= 0.55 and margin >= 0.10:
            klass = best[0]
        else:
            klass = "unknown"
            # add explicit reason for conservative unknown
            reasons.append(
                {
                    "code": "LOW_CONFIDENCE",
                    "direction": "unknown",
                    "weight": 0.20,
                    "evidence": {"p_human": p_h, "p_pet": p_p, "p_unknown": p_u},
                }
            )

    # Ensure probs sum to ~1 and are within bounds
    p_h = _clamp01(p_h)
    p_p = _clamp01(p_p)
    p_u = _clamp01(p_u)
    # Normalize again (avoid drift after clamp)
    z = p_h + p_p + p_u
    if z > 0:
        p_h, p_p, p_u = p_h / z, p_p / z, p_u / z

    # Human-friendly summary (short)
    summary_bits = []
    for r in reasons[:3]:
        summary_bits.append(r["code"])
    reason_summary = ", ".join(summary_bits) if summary_bits else "no_reasons"

    return klass, p_h, p_p, p_u, reasons, reason_summary


# -----------------------------------------------------------------------------


def insert_episodes(conn, eps: List[EpisodeDraft], dry_run: bool = True) -> int:
    """
    Insert episodes with classification=unknown (rules later).
    """
    if dry_run:
        return 0

    with conn.cursor() as cur:
        for ep in eps:
            assert ep.end_ts is not None
            duration_s = max(0, int((ep.end_ts - ep.start_ts).total_seconds()))
            rate = 0.0
            if duration_s > 0:
                rate = ep.total / (duration_s / 60.0)

            klass, p_h, p_p, p_u, reasons, reason_summary = score_episode(ep)
            cur.execute(
                """
                INSERT INTO episodes (
                  start_ts, end_ts, duration_s,
                  room, primary_sensor, sensor_set,
                  close_reason, timeout_s, quality, quality_flags,
                  event_count_total, event_count_motion, event_count_presence_on, event_count_presence_off,
                  event_rate_per_min,
                  first_event_id, last_event_id,
                  door_before_s, door_during, door_after_s,
                  tod_bucket, weekday,
                  room_type, room_sequence,
                  class, p_human, p_pet, p_unknown,
                  classifier_version, reasons, reason_summary, score_debug
                ) VALUES (
                  %s, %s, %s,
                  %s, %s, %s::jsonb,
                  %s, %s, %s, %s::jsonb,
                  %s, %s, %s, %s,
                  %s,
                  %s, %s,
                  %s, %s, %s,
                  %s, %s,
                  NULL, '[]'::jsonb,
                  %s, %s, %s, %s,
                  %s, %s::jsonb, %s, %s::jsonb
                )
                """,
                (
                    ep.start_ts,
                    ep.end_ts,
                    duration_s,
                    ep.room,
                    ep.primary_sensor,
                    psycopg2.extras.Json(ep.sensor_set),
                    ep.close_reason,
                    ep.timeout_s,
                    ep.quality,
                    psycopg2.extras.Json(ep.quality_flags),
                    ep.total,
                    ep.motion,
                    ep.presence_on,
                    ep.presence_off,
                    rate,
                    ep.first_event_id,
                    ep.last_event_id,
                    ep.door_before_s,
                    ep.door_during,
                    ep.door_after_s,
                    tod_bucket_utc(ep.start_ts),
                    int(ep.start_ts.isoweekday()),
                    klass,
                    p_h,
                    p_p,
                    p_u,
                    "rules_v1",
                    psycopg2.extras.Json(reasons),
                    reason_summary,
                    psycopg2.extras.Json(
                        {
                            "event_rate_per_min": rate,
                            "duration_s": duration_s,
                            "close_reason": ep.close_reason,
                            "timeout_s": ep.timeout_s,
                        }
                    ),
                ),
            )
        conn.commit()
    return len(eps)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--last", default="24h", help="Window to read events from (e.g. 24h, 7d)"
    )
    ap.add_argument("--dry-run", action="store_true", help="Do not write to DB")
    args = ap.parse_args()

    seconds = parse_duration_seconds(args.last)
    until = utc_now()
    since = until - timedelta(seconds=seconds)

    dsn = db_dsn_from_env()
    conn = psycopg2.connect(dsn)
    try:
        events = fetch_events(conn, since, until)
        eps = build_episodes(events)

        print(
            f"events={len(events)} episodes_built={len(eps)} window={since.isoformat()}..{until.isoformat()}"
        )
        if eps:
            # print a tiny summary for debugging
            for ep in eps[:10]:
                dur = int((ep.end_ts - ep.start_ts).total_seconds()) if ep.end_ts else 0
                print(
                    f"- room={ep.room} start={ep.start_ts.isoformat()} end={ep.end_ts.isoformat() if ep.end_ts else None} dur_s={dur} total={ep.total} motion={ep.motion} p_on={ep.presence_on} p_off={ep.presence_off} close={ep.close_reason} q={ep.quality}"
                )

        written = insert_episodes(conn, eps, dry_run=args.dry_run)
        if args.dry_run:
            print("dry-run: no DB writes")
        else:
            print(f"inserted={written}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
