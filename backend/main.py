from fastapi import FastAPI
from typing import List

from db import SessionLocal
from models.event import Event
from models.db_event import EventDB

app = FastAPI(title="AgingOS Backend")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/event")
def receive_event(event: Event):
    db = SessionLocal()
    try:
        db_event = EventDB(
            source=event.source,
            type=event.type,
            value=event.value,
            timestamp=event.timestamp,
        )
        db.add(db_event)
        db.commit()
    finally:
        db.close()

    return {"received": True}


@app.get("/events")
def list_events() -> List[Event]:
    db = SessionLocal()
    try:
        rows = db.query(EventDB).order_by(EventDB.id.desc()).all()
        return [
            Event(
                source=r.source,
                type=r.type,
                value=r.value,
                timestamp=r.timestamp,
            )
            for r in rows
        ]
    finally:
        db.close()
