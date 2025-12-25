import os

# backend/main.py
from fastapi import FastAPI, HTTPException

from db import SessionLocal
from models.event import Event
from models.db_event import EventDB

from services.scheduler import scheduler, setup_scheduler

from routes.rules import router as rules_router
from routes.deviations import router as deviations_router

from fastapi import Query
from datetime import datetime
from typing import Optional


from util.time import require_utc_aware

app = FastAPI(title="AgingOS Backend")
app.include_router(rules_router)
app.include_router(deviations_router)


@app.get("/health")
def health():
    return {"status": "ok"}


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
    if os.getenv("SCHEDULER_ENABLED", "1").lower() in ("0", "false", "no", "off"):
        # Scheduler kan slås av lokalt ved behov (f.eks. under manuell testing)
        return

    setup_scheduler()
    if not scheduler.running:
        scheduler.start()


@app.on_event("shutdown")
def on_shutdown():
    scheduler.shutdown()
