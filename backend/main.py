from fastapi import FastAPI
from typing import List

from db import SessionLocal, Base, engine
from models.event import Event
from models.db_event import EventDB

from services.scheduler import scheduler, setup_scheduler

from routes.rules import router as rules_router
from routes.deviations import router as deviations_router

app = FastAPI(title="AgingOS Backend")
app.include_router(rules_router)
app.include_router(deviations_router)

Base.metadata.create_all(bind=engine)

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
def list_events() -> list[Event]:
    db = SessionLocal()
    try:
        rows = db.query(EventDB).order_by(EventDB.id.desc()).all()
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
    setup_scheduler()
    if not scheduler.running:
        scheduler.start()


@app.on_event("shutdown")
def on_shutdown():
    scheduler.shutdown()
