# PILOT RUNBOOK (DRAFT)

Status: **DRAFT**

## Intent
Operational checklist for a pilot environment.

NOTE: In this fixpack we do **Devbox-only** work. This runbook is a skeleton only.

## Daily (read-only)
- Check `/health/detail` overall_status and ingest lag.
- Check ingest freshness per category (presence/door/ha_snapshot).
- Check room_id completeness for presence/door.
- Check baseline status/freshness.
- Check anomalies runner status.
- Check deviations/proposals/notifications queues (read-only).

NO_EVIDENCE: exact commands/locations will be finalized after audit-capture exists for Devbox.
