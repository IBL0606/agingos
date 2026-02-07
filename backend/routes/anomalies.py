
from services.anomalies_repo_lifecycle import upsert_bucket_result
# backend/routes/anomalies.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from db import get_db
from models.anomaly_episode import AnomalyLevel, AnomalyEpisode
from schemas.anomaly_episode_persisted import AnomalyEpisodePersisted
from services.anomalies_repo import list_episodes, parse_last_param_to_since
from services.anomaly_scoring import score_room_bucket
from services.anomaly_episode_engine import process_bucket_score
from services.scheduler import scheduler, ANOMALIES_RUNNER_STATUS, run_anomalies_job


router = APIRouter(prefix="/anomalies", tags=["anomalies"])


def _level_str(level: int) -> str:
    return {AnomalyLevel.GREEN: "GREEN", AnomalyLevel.YELLOW: "YELLOW", AnomalyLevel.RED: "RED"}.get(int(level), "GREEN")


def _level_int(level: str) -> int:
    s = (level or "").strip().upper()
    return {"GREEN": AnomalyLevel.GREEN, "YELLOW": AnomalyLevel.YELLOW, "RED": AnomalyLevel.RED}.get(s, AnomalyLevel.GREEN)


def _serialize(ep: AnomalyEpisode) -> dict:
    return {
        "id": ep.id,
        "room": ep.room,
        "start_ts": ep.start_ts,
        "end_ts": ep.end_ts,
        "active": ep.end_ts is None,
        "level": _level_str(ep.level),
        "score_total": float(ep.score_total or 0.0),
        "score_intensity": float(ep.score_intensity or 0.0),
        "score_sequence": float(ep.score_sequence or 0.0),
        "score_event": float(ep.score_event or 0.0),
        "peak_bucket_start_ts": ep.peak_bucket_start_ts,
        "peak_bucket_score": float(ep.peak_bucket_score) if ep.peak_bucket_score is not None else None,
        "reasons": ep.reasons or [],
        "human_weight_mode": ep.human_weight_mode,
        "pet_weight": float(ep.pet_weight or 0.0),
        "baseline_ref": ep.baseline_ref or {},
    }


@router.get("", response_model=List[AnomalyEpisodePersisted])
def get_anomalies(
    last: str = Query("24h", description="Time window, e.g. 24h, 7d, 60m"),
    room: Optional[str] = Query(default=None),
    active_only: bool = Query(default=False),
    min_level: Optional[str] = Query(default=None, description="GREEN|YELLOW|RED"),
    limit: int = Query(default=200, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    since = parse_last_param_to_since(last)
    eps = list_episodes(db, since=since, room=room, active_only=active_only, limit=limit)

    if min_level:
        min_i = _level_int(min_level)
        eps = [e for e in eps if int(e.level) >= min_i]

    return [_serialize(e) for e in eps]


@router.get("/score")
def score_anomaly_bucket(
    room: str = Query(...),
    bucket_start: str = Query(..., description="ISO8601 UTC, e.g. 2026-02-05T05:00:00Z"),
    pet_weight: float = Query(0.25, ge=0.0, le=1.0),
    unknown_weight: float = Query(0.50, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
):
    # parse bucket_start with datetime.fromisoformat (accept Z)
    bs = bucket_start.strip().replace("Z", "+00:00")
    from datetime import datetime
    dt = datetime.fromisoformat(bs)
    res = score_room_bucket(db, room=room, bucket_start=dt, pet_weight=pet_weight, unknown_weight=unknown_weight)
    return {
        "room": res.room,
        "bucket": {"start": res.bucket_start, "end": res.bucket_end, "bucket_idx": res.bucket_idx, "dow": res.dow, "is_weekend": res.is_weekend},
        "score": {
            "total": res.score_total,
            "intensity": res.score_intensity,
            "sequence": res.score_sequence,
            "event": res.score_event,
            "level": res.level,
        },
        "reasons": res.reasons,
        "details": res.details,
    }


@router.post("/run_once")
def run_once_anomaly(
    room: str = Query(...),
    bucket_start: str = Query(..., description="ISO8601 UTC, e.g. 2026-02-05T05:15:00Z"),
    close_after_green_buckets: int = Query(2, ge=1, le=10),
    pet_weight: float = Query(0.25, ge=0.0, le=1.0),
    unknown_weight: float = Query(0.50, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
):
    bs = bucket_start.strip().replace("Z", "+00:00")
    from datetime import datetime
    dt = datetime.fromisoformat(bs)

    scored = score_room_bucket(db, room=room, bucket_start=dt, pet_weight=pet_weight, unknown_weight=unknown_weight)

    ep = upsert_bucket_result(
        db,
        room=scored.room,
        bucket_start=scored.bucket_start,
        bucket_end=scored.bucket_end,
        score_total=float(scored.score_total),
        level=scored.level,
        reasons=scored.reasons,
        reasons_summary=(scored.details if hasattr(scored, "details") else None),
        close_green_n=close_after_green_buckets,
        close_timeout_minutes=90,
    )

    if ep is None:
        proc_action = "NOOP"
        proc_episode_id = None
        proc_active = False
    else:
        if bool(getattr(ep, "_noop", False)):
            proc_action = "NOOP"
        elif not bool(getattr(ep, "active", True)):
            proc_action = "CLOSE"
        elif int(getattr(ep, "bucket_count", 0) or 0) <= 1:
            proc_action = "OPEN"
        else:
            proc_action = "UPDATE"
        proc_episode_id = ep.id
        proc_active = bool(getattr(ep, "active", True))

    db.commit()

    return {
        "bucket_score": {
            "room": scored.room,
            "bucket": {
                "start": scored.bucket_start,
                "end": scored.bucket_end,
                "bucket_idx": scored.bucket_idx,
                "dow": scored.dow,
                "is_weekend": scored.is_weekend,
            },
            "score": {
                "total": scored.score_total,
                "intensity": scored.score_intensity,
                "sequence": scored.score_sequence,
                "event": scored.score_event,
                "level": scored.level,
            },
            "reasons": scored.reasons,
        },
        "episode": {
            "action": proc_action,
            "episode_id": proc_episode_id,
            "active": proc_active,
        },
    }


@router.get("/scheduler_jobs")
def scheduler_jobs():
    jobs = scheduler.get_jobs()
    return [
        {
            "id": j.id,
            "next_run_time": (j.next_run_time.isoformat() if j.next_run_time else None),
            "trigger": str(j.trigger),
        }
        for j in jobs
    ]


@router.get("/runner_status")
def anomalies_runner_status():
    # In-memory status (process-local). Good enough for dev verification.
    return ANOMALIES_RUNNER_STATUS


@router.post("/run_latest")
def run_latest():
    # Debug/manual trigger of the same logic scheduler runs.
    from datetime import datetime, timezone
    out = run_anomalies_job()

    # Update in-memory status too (useful for UI verification)
    ANOMALIES_RUNNER_STATUS["last_run_at"] = datetime.now(timezone.utc).isoformat()
    ANOMALIES_RUNNER_STATUS["last_ok_at"] = datetime.now(timezone.utc).isoformat()
    ANOMALIES_RUNNER_STATUS["last_error_at"] = None
    ANOMALIES_RUNNER_STATUS["last_error_msg"] = None
    ANOMALIES_RUNNER_STATUS["last_scored_bucket_start"] = out.get("bucket_start")
    ANOMALIES_RUNNER_STATUS["last_counts"] = out.get("counts")
    ANOMALIES_RUNNER_STATUS["last_rooms_scored"] = out.get("rooms_scored")

    return out

