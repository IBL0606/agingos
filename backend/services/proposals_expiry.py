from __future__ import annotations

import traceback
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from db import SessionLocal
from util.time import utcnow


def expire_testing_proposals(db: Session, *, now: datetime | None = None) -> dict[str, Any]:
    """
    Policy (MVP, consistent):
      - If proposal.state == TESTING and test_until < now:
          transition to NEW
          clear test_started_at/test_until
          append proposal_actions row with action='EXPIRE', prev_state='TESTING', new_state='NEW'
      - No auto-activate.
    """
    now = now or utcnow()

    # Lock candidates to avoid races with UI actions
    rows = db.execute(
        text(
            """
            SELECT proposal_id
            FROM proposals
            WHERE state = 'TESTING'
              AND test_until IS NOT NULL
              AND test_until < :now
            ORDER BY test_until ASC
            FOR UPDATE
            """
        ),
        {"now": now},
    ).mappings().all()

    expired = 0
    for r in rows:
        pid = int(r["proposal_id"])

        # Re-check under lock (defensive)
        cur = db.execute(
            text("SELECT proposal_id, state FROM proposals WHERE proposal_id=:id FOR UPDATE"),
            {"id": pid},
        ).mappings().one_or_none()
        if not cur or cur["state"] != "TESTING":
            continue

        # Apply state change
        db.execute(
            text(
                """
                UPDATE proposals
                SET state = 'NEW',
                    test_started_at = NULL,
                    test_until = NULL,
                    last_actor = NULL,
                    last_source = 'system',
                    last_note = 'test expired -> NEW'
                WHERE proposal_id = :id
                """
            ),
            {"id": pid},
        )

        # Audit trail
        db.execute(
            text(
                """
                INSERT INTO proposal_actions (
                  proposal_id, action, prev_state, new_state,
                  actor, source, note, payload
                )
                VALUES (
                  :proposal_id, 'EXPIRE', 'TESTING', 'NEW',
                  NULL, 'system', 'test expired -> NEW', '{}'::jsonb
                )
                """
            ),
            {"proposal_id": pid},
        )

        expired += 1

    return {"ts": now.isoformat().replace("+00:00", "Z"), "expired": expired}


def run_proposals_expiry_job() -> None:
    db = SessionLocal()
    try:
        with db.begin():
            expire_testing_proposals(db)
    except Exception:
        # fail-safe: do not crash scheduler
        traceback.print_exc()
    finally:
        db.close()
