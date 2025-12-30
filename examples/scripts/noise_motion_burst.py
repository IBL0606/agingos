#!/usr/bin/env python3
import argparse
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import requests


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def auth_headers() -> dict:
    api_key = os.getenv("AGINGOS_API_KEY", "")
    return {"X-API-Key": api_key} if api_key else {}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Post many motion events to test throughput/logging."
    )
    ap.add_argument(
        "--base-url", default=os.getenv("BASE_URL", "http://localhost:8000")
    )
    ap.add_argument("--rate", type=float, default=20.0, help="events per second")
    ap.add_argument("--seconds", type=int, default=30)
    ap.add_argument("--room", default="gang")
    ap.add_argument("--entity-id", default="binary_sensor.noise_test_motion")
    ap.add_argument("--timeout", type=int, default=10)
    args = ap.parse_args()

    if args.rate <= 0:
        print("rate must be > 0")
        return 2

    total = int(args.rate * args.seconds)
    sleep_s = 1.0 / args.rate

    sess = requests.Session()
    url = args.base_url.rstrip("/") + "/event"

    ok = 0
    fail = 0
    lat_ms = []

    start_ts = datetime.now(timezone.utc)

    t0 = time.perf_counter()
    for i in range(total):
        ev = {
            "id": str(uuid.uuid4()),
            # spread timestamps slightly to avoid identical-ts edge cases
            "timestamp": iso_z(start_ts + timedelta(milliseconds=i)),
            "category": "motion",
            "payload": {
                "state": "on",
                "room": args.room,
                "source": "noise_test",
                "entity_id": args.entity_id,
            },
        }

        r0 = time.perf_counter()
        try:
            resp = sess.post(url, json=ev, headers=auth_headers(), timeout=args.timeout)
            dt = (time.perf_counter() - r0) * 1000
            lat_ms.append(dt)
            if resp.status_code < 400:
                ok += 1
            else:
                fail += 1
        except Exception:
            fail += 1

        time.sleep(sleep_s)

    elapsed = time.perf_counter() - t0

    lat_ms_sorted = sorted(lat_ms)

    def pct(p: float) -> float:
        if not lat_ms_sorted:
            return float("nan")
        idx = int(round((len(lat_ms_sorted) - 1) * p))
        return lat_ms_sorted[idx]

    print("=== noise_motion_burst result ===")
    print(f"base_url:        {args.base_url}")
    print(f"target_rate_eps: {args.rate}")
    print(f"duration_s:      {args.seconds}")
    print(f"attempted:       {total}")
    print(f"ok:              {ok}")
    print(f"fail:            {fail}")
    print(f"elapsed_s:       {elapsed:.2f}")
    print(f"latency_ms_p50:  {pct(0.50):.1f}")
    print(f"latency_ms_p95:  {pct(0.95):.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
