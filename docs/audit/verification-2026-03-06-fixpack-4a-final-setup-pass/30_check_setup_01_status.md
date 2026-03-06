# CHECK-SETUP-01 status after final follow-up

Status in this container: NO_EVIDENCE (runtime Docker unavailable).

Root cause:
- `docker: command not found`.

Repo truth now includes deterministic in-repo baseline builder function path:
- `public.run_baseline_nightly(...)`
- helper functions: `_baseline_resolve_scope_from_user`, `build_daily_room_bucket_rollup`, `build_daily_transition_rollup`, `build_baseline_7d`.

Expected PASS path on dev laptop is documented in `docs/v2/SETUP_TRUTH.md`.
