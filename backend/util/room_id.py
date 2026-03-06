from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional


_ROOM_MAP_CACHE: Optional[dict[str, str]] = None


def _load_room_map() -> dict[str, str]:
    """
    Best-effort loader for backend/config/room_map.yaml.
    Returns {} if file missing or invalid.
    """
    global _ROOM_MAP_CACHE
    if _ROOM_MAP_CACHE is not None:
        return _ROOM_MAP_CACHE

    path = Path(__file__).resolve().parents[1] / "config" / "room_map.yaml"
    try:
        import yaml  # type: ignore
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
        if isinstance(raw, dict):
            _ROOM_MAP_CACHE = {str(k): str(v) for k, v in raw.items() if k is not None and v is not None}
        else:
            _ROOM_MAP_CACHE = {}
    except Exception:
        _ROOM_MAP_CACHE = {}

    return _ROOM_MAP_CACHE


def derive_room_id(payload: Mapping[str, Any]) -> Optional[str]:
    """
    Deterministic room_id derivation (payload-only):
      1) payload.room_id
      2) payload.room
      3) payload.area
      4) room_map[entity_id] fallback

    Returns trimmed string or None.
    """
    def _norm(v: Any) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    for key in ("room_id", "room", "area"):
        v = _norm(payload.get(key))
        if v:
            return v

    entity_id = _norm(payload.get("entity_id"))
    if entity_id:
        rm = _load_room_map()
        v = _norm(rm.get(entity_id))
        if v:
            return v

    return None


def derive_room_id_scoped(db: Any, scope: Any, payload: Mapping[str, Any]) -> Optional[str]:
    """
    Deterministic room_id derivation (DB + scope aware) for Fixpack-3.

    Order:
      1) payload.room_id (must exist in rooms for scope)
      2) payload.room or payload.area (match rooms.display_name case-insensitive)
      3) sensor_room_map lookup by payload.entity_id (active=true)
      4) fallback to derive_room_id(payload) (payload-only + yaml)

    Returns room_id or None.
    """
    from sqlalchemy import text  # imported here to avoid hard dependency for pure utility usage

    def _norm(v: Any) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    org_id = getattr(scope, "org_id", None)
    home_id = getattr(scope, "home_id", None)
    if not org_id or not home_id:
        # Can't scope safely → fallback to payload-only
        return derive_room_id(payload)

    params_base = {"org_id": org_id, "home_id": home_id}

    # 1) payload.room_id (validate exists)
    rid = _norm(payload.get("room_id"))
    if rid:
        r = db.execute(
            text(
                """
                SELECT 1
                FROM public.rooms
                WHERE org_id=:org_id AND home_id=:home_id AND room_id=:room_id
                LIMIT 1
                """
            ),
            {**params_base, "room_id": rid},
        ).scalar()
        if r is not None:
            return rid

    # 2) payload.room / payload.area → match display_name
    name = _norm(payload.get("room")) or _norm(payload.get("area"))
    if name:
        rid2 = db.execute(
            text(
                """
                SELECT room_id
                FROM public.rooms
                WHERE org_id=:org_id AND home_id=:home_id
                  AND lower(display_name) = lower(:display_name)
                ORDER BY room_id
                LIMIT 1
                """
            ),
            {**params_base, "display_name": name},
        ).scalar()
        if rid2:
            return str(rid2)

    # 3) entity_id mapping
    entity_id = _norm(payload.get("entity_id"))
    if entity_id:
        rid3 = db.execute(
            text(
                """
                SELECT room_id
                FROM public.sensor_room_map
                WHERE org_id=:org_id AND home_id=:home_id
                  AND entity_id=:entity_id AND active=true
                LIMIT 1
                """
            ),
            {**params_base, "entity_id": entity_id},
        ).scalar()
        if rid3:
            return str(rid3)

    # 4) fallback (payload-only + yaml)
    return derive_room_id(payload)
