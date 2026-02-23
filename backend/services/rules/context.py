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
    - Scope-aware: ctx.org_id/home_id/subject_id define the tenant slice.
    """

    session: Session
    since: datetime
    until: datetime
    now: datetime
    params: Mapping[str, Any]

    # scope + subject identity (used for filtering and evidence)
    org_id: str = "default"
    home_id: str = "default"
    subject_id: str = "default"
    subject_key: str = "default"
