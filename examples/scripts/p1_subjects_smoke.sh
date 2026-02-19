#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
KEY_A="${KEY_A:-dev-key-3}"
KEY_B="${KEY_B:-dev-key-subject-b-7N33iSrSa1y9tGtfvjwTRNytEEmDt6TO}"

j(){ python3 -m json.tool; }

echo "== P1-1 multi-subject smoke =="
echo "BASE_URL=$BASE_URL"

echo "[1/5] POST /subject_state/compute_once (as A)"
curl -sS -X POST "$BASE_URL/subject_state/compute_once?window_minutes=60" -H "X-API-Key: $KEY_A" | j >/tmp/p1_compute.json

echo "[2/5] GET /subject_state (A) scope isolation"
curl -sS "$BASE_URL/subject_state" -H "X-API-Key: $KEY_A" | j >/tmp/p1_state_a.json

echo "[3/5] GET /subject_state (B) scope isolation"
curl -sS "$BASE_URL/subject_state" -H "X-API-Key: $KEY_B" | j >/tmp/p1_state_b.json

A_SUB="$(python3 - <<'PY'
import json
print(json.load(open("/tmp/p1_state_a.json"))["subject_id"])
PY
)"
B_SUB="$(python3 - <<'PY'
import json
print(json.load(open("/tmp/p1_state_b.json"))["subject_id"])
PY
)"

echo "A_SUB=$A_SUB"
echo "B_SUB=$B_SUB"

echo "[4/5] Assert A != B"
python3 - <<'PY'
import json
a=json.load(open("/tmp/p1_state_a.json"))
b=json.load(open("/tmp/p1_state_b.json"))
assert a["subject_id"]!=b["subject_id"], "A and B subject_id must differ"
print("OK")
PY

echo "[5/5] Assert no leakage (each response subject_id matches its key scope expectation)"
# We can only assert inequality + presence of required fields; actual UUIDs are environment-dependent.
python3 - <<'PY'
import json
a=json.load(open("/tmp/p1_state_a.json"))
b=json.load(open("/tmp/p1_state_b.json"))
for x in (a,b):
    for k in ("org_id","home_id","subject_id","state"):
        assert k in x, f"missing {k}"
print("OK")
PY

echo "== OK =="
