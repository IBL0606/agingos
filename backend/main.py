import os
import httpx


# backend/main.py
from fastapi import Body, Depends, FastAPI, HTTPException, Request
from starlette.responses import Response

from db import SessionLocal
from models.event import Event
from models.db_event import EventDB

from services.scheduler import scheduler, setup_scheduler
from services.auth import (
    require_scope,
    AuthScope,
    validate_auth_config_on_startup,
)
from services.proposals_miner import mine_proposals
from services.proposals_expiry import expire_testing_proposals

from routes.rules import router as rules_router
from routes.deviations import router as deviations_router
from routes.baseline import router as baseline_router
from routes.anomalies import router as anomalies_router
from routes.notification_policy import router as notification_router

from fastapi import Query
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from util.time import require_utc_aware

app = FastAPI(title="AgingOS Backend")


# P1-5: Deprecation headers for legacy (non-/v1) API paths.
# - Additive: does not change behavior, only adds headers.
# - Exempt ops endpoints: /health, /health/detail, /debug/*
_DEPRECATION_SUNSET = os.getenv("AGINGOS_API_SUNSET_DATE", "2026-06-01")

@app.middleware("http")
async def add_deprecation_headers(request: Request, call_next):
    path = request.url.path or ""
    response: Response = await call_next(request)

    # Only tag legacy backend API routes (not /v1, not ops/debug)
    if not path.startswith("/v1"):
        if path.startswith("/health") or path.startswith("/debug"):
            return response

        # Mark legacy
        response.headers.setdefault("Deprecation", "true")
        response.headers.setdefault("Sunset", _DEPRECATION_SUNSET)

        # Simple successor mapping: prefix /v1 + same path
        # (works for most endpoints; may not exist for some legacy-only paths)
        successor = "/v1" + path
        response.headers.setdefault("Link", f'<{successor}>; rel="successor-version"')
    return response


app.include_router(rules_router, dependencies=[Depends(require_scope)])
app.include_router(deviations_router, dependencies=[Depends(require_scope)])
app.include_router(baseline_router, dependencies=[Depends(require_scope)])
app.include_router(anomalies_router, dependencies=[Depends(require_scope)])
app.include_router(notification_router, dependencies=[Depends(require_scope)])

