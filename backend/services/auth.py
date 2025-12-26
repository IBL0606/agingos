from __future__ import annotations

import os

from fastapi import Header, HTTPException, status


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
        raise RuntimeError("AGINGOS_API_KEYS must be set when AGINGOS_AUTH_MODE=api_key")

    if not x_api_key or x_api_key not in keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )


def validate_auth_config_on_startup() -> None:
    """Fail fast on invalid auth configuration."""
    mode = _auth_mode()
    if mode == "api_key" and not _api_keys():
        raise RuntimeError("AGINGOS_API_KEYS must be set when AGINGOS_AUTH_MODE=api_key")
