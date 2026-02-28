from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text

from db import SessionLocal
from services.auth import AuthScope, require_scope
from util.time import require_utc_aware

router = APIRouter(prefix="/notification", tags=["notification"])


def _actor_from_scope(scope: AuthScope) -> str:
    uid = getattr(scope, "user_id", None)
    role = getattr(scope, "role", None) or "unknown"
    if uid:
        return f"{role}:{uid}"
    return str(role)


def _iso(v):
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


class PolicyOut(BaseModel):
    org_id: str
    home_id: str
    subject_id: str
    mode: str
    quiet_start_local: Optional[str] = None
    quiet_end_local: Optional[str] = None
    tz: str
    override_until: Optional[str] = None
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None


class PartnerOverrideIn(BaseModel):
    override_until_utc: datetime


@router.get("/policy", response_model=PolicyOut)
def get_policy(scope: AuthScope = Depends(require_scope)) -> PolicyOut:
    db = SessionLocal()
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT org_id, home_id, subject_id,
                           mode, quiet_start_local, quiet_end_local, tz,
                           override_until, updated_at, updated_by
                    FROM notification_policy
                    WHERE org_id=:org AND home_id=:home AND subject_id=:sub
                    """
                ),
                {"org": scope.org_id, "home": scope.home_id, "sub": scope.subject_id},
            )
            .mappings()
            .one_or_none()
        )

        if not row:
            return PolicyOut(
                org_id=scope.org_id,
                home_id=scope.home_id,
                subject_id=scope.subject_id,
                mode="NORMAL",
                quiet_start_local=None,
                quiet_end_local=None,
                tz="Europe/Oslo",
                override_until=None,
                updated_at=None,
                updated_by=None,
            )

        return PolicyOut(
            org_id=row["org_id"],
            home_id=row["home_id"],
            subject_id=row["subject_id"],
            mode=row.get("mode") or "NORMAL",
            quiet_start_local=_iso(row.get("quiet_start_local")),
            quiet_end_local=_iso(row.get("quiet_end_local")),
            tz=row.get("tz") or "Europe/Oslo",
            override_until=_iso(row.get("override_until")),
            updated_at=_iso(row.get("updated_at")),
            updated_by=row.get("updated_by"),
        )
    finally:
        db.close()


@router.post("/policy/partner_override", response_model=PolicyOut)
def set_partner_override(
    body: PartnerOverrideIn, scope: AuthScope = Depends(require_scope)
) -> PolicyOut:
    require_utc_aware(body.override_until_utc, "override_until_utc")

    db = SessionLocal()
    try:
        actor = _actor_from_scope(scope)

        # 1) upsert override (audit trigger fires)
        db.execute(
            text(
                """
                SELECT org_id, home_id, subject_id, override_until, updated_at, updated_by
                FROM set_notification_policy_override(:org, :home, :sub, :until_ts, :updated_by)
                """
            ),
            {
                "org": scope.org_id,
                "home": scope.home_id,
                "sub": scope.subject_id,
                "until_ts": body.override_until_utc,
                "updated_by": actor,
            },
        )

        # 2) read full policy row
        row = (
            db.execute(
                text(
                    """
                    SELECT org_id, home_id, subject_id,
                           mode, quiet_start_local, quiet_end_local, tz,
                           override_until, updated_at, updated_by
                    FROM notification_policy
                    WHERE org_id=:org AND home_id=:home AND subject_id=:sub
                    """
                ),
                {"org": scope.org_id, "home": scope.home_id, "sub": scope.subject_id},
            )
            .mappings()
            .one_or_none()
        )
        if not row:
            raise RuntimeError(
                "partner_override failed: notification_policy row missing after upsert"
            )

        db.commit()

        return PolicyOut(
            org_id=row["org_id"],
            home_id=row["home_id"],
            subject_id=row["subject_id"],
            mode=row.get("mode") or "NORMAL",
            quiet_start_local=_iso(row.get("quiet_start_local")),
            quiet_end_local=_iso(row.get("quiet_end_local")),
            tz=row.get("tz") or "Europe/Oslo",
            override_until=_iso(row.get("override_until")),
            updated_at=_iso(row.get("updated_at")),
            updated_by=row.get("updated_by"),
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class AuditEventOut(BaseModel):
    id: int
    action: str
    changed_at: str
    actor: Optional[str] = None
    prev: Optional[dict[str, Any]] = None
    next: Optional[dict[str, Any]] = None


@router.get("/policy/audit", response_model=list[AuditEventOut])
def get_policy_audit(
    limit: int = Query(50, ge=1, le=500),
    scope: AuthScope = Depends(require_scope),
) -> list[AuditEventOut]:
    db = SessionLocal()
    try:
        rows = (
            db.execute(
                text(
                    """
                    SELECT id, action, changed_at, actor, prev, next
                    FROM notification_policy_events
                    WHERE org_id=:org AND home_id=:home AND subject_id=:sub
                    ORDER BY changed_at DESC, id DESC
                    LIMIT :lim
                    """
                ),
                {
                    "org": scope.org_id,
                    "home": scope.home_id,
                    "sub": scope.subject_id,
                    "lim": limit,
                },
            )
            .mappings()
            .all()
        )

        out: list[AuditEventOut] = []
        for r in rows:
            out.append(
                AuditEventOut(
                    id=int(r["id"]),
                    action=str(r["action"]),
                    changed_at=_iso(r.get("changed_at")),
                    actor=r.get("actor"),
                    prev=r.get("prev"),
                    next=r.get("next"),
                )
            )
        return out
    finally:
        db.close()
