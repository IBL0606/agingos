# Fixpack-5 MUST-3 schema reconcile patch (minimal)

Purpose:
- Align DB schema with runtime expectations used by weekly report sources:
  - `/anomalies?last=7d`
  - `/proposals?limit=500`

What migration adds (additive only):
- `proposals.home_id` (backfilled `'default'`, set NOT NULL, default `'default'`)
- Missing `anomaly_episodes` lifecycle/scope columns used by ORM model
  - includes `start_bucket`, `last_bucket`, `peak_bucket`, scope columns, and counters

Verification done in this environment:
- `python3 -m compileall backend` PASS
- `DATABASE_URL=... alembic upgrade head --sql` PASS (SQL render), excerpt saved in `61_migration_sql_render_excerpt.sql`

NO_EVIDENCE/runtime:
- Live dev DB migration apply + endpoint GET verification (`/anomalies`, `/proposals`) could not be executed here (no docker/runtime DB access in this container).
