#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import subprocess
from typing import Dict, List, Tuple

DB_CONTAINER = os.environ.get("AGINGOS_DB_CONTAINER", "agingos-db-1")
DB_USER = os.environ.get("AGINGOS_DB_USER", "agingos")
DB_NAME = os.environ.get("AGINGOS_DB_NAME", "agingos")

TABLES = [
    ("events", "retention_preview_events", "retention_prune_events", 5000),
    ("episodes", "retention_preview_episodes", "retention_prune_episodes", 2000),
    (
        "episodes_svc",
        "retention_preview_episodes_svc",
        "retention_prune_episodes_svc",
        2000,
    ),
    (
        "anomaly_episodes",
        "retention_preview_anomaly_episodes",
        "retention_prune_anomaly_episodes",
        2000,
    ),
    ("deviations", "retention_preview_deviations", "retention_prune_deviations", 2000),
]


def psql(sql: str) -> str:
    cmd = [
        "docker",
        "exec",
        "-i",
        DB_CONTAINER,
        "psql",
        "-U",
        DB_USER,
        "-d",
        DB_NAME,
        "-v",
        "ON_ERROR_STOP=1",
        "-At",
    ]
    p = subprocess.run(
        cmd, input=sql.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode("utf-8"))
    return p.stdout.decode("utf-8").strip()


def get_scopes() -> List[Tuple[str, str, str]]:
    out = psql("""
    SELECT DISTINCT org_id, home_id, subject_id
    FROM public.events
    ORDER BY 1,2,3;
    """)
    scopes = []
    if out:
        for line in out.splitlines():
            org_id, home_id, subject_id = line.split("|")
            scopes.append((org_id, home_id, subject_id))
    return scopes


def iso(ts: dt.datetime) -> str:
    return ts.replace(microsecond=0).isoformat()


def preview(scope: Tuple[str, str, str], before: dt.datetime) -> Dict[str, int]:
    org_id, home_id, subject_id = scope
    result: Dict[str, int] = {}
    for table, fn_preview, _, _limit in TABLES:
        q = f"SELECT public.{fn_preview}('{org_id}','{home_id}','{subject_id}','{iso(before)}'::timestamptz);"
        n = int(psql(q) or "0")
        result[table] = n
    return result


def prune(
    scope: Tuple[str, str, str], before: dt.datetime, execute: bool, max_rounds: int
) -> Dict[str, int]:
    org_id, home_id, subject_id = scope
    totals: Dict[str, int] = {t: 0 for t, _, _, _ in TABLES}
    if not execute:
        return totals

    for table, _prev, fn_prune, limit in TABLES:
        rounds = 0
        while rounds < max_rounds:
            q = f"SELECT public.{fn_prune}('{org_id}','{home_id}','{subject_id}','{iso(before)}'::timestamptz,{limit});"
            n = int(psql(q) or "0")
            totals[table] += n
            rounds += 1
            if n == 0:
                break
    return totals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--days",
        type=int,
        default=180,
        help="Retention window in days (delete older than now - days)",
    )
    ap.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete. Without this flag it's dry-run.",
    )
    ap.add_argument(
        "--max-rounds", type=int, default=200, help="Max batches per table per scope"
    )
    args = ap.parse_args()

    before = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.days)

    scopes = get_scopes()
    report = {
        "before": iso(before),
        "execute": args.execute,
        "scopes": [],
    }

    for scope in scopes:
        prev = preview(scope, before)
        deleted = prune(scope, before, args.execute, args.max_rounds)
        report["scopes"].append(
            {
                "org_id": scope[0],
                "home_id": scope[1],
                "subject_id": scope[2],
                "preview": prev,
                "deleted": deleted,
            }
        )

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
