#!/usr/bin/env bash
set -euo pipefail

# Run backend tests inside container with correct PYTHONPATH
# Usage:
#   tools/pytest_backend.sh                     # run all tests
#   tools/pytest_backend.sh tests/test_x.py -q  # run subset

docker exec -i agingos-backend-1 bash -lc "
set -euo pipefail
cd /app
PYTHONPATH=/app pytest \$@
"
