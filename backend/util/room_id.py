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
    Deterministic room_id derivation:
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
