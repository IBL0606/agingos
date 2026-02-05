import os
import httpx


# backend/main.py
from fastapi import Depends, FastAPI, HTTPException, Request

from db import SessionLocal
from models.event import Event
from models.db_event import EventDB

from services.scheduler import scheduler, setup_scheduler
from services.auth import require_api_key, validate_auth_config_on_startup

from routes.rules import router as rules_router
from routes.deviations import router as deviations_router
from routes.baseline import router as baseline_router
from routes.anomalies import router as anomalies_router

from fastapi import Query
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from util.time import require_utc_aware

app = FastAPI(
    title="AgingOS Backend",
    dependencies=[Depends(require_api_key)],
)

app.include_router(rules_router)
app.include_router(deviations_router)
app.include_router(baseline_router)
app.include_router(anomalies_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ai/status")
def ai_status():
    enabled = os.getenv("AI_BOT_ENABLED", "0").lower() in ("1", "true", "yes", "on")
    bot_url = os.getenv("AI_BOT_BASE_URL", "http://ai-bot:8010")

    if not enabled:
        return {
            "enabled": False,
            "reachable": False,
            "bot_url": bot_url,
            "bot_version": None,
            "schema_version": "v1",
        }

    try:
        with httpx.Client(timeout=1.5) as client:
            r = client.get(f"{bot_url}/v1/capabilities")
            r.raise_for_status()
            caps = r.json()

        return {
            "enabled": True,
            "reachable": True,
            "bot_url": bot_url,
            "bot_version": caps.get("bot_version"),
            "schema_version": caps.get("schema_version", "v1"),
            "features": caps.get("features", {}),
        }
    except Exception:
        return {
            "enabled": True,
            "reachable": False,
            "bot_url": bot_url,
            "bot_version": None,
            "schema_version": "v1",
        }


@app.get("/ai/insights")
def ai_insights(
    since: Optional[datetime] = Query(default=None),
    until: Optional[datetime] = Query(default=None),
):
    enabled = os.getenv("AI_BOT_ENABLED", "0").lower() in ("1", "true", "yes", "on")
    bot_url = os.getenv("AI_BOT_BASE_URL", "http://ai-bot:8010")

    if not enabled:
        return {
            "schema_version": "v1",
            "period": {"since": since, "until": until},
            "findings": [],
            "proposals": [],
            "note": "AI bot disabled",
        }

    # Normalize times (optional but consistent with /events)
    if since:
        since = require_utc_aware(since, "since")
    if until:
        until = require_utc_aware(until, "until")

    try:
        params = {}
        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()

        with httpx.Client(timeout=2.5) as client:
            r = client.get(f"{bot_url}/v1/insights", params=params)
            r.raise_for_status()
            payload = r.json()

        # Ensure period is always present for GUI consistency
        payload.setdefault("schema_version", "v1")
        payload.setdefault(
            "period",
            {
                "since": since.isoformat() if since else None,
                "until": until.isoformat() if until else None,
            },
        )
        payload.setdefault("findings", [])
        payload.setdefault("proposals", [])
        return payload
    except Exception:
        # Fail soft: GUI should keep working even if bot is down
        return {
            "schema_version": "v1",
            "period": {
                "since": since.isoformat() if since else None,
                "until": until.isoformat() if until else None,
            },
            "findings": [],
            "proposals": [],
            "note": "AI bot unreachable",
        }


@app.get("/ai/anomalies")
def ai_anomalies(
    since: Optional[datetime] = Query(default=None),
    until: Optional[datetime] = Query(default=None),
    window_days: int = Query(default=14, ge=3, le=60),
    min_abs_increase: Optional[int] = Query(default=None, ge=0, le=5000),
    z_threshold: Optional[float] = Query(default=None, ge=0.0, le=10.0),
    meaningful_recent_floor: Optional[int] = Query(default=None, ge=0, le=5000),
    quiet_min_room_baseline_nights: Optional[int] = Query(default=None, ge=1, le=60),
    quiet_min_room_baseline_mean: Optional[float] = Query(
        default=None, ge=0.0, le=100000.0
    ),
):
    enabled = os.getenv("AI_BOT_ENABLED", "0").lower() in ("1", "true", "yes", "on")
    bot_url = os.getenv("AI_BOT_BASE_URL", "http://ai-bot:8010")

    if not enabled:
        return {
            "schema_version": "v1",
            "period": {
                "since": since.isoformat() if since else None,
                "until": until.isoformat() if until else None,
            },
            "baseline": None,
            "findings": [],
            "note": "AI bot disabled",
        }

    if since:
        since = require_utc_aware(since, "since")
    if until:
        until = require_utc_aware(until, "until")

    try:
        params = {"window_days": window_days}
        if min_abs_increase is not None:
            params["min_abs_increase"] = min_abs_increase
        if z_threshold is not None:
            params["z_threshold"] = z_threshold
        if meaningful_recent_floor is not None:
            params["meaningful_recent_floor"] = meaningful_recent_floor
        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()
        if quiet_min_room_baseline_nights is not None:
            params["quiet_min_room_baseline_nights"] = quiet_min_room_baseline_nights
        if quiet_min_room_baseline_mean is not None:
            params["quiet_min_room_baseline_mean"] = quiet_min_room_baseline_mean

        with httpx.Client(timeout=2.5) as client:
            r = client.get(f"{bot_url}/v1/anomalies", params=params)
            r.raise_for_status()
            payload = r.json()

        payload.setdefault("schema_version", "v1")
        payload.setdefault(
            "period",
            {
                "since": since.isoformat() if since else None,
                "until": until.isoformat() if until else None,
            },
        )
        payload.setdefault("findings", [])
        return payload
    except Exception:
        return {
            "schema_version": "v1",
            "period": {
                "since": since.isoformat() if since else None,
                "until": until.isoformat() if until else None,
            },
            "baseline": None,
            "findings": [],
            "note": "AI bot unreachable",
        }


@app.post("/event")
def receive_event(event: Event):
    db = SessionLocal()
    try:
        db_event = EventDB(
            event_id=str(event.id),
            timestamp=event.timestamp,
            category=event.category,
            payload=event.payload,
        )
        db.add(db_event)
        db.commit()
    finally:
        db.close()

    return {"received": True}


@app.get("/ai/proposals")
def ai_proposals(
    request: Request,
    since: Optional[str] = Query(default=None),
    until: Optional[str] = Query(default=None),
    window_days: int = Query(default=14, ge=3, le=60),
    min_abs_increase: int = Query(default=10, ge=0, le=5000),
    z_threshold: float = Query(default=2.0, ge=0.0, le=10.0),
    meaningful_recent_floor: int = Query(default=20, ge=0, le=5000),
    quiet_min_room_baseline_nights: int = Query(7, ge=1, le=60),
    quiet_min_room_baseline_mean: float = Query(3.0, ge=0.0),
):
    """
    Sprint 3 (minimal v1): Proxy proposals from ai-bot.
    Fail-soft: return empty proposals with note if AI bot is unavailable.
    """
    import os
    import httpx

    enabled = os.getenv("AI_BOT_ENABLED", "0").lower() in ("1", "true", "yes", "on")
    bot_url = os.getenv("AI_BOT_BASE_URL", "http://ai-bot:8010")
    if not enabled:
        return {"enabled": False, "proposals": [], "note": "AI bot disabled"}

    try:
        params = {}
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        params.update(
            {
                "window_days": window_days,
                "min_abs_increase": min_abs_increase,
                "z_threshold": z_threshold,
                "meaningful_recent_floor": meaningful_recent_floor,
                "quiet_min_room_baseline_nights": quiet_min_room_baseline_nights,
                "quiet_min_room_baseline_mean": quiet_min_room_baseline_mean,
            }
        )
        with httpx.Client(timeout=2.5) as client:
            r = client.get(f"{bot_url}/v1/proposals", params=params)
            r.raise_for_status()
            payload = r.json()

            # Enrich proposals with persisted rule info (if present)
            try:
                from models.rule import Rule

                if isinstance(payload, dict):
                    ps = payload.get("proposals") or []
                    if ps:
                        db = SessionLocal()
                        try:
                            rules = db.query(Rule).order_by(Rule.id.desc()).all()
                        finally:
                            db.close()

                        by_pid = {}
                        for ru in rules:
                            p = ru.params or {}
                            pid = p.get("proposal_id")
                            if pid and pid not in by_pid:
                                by_pid[pid] = ru  # newest wins

                        for p in ps:
                            pid = p.get("id")
                            ru = by_pid.get(pid)
                            if ru:
                                ref = dict(ru.params or {})
                                ref["id"] = ru.id
                                ref["name"] = ru.name
                                ref["is_enabled"] = bool(
                                    getattr(ru, "is_enabled", False)
                                )
                                ca = getattr(ru, "created_at", None)
                                if ca is not None:
                                    try:
                                        ref["created_at"] = ca.isoformat()
                                    except Exception:
                                        pass

                                p.setdefault("references", {})
                                p["references"]["rule"] = ref

                                # reflect persisted status onto proposal.status (useful for UI)
                                st = ref.get("proposal_status")
                                if st and (p.get("status") in (None, "", "draft")):
                                    p["status"] = st
            except Exception:
                pass

            return payload

    except Exception as e:
        return {
            "schema_version": "v1",
            "period": {"since": since, "until": until},
            "proposals": [],
            "note": f"Could not fetch proposals from AI bot (fail-soft): {type(e).__name__}: {e}",
        }





# -------------------------
# Proposals (persistent MVP)
# -------------------------

from fastapi import Body
from sqlalchemy import text


@app.get("/proposals")
def list_proposals(
    last: str | None = None,
    limit: int = Query(default=200, ge=1, le=500),
):
    """
    Persistent proposals from DB (NOT ai-bot proxy).
    If `last` is provided: returns rows with updated_at > last (ISO8601 string).
    Includes recent action history (proposal_actions) in `actions`.
    """
    db = SessionLocal()
    try:
        if last:
            q = text(
                """
                SELECT
                  p.proposal_id, p.org_id, p.subject_id, p.room_id,
                  p.proposal_type, p.dedupe_key, p.state, p.priority,
                  p.evidence, p.why,
                  p.action_target, p.action_payload,
                  p.first_detected_at, p.last_detected_at,
                  p.window_start, p.window_end,
                  p.test_started_at, p.test_until,
                  p.activated_at, p.rejected_at,
                  p.last_actor, p.last_source, p.last_note,
                  p.created_at, p.updated_at,
                  COALESCE((
                    SELECT jsonb_agg(to_jsonb(a) ORDER BY a.created_at DESC, a.action_id DESC)
                    FROM (
                      SELECT action_id, action, prev_state, new_state, actor, source, note, created_at
                      FROM proposal_actions
                      WHERE proposal_id = p.proposal_id
                      ORDER BY created_at DESC, action_id DESC
                      LIMIT 20
                    ) a
                  ), '[]'::jsonb) AS actions
                FROM proposals p
                WHERE p.updated_at > :last_ts
                ORDER BY p.updated_at ASC
                LIMIT :limit
                """
            )
            rows = db.execute(q, {"last_ts": last, "limit": limit}).mappings().all()
        else:
            q = text(
                """
                SELECT
                  p.proposal_id, p.org_id, p.subject_id, p.room_id,
                  p.proposal_type, p.dedupe_key, p.state, p.priority,
                  p.evidence, p.why,
                  p.action_target, p.action_payload,
                  p.first_detected_at, p.last_detected_at,
                  p.window_start, p.window_end,
                  p.test_started_at, p.test_until,
                  p.activated_at, p.rejected_at,
                  p.last_actor, p.last_source, p.last_note,
                  p.created_at, p.updated_at,
                  COALESCE((
                    SELECT jsonb_agg(to_jsonb(a) ORDER BY a.created_at DESC, a.action_id DESC)
                    FROM (
                      SELECT action_id, action, prev_state, new_state, actor, source, note, created_at
                      FROM proposal_actions
                      WHERE proposal_id = p.proposal_id
                      ORDER BY created_at DESC, action_id DESC
                      LIMIT 20
                    ) a
                  ), '[]'::jsonb) AS actions
                FROM proposals p
                ORDER BY p.updated_at DESC
                LIMIT :limit
                """
            )
            rows = db.execute(q, {"limit": limit}).mappings().all()

        return [dict(r) for r in rows]
    finally:
        db.close()


def _transition_allowed(prev_state: str, action: str) -> bool:
    # Conservative MVP transitions
    prev_state = (prev_state or "").upper()
    action = (action or "").upper()

    if action == "TEST":
        return prev_state == "NEW"
    if action == "ACTIVATE":
        return prev_state in ("NEW", "TESTING")
    if action == "REJECT":
        return prev_state in ("NEW", "TESTING", "ACTIVE")
    return False


def _proposal_transition(
    db,
    *,
    proposal_id: int,
    action: str,          # TEST | ACTIVATE | REJECT
    actor: str | None,
    source: str,
    note: str | None,
):
    row = db.execute(
        text("SELECT proposal_id, state FROM proposals WHERE proposal_id = :id FOR UPDATE"),
        {"id": proposal_id},
    ).mappings().one_or_none()

    if not row:
        return {"ok": False, "error": "not_found"}

    prev_state = row["state"]

    if not _transition_allowed(prev_state, action):
        return {"ok": False, "error": "transition_not_allowed", "prev_state": prev_state, "action": action}

    if action == "TEST":
        new_state = "TESTING"
        db.execute(
            text(
                """
                UPDATE proposals
                SET state = 'TESTING',
                    test_started_at = now(),
                    test_until = now() + interval '7 days',
                    last_actor = :actor,
                    last_source = :source,
                    last_note = :note
                WHERE proposal_id = :id
                """
            ),
            {"id": proposal_id, "actor": actor, "source": source, "note": note},
        )

    elif action == "ACTIVATE":
        new_state = "ACTIVE"
        db.execute(
            text(
                """
                UPDATE proposals
                SET state = 'ACTIVE',
                    activated_at = now(),
                    -- clear any test window when activating
                    test_started_at = NULL,
                    test_until = NULL,
                    last_actor = :actor,
                    last_source = :source,
                    last_note = :note
                WHERE proposal_id = :id
                """
            ),
            {"id": proposal_id, "actor": actor, "source": source, "note": note},
        )

    elif action == "REJECT":
        new_state = "REJECTED"
        db.execute(
            text(
                """
                UPDATE proposals
                SET state = 'REJECTED',
                    rejected_at = now(),
                    -- clear any test window when rejecting
                    test_started_at = NULL,
                    test_until = NULL,
                    activated_at = NULL,
                    last_actor = :actor,
                    last_source = :source,
                    last_note = :note
                WHERE proposal_id = :id
                """
            ),
            {"id": proposal_id, "actor": actor, "source": source, "note": note},
        )
    else:
        return {"ok": False, "error": "bad_action"}

    db.execute(
        text(
            """
            INSERT INTO proposal_actions (
              proposal_id, action, prev_state, new_state,
              actor, source, note, payload
            )
            VALUES (
              :proposal_id, :action, :prev_state, :new_state,
              :actor, :source, :note, '{}'::jsonb
            )
            """
        ),
        {
            "proposal_id": proposal_id,
            "action": action,
            "prev_state": prev_state,
            "new_state": new_state,
            "actor": actor,
            "source": source,
            "note": note,
        },
    )

    return {"ok": True, "proposal_id": proposal_id, "prev_state": prev_state, "new_state": new_state}


@app.post("/proposals/{proposal_id}/test")
def test_proposal(proposal_id: int, body: dict = Body(default={})):
    db = SessionLocal()
    try:
        with db.begin():
            return _proposal_transition(
                db,
                proposal_id=proposal_id,
                action="TEST",
                actor=body.get("actor"),
                source=body.get("source", "ui"),
                note=body.get("note"),
            )
    finally:
        db.close()


@app.post("/proposals/{proposal_id}/activate")
def activate_proposal(proposal_id: int, body: dict = Body(default={})):
    db = SessionLocal()
    try:
        with db.begin():
            return _proposal_transition(
                db,
                proposal_id=proposal_id,
                action="ACTIVATE",
                actor=body.get("actor"),
                source=body.get("source", "ui"),
                note=body.get("note"),
            )
    finally:
        db.close()


@app.post("/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: int, body: dict = Body(default={})):
    db = SessionLocal()
    try:
        with db.begin():
            return _proposal_transition(
                db,
                proposal_id=proposal_id,
                action="REJECT",
                actor=body.get("actor"),
                source=body.get("source", "ui"),
                note=body.get("note"),
            )
    finally:
        db.close()



# --- Episodes (dev dashboard) -------------------------------------------------

def _parse_duration_seconds(s: str) -> int:
    """
    Parse simple durations like: 30s, 15m, 24h, 7d, 2w
    """
    s = (s or "").strip().lower()
    import re
    m = re.fullmatch(r"(\d+)\s*([smhdw])", s)
    if not m:
        raise ValueError("Invalid 'last' duration. Use like 24h, 7d, 30m, 90s, 2w")
    n = int(m.group(1))
    unit = m.group(2)
    mult = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}[unit]
    return n * mult


def _tod_bucket_utc(dt_utc: datetime) -> str:
    # Simple UTC buckets for now (explainable + deterministic)
    h = dt_utc.hour
    if h < 7:
        return "night"
    if h < 12:
        return "morning"
    if h < 18:
        return "day"
    return "evening"


@app.get("/episodes")
def list_episodes(
    last: str = Query(default="24h"),
    limit: int = Query(default=200, ge=1, le=5000),
    before: Optional[datetime] = Query(default=None),
    before_id: Optional[str] = Query(default=None),
    classification: Optional[str] = Query(default=None),
    room_id: Optional[str] = Query(default=None),
    quality: Optional[str] = Query(default=None),
):
    """
    Dev endpoint: return stored episodes for the last window.
    No pipeline here; this only reads from episodes + episode_labels tables.
    """
    from datetime import timezone, timedelta
    from sqlalchemy import text

    try:
        seconds = _parse_duration_seconds(last)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    now = datetime.now(timezone.utc)
    since = now - timedelta(seconds=seconds)
    until = now

    db = SessionLocal()
    try:
        # Fetch episodes (most recent first)
        # Fetch episodes with pagination + filters (stable ordering)
        # Stable sort: start_ts DESC, id DESC
        params = {"since": since, "until": until, "limit": limit}
        where = ["start_ts >= :since", "start_ts < :until"]

        # Filters
        if classification:
            c = classification.strip().lower()
            if c not in ("human", "pet", "unknown"):
                raise HTTPException(status_code=400, detail="classification must be human|pet|unknown")
            where.append("class = :class")
            params["class"] = c

        if room_id:
            where.append("room = :room")
            params["room"] = room_id

        if quality:
            q = quality.strip().lower()
            if q == "good":
                where.append("quality = :quality")
                params["quality"] = "high"
            elif q == "timeout":
                where.append("close_reason = :close_reason")
                params["close_reason"] = "timeout"
            elif q in ("high", "low"):
                where.append("quality = :quality")
                params["quality"] = q
            else:
                raise HTTPException(status_code=400, detail="quality must be high|low|good|timeout")

        # Pagination cursor
        if before is not None:
            try:
                before_utc = require_utc_aware(before, "before")
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

            if before_id:
                import uuid
                try:
                    uuid.UUID(before_id)
                except Exception:
                    raise HTTPException(status_code=400, detail="before_id must be a UUID")
                where.append("(start_ts < :before_ts OR (start_ts = :before_ts AND id < :before_id))")
                params["before_ts"] = before_utc
                params["before_id"] = before_id
            else:
                where.append("start_ts < :before_ts")
                params["before_ts"] = before_utc

        sql = f"""
                SELECT
                  id, room, room_type, primary_sensor, sensor_set,
                  start_ts, end_ts, duration_s,
                  close_reason, timeout_s, quality, quality_flags,
                  event_count_total, event_count_motion, event_count_presence_on, event_count_presence_off,
                  event_rate_per_min,
                  door_before_s, door_during, door_after_s,
                  tod_bucket, weekday,
                  class, p_human, p_pet, p_unknown,
                  classifier_version, feature_version, reasons, reason_summary
                FROM episodes
                WHERE {' AND '.join(where)}
                ORDER BY start_ts DESC, id DESC
                LIMIT :limit
        """

        ep_rows = db.execute(text(sql), params).fetchall()

        episodes = []
        ep_ids = []

        for r in ep_rows:
            m = dict(r._mapping)
            ep_ids.append(m["id"])

            # Normalize for JSON (psycopg handles most; be explicit with datetimes)
            start_ts = m["start_ts"]
            end_ts = m["end_ts"]
            episodes.append(
                {
                    "id": str(m["id"]),
                    "room": m["room"],
                    "room_type": m.get("room_type"),
                    "primary_sensor": m["primary_sensor"],
                    "sensor_set": m.get("sensor_set") or [],
                    "start_ts": start_ts.isoformat() if start_ts else None,
                    "end_ts": end_ts.isoformat() if end_ts else None,
                    "duration_s": m.get("duration_s"),
                    "close_reason": m["close_reason"],
                    "timeout_s": m["timeout_s"],
                    "quality": m["quality"],
                    "quality_flags": m.get("quality_flags") or [],
                    "event_agg": {
                        "total": m["event_count_total"],
                        "motion": m["event_count_motion"],
                        "presence_on": m["event_count_presence_on"],
                        "presence_off": m["event_count_presence_off"],
                        "event_rate_per_min": float(m["event_rate_per_min"]),
                    },
                    "context": {
                        "tod_bucket": m.get("tod_bucket") or _tod_bucket_utc(start_ts),
                        "weekday": m.get("weekday"),
                        "door_before_s": m.get("door_before_s"),
                        "door_during": bool(m.get("door_during")),
                        "door_after_s": m.get("door_after_s"),
                    },
                    "classification": {
                        "class": m["class"],
                        "p_human": float(m["p_human"]),
                        "p_pet": float(m["p_pet"]),
                        "p_unknown": float(m["p_unknown"]),
                        "classifier_version": m["classifier_version"],
                        "feature_version": m.get("feature_version") or "features_v1",
                        "reason_summary": m.get("reason_summary") or "",
                        "reasons": m.get("reasons") or [],
                    },
                    "label": None,  # filled below
                }
            )

        # Fetch labels for these episodes and compute:
        # - labels[] history (newest first), including undone_by_label_id
        # - label.current (effective label after applying undo)
        #
        # Undo rule:
        # - If label.is_undo=true and undone_label_id matches a label, that label is considered undone.
        # - Current label = newest non-undo label that is not undone.
        label_current_by_episode = {}
        labels_history_by_episode = {}

        if ep_ids:
            lab_rows = db.execute(
                text(
                    """
                    SELECT
                      id, episode_id, label, actor, created_at, note, is_undo, undone_label_id
                    FROM episode_labels
                    WHERE episode_id = ANY(:ep_ids)
                    ORDER BY episode_id, created_at ASC, id ASC
                    """
                ),
                {"ep_ids": ep_ids},
            ).fetchall()

            from collections import defaultdict

            # Track undo relations: target_label_id -> undo_label_id (per episode)
            undone_by = defaultdict(dict)  # episode_id -> {target_label_id: undo_label_id}

            # Collect all non-undo labels in insertion order (oldest->newest)
            history = defaultdict(list)  # episode_id -> [label_item...]

            # First pass: record undo relations + collect labels
            for r in lab_rows:
                m = dict(r._mapping)
                lid = str(m["id"])
                eid = str(m["episode_id"])
                is_undo = bool(m.get("is_undo"))
                target = str(m["undone_label_id"]) if m.get("undone_label_id") else None

                if is_undo and target:
                    # If multiple undos target same label, keep the first (oldest) for determinism
                    undone_by[eid].setdefault(target, lid)
                    continue

                if not is_undo:
                    item = {
                        "label_id": lid,
                        "label": m["label"],
                        "source": "manual" if (m.get("actor") not in (None, "")) else "unknown",
                        "actor": m.get("actor"),
                        "created_at": m["created_at"].isoformat() if m.get("created_at") else None,
                        "note": m.get("note"),
                        "undone_by_label_id": None,  # filled after we know undo mapping
                    }
                    history[eid].append(item)

            # Second pass: annotate history with undone_by_label_id + compute current
            for eid, items in history.items():
                for it in items:
                    it_id = it["label_id"]
                    it["undone_by_label_id"] = undone_by[eid].get(it_id)

                # labels[] should be newest first
                labels_history_by_episode[eid] = list(reversed(items))

                # Current = newest label that is not undone
                current = None
                for it in reversed(items):
                    if it.get("undone_by_label_id"):
                        continue
                    current = it
                    break

                if current:
                    label_current_by_episode[eid] = {
                        "current": current["label"],
                        "current_source": current["source"],
                        "actor": current["actor"],
                        "created_at": current["created_at"],
                        "note": current.get("note"),
                        "label_id": current["label_id"],
                    }
        # Attach label info
        for ep in episodes:
            ep["label"] = label_current_by_episode.get(ep["id"])
            ep["labels"] = labels_history_by_episode.get(ep["id"], [])

        return {
            "schema_version": "v1",
            "period": {"since": since.isoformat(), "until": until.isoformat()},
            "episodes": episodes,
        }

    finally:
        db.close()

# -----------------------------------------------------------------------------


class EpisodeLabelIn(BaseModel):
    label: str
    actor: str
    note: Optional[str] = None


class EpisodeUndoIn(BaseModel):
    actor: str
    label_id: str
    note: Optional[str] = None


@app.post("/episodes/{episode_id}/label")
def set_episode_label(episode_id: str, body: EpisodeLabelIn):
    """
    Persist a user label for an episode (audit trail in episode_labels).
    """
    from sqlalchemy import text

    lbl = (body.label or "").strip().lower()
    if lbl not in ("human", "pet", "unknown"):
        raise HTTPException(status_code=400, detail="label must be one of: human, pet, unknown")
    actor = (body.actor or "").strip()
    if not actor:
        raise HTTPException(status_code=400, detail="actor is required")

    db = SessionLocal()
    try:
        # Ensure episode exists
        ep = db.execute(text("SELECT id FROM episodes WHERE id = :id"), {"id": episode_id}).fetchone()
        if not ep:
            raise HTTPException(status_code=404, detail="episode not found")

        row = db.execute(
            text(
                """
                INSERT INTO episode_labels (episode_id, label, actor, note, is_undo, undone_label_id)
                VALUES (:episode_id, :label, :actor, :note, false, NULL)
                RETURNING id, created_at
                """
            ),
            {"episode_id": episode_id, "label": lbl, "actor": actor, "note": body.note},
        ).fetchone()
        db.commit()

        return {
            "ok": True,
            "episode_id": episode_id,
            "label_id": str(row._mapping["id"]),
            "current_label": lbl,
            "created_at": row._mapping["created_at"].isoformat() if row._mapping["created_at"] else None,
        }
    finally:
        db.close()


@app.post("/episodes/{episode_id}/label/undo")
def undo_episode_label(episode_id: str, body: EpisodeUndoIn):
    """
    Undo a previous label by inserting an undo record that targets label_id.
    """
    from sqlalchemy import text

    actor = (body.actor or "").strip()
    if not actor:
        raise HTTPException(status_code=400, detail="actor is required")

    target = (body.label_id or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="label_id is required")

    db = SessionLocal()
    try:
        # Ensure episode exists
        ep = db.execute(text("SELECT id FROM episodes WHERE id = :id"), {"id": episode_id}).fetchone()
        if not ep:
            raise HTTPException(status_code=404, detail="episode not found")

        # Ensure target label exists and belongs to this episode and is not an undo itself
        t = db.execute(
            text(
                """
                SELECT id, is_undo
                FROM episode_labels
                WHERE id = :label_id AND episode_id = :episode_id
                """
            ),
            {"label_id": target, "episode_id": episode_id},
        ).fetchone()
        if not t:
            raise HTTPException(status_code=404, detail="label not found for this episode")
        if bool(t._mapping["is_undo"]):
            raise HTTPException(status_code=400, detail="cannot undo an undo label")

        row = db.execute(
            text(
                """
                INSERT INTO episode_labels (episode_id, label, actor, note, is_undo, undone_label_id)
                VALUES (:episode_id, 'unknown', :actor, :note, true, :undone_label_id)
                RETURNING id, created_at
                """
            ),
            {"episode_id": episode_id, "actor": actor, "note": body.note, "undone_label_id": target},
        ).fetchone()
        db.commit()

        return {
            "ok": True,
            "episode_id": episode_id,
            "undo_label_id": str(row._mapping["id"]),
            "undone_label_id": target,
            "created_at": row._mapping["created_at"].isoformat() if row._mapping["created_at"] else None,
        }
    finally:
        db.close()




@app.get("/events")
def list_events(
    category: Optional[str] = Query(default=None),
    since: Optional[datetime] = Query(default=None),
    until: Optional[datetime] = Query(default=None),
    before: Optional[datetime] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[Event]:
    db = SessionLocal()
    try:
        query = db.query(EventDB)

        if category:
            query = query.filter(EventDB.category == category)
        if since:
            try:
                since_utc = require_utc_aware(since, "since")
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
            query = query.filter(EventDB.timestamp >= since_utc)
        if until:
            try:
                until_utc = require_utc_aware(until, "until")
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
            query = query.filter(EventDB.timestamp < until_utc)
        if before:
            try:
                before_utc = require_utc_aware(before, "before")
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
            query = query.filter(EventDB.timestamp < before_utc)

        rows = query.order_by(EventDB.timestamp.desc()).limit(limit).all()

        return [
            Event(
                id=r.event_id,
                timestamp=r.timestamp,
                category=r.category,
                payload=r.payload,
            )
            for r in rows
        ]
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    # Fail fast on bad auth config
    validate_auth_config_on_startup()

    if os.getenv("SCHEDULER_ENABLED", "1").lower() in ("0", "false", "no", "off"):
        # Scheduler kan slås av lokalt ved behov (f.eks. under manuell testing)
        return

    setup_scheduler()
    if not scheduler.running:
        scheduler.start()


@app.on_event("shutdown")
def on_shutdown():
    scheduler.shutdown()
