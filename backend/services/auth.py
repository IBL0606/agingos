from __future__ import annotations

import os
from dataclasses import dataclass
import hashlib

from fastapi import Header, HTTPException, status
from sqlalchemy import text
from db import SessionLocal


def _auth_mode() -> str:
    return os.getenv("AGINGOS_AUTH_MODE", "off").strip().lower()


def _api_keys() -> set[str]:
    raw = os.getenv("AGINGOS_API_KEYS", "").strip()
    if not raw:
        return set()
    return {x.strip() for x in raw.split(",") if x.strip()}


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """
    Minimal API protection for field pilot.

    Behavior:
    - AGINGOS_AUTH_MODE=off  -> allow all
    - AGINGOS_AUTH_MODE=api_key -> require X-API-Key to match one of AGINGOS_API_KEYS
    """
    mode = _auth_mode()
    if mode == "off":
        return
    if mode != "api_key":
        raise RuntimeError(f"Unknown AGINGOS_AUTH_MODE: {mode!r}")

    keys = _api_keys()
    if not keys:
        raise RuntimeError(
            "AGINGOS_API_KEYS must be set when AGINGOS_AUTH_MODE=api_key"
        )

    if not x_api_key or x_api_key not in keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )


def validate_auth_config_on_startup() -> None:
    """Fail fast on invalid auth configuration."""
    mode = _auth_mode()
    if mode == "api_key" and not _api_keys():
        raise RuntimeError(
            "AGINGOS_API_KEYS must be set when AGINGOS_AUTH_MODE=api_key"
        )


# -------------------------
# Tenant scope (P0-2, minimal)
# -------------------------


@dataclass(frozen=True)
class AuthScope:
    org_id: str
    home_id: str
    subject_id: str
    role: str
    api_key_hash: str
    user_id: str | None


def _sha256_hex(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


def _lookup_scope_by_api_key(x_api_key: str) -> AuthScope | None:
    # Hash key in app layer; DB stores only hash.
    h = _sha256_hex(x_api_key)
    db = SessionLocal()
    try:
        row = (
            db.execute(
                text(
                    """
                SELECT org_id, home_id, subject_id, role, api_key_hash, user_id
                FROM api_key_scopes
                WHERE api_key_hash = :h AND active = true
                """
                ),
                {"h": h},
            )
            .mappings()
            .one_or_none()
        )
        if not row:
            return None
        return AuthScope(
            org_id=row["org_id"],
            home_id=row["home_id"],
            subject_id=row["subject_id"],
            role=row["role"],
            api_key_hash=row["api_key_hash"],
            user_id=str(row["user_id"]) if row.get("user_id") is not None else None,
        )
    finally:
        db.close()


def require_scope(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> AuthScope:
    """
    Auth dependency that returns tenant scope.

    Policy (controlled transition):
    - Still enforces allow/deny like require_api_key.
    - Additionally requires the key to have an ACTIVE row in api_key_scopes.
      (We can later relax this for bootstrap if needed, but default is strict.)
    """
    # First: reuse existing allow/deny rules (mode + AGINGOS_API_KEYS)
    require_api_key(x_api_key)

    # Second: require DB scope mapping
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )

    scope = _lookup_scope_by_api_key(x_api_key)
    if not scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: API key has no active scope mapping",
        )
    return scope
