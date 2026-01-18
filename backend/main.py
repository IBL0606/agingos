import os
import httpx


# backend/main.py
from fastapi import Depends, FastAPI, HTTPException

from db import SessionLocal
from models.event import Event
from models.db_event import EventDB

from services.scheduler import scheduler, setup_scheduler
from services.auth import require_api_key, validate_auth_config_on_startup

from routes.rules import router as rules_router
from routes.deviations import router as deviations_router

from fastapi import Query
from datetime import datetime
from typing import Optional

from util.time import require_utc_aware

app = FastAPI(
    title="AgingOS Backend",
    dependencies=[Depends(require_api_key)],
)

app.include_router(rules_router)
app.include_router(deviations_router)


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
