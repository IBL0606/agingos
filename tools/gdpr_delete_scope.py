#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import secrets
import subprocess
from pathlib import Path
from typing import Any, Dict

DB_CONTAINER = os.environ.get("AGINGOS_DB_CONTAINER", "agingos-db-1")
DB_USER = os.environ.get("AGINGOS_DB_USER", "agingos")
DB_NAME = os.environ.get("AGINGOS_DB_NAME", "agingos")


def psql_scalar(sql: str) -> str:
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


def gdpr_report(
    org_id: str, home_id: str, subject_id: str, dry_run: bool
) -> Dict[str, Any]:
    sql = (
        "SELECT public.gdpr_delete_scope("
        f"'{org_id}','{home_id}','{subject_id}',"
        f"{'true' if dry_run else 'false'}"
        ");"
    )
    out = psql_scalar(sql)
    return json.loads(out) if out else {}


def scope_counts(org_id: str, home_id: str, subject_id: str) -> Dict[str, int]:
    sql = f"""
    WITH x AS (
      SELECT 'events'::text AS t, COUNT(*)::bigint AS n
        FROM public.events WHERE org_id='{org_id}' AND home_id='{home_id}' AND subject_id='{subject_id}'
      UNION ALL
      SELECT 'episodes', COUNT(*) FROM public.episodes WHERE org_id='{org_id}' AND home_id='{home_id}' AND subject_id='{subject_id}'
      UNION ALL
      SELECT 'episodes_svc', COUNT(*) FROM public.episodes_svc WHERE org_id='{org_id}' AND home_id='{home_id}' AND subject_id='{subject_id}'
      UNION ALL
      SELECT 'anomaly_episodes', COUNT(*) FROM public.anomaly_episodes WHERE org_id='{org_id}' AND home_id='{home_id}' AND subject_id='{subject_id}'
      UNION ALL
      SELECT 'deviations', COUNT(*) FROM public.deviations WHERE org_id='{org_id}' AND home_id='{home_id}' AND subject_id='{subject_id}'
      UNION ALL
      SELECT 'proposals', COUNT(*) FROM public.proposals WHERE org_id='{org_id}' AND home_id='{home_id}' AND subject_id='{subject_id}'
      UNION ALL
      SELECT 'baseline_room_bucket', COUNT(*) FROM public.baseline_room_bucket WHERE org_id='{org_id}' AND home_id='{home_id}' AND subject_id='{subject_id}'
      UNION ALL
      SELECT 'baseline_transition', COUNT(*) FROM public.baseline_transition WHERE org_id='{org_id}' AND home_id='{home_id}' AND subject_id='{subject_id}'
      UNION ALL
      SELECT 'baseline_model_status', COUNT(*) FROM public.baseline_model_status WHERE org_id='{org_id}' AND home_id='{home_id}' AND subject_id='{subject_id}'
      UNION ALL
      SELECT 'subjects', COUNT(*) FROM public.subjects WHERE org_id='{org_id}' AND home_id='{home_id}' AND subject_id='{subject_id}'
    )
    SELECT t || '=' || n FROM x ORDER BY t;
    """
    out = psql_scalar(sql)
    counts: Dict[str, int] = {}
    if out:
        for line in out.splitlines():
            k, v = line.split("=")
            counts[k] = int(v)
    return counts


def vacuum_analyze_tables():
    sql = """
    VACUUM (ANALYZE) public.events;
    VACUUM (ANALYZE) public.episodes;
    VACUUM (ANALYZE) public.episodes_svc;
    VACUUM (ANALYZE) public.anomaly_episodes;
    VACUUM (ANALYZE) public.deviations;
    VACUUM (ANALYZE) public.proposals;
    VACUUM (ANALYZE) public.proposal_actions;
    VACUUM (ANALYZE) public.baseline_room_bucket;
    VACUUM (ANALYZE) public.baseline_transition;
    VACUUM (ANALYZE) public.baseline_model_status;
    VACUUM (ANALYZE) public.notification_outbox;
    VACUUM (ANALYZE) public.notification_deliveries;
    """
    _ = psql_scalar(sql)


def token_file_path(org_id: str, home_id: str, subject_id: str) -> Path:
    safe = f"{org_id}__{home_id}__{subject_id}".replace("/", "_")
    return Path(f"/tmp/agingos_gdpr_token_salt__{safe}")


def compute_token(
    org_id: str, home_id: str, subject_id: str, report: Dict[str, Any], salt: str
) -> str:
    body = json.dumps(report, sort_keys=True, separators=(",", ":"))
    raw = f"{org_id}|{home_id}|{subject_id}|{salt}|{body}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser(
        description="Pilot-safe GDPR delete scope wrapper for AgingOS"
    )
    ap.add_argument("--org-id", required=True)
    ap.add_argument("--home-id", required=True)
    ap.add_argument("--subject-id", required=True)
    ap.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete. Without this, only dry-run.",
    )
    ap.add_argument(
        "--confirm-token",
        default="",
        help="Required when using --execute. From latest dry-run.",
    )
    ap.add_argument(
        "--vacuum-analyze",
        action="store_true",
        help="Run VACUUM(ANALYZE) after execute.",
    )
    ap.add_argument(
        "--reset-token",
        action="store_true",
        help="Reset token salt file for this scope (dry-run only).",
    )
    args = ap.parse_args()

    # Always do dry-run first
    dry = gdpr_report(args.org_id, args.home_id, args.subject_id, True)

    tf = token_file_path(args.org_id, args.home_id, args.subject_id)
    if args.reset_token and tf.exists():
        tf.unlink()

    if not tf.exists():
        tf.write_text(secrets.token_urlsafe(18))

    salt = tf.read_text().strip()
    token = compute_token(args.org_id, args.home_id, args.subject_id, dry, salt)

    print(
        json.dumps(
            {
                "mode": "dry-run",
                "org_id": args.org_id,
                "home_id": args.home_id,
                "subject_id": args.subject_id,
                "report": dry,
                "confirm_token": token,
                "token_file": str(tf),
            },
            indent=2,
        )
    )

    if not args.execute:
        return

    if not args.confirm_token or args.confirm_token != token:
        raise SystemExit(
            "REFUSING: --execute requires --confirm-token matching the latest dry-run token for this scope."
        )

    executed = gdpr_report(args.org_id, args.home_id, args.subject_id, False)
    post = scope_counts(args.org_id, args.home_id, args.subject_id)

    print(
        json.dumps(
            {
                "mode": "executed",
                "org_id": args.org_id,
                "home_id": args.home_id,
                "subject_id": args.subject_id,
                "report": executed,
                "post_counts": post,
            },
            indent=2,
        )
    )

    if args.vacuum_analyze:
        vacuum_analyze_tables()
        print(json.dumps({"vacuum_analyze": "done"}, indent=2))


if __name__ == "__main__":
    main()
