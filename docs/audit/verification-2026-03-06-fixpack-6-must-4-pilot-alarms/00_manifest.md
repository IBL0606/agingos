# verification-2026-03-06-fixpack-6-must-4-pilot-alarms MANIFEST

Scope: MUST-4 pilot alarm system only (dev/repo truth).

Status in this container:
- Repo proof: AVAILABLE
- Runtime API/DB proof: NO_EVIDENCE (depends on local docker/runtime)

Checks covered:
- CHECK-RULES-01: explicit pilot rule pack structure + truth-source mapping
- CHECK-RULES-02: quiet/override/anti-spam semantics from existing policy+worker code
- CHECK-RULES-03: ACK/CLOSE lifecycle path and executable command plan
