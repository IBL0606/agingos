# services/anomaly_scoring.py
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any, Optional

from fastapi import HTTPException

from services.auth import AuthScope
from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class BucketScore:
    room: str
    bucket_start: datetime
    bucket_end: datetime
    dow: int
    is_weekend: bool
    bucket_idx: int

    score_total: float
    score_intensity: float
    score_sequence: float
    score_event: float
    level: str  # GREEN|YELLOW|RED
    reasons: list[dict]
    details: dict


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


OSLO = ZoneInfo("Europe/Oslo")


def _level_from_score(score: float) -> str:
    if score >= 4.0:
        return "RED"
    if score >= 2.0:
        return "YELLOW"
    return "GREEN"


def _bucket_idx_15m(dt: datetime) -> int:
    # Bucket index must match baseline_bucket_idx_oslo() (Europe/Oslo local time)
    local = dt.astimezone(OSLO)
    m = local.hour * 60 + local.minute
    return int(m // 15)


def _norm_room(room: str) -> str:
    return (room or "").strip()


def _get_instance_user_id(scope: AuthScope) -> str:
    uid = getattr(scope, "user_id", None)
    if not uid:
        raise HTTPException(
            status_code=500, detail="scope missing user_id (api_key_scopes.user_id)"
        )
    return str(uid)


def _get_latest_model_end(db: Session, scope: AuthScope) -> Optional[str]:
    row = (
        db.execute(
            text(
                """
            SELECT model_end
            FROM baseline_model_status
            WHERE org_id = :org_id AND home_id = :home_id AND subject_id = :subject_id
            ORDER BY model_end DESC
            LIMIT 1
            """
            ),
            {
                "org_id": scope.org_id,
                "home_id": scope.home_id,
                "subject_id": scope.subject_id,
            },
        )
        .mappings()
        .first()
    )
    if not row:
        return None
    return row["model_end"]


def _prev_room(db: Session, scope: AuthScope, bucket_start: datetime) -> Optional[str]:
    row = (
        db.execute(
            text(
                """
            SELECT room
            FROM episodes
            WHERE org_id = :org_id AND home_id = :home_id AND subject_id = :subject_id
              AND end_ts IS NOT NULL AND end_ts <= :t
            ORDER BY end_ts DESC
            LIMIT 1
            """
            ),
            {
                "t": bucket_start,
                "org_id": scope.org_id,
                "home_id": scope.home_id,
                "subject_id": scope.subject_id,
            },
        )
        .mappings()
        .first()
    )
    return row["room"] if row else None


def _observed_activity(
    db: Session,
    scope: AuthScope,
    room: str,
    start: datetime,
    end: datetime,
    *,
    pet_weight: float,
    unknown_weight: float,
) -> tuple[float, dict]:
    """
    activity_obs = sum over episodes overlapping [start,end):
      (event_rate_per_min * overlap_minutes) * weight
    weight = p_human + pet_weight*p_pet + unknown_weight*p_unknown
    """
    rows = (
        db.execute(
            text(
                """
            SELECT
              start_ts, end_ts, event_rate_per_min,
              class, p_human, p_pet, p_unknown
            FROM episodes
            WHERE org_id = :org_id AND home_id = :home_id AND subject_id = :subject_id
              AND room = :room
              AND start_ts < :end
              AND end_ts IS NOT NULL
              AND end_ts > :start
            ORDER BY start_ts ASC
            """
            ),
            {
                "room": room,
                "start": start,
                "end": end,
                "org_id": scope.org_id,
                "home_id": scope.home_id,
                "subject_id": scope.subject_id,
            },
        )
        .mappings()
        .all()
    )

    total = 0.0
    used = 0
    for r in rows:
        ep_start = r["start_ts"]
        ep_end = r["end_ts"]
        overlap_s = (min(ep_end, end) - max(ep_start, start)).total_seconds()
        if overlap_s <= 0:
            continue
        overlap_min = overlap_s / 60.0
        rate = float(r["event_rate_per_min"] or 0.0)

        p_h = float(r["p_human"] or 0.0)
        p_p = float(r["p_pet"] or 0.0)
        p_u = float(r["p_unknown"] or 0.0)
        w = p_h + pet_weight * p_p + unknown_weight * p_u

        total += rate * overlap_min * w
        used += 1

    return total, {
        "episodes_used": used,
        "pet_weight": pet_weight,
        "unknown_weight": unknown_weight,
    }


def _observed_door_events(
    db: Session, scope: AuthScope, room: str, start: datetime, end: datetime
) -> int:
    # events.payload has room/area; we accept both keys.
    row = (
        db.execute(
            text(
                """
            SELECT COUNT(*)::int AS n
            FROM events
            WHERE org_id = :org_id AND home_id = :home_id AND subject_id = :subject_id
              AND "timestamp" >= :start AND "timestamp" < :end
              AND category = 'door'
              AND (
                (payload->>'room') = :room
                OR (payload->>'area') = :room
              )
            """
            ),
            {
                "start": start,
                "end": end,
                "room": room,
                "org_id": scope.org_id,
                "home_id": scope.home_id,
                "subject_id": scope.subject_id,
            },
        )
        .mappings()
        .first()
    )
    return int(row["n"] or 0) if row else 0


def score_room_bucket(
    db: Session,
    *,
    scope: AuthScope,
    room: str,
    bucket_start: datetime,
    pet_weight: float = 0.25,
    unknown_weight: float = 0.50,
    p_floor: float = 1e-6,
) -> BucketScore:
    room = _norm_room(room)
    if not room:
        raise HTTPException(status_code=400, detail="room is required")

    if bucket_start.tzinfo is None:
        raise HTTPException(
            status_code=400, detail="bucket_start must be timezone-aware UTC"
        )

    bucket_start = bucket_start.astimezone(timezone.utc).replace(
        second=0, microsecond=0
    )
    bucket_end = bucket_start + timedelta(minutes=15)
    bucket_local = bucket_start.astimezone(OSLO)
    dow = (int(bucket_local.weekday()) + 1) % 7  # pg_dow: 0=Sunday .. 6=Saturday (OSLO)
    is_weekend = dow in (0, 6)  # Sunday(0) or Saturday(6)
    bucket_idx = _bucket_idx_15m(bucket_start)

    uid = _get_instance_user_id(scope)

    model_end = _get_latest_model_end(db, scope)
    row_status = (
        db.execute(
            text(
                """
                SELECT baseline_ready
                FROM baseline_model_status
                WHERE org_id = :org_id AND home_id = :home_id AND subject_id = :subject_id
                ORDER BY model_end DESC
                LIMIT 1
                """
            ),
            {
                "org_id": scope.org_id,
                "home_id": scope.home_id,
                "subject_id": scope.subject_id,
            },
        )
        .mappings()
        .first()
    )
    baseline_ready = (
        bool(row_status.get("baseline_ready"))
        if row_status and row_status.get("baseline_ready") is not None
        else None
    )

    reasons: list[dict] = []
    details: dict[str, Any] = {
        "user_id": uid,
        "model_end": model_end,
        "baseline_ready": baseline_ready,
        "room": room,
        "bucket": {
            "start": bucket_start.isoformat(),
            "end": bucket_end.isoformat(),
            "bucket_idx": bucket_idx,
            "dow": dow,
            "is_weekend": is_weekend,
        },
    }

    # Observed
    activity_obs, act_meta = _observed_activity(
        db,
        scope,
        room,
        bucket_start,
        bucket_end,
        pet_weight=pet_weight,
        unknown_weight=unknown_weight,
    )
    door_obs = _observed_door_events(db, scope, room, bucket_start, bucket_end)

    details["observed"] = {
        "activity_obs": activity_obs,
        "door_obs": door_obs,
        **act_meta,
    }

    # Defaults (robust)
    score_intensity = 0.0
    score_event = 0.0
    score_sequence = 0.0

    # Baseline not present -> GREEN + explainable reason
    if not model_end:
        reasons.append(
            {
                "reason_code": "BASELINE_STATUS_MISSING",
                "component": "meta",
                "points": 0.0,
                "evidence": {"note": "No baseline_model_status rows"},
            }
        )
        total = 0.0
        return BucketScore(
            room=room,
            bucket_start=bucket_start,
            bucket_end=bucket_end,
            dow=dow,
            is_weekend=is_weekend,
            bucket_idx=bucket_idx,
            score_total=total,
            score_intensity=0.0,
            score_sequence=0.0,
            score_event=0.0,
            level=_level_from_score(total),
            reasons=reasons,
            details=details,
        )

    # Room-bucket baseline
    b = (
        db.execute(
            text(
                """
            SELECT
              activity_median, activity_sigma, activity_support_n, sigma_floor,
              door_median, door_sigma, door_support_n
            FROM baseline_room_bucket
            WHERE org_id = :org_id AND home_id = :home_id AND subject_id = :subject_id
              AND model_end = :model_end
              AND dow = :dow
              AND is_weekend = :is_weekend
              AND room_id = :room
              AND bucket_idx = :bucket_idx
            LIMIT 1
            """
            ),
            {
                "org_id": scope.org_id,
                "home_id": scope.home_id,
                "subject_id": scope.subject_id,
                "model_end": model_end,
                "dow": dow,
                "is_weekend": is_weekend,
                "room": room,
                "bucket_idx": bucket_idx,
            },
        )
        .mappings()
        .first()
    )
    if not b:
        reasons.append(
            {
                "reason_code": "BASELINE_MISSING_ROOM_BUCKET",
                "component": "meta",
                "points": 0.0,
                "evidence": {
                    "room": room,
                    "bucket_idx": bucket_idx,
                    "dow": dow,
                    "is_weekend": is_weekend,
                },
            }
        )
        # QUIET_BASELINE_FALLBACK_V1 (missing baseline_room_bucket)
        # 0 observed => treat as quiet/green (explainable).
        # observed > 0 => assign small deterministic points to make it actionable even without baseline support.
        if float(activity_obs or 0.0) <= 0.05 and float(door_obs or 0.0) <= 0.0:
            reasons.append(
                {
                    "reason_code": "QUIET_BASELINE_ASSUMED_QUIET",
                    "component": "meta",
                    "points": 0.0,
                    "evidence": {
                        "activity_obs": activity_obs,
                        "door_obs": door_obs,
                        "note": "Missing baseline_room_bucket; treated as quiet",
                    },
                }
            )
        else:
            qa = _clamp(
                math.log1p(max(0.0, float(activity_obs or 0.0))) / 2.0, 0.0, 3.0
            )
            if qa > 0:
                score_intensity = max(score_intensity, qa)
                reasons.append(
                    {
                        "reason_code": "QUIET_BASELINE_ACTIVITY",
                        "component": "intensity",
                        "points": round(qa, 4),
                        "evidence": {
                            "activity_obs": activity_obs,
                            "note": "Missing baseline_room_bucket; quiet-assumption fallback",
                        },
                    }
                )
            qd = _clamp(float(door_obs or 0.0) * 1.0, 0.0, 3.0)
            if qd > 0:
                score_event = max(score_event, qd)
                reasons.append(
                    {
                        "reason_code": "EVENT_DOOR_BURST",
                        "component": "event",
                        "points": round(qd, 4),
                        "evidence": {
                            "door_obs": door_obs,
                            "note": "Missing baseline_room_bucket; quiet-assumption fallback",
                        },
                    }
                )

    else:
        # Intensity component (activity)
        mu = b["activity_median"]
        sig = b["activity_sigma"]
        sigma_floor = float(b["sigma_floor"] or 0.1)
        n = int(b["activity_support_n"] or 0)

        if mu is None or sig is None or n <= 0:
            reasons.append(
                {
                    "reason_code": "BASELINE_ACTIVITY_UNSUPPORTED",
                    "component": "intensity",
                    "points": 0.0,
                    "evidence": {"support_n": n, "mu": mu, "sigma": sig},
                }
            )
            # QUIET_BASELINE_FALLBACK_V1 (activity unsupported)
            if float(activity_obs or 0.0) <= 0.05:
                reasons.append(
                    {
                        "reason_code": "QUIET_BASELINE_ACTIVITY_QUIET",
                        "component": "intensity",
                        "points": 0.0,
                        "evidence": {
                            "activity_obs": activity_obs,
                            "note": "Unsupported activity baseline; treated as quiet",
                        },
                    }
                )
            else:
                qa = _clamp(
                    math.log1p(max(0.0, float(activity_obs or 0.0))) / 2.0, 0.0, 3.0
                )
                if qa > 0:
                    score_intensity = max(score_intensity, qa)
                    reasons.append(
                        {
                            "reason_code": "QUIET_BASELINE_ACTIVITY",
                            "component": "intensity",
                            "points": round(qa, 4),
                            "evidence": {
                                "activity_obs": activity_obs,
                                "note": "Unsupported activity baseline; quiet-assumption fallback",
                            },
                        }
                    )
        else:
            mu = float(mu)
            sig = float(sig)
            sigma_eff = max(sig, sigma_floor)
            z = (activity_obs - mu) / sigma_eff if sigma_eff > 0 else 0.0
            z_pos = max(0.0, z)
            # deterministic points: 0 until 2σ, then linear up to 3
            score_intensity = _clamp((z_pos - 2.0) / 1.0, 0.0, 3.0)
            if score_intensity > 0:
                reasons.append(
                    {
                        "reason_code": "INTENSITY_ACTIVITY_Z",
                        "component": "intensity",
                        "points": round(score_intensity, 4),
                        "evidence": {
                            "obs": activity_obs,
                            "mu": mu,
                            "sigma_eff": sigma_eff,
                            "z": z,
                            "support_n": n,
                        },
                    }
                )

        # Event component (door)
        dmu = b["door_median"]
        dsig = b["door_sigma"]
        dn = int(b["door_support_n"] or 0)
        if dmu is None or dsig is None or dn <= 0:
            # still allow a special-case: baseline says nothing, but a door at all is notable at night-ish? (kept 0 here; rules later)
            reasons.append(
                {
                    "reason_code": "BASELINE_DOOR_UNSUPPORTED",
                    "component": "event",
                    "points": 0.0,
                    "evidence": {"support_n": dn, "mu": dmu, "sigma": dsig},
                }
            )
            # QUIET_BASELINE_FALLBACK_V1 (door unsupported)
            if float(door_obs or 0.0) <= 0.0:
                reasons.append(
                    {
                        "reason_code": "QUIET_BASELINE_DOOR_QUIET",
                        "component": "event",
                        "points": 0.0,
                        "evidence": {
                            "door_obs": door_obs,
                            "note": "Unsupported door baseline; treated as quiet",
                        },
                    }
                )
            else:
                qd = _clamp(float(door_obs or 0.0) * 1.0, 0.0, 3.0)
                if qd > 0:
                    score_event = max(score_event, qd)
                    reasons.append(
                        {
                            "reason_code": "EVENT_DOOR_BURST",
                            "component": "event",
                            "points": round(qd, 4),
                            "evidence": {
                                "door_obs": door_obs,
                                "note": "Unsupported door baseline; quiet-assumption fallback",
                            },
                        }
                    )
        else:
            dmu = float(dmu)
            dsig = float(dsig)
            dsigma_eff = max(dsig, sigma_floor)
            dz = (door_obs - dmu) / dsigma_eff if dsigma_eff > 0 else 0.0
            dz_pos = max(0.0, dz)
            score_event = _clamp((dz_pos - 1.0) / 1.0, 0.0, 3.0)
            if score_event > 0:
                reasons.append(
                    {
                        "reason_code": "EVENT_DOOR_Z",
                        "component": "event",
                        "points": round(score_event, 4),
                        "evidence": {
                            "door_obs": door_obs,
                            "mu": dmu,
                            "sigma_eff": dsigma_eff,
                            "z": dz,
                            "support_n": dn,
                        },
                    }
                )

    # Sequence component via transitions
    prev = _prev_room(db, scope, bucket_start)
    details["observed"]["prev_room"] = prev

    if prev and prev != room:
        t = (
            db.execute(
                text(
                    """
                SELECT p_smoothed, trans_count, from_total, alpha
                FROM baseline_transition
                WHERE org_id = :org_id AND home_id = :home_id AND subject_id = :subject_id
                  AND model_end = :model_end
                  AND dow = :dow
                  AND is_weekend = :is_weekend
                  AND bucket_idx = :bucket_idx
                  AND from_room_id = :from_room
                  AND to_room_id = :to_room
                LIMIT 1
                """
                ),
                {
                    "org_id": scope.org_id,
                    "home_id": scope.home_id,
                    "subject_id": scope.subject_id,
                    "model_end": model_end,
                    "dow": dow,
                    "is_weekend": is_weekend,
                    "bucket_idx": bucket_idx,
                    "from_room": prev,
                    "to_room": room,
                },
            )
            .mappings()
            .first()
        )

        if not t or t["p_smoothed"] is None:
            reasons.append(
                {
                    "reason_code": "TRANSITION_BASELINE_MISSING",
                    "component": "sequence",
                    "points": 0.0,
                    "evidence": {
                        "from_room": prev,
                        "to_room": room,
                        "note": "Pilot: transition baseline often missing; 0 points",
                    },
                }
            )
        else:
            p = float(t["p_smoothed"])
            p_eff = max(p, p_floor)
            rarity = -math.log(p_eff)
            # 0 until rarity ~2, then scale to 3 by rarity ~8
            score_sequence = _clamp((rarity - 2.0) / 2.0, 0.0, 3.0)
            if score_sequence > 0:
                reasons.append(
                    {
                        "reason_code": "SEQUENCE_TRANSITION_RARITY",
                        "component": "sequence",
                        "points": round(score_sequence, 4),
                        "evidence": {
                            "from_room": prev,
                            "to_room": room,
                            "p": p,
                            "p_floor": p_floor,
                            "rarity": rarity,
                            "trans_count": float(t.get("trans_count") or 0.0),
                            "from_total": float(t.get("from_total") or 0.0),
                            "alpha": float(t.get("alpha") or 0.0),
                        },
                    }
                )

    total = float(score_intensity + score_event + score_sequence)
    level = _level_from_score(total)

    return BucketScore(
        room=room,
        bucket_start=bucket_start,
        bucket_end=bucket_end,
        dow=dow,
        is_weekend=is_weekend,
        bucket_idx=bucket_idx,
        score_total=total,
        score_intensity=float(score_intensity),
        score_sequence=float(score_sequence),
        score_event=float(score_event),
        level=level,
        reasons=reasons,
        details=details,
    )