# P1-5: /v1 stable contract (additive). Keep legacy paths working.
app.include_router(rules_router, prefix="/v1", dependencies=[Depends(require_scope)])
app.include_router(deviations_router, prefix="/v1", dependencies=[Depends(require_scope)])
app.include_router(baseline_router, prefix="/v1", dependencies=[Depends(require_scope)])
app.include_router(anomalies_router, prefix="/v1", dependencies=[Depends(require_scope)])
app.include_router(notification_router, prefix="/v1", dependencies=[Depends(require_scope)])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/detail")
def health_detail(scope: "AuthScope" = Depends(require_scope)):
    """
    Full pipeline health (P0-5).
    - Always scoped: returns explicit resolved scope to avoid false confidence.
    - Additive: does not change /health.
    """
    from datetime import datetime, timezone
    from sqlalchemy import text
    from db import SessionLocal
    from services.scheduler import scheduler, ANOMALIES_RUNNER_STATUS

    now = datetime.now(timezone.utc)

    out = {
        "schema_version": "v1",
        "now_utc": now.isoformat(),
        "scope": {
            "org_id": scope.org_id,
            "home_id": scope.home_id,
            "subject_id": scope.subject_id,
            "role": scope.role,
            "user_id": scope.user_id,
        },
        "components": {},
        "overall_status": "OK",
        "reasons": [],
    }

    def degrade(level: str, reason: str):
        # level: DEGRADED or ERROR
        if level == "ERROR":
            out["overall_status"] = "ERROR"
        elif out["overall_status"] != "ERROR":
            out["overall_status"] = "DEGRADED"
        out["reasons"].append(reason)

    # ---- ingest lag (events) ----
    stream_id = os.getenv("AGINGOS_STREAM_ID", "prod")
    db = SessionLocal()
    try:
        row = (
            db.execute(
                text("""
                SELECT MAX(\"timestamp\") AS max_ts, COUNT(*)::int AS n
                FROM events
                WHERE org_id = :org AND home_id = :home AND subject_id = :sub
                  AND stream_id = :stream_id
                """),
                {"org": scope.org_id, "home": scope.home_id, "sub": scope.subject_id, "stream_id": stream_id},
            )
            .mappings()
            .one()
        )

        max_ts = row["max_ts"]
        n = int(row["n"] or 0)
        lag_s = None
        if max_ts is not None:
            # max_ts is timestamptz from DB driver => aware datetime
            lag_s = max(0.0, (now - max_ts).total_seconds())

        out["components"]["ingest"] = {
            "status": "OK",
            "events_n": n,
            "max_event_ts": (max_ts.isoformat() if max_ts is not None else None),
            "lag_seconds": lag_s,
        }

        # Threshold is explicit and returned; can be tuned later without changing semantics.
        INGEST_LAG_DEGRADED_S = int(
            os.getenv("AGINGOS_HEALTH_INGEST_LAG_DEGRADED_S", "900")
        )  # 15 min
        INGEST_LAG_ERROR_S = int(
            os.getenv("AGINGOS_HEALTH_INGEST_LAG_ERROR_S", "7200")
        )  # 2 hours
        out["components"]["ingest"]["thresholds"] = {
            "degraded_seconds": INGEST_LAG_DEGRADED_S,
            "error_seconds": INGEST_LAG_ERROR_S,
        }

        if n == 0:
            out["components"]["ingest"]["status"] = "ERROR"
            degrade("ERROR", "no events found for this scope")
        elif lag_s is not None and lag_s >= INGEST_LAG_ERROR_S:
            out["components"]["ingest"]["status"] = "ERROR"
            degrade("ERROR", f"ingest lag >= {INGEST_LAG_ERROR_S}s")
        elif lag_s is not None and lag_s >= INGEST_LAG_DEGRADED_S:
            out["components"]["ingest"]["status"] = "DEGRADED"
            degrade("DEGRADED", f"ingest lag >= {INGEST_LAG_DEGRADED_S}s")

        # ---- baseline stale (baseline_model_status) ----
        baseline_table_missing = False
        try:
            b = (
                db.execute(
                    text("""
                    SELECT model_start, model_end, baseline_ready, computed_at,
                           days_in_window, days_with_data,
                           room_bucket_rows, room_bucket_supported,
                           transition_rows, transition_supported
                    FROM baseline_model_status
                    WHERE org_id = :org AND home_id = :home AND subject_id = :sub
                    ORDER BY model_end DESC
                    LIMIT 1
                """),
                    {
                        "org": scope.org_id,
                        "home": scope.home_id,
                        "sub": scope.subject_id,
                    },

                )
                .mappings()
                .one_or_none()
            )

        except Exception as e:
            # Fail-soft if table does not exist yet (e.g. migrations not applied)
            msg = str(e)
            if "subject_state" in msg and ("does not exist" in msg or "UndefinedTable" in msg):
                return {
                    "available": False,
                    "org_id": scope.org_id,
                    "home_id": scope.home_id,
                    "subject_id": scope.subject_id,
                    "state": "unknown",
                    "state_since": None,
                    "last_event_ts": None,
                    "updated_at": None,
                    "note": "subject_state table missing (migrations not applied yet)",
                }
            raise
        except Exception as e:
            from sqlalchemy.exc import ProgrammingError

            if isinstance(e, ProgrammingError):
                db.rollback()
                baseline_table_missing = True
                b = None
            else:
                raise

        # Expected end day (Oslo "yesterday") computed in DB to avoid timezone guessing in app.
        exp = (
            db.execute(
                text("""
            SELECT ((now() AT TIME ZONE 'Europe/Oslo')::date - 1) AS expected_end_day
        """)
            )
            .mappings()
            .one()
        )
        expected_end = exp["expected_end_day"]

        out["components"]["baseline"] = {
            "status": "OK",
            "expected_model_end": (
                expected_end.isoformat() if expected_end is not None else None
            ),
            "latest": None,
        }

        BASELINE_MAX_AGE_HOURS = int(
            os.getenv("AGINGOS_HEALTH_BASELINE_MAX_AGE_HOURS", "36")
        )
        out["components"]["baseline"]["thresholds"] = {
            "max_age_hours": BASELINE_MAX_AGE_HOURS
        }

        if baseline_table_missing:
            out["components"]["baseline"]["status"] = "SKIPPED"
            degrade("DEGRADED", "baseline tables missing (rules-only mode)")
        elif not b:
            out["components"]["baseline"]["status"] = "ERROR"
            degrade("ERROR", "no baseline_model_status rows for this scope")
        else:
            latest = dict(b)
            # Normalize datetimes/dates to isoformat for JSON
            for k in ("model_start", "model_end"):
                if latest.get(k) is not None:
                    latest[k] = latest[k].isoformat()
            if latest.get("computed_at") is not None:
                latest["computed_at"] = latest["computed_at"].isoformat()

            out["components"]["baseline"]["latest"] = latest

            # Evaluate staleness/readiness
            model_end = b["model_end"]
            computed_at = b["computed_at"]
            baseline_ready = bool(b["baseline_ready"])

            age_hours = None
            if computed_at is not None:
                age_hours = max(0.0, (now - computed_at).total_seconds() / 3600.0)
            out["components"]["baseline"]["age_hours"] = age_hours

            if not baseline_ready:
                out["components"]["baseline"]["status"] = "DEGRADED"
                degrade("DEGRADED", "baseline_ready=false")
            if (
                expected_end is not None
                and model_end is not None
                and model_end < expected_end
            ):
                out["components"]["baseline"]["status"] = "DEGRADED"
                degrade("DEGRADED", "baseline model_end is behind expected_end_day")
            if age_hours is not None and age_hours > BASELINE_MAX_AGE_HOURS:
                out["components"]["baseline"]["status"] = "DEGRADED"
                degrade(
                    "DEGRADED",
                    f"baseline computed_at older than {BASELINE_MAX_AGE_HOURS}h",
                )

    finally:
        db.close()

    # ---- scheduler status ----
    jobs = scheduler.get_jobs()
    out["components"]["scheduler"] = {
        "status": "OK",
        "running": bool(getattr(scheduler, "running", False)),
        "jobs": [
            {
                "id": j.id,
                "next_run_time": (
                    j.next_run_time.isoformat() if j.next_run_time else None
                ),
                "trigger": str(j.trigger),
            }
            for j in jobs
        ],
    }
    if not out["components"]["scheduler"]["running"]:
        out["components"]["scheduler"]["status"] = "ERROR"
        degrade("ERROR", "scheduler not running")
    elif len(jobs) == 0:
        out["components"]["scheduler"]["status"] = "DEGRADED"
        degrade("DEGRADED", "scheduler has zero jobs configured")

    # ---- anomalies runner status (process-local) ----
    rs = dict(ANOMALIES_RUNNER_STATUS)
    out["components"]["anomalies_runner"] = {
        "status": "OK",
        "runner_status": rs,
    }
    if rs.get("last_error_at"):
        out["components"]["anomalies_runner"]["status"] = "DEGRADED"
        degrade("DEGRADED", "anomalies runner has last_error_at set")
    elif not rs.get("last_ok_at") and not rs.get("last_run_at"):
        # MVP: after restart, runner status is process-local; don't degrade if scheduler is configured.
        job_ids = set(j.get("id") for j in out["components"]["scheduler"].get("jobs", []))
        if out["components"]["scheduler"].get("running") and "anomalies_job" in job_ids:
            rs["note"] = "runner status is process-local and not yet populated after restart; anomalies_job is scheduled"
            out["components"]["anomalies_runner"]["status"] = "OK"
        else:
            out["components"]["anomalies_runner"]["status"] = "DEGRADED"
            degrade("DEGRADED", "anomalies runner has never run in this process")

    return out


