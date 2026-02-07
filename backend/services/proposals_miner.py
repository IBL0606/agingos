from __future__ import annotations

import json
import uuid
import time
import traceback
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import text

from util.time import utcnow


def _utc_iso(dt: datetime) -> str:
    s = dt.isoformat()
    return s.replace("+00:00", "Z")



def _set_job_status(db: Session, *, job_key: str, ok: bool, now: datetime, payload: dict, error_msg: str | None = None) -> None:
    import json as _json
    db.execute(
        text(
            "INSERT INTO job_status (job_key, last_run_at, last_ok_at, last_error_at, last_error_msg, last_payload) "
            "VALUES (:job_key, :now, CASE WHEN :ok THEN :now ELSE NULL END, CASE WHEN :ok THEN NULL ELSE :now END, :err, CAST(:payload AS jsonb)) "
            "ON CONFLICT (job_key) DO UPDATE SET "
            "  last_run_at = EXCLUDED.last_run_at, "
            "  last_ok_at = COALESCE(EXCLUDED.last_ok_at, job_status.last_ok_at), "
            "  last_error_at = COALESCE(EXCLUDED.last_error_at, job_status.last_error_at), "
            "  last_error_msg = EXCLUDED.last_error_msg, "
            "  last_payload = EXCLUDED.last_payload"
        ),
        {
            "job_key": job_key,
            "now": now,
            "ok": ok,
            "err": (None if ok else (error_msg or "unknown error")),
            "payload": _json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        },
    )
def _upsert_proposal(
    db: Session,
    *,
    org_id: str,
    subject_id: str,
    room_id: str | None,
    proposal_type: str,
    dedupe_key: str,
    priority: int,
    evidence: dict[str, Any],
    why: list[dict[str, Any]],
    action_target: str,
    action_payload: dict[str, Any],
    window_start: datetime | None,
    window_end: datetime | None,
) -> None:
    """
    Upsert only against "open" proposals (NEW/TESTING/ACTIVE).
    If the only historical row is REJECTED, we insert a new row (no conflict).
    """
    q = text(
        """
        INSERT INTO proposals (
          org_id, subject_id, room_id,
          proposal_type, dedupe_key,
          state, priority,
          evidence, why,
          action_target, action_payload,
          first_detected_at, last_detected_at,
          window_start, window_end
        )
        VALUES (
          :org_id, :subject_id, :room_id,
          :proposal_type, :dedupe_key,
          'NEW', :priority,
          CAST(:evidence AS jsonb), CAST(:why AS jsonb),
          :action_target, CAST(:action_payload AS jsonb),
          now(), now(),
          :window_start, :window_end
        )
        ON CONFLICT (org_id, subject_id, proposal_type, dedupe_key)
        WHERE state IN ('NEW','TESTING','ACTIVE')
        DO UPDATE SET
          last_detected_at = now(),
          evidence = EXCLUDED.evidence,
          why = EXCLUDED.why,
          priority = EXCLUDED.priority,
          action_target = EXCLUDED.action_target,
          action_payload = EXCLUDED.action_payload,
          window_start = EXCLUDED.window_start,
          window_end = EXCLUDED.window_end
        ;
        """
    )

    db.execute(
        q,
        dict(
            org_id=org_id,
            subject_id=subject_id,
            room_id=room_id,
            proposal_type=proposal_type,
            dedupe_key=dedupe_key,
            priority=priority,
            evidence=json.dumps(evidence, ensure_ascii=False),
            why=json.dumps(why, ensure_ascii=False),
            action_target=action_target,
            action_payload=json.dumps(action_payload, ensure_ascii=False),
            window_start=window_start,
            window_end=window_end,
        ),
    )


