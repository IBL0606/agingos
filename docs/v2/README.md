# docs/v2 (canonical)

## Status-policy
All docs in this folder MUST have a status header:

- **ACTIVE**: current canonical documentation for how to operate/test/run the system.
- **DRAFT**: incomplete, under construction, not yet canonical.
- **OBSOLETE**: kept only for historical reference; not to be used for operations.

Rule: If a statement is not proven by evidence, it MUST be labeled **NO_EVIDENCE** or **HYPOTHESIS** until evidence exists.

## Scope separation
- **Devbox** = laptop repo at `~/dev/agingos` using Docker Desktop.
- **Pilot/Prod (MiniPC)** = read-only evidence capture only, and ONLY when explicitly decided.

This Phase 4 fixpack is **Devbox-only**.
