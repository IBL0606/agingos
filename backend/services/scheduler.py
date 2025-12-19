from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from services.rule_engine import run_rules
from db import SessionLocal
from config.rule_config import load_rule_config

scheduler = BackgroundScheduler()


def run_rule_engine_job():
    db = SessionLocal()
    try:
        run_rules(db)
    finally:
        db.close()


def setup_scheduler():
    cfg = load_rule_config()
    interval_minutes = cfg.scheduler_interval_minutes()

    scheduler.add_job(
        run_rule_engine_job,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="rule_engine_job",
        replace_existing=True,
    )
