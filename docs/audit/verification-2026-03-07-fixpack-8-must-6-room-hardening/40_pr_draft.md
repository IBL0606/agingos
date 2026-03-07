# PR draft — Fixpack-8 MUST-6 room model hardening

## Title
Fixpack-8: MUST-6 room model hardening (truthful room-name variant documentation)

## Summary
- Scope limited to MUST-6 and dev/docs hardening only.
- No re-implementation of Fixpack-3 deterministic room mapping.
- Documented clear boundary between:
  1) generic system/code-path support
  2) real-home tested room-name variants
- Added evidence pack proving current generic logic and explicit NO_EVIDENCE status for specific variants (`bod`, `loft`, `kjellerstue`).

## Claim-set
- CHECK-ROOM-01: REFERENCED (PROVEN by Fixpack-3 baseline).
- CHECK-ROOM-02: NO_EVIDENCE (no direct real-home evidence present in repo for listed variants).

## Risk / follow-up
- To move CHECK-ROOM-02 from NO_EVIDENCE to PASS, add pilot/home evidence capture demonstrating variant inputs and resolved room_id outcomes per home scope.
