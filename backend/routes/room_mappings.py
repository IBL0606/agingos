# backend/routes/room_mappings.py

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from db import get_db
from services.auth import AuthScope, require_scope


router = APIRouter(prefix="/room_mappings", tags=["room_mappings"])


class RoomMappingIn(BaseModel):
    entity_id: str = Field(..., min_length=1)
    room_id: str = Field(..., min_length=1)
    active: bool = True
    note: Optional[str] = None


class RoomMappingOut(RoomMappingIn):
    org_id: str
    home_id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UnknownSensorOut(BaseModel):
    entity_id: str


def _norm(v: str | None) -> str:
    return (v or "").strip()


@router.get("", response_model=List[RoomMappingOut])
def list_room_mappings_v1(
    scope: AuthScope = Depends(require_scope),
    db: Session = Depends(get_db),
):
    rows = (
        db.execute(
            text(
                """
                SELECT org_id, home_id, entity_id, room_id, active, note, created_at, updated_at
                FROM public.sensor_room_map
                WHERE org_id=:org_id AND home_id=:home_id
                ORDER BY entity_id
                """
            ),
            {"org_id": scope.org_id, "home_id": scope.home_id},
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


@router.post("", response_model=RoomMappingOut)
def upsert_room_mapping_v1(
    body: RoomMappingIn,
    scope: AuthScope = Depends(require_scope),
    db: Session = Depends(get_db),
):
    entity_id = _norm(body.entity_id)
    room_id = _norm(body.room_id)
    note = _norm(body.note) if body.note is not None else None
    active = bool(body.active)

    if not entity_id:
        raise HTTPException(status_code=400, detail="entity_id is required")
    if not room_id:
        raise HTTPException(status_code=400, detail="room_id is required")

    # validate room exists in scope
    ok = db.execute(
        text(
            """
            SELECT 1
            FROM public.rooms
            WHERE org_id=:org_id AND home_id=:home_id AND room_id=:room_id
            LIMIT 1
            """
        ),
        {"org_id": scope.org_id, "home_id": scope.home_id, "room_id": room_id},
    ).scalar()
    if ok is None:
        raise HTTPException(status_code=400, detail="room_id not found in rooms")

    row = (
        db.execute(
            text(
                """
                INSERT INTO public.sensor_room_map (org_id, home_id, entity_id, room_id, active, note)
                VALUES (:org_id, :home_id, :entity_id, :room_id, :active, :note)
                ON CONFLICT (org_id, home_id, entity_id)
                DO UPDATE SET
                  room_id    = EXCLUDED.room_id,
                  active     = EXCLUDED.active,
                  note       = EXCLUDED.note,
                  updated_at = now()
                RETURNING org_id, home_id, entity_id, room_id, active, note, created_at, updated_at
                """
            ),
            {
                "org_id": scope.org_id,
                "home_id": scope.home_id,
                "entity_id": entity_id,
                "room_id": room_id,
                "active": active,
                "note": note,
            },
        )
        .mappings()
        .one()
    )
    db.commit()
    return dict(row)


@router.get("/unknown_sensors", response_model=List[UnknownSensorOut])
def list_unknown_sensors_v1(
    stream_id: str = Query("prod"),
    scope: AuthScope = Depends(require_scope),
    db: Session = Depends(get_db),
):
    # Distinct entity_id in presence/door events (scope + stream), where no active mapping exists
    rows = (
        db.execute(
            text(
                """
                WITH ev AS (
                  SELECT DISTINCT (payload->>'entity_id') AS entity_id
                  FROM public.events
                  WHERE org_id=:org_id AND home_id=:home_id AND subject_id=:subject_id
                    AND stream_id=:stream_id
                    AND category IN ('presence','door')
                                        AND (payload->>'entity_id') IS NOT NULL
                    AND (payload->>'entity_id') <> ''
                )
                SELECT ev.entity_id
                FROM ev
                LEFT JOIN public.sensor_room_map m
                  ON m.org_id=:org_id AND m.home_id=:home_id
                 AND m.entity_id = ev.entity_id
                 AND m.active = true
                WHERE m.entity_id IS NULL
                ORDER BY ev.entity_id
                """
            ),
            {
                "org_id": scope.org_id,
                "home_id": scope.home_id,
                "subject_id": scope.subject_id,
                "stream_id": stream_id,
            },
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]