@app.post("/v1/pattern_miner/run_once")
def pattern_miner_run_once_v1(request: Request, scope: "AuthScope" = Depends(require_scope)):
    # P1-5: /v1 stable alias; re-use legacy implementation
    return pattern_miner_run_once(request)

@app.post("/pattern_miner/run_once")
def pattern_miner_run_once(request: Request):
    # manual trigger for testing (auth already enforced globally)
    db = SessionLocal()
    try:
        res = mine_proposals(db)
        db.commit()
        return {"status": "ok", "result": res}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


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


@app.get("/debug/scope")
def debug_scope(scope: "AuthScope" = Depends(require_scope)):
    """Debug: return resolved scope for current API key."""
    try:
        return scope.model_dump()
    except Exception:
        # pydantic v1 fallback
        return getattr(
            scope,
            "dict",
            lambda: {
                "org_id": scope.org_id,
                "home_id": scope.home_id,
                "subject_id": scope.subject_id,
                "role": getattr(scope, "role", None),
                "user_id": getattr(scope, "user_id", None),
            },
        )()


# --- Episodes SVC (incremental + idempotent) ----------------------------------


class EpisodesSvcBuildIn(BaseModel):
    since: Optional[str] = None  # ISO 8601 (UTC/offset), optional window replay
    until: Optional[str] = None
    advance_watermark: bool = False  # only relevant when since/until provided
    batch: int = 5000
    builder_name: str = "episodes_svc_v1"


