from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from db import SessionLocal

router = APIRouter(prefix="/baseline", tags=["baseline"])


def _get_instance_user_id(db) -> str:
    row = (
        db.execute(text("SELECT id::text AS id FROM app_instance LIMIT 1"))
        .mappings()
        .first()
    )
    if not row or not row.get("id"):
        raise HTTPException(
            status_code=500, detail="app_instance missing (no instance user_id)"
        )
    return row["id"]


@router.get("/status")
def baseline_status() -> dict[str, Any]:
    db = SessionLocal()
    try:
        uid = _get_instance_user_id(db)

        row = (
            db.execute(
                text(
                    """
                SELECT
                  user_id::text AS user_id,
                  model_start,
                  model_end,
                  min_days_required,
                  days_in_window,
                  days_with_data,
                  room_bucket_rows,
                  room_bucket_supported,
                  transition_rows,
                  transition_supported,
                  baseline_ready,
                  computed_at
                FROM baseline_model_status
                WHERE user_id = CAST(:uid AS uuid)
                ORDER BY model_end DESC
                LIMIT 1
                """
                ),
                {"uid": uid},
            )
            .mappings()
            .first()
        )

        if not row:
            return {
                "user_id": uid,
                "baseline_ready": False,
                "note": "no baseline_model_status rows yet",
            }

        room_bucket_coverage = None
        if row["room_bucket_rows"]:
            room_bucket_coverage = (
                row["room_bucket_supported"] / row["room_bucket_rows"]
            )

        transition_coverage = None
        if row["transition_rows"]:
            transition_coverage = row["transition_supported"] / row["transition_rows"]

        return {
            **dict(row),
            "coverage": {
                "room_bucket": room_bucket_coverage,
                "transition": transition_coverage,
            },
        }
    finally:
        db.close()


@router.get("")
def baseline_dev(
    room: Optional[str] = Query(default=None),
    bucket: Optional[int] = Query(default=None, ge=0, le=95),
    dow: Optional[int] = Query(default=None, ge=0, le=6),
    is_weekend: Optional[bool] = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
    rooms: Optional[bool] = Query(
        default=None, description="If true, return available rooms summary"
    ),
) -> dict[str, Any]:
    db = SessionLocal()
    try:
        uid = _get_instance_user_id(db)

        status = (
            db.execute(
                text(
                    """
                SELECT model_end, model_start, baseline_ready, days_with_data
                FROM baseline_model_status
                WHERE user_id = CAST(:uid AS uuid)
                ORDER BY model_end DESC
                LIMIT 1
                """
                ),
                {"uid": uid},
            )
            .mappings()
            .first()
        )

        if not status:
            raise HTTPException(
                status_code=404, detail="No baseline_model_status found yet"
            )

        model_end = status["model_end"]

        # Optional: rooms summary for discovery/debug
        if rooms:
            rows = (
                db.execute(
                    text(
                        """
                    SELECT room_id, COUNT(*) AS n_rows,
                           MIN(bucket_idx) AS min_bucket, MAX(bucket_idx) AS max_bucket
                    FROM baseline_room_bucket
                    WHERE user_id = CAST(:uid AS uuid)
                      AND model_end = :model_end
                    GROUP BY room_id
                    ORDER BY room_id
                    """
                    ),
                    {"uid": uid, "model_end": model_end},
                )
                .mappings()
                .all()
            )

            return {
                "status": dict(status),
                "rooms": [dict(r) for r in rows],
            }

        where = ["user_id = CAST(:uid AS uuid)", "model_end = :model_end"]
        params: dict[str, Any] = {"uid": uid, "model_end": model_end}

        if room is not None:
            where.append("room_id = :room")
            params["room"] = room
        if bucket is not None:
            where.append("bucket_idx = :bucket")
            params["bucket"] = bucket
        if dow is not None:
            where.append("dow = :dow")
            params["dow"] = dow
        if is_weekend is not None:
            where.append("is_weekend = :is_weekend")
            params["is_weekend"] = is_weekend

        baseline_rows = (
            db.execute(
                text(
                    f"""
                SELECT
                  user_id::text AS user_id,
                  model_start,
                  model_end,
                  dow,
                  is_weekend,
                  room_id,
                  bucket_idx,
                  activity_median,
                  activity_sigma,
                  activity_support_n,
                  activity_support_days,
                  door_median,
                  door_sigma,
                  door_support_n,
                  door_support_days,
                  sigma_floor,
                  computed_at
                FROM baseline_room_bucket
                WHERE {" AND ".join(where)}
                ORDER BY room_id, dow, bucket_idx
                LIMIT :limit
                """
                ),
                {**params, "limit": limit},
            )
            .mappings()
            .all()
        )

        transitions: list[dict[str, Any]] = []
        if room is not None:
            t_where = [
                "user_id = CAST(:uid AS uuid)",
                "model_end = :model_end",
                "from_room_id = :room",
            ]
            t_params = {"uid": uid, "model_end": model_end, "room": room}

            if bucket is not None:
                t_where.append("bucket_idx = :bucket")
                t_params["bucket"] = bucket
            if dow is not None:
                t_where.append("dow = :dow")
                t_params["dow"] = dow
            if is_weekend is not None:
                t_where.append("is_weekend = :is_weekend")
                t_params["is_weekend"] = is_weekend

            transitions = [
                dict(r)
                for r in db.execute(
                    text(
                        f"""
                        SELECT
                          user_id::text AS user_id,
                          model_start,
                          model_end,
                          dow,
                          is_weekend,
                          bucket_idx,
                          from_room_id,
                          to_room_id,
                          trans_count,
                          from_total,
                          alpha,
                          p_smoothed,
                          support_days,
                          computed_at
                        FROM baseline_transition
                        WHERE {" AND ".join(t_where)}
                        ORDER BY dow, bucket_idx, p_smoothed DESC NULLS LAST
                        LIMIT :limit
                        """
                    ),
                    {**t_params, "limit": limit},
                )
                .mappings()
                .all()
            ]

        return {
            "status": dict(status),
            "baseline_room_bucket": [dict(r) for r in baseline_rows],
            "baseline_transition": transitions,
        }
    finally:
        db.close()
