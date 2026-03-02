# AS-IS Evidence Pack (2026-03-01)

This evidence pack captures the current state **without functional changes**.

## Scope
- Repository state: branch, latest commit, HEAD SHA.
- Runtime/container state: `docker compose ps`, backend/console/db logs.
- Health endpoints: `/health`, `/health/detail`, console proxy `/api/health`.
- Environment inventory: key names only (no values) and compose profiles in use.
- Test attempts and raw failure outputs.

## Status Summary

### ✅ OK
- Evidence collection directory and files were created under `docs/audit/as-is-2026-03-01/`.
- Git metadata commands executed and produced outputs:
  - `git status -sb` → `git-status-sb.txt`
  - `git log -1` → `git-log-1.txt`
  - `git rev-parse HEAD` → `git-rev-parse-head.txt`

### ⚠️ DEGRADED
- Docker/Compose commands are unavailable in this environment (`bash: command not found: docker`), so compose process state and service logs could not be collected from a running stack:
  - `docker-compose-ps.txt`
  - `docker-compose-logs-backend.txt`
  - `docker-compose-logs-console.txt`
  - `docker-compose-logs-db.txt`
  - `compose-profiles.txt`
- Health endpoint checks to `localhost` failed with connection errors (`curl: (7) Failed to connect ...`):
  - `curl-health.txt`
  - `curl-health-detail.txt`
  - `curl-console-proxy-api-health.txt`

### ❌ BROKEN
- Backend pytest invocation fails during collection due to missing Python import path/module resolution (`ModuleNotFoundError: No module named 'services'`):
  - `test-pytest-q-backend-tests.txt`
- Scripted backend pytest helper fails because Docker is unavailable (`tools/pytest_backend.sh: line 9: docker: command not found`):
  - `test-tools-pytest_backend-sh.txt`

## Captured Artifacts
- `git-status-sb.txt`
- `git-log-1.txt`
- `git-rev-parse-head.txt`
- `docker-compose-ps.txt`
- `docker-compose-logs-backend.txt`
- `docker-compose-logs-console.txt`
- `docker-compose-logs-db.txt`
- `curl-health.txt`
- `curl-health-detail.txt`
- `curl-console-proxy-api-health.txt`
- `env-keys.txt`
- `compose-profiles.txt`
- `test-pytest-q-backend-tests.txt`
- `test-tools-pytest_backend-sh.txt`
