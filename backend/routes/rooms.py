# backend/routes/rooms.py

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from db import get_db
from services.auth import AuthScope, require_scope


router = APIRouter(prefix="/rooms", tags=["rooms"])


class RoomIn(BaseModel):
    room_id: str = Field(..., min_length=1)
    display_name: str = Field(..., min_length=1)
    room_type: str = Field("OTHER", min_length=1)


class RoomOut(RoomIn):
    org_id: str
    home_id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


def _norm(v: str | None) -> str:
    return (v or "").strip()


@router.get("", response_model=List[RoomOut])
def list_rooms_v1(
    scope: AuthScope = Depends(require_scope),
    db: Session = Depends(get_db),
):
    rows = (
        db.execute(
            text(
                """
                SELECT org_id, home_id, room_id, display_name, room_type, created_at, updated_at
                FROM public.rooms
                WHERE org_id=:org_id AND home_id=:home_id
                ORDER BY room_id
                """
            ),
            {"org_id": scope.org_id, "home_id": scope.home_id},
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


@router.post("", response_model=RoomOut)
def upsert_room_v1(
    body: RoomIn,
    scope: AuthScope = Depends(require_scope),
    db: Session = Depends(get_db),
):
    room_id = _norm(body.room_id)
    display_name = _norm(body.display_name)
    room_type = _norm(body.room_type) or "OTHER"

    if not room_id:
        raise HTTPException(status_code=400, detail="room_id is required")
    if not display_name:
        raise HTTPException(status_code=400, detail="display_name is required")

    row = (
        db.execute(
            text(
                """
                INSERT INTO public.rooms (org_id, home_id, room_id, display_name, room_type)
                VALUES (:org_id, :home_id, :room_id, :display_name, :room_type)
                ON CONFLICT (org_id, home_id, room_id)
                DO UPDATE SET
                  display_name = EXCLUDED.display_name,
                  room_type    = EXCLUDED.room_type,
                  updated_at   = now()
                RETURNING org_id, home_id, room_id, display_name, room_type, created_at, updated_at
                """
            ),
            {
                "org_id": scope.org_id,
                "home_id": scope.home_id,
                "room_id": room_id,
                "display_name": display_name,
                "room_type": room_type,
            },
        )
        .mappings()
        .one()
    )

    db.commit()
    return dict(row)