def mine_proposals(db: Session, *, now: datetime | None = None) -> dict[str, Any]:
    """
    MVP miner (pilot-friendly thresholds, no spam):
      1) NIGHT_ACTIVITY_EARLY_SIGNAL_1_OF_7  (per subject)
      2) DOOR_ANOMALY_BURST_3_OF_14         (per subject)

    Input: anomaly_episodes only.
    subject_id source: anomaly_episodes.peak_bucket_details->>'user_id' (string UUID)
    org_id: "default" (MVP)
    """
    now = now or utcnow()
    org_id = "default"

    # 1) NIGHT_ACTIVITY_EARLY_SIGNAL_1_OF_7
    # Define "night" using Europe/Oslo local hour: hour>=22 OR hour<7
    night_q = text(
        """
        WITH ae AS (
          SELECT
            (peak_bucket_details->>'user_id') AS subject_id,
            start_ts,
            (start_ts AT TIME ZONE 'Europe/Oslo') AS local_ts
          FROM anomaly_episodes
          WHERE start_ts >= (now() - interval '8 days')
            AND peak_bucket_details ? 'user_id'
        ),
        nights AS (
          SELECT
            subject_id,
            (local_ts::date) AS local_date,
            COUNT(*)::int AS cnt
          FROM ae
          WHERE (EXTRACT(HOUR FROM local_ts) >= 22 OR EXTRACT(HOUR FROM local_ts) < 7)
          GROUP BY 1,2
        ),
        windowed AS (
          SELECT
            subject_id,
            COUNT(*) FILTER (WHERE cnt >= 1)::int AS nights_over_threshold,
            ARRAY_AGG(
              jsonb_build_object('date', local_date::text, 'count', cnt)
              ORDER BY local_date DESC
            ) AS per_night
          FROM nights
          WHERE local_date >= ((now() AT TIME ZONE 'Europe/Oslo')::date - 6)
          GROUP BY 1
        )
        SELECT
          subject_id,
          nights_over_threshold,
          per_night
        FROM windowed
        WHERE nights_over_threshold >= 1
        ;
        """
    )

    night_rows = db.execute(night_q).mappings().all()
    night_upserts = 0
    for r in night_rows:
        subject_id = r["subject_id"]
        evidence = {
            "nights_window": 7,
            "nights_over_threshold": int(r["nights_over_threshold"]),
            "threshold": 1,
            "night_hours_local": {"start": "22:00", "end": "07:00"},
            "per_night": r["per_night"] or [],
        }
        why = [
            {
                "reason_code": "NIGHT_ACTIVITY_EARLY_SIGNAL_1_OF_7",
                "text": "Nattlig aktivitet forekommer på >=1 av de siste 7 nettene (lokal tid).",
                "weight": 1.0,
                "data": {"nights_over_threshold": evidence["nights_over_threshold"]},
            }
        ]
        _upsert_proposal(
            db,
            org_id=org_id,
            subject_id=subject_id,
            room_id=None,
            proposal_type="NIGHT_ACTIVITY_EARLY_SIGNAL_1_OF_7",
            dedupe_key="night_activity:all",
            priority=35,
            evidence=evidence,
            why=why,
            action_target="monitor:R-001",
            action_payload={
                "mode_test": "TEST",
                "mode_on": "ON",
                "params": {"nights_window": 7, "min_nights": 1, "threshold": 1},
                "note": "MVP: TEST skal gi overvåkning uten actionable alerts (kobles senere i rule-engine).",
            },
            window_start=now - timedelta(days=7),
            window_end=now,
        )
        night_upserts += 1

    # 2) DOOR_ANOMALY_BURST_3_OF_14
    # Door anomaly if ANY reasons[].reason_code starts with "EVENT_DOOR"
    door_q = text(
        """
        WITH ae AS (
          SELECT
            (peak_bucket_details->>'user_id') AS subject_id,
            start_ts,
            reasons
          FROM anomaly_episodes
          WHERE start_ts >= (now() - interval '14 days')
            AND peak_bucket_details ? 'user_id'
        ),
        door AS (
          SELECT
            subject_id,
            (start_ts AT TIME ZONE 'Europe/Oslo')::date AS local_date,
            COUNT(*)::int AS cnt
          FROM ae
          WHERE EXISTS (
            SELECT 1
            FROM jsonb_array_elements(COALESCE(reasons, '[]'::jsonb)) elem
            WHERE (elem->>'reason_code') LIKE 'EVENT_DOOR%'
          )
          GROUP BY 1,2
        ),
        agg AS (
          SELECT
            subject_id,
            COALESCE(SUM(cnt), 0)::int AS door_anomaly_count,
            ARRAY_AGG(
              jsonb_build_object('date', local_date::text, 'count', cnt)
              ORDER BY local_date DESC
            ) AS per_day
          FROM door
          GROUP BY 1
        )
        SELECT subject_id, door_anomaly_count, per_day
        FROM agg
        WHERE door_anomaly_count >= 3
        ;
        """
    )

    door_rows = db.execute(door_q).mappings().all()
    door_upserts = 0
    for r in door_rows:
        subject_id = r["subject_id"]
        door_anomaly_count = int(r["door_anomaly_count"])
        evidence = {
            "window_days": 14,
            "door_anomaly_count": door_anomaly_count,
            "min_count": 3,
            "per_day": r["per_day"] or [],
            "reason_code_prefix": "EVENT_DOOR",
        }
        why = [
            {
                "reason_code": "DOOR_ANOMALY_BURST_3_OF_14",
                "text": "Dør-relaterte anomalier forekommer >=3 ganger siste 14 dager (lokal tid).",
                "weight": 1.0,
                "data": {"door_anomaly_count": door_anomaly_count},
            }
        ]
        _upsert_proposal(
            db,
            org_id=org_id,
            subject_id=subject_id,
            room_id=None,
            proposal_type="DOOR_ANOMALY_BURST_3_OF_14",
            dedupe_key="door_usage:all",
            priority=40,
            evidence=evidence,
            why=why,
            action_target="monitor:R-002",
            action_payload={
                "mode_test": "TEST",
                "mode_on": "ON",
                "params": {"window_days": 14, "min_count": 3},
                "suppress_alerts_in_test": True,
                "note": "MVP: kobles senere til faktisk rule mode (OFF/TEST/ON).",
            },
            window_start=now - timedelta(days=14),
            window_end=now,
        )
        door_upserts += 1


    # 3) MVP_BOOTSTRAP_ANY_L2_1_OF_7
    # Enables lifecycle/API/UI testing early in pilot with minimal data.
    bootstrap_q = text(
        """
        SELECT
          (peak_bucket_details->>'user_id') AS subject_id,
          COUNT(*)::int AS anomaly_count,
          MAX(start_ts) AS last_ts
        FROM anomaly_episodes
        WHERE start_ts >= (now() - interval '7 days')
          AND peak_bucket_details ? 'user_id'
          AND level >= 2
        GROUP BY 1
        HAVING COUNT(*) >= 1
        ;
        """
    )

    bs_rows = db.execute(bootstrap_q).mappings().all()
    bs_upserts = 0
    for r in bs_rows:
        subject_id = r["subject_id"]
        anomaly_count = int(r["anomaly_count"])
        evidence = {
            "window_days": 7,
            "level_min": 2,
            "anomaly_count": anomaly_count,
            "last_ts": (r["last_ts"].isoformat() if r["last_ts"] else None),
            "mvp_bootstrap": True,
        }
        why = [
            {
                "reason_code": "MVP_BOOTSTRAP_ANY_L2_1_OF_7",
                "text": "Bootstrap-proposal for å teste lifecycle/API/UI: minst én L2+ anomaly siste 7 dager.",
                "weight": 1.0,
                "data": {"anomaly_count": anomaly_count},
            }
        ]
        _upsert_proposal(
            db,
            org_id=org_id,
            subject_id=subject_id,
            room_id=None,
            proposal_type="MVP_BOOTSTRAP_ANY_L2_1_OF_7",
            dedupe_key="mvp_bootstrap:any_l2",
            priority=10,
            evidence=evidence,
            why=why,
            action_target="monitor:R-003",
            action_payload={
                "mode_test": "TEST",
                "mode_on": "ON",
                "params": {"note": "MVP bootstrap only"},
            },
            window_start=now - timedelta(days=7),
            window_end=now,
        )
        bs_upserts += 1

    # 4) NIGHT_ACTIVITY_FREQUENT_4_OF_7 (per room)
    # Yellow/Red night anomaly (level>=2) >=4 of last 7 nights in same room.
    # Night window: 22:00–06:00 Europe/Oslo. night_date assigns 00:00–05:59 to previous date.
    night_room_q = text(
        '''
        WITH ae AS (
          SELECT
            (peak_bucket_details->>'user_id') AS subject_id,
            room AS room_id,
            id AS episode_id,
            level,
            (start_ts AT TIME ZONE 'Europe/Oslo') AS local_ts
          FROM anomaly_episodes
          WHERE start_ts >= (now() - interval '8 days')
            AND peak_bucket_details ? 'user_id'
        ),
        night_eps AS (
          SELECT
            subject_id,
            room_id,
            episode_id,
            level,
            local_ts,
            EXTRACT(HOUR FROM local_ts) AS h,
            CASE
              WHEN EXTRACT(HOUR FROM local_ts) < 6 THEN (local_ts::date - 1)
              ELSE local_ts::date
            END AS night_date
          FROM ae
        ),
        filtered AS (
          SELECT *
          FROM night_eps
          WHERE (h >= 22 OR h < 6)
            AND level >= 2
            AND night_date >= ((now() AT TIME ZONE 'Europe/Oslo')::date - 6)
        ),
        agg AS (
          SELECT
            subject_id,
            room_id,
            COUNT(DISTINCT night_date)::int AS nights_hit,
            ARRAY_AGG(DISTINCT night_date ORDER BY night_date DESC) AS night_dates,
            ARRAY_AGG(episode_id ORDER BY episode_id DESC) AS episode_ids
          FROM filtered
          GROUP BY 1,2
        )
        SELECT subject_id, room_id, nights_hit, night_dates, episode_ids
        FROM agg
        WHERE nights_hit >= 4
        ;
        '''
    )

    nr_rows = db.execute(night_room_q).mappings().all()
    night_room_upserts = 0
    for r in nr_rows:
        subject_id = r["subject_id"]
        room_id = r["room_id"]
        nights_hit = int(r["nights_hit"] or 0)
        night_dates = r["night_dates"] or []
        episode_ids = r["episode_ids"] or []

        evidence = {
            "nights_window": 7,
            "min_nights": 4,
            "level_min": 2,
            "night_hours_local": {"start": "22:00", "end": "06:00"},
            "count_7d": nights_hit,
            "night_dates": [str(d) for d in night_dates[:10]],
            "episode_ids": [int(x) for x in episode_ids[:20]],
        }
        why = [
            {
                "reason_code": "NIGHT_ACTIVITY_FREQUENT_4_OF_7",
                "text": "Gul/rød natt-anomali forekommer >=4 av de siste 7 nettene i samme rom (lokal tid).",
                "weight": 1.0,
                "data": {"count_7d": nights_hit, "room_id": room_id},
            }
        ]

        _upsert_proposal(
            db,
            org_id=org_id,
            subject_id=subject_id,
            room_id=room_id,
            proposal_type="NIGHT_ACTIVITY_FREQUENT_4_OF_7",
            dedupe_key=f"room:{room_id}",
            priority=60,
            evidence=evidence,
            why=why,
            action_target="monitor:R-001",
            action_payload={
                "monitor_key": "R-001",
                "room_id": room_id,
                "params": {"nights_window": 7, "min_nights": 4, "level_min": 2},
                "note": "MVP miner: per-room night activity frequent.",
            },
            window_start=now - timedelta(days=7),
            window_end=now,
        )
        night_room_upserts += 1

    return {
        "ts": _utc_iso(now),
        "counts": {
            "night_proposals_upserted": night_upserts,
            "door_proposals_upserted": door_upserts,
            "bootstrap_proposals_upserted": bs_upserts,
        
            "night_room_proposals_upserted": night_room_upserts,},
    }


