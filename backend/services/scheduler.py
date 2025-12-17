# backend/services/scheduler.py

from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from db import SessionLocal
from config import DEFAULT_LOOKBACK_MINUTES, DEFAULT_EXPIRE_AFTER_MINUTES
from services.deviation_store_v1 import upsert_deviations_v1, close_stale_deviations_v1
from services.rules.r001 import eval_r001_no_motion
from services.rules.r002 import eval_r002_front_door_open_at_night
from services.rules.r003 import eval_r003_front_door_open_no_motion_after

scheduler = BackgroundScheduler()

RULE_IDS = ["R-002", "R-003"]
DEFAULT_SUBJECT_KEY = "default"


def _compute_deviations(db, since, until):
    now = datetime.now(timezone.utc)
    devs = []
    devs += eval_r002_front_door_open_at_night(db, since=since, until=until, now=now)
    devs += eval_r003_front_door_open_no_motion_after(db, since=since, until=until, now=now)
    return devs


def run_persist_job():
    """
    Periodisk jobb:
      - Evaluerer siste N minutter (DEFAULT_LOOKBACK_MINUTES)
      - Upserter deviations_v1
      - Lukker stale avvik (DEFAULT_EXPIRE_AFTER_MINUTES)
    """
    until = datetime.now(timezone.utc)
    since = until - timedelta(minutes=DEFAULT_LOOKBACK_MINUTES)

    db = SessionLocal()
    try:
        devs = _compute_deviations(db=db, since=since, until=until)

        now_db = datetime.utcnow()  # naive UTC for DB-felter (timestamp without time zone)

        result, seen_keys = upsert_deviations_v1(
            db=db,
            deviations=devs,
            subject_key=DEFAULT_SUBJECT_KEY,
            now=now_db,
        )

        closed = close_stale_deviations_v1(
            db=db,
            subject_key=DEFAULT_SUBJECT_KEY,
            rule_ids=RULE_IDS,
            seen_keys=seen_keys,
            now=now_db,
            expire_after_minutes=DEFAULT_EXPIRE_AFTER_MINUTES,
        )

        db.commit()

        # (valgfritt) minimal logg – kan fjernes hvis dere vil ha helt stille scheduler
        print(
            f"[scheduler] persist window [{since.isoformat()} .. {until.isoformat()}): "
            f"created={result.created} updated={result.updated} reopened={result.reopened} closed={closed}"
        )
    finally:
        db.close()


def setup_scheduler():
    # Unngå duplikat-jobb ved reload
    if scheduler.get_job("persist_deviations_v1") is None:
        scheduler.add_job(
            run_persist_job,
            trigger=IntervalTrigger(minutes=1),
            id="persist_deviations_v1",
            name="Persist deviations v1",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
