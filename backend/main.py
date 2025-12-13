from fastapi import FastAPI
from typing import List

from models.event import Event

app = FastAPI(title="AgingOS Backend")

events: List[Event] = []


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/event")
def receive_event(event: Event):
    events.append(event)
    return {"received": True}


@app.get("/events")
def list_events():
    return events