def run_proposals_miner_job() -> None:
    """
    Entrypoint for scheduler. Mirrors scheduler logging style (message-only JSONL).
    """
    run_id = str(uuid.uuid4())
    t0 = time.monotonic()

    # Lazy import to avoid circular deps
    from db import SessionLocal

    db = SessionLocal()
    try:
        result = mine_proposals(db)
        _set_job_status(db, job_key="proposals_miner", ok=True, now=utcnow(), payload=result)
        db.commit()

        duration_ms = int((time.monotonic() - t0) * 1000)
        print(
            json.dumps(
                {
                    "ts": _utc_iso(utcnow()),
                    "level": "INFO",
                    "component": "proposals_miner",
                    "event": "proposals_miner_run_end",
                    "run_id": run_id,
                    "msg": "proposals miner finished",
                    "duration_ms": duration_ms,
                    **result,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    except Exception as e:
        db.rollback()
        _set_job_status(db, job_key="proposals_miner", ok=False, now=utcnow(), payload={}, error_msg=str(e))
        duration_ms = int((time.monotonic() - t0) * 1000)
        print(
            json.dumps(
                {
                    "ts": _utc_iso(utcnow()),
                    "level": "ERROR",
                    "component": "proposals_miner",
                    "event": "proposals_miner_run_error",
                    "run_id": run_id,
                    "msg": "proposals miner failed",
                    "duration_ms": duration_ms,
                    "error": {
                        "type": type(e).__name__,
                        "message": str(e),
                        "stacktrace": traceback.format_exc(),
                    },
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    finally:
        db.close()
