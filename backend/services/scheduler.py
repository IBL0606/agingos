from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from services.rule_engine import run_rules

scheduler = BackgroundScheduler()


def run_rule_engine_job():
    run_rules()

    
def setup_scheduler():
    scheduler.add_job(
        run_rule_engine_job,
        trigger=IntervalTrigger(minutes=1),
        id="rule_engine_job",
        replace_existing=True,
    )