def _parse_iso_ts(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


@app.post("/v1/episodes_svc/build_once")
def episodes_svc_build_once_v1(body: EpisodesSvcBuildIn, scope: "AuthScope" = Depends(require_scope)):
    # P1-5: /v1 stable alias; re-use legacy implementation
    return episodes_svc_build_once(body=body, scope=scope)

@app.post("/episodes_svc/build_once")
def episodes_svc_build_once(
    body: EpisodesSvcBuildIn, scope: "AuthScope" = Depends(require_scope)
):
    """
    Build presence-room episodes into episodes_svc.
    - Incremental by default (uses episode_builder_state watermark).
    - Idempotent writes (unique key on episodes_svc).
    - Optional window replay with since/until; watermark advances only if advance_watermark=true.
    """
    from services.episodes_svc_builder import build_presence_room_v1

    # DB DSN: same convention as elsewhere in backend
    # Prefer DATABASE_URL if set; fallback to local docker-compose defaults.
    import os

    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        host = os.getenv("PGHOST", "db")
        port = os.getenv("PGPORT", "5432")
        user = os.getenv("PGUSER", "agingos")
        pwd = os.getenv("PGPASSWORD", "agingos")
        db = os.getenv("PGDATABASE", "agingos")
        dsn = f"postgresql://{user}:{pwd}@{host}:{port}/{db}"

    since = _parse_iso_ts(body.since)
    until = _parse_iso_ts(body.until)

    res = build_presence_room_v1(
        db_dsn=dsn,
        org_id=scope.org_id,
        home_id=scope.home_id,
        subject_id=scope.subject_id,
        builder_name=body.builder_name,
        since=since,
        until=until,
        advance_watermark=bool(body.advance_watermark),
        batch=int(body.batch),
    )

    return {
        "builder": body.builder_name,
        "scope": {
            "org_id": scope.org_id,
            "home_id": scope.home_id,
            "subject_id": scope.subject_id,
        },
        "since": body.since,
        "until": body.until,
        "advance_watermark": bool(body.advance_watermark),
        "batch": int(body.batch),
        "events_read": res.events_read,
        "episodes_upserted": res.episodes_upserted,
        "skipped": {
            "no_room": res.skipped_no_room,
            "no_state": res.skipped_no_state,
            "unknown_state": res.skipped_unknown_state,
        },
        "watermark_before": {
            "last_event_ts": res.watermark_before_ts.isoformat()
            if res.watermark_before_ts
            else None,
            "last_event_row_id": res.watermark_before_id,
        },
        "watermark_after": {
            "last_event_ts": res.watermark_after_ts.isoformat()
            if res.watermark_after_ts
            else None,
            "last_event_row_id": res.watermark_after_id,
        },
    }


@app.post("/v1/event")
def receive_event_v1(event: Event, stream_id: str = Query(default="prod"), scope: AuthScope = Depends(require_scope)):
    # P1-5: /v1 stable alias; re-use legacy implementation
    return receive_event(event=event, scope=scope, stream_id=stream_id)

@app.post("/event")
def receive_event(event: Event, stream_id: str = Query(default="prod"), scope: AuthScope = Depends(require_scope)):
    db = SessionLocal()
    try:
        db_event = EventDB(
            event_id=str(event.id),
            timestamp=event.timestamp,
            category=event.category,
            payload=event.payload,
            org_id=scope.org_id,
            home_id=scope.home_id,
            subject_id=scope.subject_id,
        )
        # P1-7: force stream_id onto row (robust even if constructor args change)
        db_event.stream_id = stream_id

        db.add(db_event)
        try:
            db.commit()
            return {"received": True, "deduped": False}
        except IntegrityError as e:
            db.rollback()
            constraint = getattr(getattr(e.orig, "diag", None), "constraint_name", None)
            if constraint in ("events_event_id_unique","ux_events_scope_event_id","ux_events_scope_stream_event_id"):
                return {"received": True, "deduped": True}
            raise HTTPException(
                status_code=500, detail=f"db integrity error: {constraint or str(e)}"
            )
    finally:
        db.close()


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


def _monitor_key_from_action_target(action_target: str) -> str:
    """
    Normalize proposal action_target -> canonical monitor_key used by scheduler/monitor_modes.

    Canonical monitor_key in monitor_modes: rule key like "R-001", "R-002", ...
    Proposals may emit friendly keys like "monitor:night_activity"; we map those here (MVP).
    """
    s = (action_target or "").strip()
    if s.startswith("monitor:"):
        key = s.split(":", 1)[1].strip()
    else:
        key = s

    # MVP mapping: proposal "friendly key" -> rule key
    FRIENDLY_TO_RULE = {
        "night_activity": "R-001",
        "door_watch": "R-002",
        "mvp_bootstrap": "R-003",
    }
    return FRIENDLY_TO_RULE.get(key, key)


def _upsert_monitor_mode(
    db, *, scope: "AuthScope", monitor_key: str, room_id: str, mode: str
) -> None:
    db.execute(
        text(
            """
            INSERT INTO monitor_modes (org_id, home_id, subject_id, monitor_key, room_id, mode, updated_at)
              VALUES (:org_id, :home_id, :subject_id, :k, :r, :m, now())
              ON CONFLICT (org_id, home_id, subject_id, monitor_key, room_id)
              DO UPDATE SET mode = EXCLUDED.mode, updated_at = now()
            """
        ),
        {
            "org_id": scope.org_id,
            "home_id": scope.home_id,
            "subject_id": scope.subject_id,
            "k": monitor_key,
            "r": room_id,
            "m": mode,
        },
    )


@app.get("/v1/proposals")
def list_proposals_v1(
    last: str | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    scope: "AuthScope" = Depends(require_scope),
):
    # P1-5: /v1 stable alias; forward plain query values
    return list_proposals(last=last, limit=int(limit), scope=scope)

@app.get("/proposals")
def list_proposals(
    last: str | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    scope: AuthScope = Depends(require_scope),
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
                  p.proposal_id, p.org_id, p.home_id, p.subject_id, p.room_id,
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
                WHERE p.org_id = :org_id AND p.home_id = :home_id AND p.subject_id = :subject_id AND p.updated_at > :last_ts
                ORDER BY p.updated_at ASC
                LIMIT :limit
                """
            )
            rows = (
                db.execute(
                    q,
                    {
                        "org_id": scope.org_id,
                        "home_id": scope.home_id,
                        "subject_id": scope.subject_id,
                        "last_ts": last,
                        "limit": limit,
                    },
                )
                .mappings()
                .all()
            )
        else:
            q = text(
                """
                SELECT
                  p.proposal_id, p.org_id, p.home_id, p.subject_id, p.room_id,
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
                WHERE p.org_id = :org_id AND p.home_id = :home_id AND p.subject_id = :subject_id
                ORDER BY p.updated_at DESC
                LIMIT :limit
                """
            )
            rows = (
                db.execute(
                    q,
                    {
                        "org_id": scope.org_id,
                        "home_id": scope.home_id,
                        "subject_id": scope.subject_id,
                        "limit": limit,
                    },
                )
                .mappings()
                .all()
            )

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
    org_id: str,
    home_id: str,
    subject_id: str,
    action: str,  # TEST | ACTIVATE | REJECT
    actor: str | None,
    source: str,
    note: str | None,
):
    row = (
        db.execute(
            text(
                "SELECT proposal_id, state, action_target, room_id FROM proposals WHERE proposal_id = :id AND org_id = :org_id AND home_id = :home_id AND subject_id = :subject_id FOR UPDATE"
            ),
            {
                "id": proposal_id,
                "org_id": org_id,
                "home_id": home_id,
                "subject_id": subject_id,
            },
        )
        .mappings()
        .one_or_none()
    )

    if not row:
        return {"ok": False, "error": "not_found"}

    prev_state = row["state"]

    if not _transition_allowed(prev_state, action):
        return {
            "ok": False,
            "error": "transition_not_allowed",
            "prev_state": prev_state,
            "action": action,
        }

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

    # Apply real effect: monitor mode OFF|TEST|ON based on lifecycle action
    try:
        monitor_key = _monitor_key_from_action_target(row.get("action_target") or "")
        room_id = row.get("room_id") or "__GLOBAL__"
        mode = {"TEST": "TEST", "ACTIVATE": "ON", "REJECT": "OFF"}.get(action, "OFF")
        if monitor_key:
            _upsert_monitor_mode(
                db, monitor_key=monitor_key, room_id=room_id, mode=mode
            )
    except Exception:
        # fail-safe: do not break lifecycle if mode update fails
        pass

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

    return {
        "ok": True,
        "proposal_id": proposal_id,
        "prev_state": prev_state,
        "new_state": new_state,
    }


@app.post("/proposals/{proposal_id}/test")
def test_proposal(
    proposal_id: int,
    body: dict = Body(default={}),
    scope: AuthScope = Depends(require_scope),
):
    db = SessionLocal()
    try:
        with db.begin():
            return _proposal_transition(
                db,
                proposal_id=proposal_id,
                org_id=scope.org_id,
                home_id=scope.home_id,
                subject_id=scope.subject_id,
                action="TEST",
                actor=body.get("actor"),
                source=body.get("source", "ui"),
                note=body.get("note"),
            )
    finally:
        db.close()


@app.post("/proposals/{proposal_id}/activate")
def activate_proposal(
    proposal_id: int,
    body: dict = Body(default={}),
    scope: AuthScope = Depends(require_scope),
):
    db = SessionLocal()
    try:
        with db.begin():
            return _proposal_transition(
                db,
                proposal_id=proposal_id,
                org_id=scope.org_id,
                home_id=scope.home_id,
                subject_id=scope.subject_id,
                action="ACTIVATE",
                actor=body.get("actor"),
                source=body.get("source", "ui"),
                note=body.get("note"),
            )
    finally:
        db.close()


@app.post("/proposals/{proposal_id}/reject")
def reject_proposal(
    proposal_id: int,
    body: dict = Body(default={}),
    scope: AuthScope = Depends(require_scope),
):
    db = SessionLocal()
    try:
        with db.begin():
            return _proposal_transition(
                db,
                proposal_id=proposal_id,
                org_id=scope.org_id,
                home_id=scope.home_id,
                subject_id=scope.subject_id,
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
    scope: "AuthScope" = Depends(require_scope),
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
        params["org_id"] = scope.org_id
        params["home_id"] = scope.home_id
        params["subject_id"] = scope.subject_id
        where = [
            "org_id = :org_id",
            "home_id = :home_id",
            "subject_id = :subject_id",
            "start_ts >= :since",
            "start_ts < :until",
        ]

        # Filters
        if classification:
            c = classification.strip().lower()
            if c not in ("human", "pet", "unknown"):
                raise HTTPException(
                    status_code=400, detail="classification must be human|pet|unknown"
                )
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
                raise HTTPException(
                    status_code=400, detail="quality must be high|low|good|timeout"
                )

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
                    raise HTTPException(
                        status_code=400, detail="before_id must be a UUID"
                    )
                where.append(
                    "(start_ts < :before_ts OR (start_ts = :before_ts AND id < :before_id))"
                )
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
                WHERE {" AND ".join(where)}
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
            undone_by = defaultdict(
                dict
            )  # episode_id -> {target_label_id: undo_label_id}

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
                        "source": "manual"
                        if (m.get("actor") not in (None, ""))
                        else "unknown",
                        "actor": m.get("actor"),
                        "created_at": m["created_at"].isoformat()
                        if m.get("created_at")
                        else None,
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
def set_episode_label(
    episode_id: str, body: EpisodeLabelIn, scope: "AuthScope" = Depends(require_scope)
):
    """
    Persist a user label for an episode (audit trail in episode_labels).
    """
    from sqlalchemy import text
    from uuid import UUID
    try:
        UUID(str(episode_id))
    except Exception:
        raise HTTPException(status_code=400, detail="episode_id must be a UUID")


    lbl = (body.label or "").strip().lower()
    if lbl not in ("human", "pet", "unknown"):
        raise HTTPException(
            status_code=400, detail="label must be one of: human, pet, unknown"
        )
    actor = (body.actor or "").strip()
    if not actor:
        raise HTTPException(status_code=400, detail="actor is required")

    db = SessionLocal()
    try:
        # Ensure episode exists
        ep = db.execute(
            text(
                "SELECT id FROM episodes "
                "WHERE id = :id AND org_id = :org_id AND home_id = :home_id AND subject_id = :subject_id"
            ),
            {
                "id": episode_id,
                "org_id": scope.org_id,
                "home_id": scope.home_id,
                "subject_id": scope.subject_id,
            },
        ).fetchone()
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
            "created_at": row._mapping["created_at"].isoformat()
            if row._mapping["created_at"]
            else None,
        }
    finally:
        db.close()


@app.post("/episodes/{episode_id}/label/undo")
def undo_episode_label(
    episode_id: str, body: EpisodeUndoIn, scope: "AuthScope" = Depends(require_scope)
):
    """
    Undo a previous label by inserting an undo record that targets label_id.
    """
    from sqlalchemy import text
    from uuid import UUID
    try:
        UUID(str(episode_id))
    except Exception:
        raise HTTPException(status_code=400, detail="episode_id must be a UUID")


    actor = (body.actor or "").strip()
    if not actor:
        raise HTTPException(status_code=400, detail="actor is required")

    target = (body.label_id or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="label_id is required")

    db = SessionLocal()
    try:
        # Ensure episode exists
        ep = db.execute(
            text(
                "SELECT id FROM episodes "
                "WHERE id = :id AND org_id = :org_id AND home_id = :home_id AND subject_id = :subject_id"
            ),
            {
                "id": episode_id,
                "org_id": scope.org_id,
                "home_id": scope.home_id,
                "subject_id": scope.subject_id,
            },
        ).fetchone()
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
            raise HTTPException(
                status_code=404, detail="label not found for this episode"
            )
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
            {
                "episode_id": episode_id,
                "actor": actor,
                "note": body.note,
                "undone_label_id": target,
            },
        ).fetchone()
        db.commit()

        return {
            "ok": True,
            "episode_id": episode_id,
            "undo_label_id": str(row._mapping["id"]),
            "undone_label_id": target,
            "created_at": row._mapping["created_at"].isoformat()
            if row._mapping["created_at"]
            else None,
        }
    finally:
        db.close()


@app.get("/v1/events")
def list_events_v1(
    category: Optional[str] = Query(default=None),
    since: Optional[datetime] = Query(default=None),
    until: Optional[datetime] = Query(default=None),
    before: Optional[datetime] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    stream_id: str = Query(default="prod"),
    scope: "AuthScope" = Depends(require_scope),
) -> list[Event]:
    # P1-5: /v1 stable alias; re-use legacy implementation
    return list_events(category=category, since=since, until=until, before=before, limit=limit, stream_id=stream_id, scope=scope)

@app.get("/events")
def list_events(
    category: Optional[str] = Query(default=None),
    since: Optional[datetime] = Query(default=None),
    until: Optional[datetime] = Query(default=None),
    before: Optional[datetime] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    stream_id: str = Query(default="prod"),
    scope: "AuthScope" = Depends(require_scope),
) -> list[Event]:
    db = SessionLocal()
    try:
        query = db.query(EventDB)

        # Scope enforcement (P0-2): only return data for this API-key scope
        query = query.filter(
            EventDB.org_id == scope.org_id,
            EventDB.home_id == scope.home_id,
            EventDB.subject_id == scope.subject_id,
        )

        # Stream enforcement (P1-7): default 'prod' unless specified
        query = query.filter(EventDB.stream_id == stream_id)

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


@app.get("/v1/subject_state")
def get_subject_state_v1(scope: "AuthScope" = Depends(require_scope)) -> dict:
    # P1-5: /v1 stable alias; re-use legacy implementation
    return get_subject_state(scope=scope)

@app.get("/subject_state")
def get_subject_state(scope: "AuthScope" = Depends(require_scope)) -> dict:
    """
    Read-only subject state (P1-1-1 MVP).
    Scope enforced: returns only this API-key subject.
    """
    db = SessionLocal()
    try:
        # Fail-soft if table is missing (migrations not applied yet)
        chk = db.execute(text("SELECT to_regclass(\x27public.subject_state\x27) AS t")).mappings().one()
        if not chk.get("t"):
            return {
                "available": False,
                "org_id": scope.org_id,
                "home_id": scope.home_id,
                "subject_id": scope.subject_id,
                "state": "unknown",
                "state_since": None,
                "last_event_ts": None,
                "updated_at": None,
                "note": "subject_state table missing (migrations not applied yet)",
            }

        row = (
            db.execute(
                text(
                    """
                SELECT org_id, home_id, subject_id, state, state_since, last_event_ts, updated_at
                FROM subject_state
                WHERE org_id = :org AND home_id = :home AND subject_id = :sub
                """
                ),
                {"org": scope.org_id, "home": scope.home_id, "sub": scope.subject_id},
            )
            .mappings()
            .one_or_none()
        )

        if not row:
            return {
                "org_id": scope.org_id,
                "home_id": scope.home_id,
                "subject_id": scope.subject_id,
                "state": "unknown",
                "state_since": None,
                "last_event_ts": None,
                "updated_at": None,
            }

        r = dict(row)
        # Normalize datetimes to ISO
        for k in ("state_since", "last_event_ts", "updated_at"):
            v = r.get(k)
            if v is not None:
                try:
                    r[k] = v.isoformat()
                except Exception:
                    pass
        return r
    finally:
        db.close()


@app.post("/subject_state/compute_once")
def compute_subject_state_once(
    window_minutes: int = Query(default=60, ge=1, le=24 * 60),
    scope: "AuthScope" = Depends(require_scope),
) -> dict:
    """
    Computes subject_state for this (org_id, home_id) using DB function.
    Explicit trigger only; safe & deterministic. No data returned beyond counts.
    """
    db = SessionLocal()
    try:
        row = (
            db.execute(
                text(
                    "SELECT * FROM public.compute_subject_state_once(:org, :home, :mins)"
                ),
                {
                    "org": scope.org_id,
                    "home": scope.home_id,
                    "mins": int(window_minutes),
                },
            )
            .mappings()
            .one()
        )
        db.commit()
        return {
            "ok": True,
            "org_id": scope.org_id,
            "home_id": scope.home_id,
            **dict(row),
        }
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


# -------------------------
# Proposals: test expiry (manual trigger)
# -------------------------


@app.post("/v1/proposals/expire_once")
def proposals_expire_once_v1(scope: "AuthScope" = Depends(require_scope)):
    # P1-5: /v1 stable alias; re-use legacy implementation
    return proposals_expire_once()

@app.post("/proposals/expire_once")
def proposals_expire_once():
    db = SessionLocal()
    try:
        with db.begin():
            res = expire_testing_proposals(db)
        return {"status": "ok", "result": res}
    finally:
        db.close()


# -------------------------
# Monitor modes (read-back)
# -------------------------


@app.post("/v1/proposals/mine_once")
def mine_once_v1(scope: "AuthScope" = Depends(require_scope)) -> dict:
    # P1-5: /v1 stable alias; re-use legacy implementation
    return mine_once(scope=scope)

@app.post("/proposals/mine_once")
def mine_once(scope: AuthScope = Depends(require_scope)) -> dict:
    """
    Dev endpoint: run proposals miner immediately.
    Intended for dev-dashboard verification.
    """
    from db import SessionLocal
    from services.proposals_miner import mine_proposals

    db = SessionLocal()
    try:
        result = mine_proposals(db, scope=scope)
        db.execute(
            text(
                "INSERT INTO job_status (job_key, last_run_at, last_ok_at, last_error_at, last_error_msg, last_payload) "
                "VALUES ('proposals_miner', now(), now(), NULL, NULL, CAST(:payload AS jsonb)) "
                "ON CONFLICT (job_key) DO UPDATE SET "
                "  last_run_at = EXCLUDED.last_run_at, "
                "  last_ok_at = EXCLUDED.last_ok_at, "
                "  last_error_at = NULL, "
                "  last_error_msg = NULL, "
                "  last_payload = EXCLUDED.last_payload"
            ),
            {
                "payload": __import__("json").dumps(
                    result, ensure_ascii=False, separators=(",", ":")
                )
            },
        )
        db.commit()
        return {"ok": True, **result}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail={"error": str(e)})
    finally:
        db.close()


@app.get("/v1/proposals/miner_status")
def proposals_miner_status_v1(scope: "AuthScope" = Depends(require_scope)) -> dict:
    # P1-5: /v1 stable alias; re-use legacy implementation
    return proposals_miner_status()

@app.get("/proposals/miner_status")
def proposals_miner_status() -> dict:
    from db import SessionLocal

    db = SessionLocal()
    try:
        row = (
            db.execute(
                text(
                    "SELECT job_key, last_run_at, last_ok_at, last_error_at, last_error_msg, last_payload "
                    "FROM job_status WHERE job_key = 'proposals_miner'"
                )
            )
            .mappings()
            .first()
        )
        return {"ok": True, "status": (dict(row) if row else None)}
    finally:
        db.close()


@app.get("/v1/monitor_modes")
def list_monitor_modes_v1(
    monitor_key: str | None = None,
    room_id: str | None = None,
    limit: int = Query(default=500, ge=1, le=5000),
    scope: "AuthScope" = Depends(require_scope),
):
    # P1-5: /v1 stable alias; forward plain query values
    return list_monitor_modes(monitor_key=monitor_key, room_id=room_id, limit=int(limit), scope=scope)

@app.get("/monitor_modes")
def list_monitor_modes(
    monitor_key: str | None = None,
    room_id: str | None = None,
    limit: int = Query(default=500, ge=1, le=5000),
    scope: "AuthScope" = Depends(require_scope),
):
    """
    Read current monitor_modes rows for ops/debug without psql.

    Filters:
      - monitor_key: exact match
      - room_id: exact match

    Returns rows sorted by updated_at desc.
    """
    db = SessionLocal()
    try:
        where = ["org_id = :org_id", "home_id = :home_id", "subject_id = :subject_id"]
        params = {
            "limit": limit,
            "org_id": scope.org_id,
            "home_id": scope.home_id,
            "subject_id": scope.subject_id,
        }

        if monitor_key:
            where.append("monitor_key = :k")
            params["k"] = monitor_key

        if room_id:
            where.append("room_id = :r")
            params["r"] = room_id

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        q = text(
            f"""
            SELECT monitor_key, room_id, mode, updated_at
            FROM monitor_modes
            {where_sql}
            ORDER BY updated_at DESC, monitor_key ASC, room_id ASC
            LIMIT :limit
            """
        )
        rows = db.execute(q, params).mappings().all()
        return {"status": "ok", "rows": [dict(r) for r in rows]}
    finally:
        db.close()


@app.post("/monitor_modes")
def set_monitor_mode(
    payload: dict, scope: "AuthScope" = Depends(require_scope)
) -> dict:
    """
    Dev endpoint: upsert monitor_modes.
    Expected JSON:
      { "monitor_key": "R-001", "room_id": "__GLOBAL__", "mode": "OFF|TEST|ON" }
    """
    monitor_key = str(payload.get("monitor_key") or "").strip()
    room_id = str(payload.get("room_id") or "__GLOBAL__").strip() or "__GLOBAL__"
    mode = str(payload.get("mode") or "").strip().upper()

    if not monitor_key:
        raise HTTPException(status_code=400, detail="monitor_key required")
    if mode not in ("OFF", "TEST", "ON"):
        raise HTTPException(status_code=400, detail=f"invalid mode: {mode}")

    db = SessionLocal()
    try:
        _upsert_monitor_mode(
            db, scope=scope, monitor_key=monitor_key, room_id=room_id, mode=mode
        )
        db.commit()
        row = (
            db.execute(
                text(
                    "SELECT monitor_key, room_id, mode, updated_at "
                    "FROM monitor_modes WHERE org_id=:org_id AND home_id=:home_id AND subject_id=:subject_id AND monitor_key=:k AND room_id=:r"
                ),
                {
                    "org_id": scope.org_id,
                    "home_id": scope.home_id,
                    "subject_id": scope.subject_id,
                    "k": monitor_key,
                    "r": room_id,
                },
            )
            .mappings()
            .first()
        )
        return {"status": "ok", "row": (dict(row) if row else None)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail={"error": str(e)})
    finally:
        db.close()
