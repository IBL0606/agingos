#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlencode

import requests
import yaml


@dataclass
class Scenario:
    id: str
    description: str
    events: List[Dict[str, Any]]
    evaluate: Dict[str, Any]
    expect: Dict[str, Any]
    path: Path


def _load_scenario(path: Path) -> Scenario:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        data = yaml.safe_load(raw)
    elif path.suffix.lower() == ".json":
        data = json.loads(raw)
    else:
        raise ValueError(
            f"Unsupported scenario extension: {path.suffix} (use .yaml/.yml/.json)"
        )

    for k in ("id", "events", "evaluate", "expect"):
        if k not in data:
            raise ValueError(f"Scenario missing required field '{k}' in {path}")

    return Scenario(
        id=str(data["id"]),
        description=str(data.get("description", "")),
        events=list(data["events"]),
        evaluate=dict(data["evaluate"]),
        expect=dict(data["expect"]),
        path=path,
    )


def _run_reset(make_target: str) -> None:
    # Uses Makefile target; keeps reset logic in one place.
    res = subprocess.run(["make", make_target], capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(
            f"DB reset failed (make {make_target}).\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
        )


def _iso(dt_str: str) -> str:
    # Keep as string; API already validates UTC-aware. This is only for sanity checks / printing.
    return dt_str


def _auth_headers() -> Dict[str, str]:
    api_key = os.getenv("AGINGOS_API_KEY", "")
    return {"X-API-Key": api_key} if api_key else {}


def _post_event(base_url: str, ev: Dict[str, Any], timeout_s: int) -> None:
    url = f"{base_url.rstrip('/')}/event"
    r = requests.post(url, json=ev, headers=_auth_headers(), timeout=timeout_s)
    if r.status_code >= 400:
        raise RuntimeError(
            f"POST /event failed ({r.status_code}): {r.text}\nEvent: {json.dumps(ev, ensure_ascii=False)}"
        )


def _get_deviations(
    base_url: str, since: str, until: str, timeout_s: int
) -> List[Dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/deviations/evaluate"
    params = {"since": since, "until": until}
    r = requests.get(url, params=params, headers=_auth_headers(), timeout=timeout_s)
    if r.status_code >= 400:
        raise RuntimeError(
            f"GET /deviations/evaluate failed ({r.status_code}): {r.text}\n"
            f"URL: {url}?{urlencode(params)}"
        )
    return r.json()


def _subset(sub: List[str], sup: List[str]) -> bool:
    sup_set = set(sup)
    return all(x in sup_set for x in sub)


def _match_expected_to_actual(
    exp: Dict[str, Any], act: Dict[str, Any]
) -> Tuple[bool, str]:
    # Required: rule_id exact
    if str(exp.get("rule_id")) != str(act.get("rule_id")):
        return False, "rule_id mismatch"

    # Optional exacts
    if "severity" in exp and str(exp["severity"]) != str(act.get("severity")):
        return False, "severity mismatch"
    if "title" in exp and str(exp["title"]) != str(act.get("title")):
        return False, "title mismatch"

    # Optional contains
    if "explanation_contains" in exp:
        needle = str(exp["explanation_contains"])
        hay = str(act.get("explanation", ""))
        if needle not in hay:
            return False, "explanation_contains not found"

    # Evidence subset
    if "evidence_contains" in exp:
        exp_evs = [str(x) for x in exp["evidence_contains"]]
        act_evs = [str(x) for x in (act.get("evidence") or [])]
        if not _subset(exp_evs, act_evs):
            return False, "evidence_contains not satisfied"

    # Window exact match if specified
    if "window" in exp:
        ew = exp["window"] or {}
        aw = act.get("window") or {}
        if "since" in ew and str(ew["since"]) != str(aw.get("since")):
            return False, "window.since mismatch"
        if "until" in ew and str(ew["until"]) != str(aw.get("until")):
            return False, "window.until mismatch"

    return True, "ok"


def _evaluate_expectations(
    scenario: Scenario, actual: List[Dict[str, Any]]
) -> Tuple[bool, List[str]]:
    exp_block = scenario.expect
    pass_condition = exp_block.get("pass_condition", "contains")
    expected_list = exp_block.get("deviations") or []

    if pass_condition not in ("contains", "exact"):
        return False, [
            f"Invalid pass_condition={pass_condition!r} (use 'contains' or 'exact')"
        ]

    # Greedy matching: for each expected, find one unmatched actual that matches.
    unmatched_actual_idx = set(range(len(actual)))
    errors: List[str] = []
    matched_pairs: List[Tuple[int, int]] = []

    for ei, exp in enumerate(expected_list):
        found = False
        for ai in list(unmatched_actual_idx):
            ok, _reason = _match_expected_to_actual(exp, actual[ai])
            if ok:
                unmatched_actual_idx.remove(ai)
                matched_pairs.append((ei, ai))
                found = True
                break
        if not found:
            errors.append(
                f"Expected deviation #{ei} not found: {json.dumps(exp, ensure_ascii=False)}"
            )

    if errors:
        return False, errors

    if pass_condition == "exact":
        # No extra actual deviations allowed
        if unmatched_actual_idx:
            extras = [actual[i] for i in sorted(unmatched_actual_idx)]
            errors.append(
                f"Exact match failed: extra deviations returned: {json.dumps(extras, ensure_ascii=False)}"
            )
            return False, errors

    return True, []


def _fail_report(
    scenario: Scenario,
    base_url: str,
    since: str,
    until: str,
    actual: List[Dict[str, Any]],
    errors: List[str],
) -> str:
    lines = []
    lines.append(f"SCENARIO FAIL: {scenario.id}")
    if scenario.description:
        lines.append(f"Description: {scenario.description}")
    lines.append(f"File: {scenario.path}")
    lines.append("")
    lines.append("Reasons:")
    for e in errors:
        lines.append(f"- {e}")
    lines.append("")
    lines.append("Actual deviations:")
    lines.append(json.dumps(actual, indent=2, ensure_ascii=False))
    lines.append("")
    lines.append("Repro commands:")
    lines.append(
        f'curl -s "{base_url.rstrip("/")}/deviations/evaluate?since={since}&until={until}" | jq'
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="AgingOS scenario runner (posts events + verifies /deviations/evaluate)"
    )
    ap.add_argument("scenario", help="Path to scenario file (.yaml/.yml/.json)")
    ap.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Backend base URL (default: http://localhost:8000)",
    )
    ap.add_argument(
        "--no-reset", action="store_true", help="Skip DB reset (not recommended)"
    )
    ap.add_argument(
        "--reset-target",
        default="scenario-reset",
        help="Make target to reset DB (default: scenario-reset)",
    )
    ap.add_argument(
        "--timeout", type=int, default=10, help="HTTP timeout seconds (default: 10)"
    )
    args = ap.parse_args()

    scenario_path = Path(args.scenario)
    scenario = _load_scenario(scenario_path)

    if not args.no_reset:
        _run_reset(args.reset_target)

    # Post events
    for ev in scenario.events:
        _post_event(args.base_url, ev, args.timeout)

    since = str(scenario.evaluate.get("since"))
    until = str(scenario.evaluate.get("until"))
    if not since or not until:
        raise ValueError("Scenario.evaluate must include 'since' and 'until'")

    actual = _get_deviations(
        args.base_url, since=since, until=until, timeout_s=args.timeout
    )

    ok, errors = _evaluate_expectations(scenario, actual)
    if not ok:
        print(
            _fail_report(scenario, args.base_url, since, until, actual, errors),
            file=sys.stderr,
        )
        return 2

    print(f"SCENARIO PASS: {scenario.id}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"SCENARIO ERROR: {e}", file=sys.stderr)
        raise
