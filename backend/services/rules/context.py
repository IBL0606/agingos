from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class RuleContext:
    """
    Immutable context passed to rules.

    Contract:
    - Deterministic: rules must not call implicit "now"; use ctx.now.
    - Side-effect free: rules may read DB via ctx.session, but must not write.
    """

    session: Session
    since: datetime
    until: datetime
    now: datetime
    params: Mapping[str, Any]
