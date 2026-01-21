import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

import httpx
from fastapi import FastAPI, Query

app = FastAPI(title="AgingOS AI Bot", version="0.1.0")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso_z(s: str) -> datetime:
    # Accepts "Z" or "+00:00"
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def _night_window_utc(now: datetime) -> tuple[datetime, datetime]:
    """
    Night window interpreted in local time (Europe/Oslo by default) and returned as UTC.

    MVP definition:
    Night is from 22:00 to 07:00 local time (spanning midnight).
    This avoids confusing results for Norwegian users and handles DST via zoneinfo.
    """
    from zoneinfo import ZoneInfo

    tz_name = os.getenv("AGINGOS_TIMEZONE", "Europe/Oslo")
    tz = ZoneInfo(tz_name)

    now_local = now.astimezone(tz)

    # "Last night" window: 22:00 previous local day -> 07:00 current local day
    end_local = now_local.replace(hour=7, minute=0, second=0, microsecond=0)
    start_local = (end_local - timedelta(days=1)).replace(
        hour=22, minute=0, second=0, microsecond=0
    )

    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)



def _agingos_client() -> httpx.Client:
    base = os.getenv("AGINGOS_API_BASE_URL", "http://backend:8000").rstrip("/")
    key = os.getenv("AGINGOS_API_KEY", "").strip()
    headers = {}
    if key:
        headers["X-API-Key"] = key
    return httpx.Client(base_url=base, headers=headers, timeout=5.0)


def _fetch_events(
    since: datetime, until: datetime, limit: int = 1000
) -> list[dict[str, Any]]:
    params = {
        "since": since.isoformat().replace("+00:00", "Z"),
        "until": until.isoformat().replace("+00:00", "Z"),
        "limit": limit,
    }
    with _agingos_client() as client:
        r = client.get("/events", params=params)
        r.raise_for_status()
        return r.json()


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/v1/capabilities")
def capabilities():
    return {
        "bot_version": "0.1.0",
        "schema_version": "v1",
        "features": {"insights": True, "proposals": True, "anomalies": True},
    }


@app.get("/v1/anomalies")
def anomalies(
    since: Optional[str] = Query(default=None),
    until: Optional[str] = Query(default=None),
    window_days: int = Query(default=14, ge=3, le=60),
    min_abs_increase: int = Query(default=10, ge=0, le=5000),
    z_threshold: float = Query(default=2.0, ge=0.0, le=10.0),
    meaningful_recent_floor: int = Query(default=20, ge=0, le=5000),
    quiet_min_room_baseline_nights: int = Query(7, ge=1, le=60),
    quiet_min_room_baseline_mean: float = Query(3.0, ge=0.0),
):
    """Sprint 2 (first implementation): patterns/anomalies.

    First conservative, explainable anomaly:
    - "Uvanlig mye nattaktivitet" based on motion/presence count
      compared to baseline nights (window_days).
    NOTE: Night window is still UTC for now; Oslo/local-time hardening is a later step.
    """
    import statistics

    now = _utc_now()
    # Allow deterministic testing/backfills by overriding reference time.
    # If 'until' is provided, use it as the reference 'now' for night/morning windows.
    if until:
        try:
            now = _parse_iso_z(until)
        except Exception:
            pass

    # Caller-provided period is accepted, but anomaly uses "last night" window for the headline metric
    recent_since, recent_until = _night_window_utc(now)

    # Baseline: previous N nights before recent_since
    baseline_night_windows = []
    for d in range(1, window_days + 1):
        s = recent_since - timedelta(days=d)
        e = recent_until - timedelta(days=d)
        baseline_night_windows.append((s, e))

    def motion_presence_count_by_room(events: list[dict[str, Any]]) -> dict[str, int]:
        out: dict[str, int] = {}
        for ev in events:
            cat = (ev.get("category") or "").lower()
            if cat not in ("motion", "presence"):
                continue
            payload = ev.get("payload") or {}
            room = payload.get("room")
            if not room:
                continue
            out[room] = out.get(room, 0) + 1
        return out

    def motion_presence_count(events: list[dict[str, Any]]) -> int:
        return sum(
            1
            for ev in events
            if (ev.get("category") or "").lower() in ("motion", "presence")
        )

    # Fail-soft: if backend unreachable, return structured empty response
    try:
        recent_events = _fetch_events(recent_since, recent_until, limit=1000)
        recent_mp = motion_presence_count(recent_events)
        recent_by_room = motion_presence_count_by_room(recent_events)


        baseline_counts = []
        baseline_by_room: dict[str, list[int]] = {}
        for s, e in baseline_night_windows:
            evs = _fetch_events(s, e, limit=1000)
            baseline_counts.append(motion_presence_count(evs))
            by_room = motion_presence_count_by_room(evs)
            # ensure every seen room gets a value for this night
            rooms = set(baseline_by_room.keys()) | set(by_room.keys()) | set(recent_by_room.keys())
            for room in rooms:
                baseline_by_room.setdefault(room, []).append(by_room.get(room, 0))

        # If baseline is empty (shouldn't happen), just return no findings
        if not baseline_counts:
            return {
                "schema_version": "v1",
                "period": {"since": recent_since.isoformat(), "until": recent_until.isoformat()},
                "baseline": {
                    "since": baseline_night_windows[-1][0].isoformat(),
                    "until": baseline_night_windows[0][1].isoformat(),
                    "window_days": window_days,
                },
                "findings": [],
                "note": "No baseline data available.",
            }

        mean = statistics.mean(baseline_counts)
        stdev = statistics.pstdev(baseline_counts)  # population stdev for stability on small N
        threshold = mean + (z_threshold * stdev)

        findings = []

        # Conservative gating:
        # - must exceed statistical threshold
        # - must exceed baseline mean by at least min_abs_increase events
        # - must have a meaningful absolute recent count (avoid tiny-number noise)
        if (
            recent_mp >= threshold
            and recent_mp >= mean + min_abs_increase
            and recent_mp >= meaningful_recent_floor
        ):
            # Basic severity/uncertainty heuristics
            if stdev == 0:
                confidence = "middels"
            else:
                z = (recent_mp - mean) / stdev if stdev else 999.0
                confidence = "høy" if z >= (z_threshold + 1.0) else "middels"

            findings.append(
                {
                    "id": f"anomaly-night-activity-{recent_since.date().isoformat()}",
                    "title": "Uvanlig mye nattaktivitet",
                    "summary": (
                        f"Nattaktivitet (bevegelse/presence) var {recent_mp} i natt, "
                        f"sammenlignet med et baseline-snitt på {mean:.1f} (siste {window_days} netter)."
                    ),
                    "severity": "observe",
                    "confidence": confidence,
                    "normal": {
                        "baseline_window_days": window_days,
                        "baseline_mean_motion_presence_night": mean,
                        "baseline_stdev_motion_presence_night": stdev,
                        "z_threshold": z_threshold,
                        "computed_threshold": threshold,
                        "min_abs_increase": min_abs_increase,
                        "meaningful_recent_floor": meaningful_recent_floor,
                    },
                    "because": [
                        f"Natt (UTC): {recent_since.isoformat()} → {recent_until.isoformat()}",
                        f"Metrikk: antall events med category=motion/presence",
                        f"I natt: {recent_mp}",
                        f"Baseline (siste {window_days} netter): snitt={mean:.1f}, spredning(stdev)={stdev:.1f}",
                        f"Terskel: snitt + {z_threshold}*stdev = {threshold:.1f}",
                        f"Konservativt krav: minst +{min_abs_increase} over snitt og minst {meaningful_recent_floor} events totalt",
                    ],
                    "evidence": {
                        "source": "events",
                        "recent": {
                            "since": recent_since.isoformat(),
                            "until": recent_until.isoformat(),
                            "category": "motion,presence",
                            "limit": 1000,
                        },
                        "baseline": {
                            "since": baseline_night_windows[-1][0].isoformat(),
                            "until": baseline_night_windows[0][1].isoformat(),
                            "window_days": window_days,
                            "night_counts": baseline_counts,
                        },
                    },                    "period": {
                        "since": recent_since.isoformat(),
                        "until": recent_until.isoformat(),
                    },
                }
            )

        # --- Per-room night activity anomaly (Sprint 2) ---
        # Detect rooms with unusually high night motion/presence compared to room-specific baseline.
        for room in sorted(baseline_by_room.keys()):
            recent_room_mp = recent_by_room.get(room, 0)
            room_counts = baseline_by_room.get(room) or []
            if not room_counts:
                continue
            mean_r = statistics.mean(room_counts)
            stdev_r = statistics.pstdev(room_counts)
            threshold_r = mean_r + (z_threshold * stdev_r)

            if (
                recent_room_mp >= threshold_r
                and recent_room_mp >= mean_r + min_abs_increase
                and recent_room_mp >= meaningful_recent_floor
            ):
                findings.append(
                    {
                        "id": f"anomaly-night-activity-room-{room}-{recent_since.date().isoformat()}",
                        "title": f"Rom uvanlig aktivt om natten: {room}",
                        "summary": (
                            f"Nattaktivitet (bevegelse/presence) i {room} var {recent_room_mp} i natt, "
                            f"sammenlignet med et baseline-snitt på {mean_r:.1f} (siste {window_days} netter)."
                        ),
                        "severity": "observe",
                        "confidence": "middels" if stdev_r == 0 else ("høy" if ((recent_room_mp - mean_r) / stdev_r) >= (z_threshold + 1.0) else "middels"),
                        "normal": {
                            "room": room,
                            "baseline_window_days": window_days,
                            "baseline_mean_motion_presence_night": mean_r,
                            "baseline_stdev_motion_presence_night": stdev_r,
                            "z_threshold": z_threshold,
                            "computed_threshold": threshold_r,
                            "min_abs_increase": min_abs_increase,
                            "meaningful_recent_floor": meaningful_recent_floor,
                        },
                        "because": [
                            f"Rom: {room}",
                            f"Natt (UTC): {recent_since.isoformat()} → {recent_until.isoformat()}",
                            f"Metrikk: antall events med category=motion/presence og payload.room={room}",
                            f"I natt: {recent_room_mp}",
                            f"Baseline (siste {window_days} netter): snitt={mean_r:.1f}, spredning(stdev)={stdev_r:.1f}",
                            f"Terskel: snitt + {z_threshold}*stdev = {threshold_r:.1f}",
                            f"Konservativt krav: minst +{min_abs_increase} over snitt og minst {meaningful_recent_floor} events totalt",
                        ],
                        "evidence": {
                            "source": "events",
                            "room": room,
                            "recent": {
                                "since": recent_since.isoformat(),
                                "until": recent_until.isoformat(),
                                "category": "motion,presence",
                                "limit": 1000,
                            },
                            "baseline": {
                                "since": baseline_night_windows[-1][0].isoformat(),
                                "until": baseline_night_windows[0][1].isoformat(),
                                "window_days": window_days,
                                "night_counts": room_counts,
                            },
                        },
                        "period": {
                            "since": recent_since.isoformat(),
                            "until": recent_until.isoformat(),
                        },
                    }
                )


        # --- Per-room night inactivity anomaly (Sprint 2) ---
        # Detect rooms with unusually low night motion/presence compared to room-specific baseline.
        # Conservative gating: require enough baseline nights and a minimum baseline activity level.
        min_room_baseline_nights = quiet_min_room_baseline_nights
        min_room_baseline_mean = quiet_min_room_baseline_mean

        for room in sorted(baseline_by_room.keys()):
            recent_room_mp = recent_by_room.get(room, 0)
            room_counts = baseline_by_room.get(room) or []
            if len(room_counts) < min_room_baseline_nights:
                continue

            mean_r = statistics.mean(room_counts)
            stdev_r = statistics.pstdev(room_counts)

            if mean_r < min_room_baseline_mean:
                continue

            # Low threshold: mean - z*stdev (clamped at 0)
            low_threshold_r = max(0.0, mean_r - (z_threshold * stdev_r))

            # Reuse min_abs_increase as an absolute *decrease* gate for silence (keeps API stable)
            min_abs_decrease = float(min_abs_increase)

            if (recent_room_mp <= low_threshold_r) and ((mean_r - recent_room_mp) >= min_abs_decrease):
                findings.append(
                    {
                        "id": f"anomaly-night-quiet-room-{room}-{recent_since.date().isoformat()}",
                        "title": f"Rom uvanlig stille: {room}",
                        "summary": (
                            f"Nattaktivitet (bevegelse/presence) i {room} var {recent_room_mp} i natt, "
                            f"som er lavere enn forventet basert på baseline-snitt {mean_r:.1f} "
                            f"(siste {window_days} netter)."
                        ),
                        "severity": "observe",
                        "confidence": "middels"
                        if stdev_r == 0
                        else (
                            "høy"
                            if ((mean_r - recent_room_mp) / stdev_r) >= (z_threshold + 1.0)
                            else "middels"
                        ),
                        "normal": {
                            "room": room,
                            "baseline_window_days": window_days,
                            "baseline_mean_motion_presence_night": mean_r,
                            "baseline_stdev_motion_presence_night": stdev_r,
                            "z_threshold": z_threshold,
                            "computed_low_threshold": low_threshold_r,
                            "min_abs_decrease": min_abs_decrease,
                            "min_room_baseline_nights": min_room_baseline_nights,
                            "min_room_baseline_mean": min_room_baseline_mean,
                        },
                        "because": [
                            f"Rom: {room}",
                            f"Natt (UTC): {recent_since.isoformat()} → {recent_until.isoformat()}",
                            f"Metrikk: antall events med category=motion/presence og payload.room={room}",
                            f"I natt: {recent_room_mp}",
                            f"Baseline (siste {window_days} netter): snitt={mean_r:.1f}, spredning(stdev)={stdev_r:.1f}",
                            f"Lav-terskel: snitt - {z_threshold}*stdev = {low_threshold_r:.1f}",
                            f"Konservativt krav: minst -{min_abs_decrease} under snitt og minst {min_room_baseline_nights} baseline-netter",
                        ],
                        "evidence": {
                            "source": "events",
                            "room": room,
                            "recent": {
                                "since": recent_since.isoformat(),
                                "until": recent_until.isoformat(),
                                "category": "motion,presence",
                                "limit": 1000,
                            },
                            "baseline": {
                                "since": baseline_night_windows[-1][0].isoformat(),
                                "until": baseline_night_windows[0][1].isoformat(),
                                "window_days": window_days,
                                "night_counts": room_counts,
                            },
                        },
                        "period": {
                            "since": recent_since.isoformat(),
                            "until": recent_until.isoformat(),
                        },
                    }
                )


        # --- Morning routine anomaly (Sprint 2) ---
        # Conservative, explainable: compare first motion/presence in the morning window vs baseline median.
        from zoneinfo import ZoneInfo

        tz_name = os.getenv("AGINGOS_TIMEZONE", "Europe/Oslo")
        tz = ZoneInfo(tz_name)
        now_local = now.astimezone(tz)

        # Morning window (local time)
        morning_start_h = 5
        morning_end_h = 12

        # Trigger if today's first activity is >= this many minutes later than baseline median
        delay_threshold_minutes = 60

        # Require baseline observations to avoid noise
        min_baseline_days = 5

        def _first_motion_presence_minute_in_window(s_utc, e_utc):
          events = _fetch_events(s_utc, e_utc, limit=1000)
          times = []
          for ev in events:
              if (ev.get("category") or "").lower() in ("motion", "presence"):
                  ts = ev.get("timestamp")
                  if ts:
                      try:
                          times.append(_parse_iso_z(ts))
                      except Exception:
                          pass
          if not times:
              return None, {"since": s_utc.isoformat(), "until": e_utc.isoformat(), "count": 0}
          first = min(times)
          first_local = first.astimezone(tz)
          minute = first_local.hour * 60 + first_local.minute
          return minute, {"since": s_utc.isoformat(), "until": e_utc.isoformat(), "count": len(times)}

        # Baseline: previous N mornings
        baseline_minutes = []
        baseline_meta = []
        for d in range(1, window_days + 1):
            day = (now_local.date() - timedelta(days=d))
            s_local = datetime(day.year, day.month, day.day, morning_start_h, 0, 0, tzinfo=tz)
            e_local = datetime(day.year, day.month, day.day, morning_end_h, 0, 0, tzinfo=tz)
            s_utc = s_local.astimezone(timezone.utc)
            e_utc = e_local.astimezone(timezone.utc)
            minute, meta = _first_motion_presence_minute_in_window(s_utc, e_utc)
            baseline_meta.append(meta)
            if minute is not None:
                baseline_minutes.append(minute)

        # Recent: today morning (up to now, not beyond morning_end)
        recent_minute = None
        recent_window = None
        if now_local.hour >= morning_start_h:
            today = now_local.date()
            s_local = datetime(today.year, today.month, today.day, morning_start_h, 0, 0, tzinfo=tz)
            e_local = datetime(today.year, today.month, today.day, morning_end_h, 0, 0, tzinfo=tz)
            end_local = now_local if now_local < e_local else e_local
            s_utc = s_local.astimezone(timezone.utc)
            e_utc = end_local.astimezone(timezone.utc)
            recent_minute, recent_window = _first_motion_presence_minute_in_window(s_utc, e_utc)

        def _fmt_minute(m):
            hh = int(m) // 60
            mm = int(m) % 60
            return f"{hh:02d}:{mm:02d}"

        if recent_minute is not None and len(baseline_minutes) >= min_baseline_days:
            baseline_median = statistics.median(baseline_minutes)
            # Typical range (robust): 10th–90th percentile of baseline minutes
            b_sorted = sorted(baseline_minutes)
            def _pct(vals, p):
                if not vals:
                    return None
                k = (len(vals) - 1) * p
                f = int(k)
                c = min(f + 1, len(vals) - 1)
                if f == c:
                    return float(vals[f])
                return float(vals[f]) + (k - f) * (float(vals[c]) - float(vals[f]))
            p10 = _pct(b_sorted, 0.10)
            p90 = _pct(b_sorted, 0.90)
            delta = recent_minute - baseline_median

            if delta >= delay_threshold_minutes:
                # Confidence heuristic
                if len(baseline_minutes) >= 10 and delta >= 120:
                    confidence = "høy"
                elif len(baseline_minutes) >= 7:
                    confidence = "middels"
                else:
                    confidence = "lav"

                # Define a period for "Vis grunnlag" (events): the recent morning window
                finding_since = recent_window["since"]
                finding_until = recent_window["until"]

                findings.append(
                    {
                        "id": f"anomaly-morning-late-{now_local.date().isoformat()}",
                        "title": "Morgenrutine startet senere enn normalt",
                        "summary": (
                            f"Første registrerte aktivitet i morges var kl. {_fmt_minute(recent_minute)} "
                            f"(lokal tid), som er ca. {int(delta)} minutter senere enn normalt "
                            f"(baseline-median {_fmt_minute(baseline_median)} de siste {window_days} dagene)."
                        ),
                        "severity": "observe",
                        "confidence": confidence,
                        "normal": {
                            "timezone": tz_name,
                            "morning_window_local": f"{morning_start_h:02d}:00–{morning_end_h:02d}:00",
                            "baseline_window_days": window_days,
                            "baseline_days_with_data": len(baseline_minutes),
                            "baseline_median_minutes_local": baseline_median,
                            "baseline_p10_minutes_local": p10,
                            "baseline_p90_minutes_local": p90,
                            "delay_threshold_minutes": delay_threshold_minutes,
                        },
                        "because": [
                            f"Tidssone: {tz_name}",
                            f"Morgen-vindu (lokal tid): {morning_start_h:02d}:00–{morning_end_h:02d}:00",
                            f"Metrikk: første event med category=motion/presence i morgen-vinduet",
                            f"I dag: {_fmt_minute(recent_minute)}",
                            f"Baseline: median {_fmt_minute(baseline_median)} (antall dager med data: {len(baseline_minutes)})",
                            f"Terskel: >= {delay_threshold_minutes} minutter senere enn baseline",
                        ],
                        "evidence": {
                            "source": "events",
                            "recent": {
                                "since": finding_since,
                                "until": finding_until,
                                "category": "motion,presence",
                                "limit": 1000,
                            },
                            "baseline": {
                                "window_days": window_days,
                                "days_with_data": len(baseline_minutes),
                                "baseline_minutes_local": baseline_minutes,
                                "baseline_median_minutes_local": baseline_median,
                                "note": "Baseline_minutes er minutter siden midnatt (lokal tid).",
                            },
                        },
                        "period": {
                            "since": finding_since,
                            "until": finding_until,
                        },
                    }
                )

        return {
            "schema_version": "v1",
            "period": {"since": recent_since.isoformat(), "until": recent_until.isoformat()},
            "baseline": {
                "since": baseline_night_windows[-1][0].isoformat(),
                "until": baseline_night_windows[0][1].isoformat(),
                "window_days": window_days,
            },
            "findings": findings,
        }

    except Exception as e:
        return {
            "schema_version": "v1",
            "period": {"since": recent_since.isoformat(), "until": recent_until.isoformat()},
            "baseline": {
                "since": baseline_night_windows[-1][0].isoformat(),
                "until": baseline_night_windows[0][1].isoformat(),
                "window_days": window_days,
            },
            "findings": [],
            "note": f"Could not compute anomalies (fail-soft): {type(e).__name__}",
        }



@app.get("/v1/proposals")
def proposals(
    since: Optional[str] = Query(default=None),
    until: Optional[str] = Query(default=None),
    window_days: int = Query(default=14, ge=3, le=60),
    min_abs_increase: int = Query(default=10, ge=0, le=5000),
    z_threshold: float = Query(default=2.0, ge=0.0, le=10.0),
    meaningful_recent_floor: int = Query(default=20, ge=0, le=5000),
    quiet_min_room_baseline_nights: int = Query(7, ge=1, le=60),
    quiet_min_room_baseline_mean: float = Query(3.0, ge=0.0),
):
    """
    Sprint 3 (minimal v1): Generate draft proposals from anomaly findings.
    - Read-only. No persistence. No lifecycle transitions yet.
    - Fail-soft: if anomalies cannot be computed, return empty proposals with note.
    """
    try:
        resp = anomalies(
            since=since,
            until=until,
            window_days=window_days,
            min_abs_increase=min_abs_increase,
            z_threshold=z_threshold,
            meaningful_recent_floor=meaningful_recent_floor,
            quiet_min_room_baseline_nights=quiet_min_room_baseline_nights,
            quiet_min_room_baseline_mean=quiet_min_room_baseline_mean,
        )
    except Exception as e:
        return {
            "schema_version": "v1",
            "period": {"since": since, "until": until},
            "proposals": [],
            "note": f"Could not compute proposals (fail-soft): {type(e).__name__}",
        }

    props = []
    findings = resp.get("findings") or []
    for f in findings:
        fid = f.get("id") or ""
        if not fid.startswith("anomaly-night-quiet-room-"):
            continue

        ev = f.get("evidence") or {}
        room = ev.get("room") or (f.get("normal") or {}).get("room") or "unknown"

        props.append(
            {
                "id": f"proposal-test-quiet-room-{room}-{(resp.get('period') or {}).get('since','')[:10]}",
                "title": f"Forslag: Test varsel for uvanlig stille rom ({room})",
                "summary": "Utkast til regel basert på funn. Test i 7 dager før eventuell aktivering.",
                "status": "draft",
                "lifecycle": {
                    "stage": "draft",
                    "actions": [
                        {"action": "test_7_days", "label": "Test i 7 dager"},
                        {"action": "activate", "label": "Aktiver"},
                        {"action": "reject", "label": "Avvis"},
                    ],
                },
                "normal": f.get("normal") or {},
                "because": [
                    f"Referansefunn: {fid}",
                    "Bygger på romspesifikk baseline og nattvindu.",
                    "Test først i 7 dager for å validere før aktivering.",
                ],
                "evidence": ev,
                "references": {"finding_id": fid, "anomaly_params": {
                    "window_days": window_days,
                    "min_abs_increase": min_abs_increase,
                    "z_threshold": z_threshold,
                    "meaningful_recent_floor": meaningful_recent_floor,
                    "quiet_min_room_baseline_nights": quiet_min_room_baseline_nights,
                    "quiet_min_room_baseline_mean": quiet_min_room_baseline_mean,
                    "since": since,
                    "until": until,
                }},
                "rule_draft": {
                    "type": "anomaly_followup",
                    "anomaly_id_prefix": "anomaly-night-quiet-room-",
                    "room": room,
                    "action": "notify",
                    "test_days": 7,
                },
            }
        )

    return {
        "schema_version": "v1",
        "period": resp.get("period"),
        "proposals": props,
    }
@app.get("/v1/insights")
def insights(
    since: Optional[str] = Query(default=None),
    until: Optional[str] = Query(default=None),
):
    # Period: if caller provides since/until use those; else compute "last night"
    now = _utc_now()

    if since and until:
        period_since = _parse_iso_z(since)
        period_until = _parse_iso_z(until)
    else:
        period_since, period_until = _night_window_utc(now)

    findings = []
    proposals = []

    # Try fetching events; fail soft if backend unreachable/auth fails
    try:
        events = _fetch_events(period_since, period_until, limit=1000)
    except Exception as e:
        return {
            "schema_version": "v1",
            "period": {
                "since": period_since.isoformat(),
                "until": period_until.isoformat(),
            },
            "findings": [],
            "proposals": [],
            "note": f"Could not fetch events from AgingOS: {type(e).__name__}",
        }

    total = len(events)

    # Basic signals (very conservative for MVP)
    motion_count = sum(
        1
        for ev in events
        if (ev.get("category") or "").lower() in ("motion", "presence")
    )
    door_count = sum(
        1
        for ev in events
        if (ev.get("category") or "").lower() in ("door", "door_open", "door_closed")
    )
    heartbeat_count = sum(
        1 for ev in events if (ev.get("category") or "").lower() == "heartbeat"
    )

    # Human-readable finding
    title = "I natt (oppsummering)"
    summary = f"Registrerte {total} hendelser i perioden."
    because = [
        f"Periode: {period_since.isoformat()} til {period_until.isoformat()}",
        f"Totalt antall hendelser: {total}",
        f"Bevegelse/presence: {motion_count}",
        f"Dør-hendelser: {door_count}",
        f"Heartbeat: {heartbeat_count}",
    ]

    findings.append(
        {
            "id": f"night-summary-{period_since.date().isoformat()}",
            "title": title,
            "summary": summary,
            "severity": "info",
            "because": because,
            "evidence": {
                "source": "events",
                "since": period_since.isoformat(),
                "until": period_until.isoformat(),
                "limit": 1000,
            },
            "period": {
                "since": period_since.isoformat(),
                "until": period_until.isoformat(),
            },
        }
    )
    # --- Last 24 hours summary + sensor health (Sprint 1) ---
    last24_since = now - timedelta(hours=24)
    last24_until = now

    try:
        events_24h = _fetch_events(last24_since, last24_until, limit=1000)
        total_24h = len(events_24h)
        motion_24h = sum(
            1
            for ev in events_24h
            if (ev.get("category") or "").lower() in ("motion", "presence")
        )
        door_24h = sum(
            1
            for ev in events_24h
            if (ev.get("category") or "").lower()
            in ("door", "door_open", "door_closed")
        )
        heartbeat_24h = sum(
            1 for ev in events_24h if (ev.get("category") or "").lower() == "heartbeat"
        )

        # Sensor health: heartbeat missing/unstable
        hb_events = [
            ev for ev in events_24h if (ev.get("category") or "").lower() == "heartbeat"
        ]
        hb_times = []
        for ev in hb_events:
            ts = ev.get("timestamp")
            if ts:
                try:
                    hb_times.append(_parse_iso_z(ts))
                except Exception:
                    pass
        hb_times.sort()

        if heartbeat_24h == 0:
            findings.append(
                {
                    "id": f"sensor-health-heartbeat-missing-{now.date().isoformat()}",
                    "title": "Sensorhelse: Heartbeat mangler",
                    "summary": "Ingen heartbeat-hendelser siste 24 timer. Dette kan bety at en sensor er offline eller at heartbeat ikke sendes.",
                    "severity": "observe",
                    "because": [
                        f"Periode: {last24_since.isoformat()} til {last24_until.isoformat()}",
                        "Antall heartbeat: 0",
                        "Vurder å sjekke sensor/tilkobling og strøm/batteri.",
                    ],
                    "evidence": {
                        "source": "events",
                        "since": last24_since.isoformat(),
                        "until": last24_until.isoformat(),
                        "category": "heartbeat",
                        "limit": 1000,
                    },
                    "period": {
                        "since": last24_since.isoformat(),
                        "until": last24_until.isoformat(),
                    },
                }
            )
        else:
            max_gap = timedelta(0)
            max_gap_from = None
            max_gap_to = None
            for a, b in zip(hb_times, hb_times[1:]):
                gap = b - a
                if gap > max_gap:
                    max_gap = gap
                    max_gap_from = a
                    max_gap_to = b

            if max_gap > timedelta(minutes=30) and max_gap_from and max_gap_to:
                findings.append(
                    {
                        "id": f"sensor-health-heartbeat-unstable-{now.date().isoformat()}",
                        "title": "Sensorhelse: Heartbeat ustabil",
                        "summary": f"Heartbeat har et stort opphold (ca. {int(max_gap.total_seconds() // 60)} minutter) siste 24 timer.",
                        "severity": "observe",
                        "because": [
                            f"Periode: {last24_since.isoformat()} til {last24_until.isoformat()}",
                            f"Antall heartbeat: {heartbeat_24h}",
                            f"Største opphold: {max_gap_from.isoformat()} → {max_gap_to.isoformat()}",
                            "Dette kan skyldes nettverk, strøm/batteri eller at sensoren restarter.",
                        ],
                        "evidence": {
                            "source": "events",
                            "since": last24_since.isoformat(),
                            "until": last24_until.isoformat(),
                            "category": "heartbeat",
                            "limit": 1000,
                        },
                        "period": {
                            "since": last24_since.isoformat(),
                            "until": last24_until.isoformat(),
                        },
                    }
                )

        findings.append(
            {
                "id": f"last24h-summary-{now.date().isoformat()}",
                "title": "Siste 24 timer (oppsummering)",
                "summary": f"Registrerte {total_24h} hendelser siste 24 timer.",
                "severity": "info",
                "because": [
                    f"Periode: {last24_since.isoformat()} til {last24_until.isoformat()}",
                    f"Totalt antall hendelser: {total_24h}",
                    f"Bevegelse/presence: {motion_24h}",
                    f"Dør-hendelser: {door_24h}",
                    f"Heartbeat: {heartbeat_24h}",
                ],
                "evidence": {
                    "source": "events",
                    "since": last24_since.isoformat(),
                    "until": last24_until.isoformat(),
                    "limit": 1000,
                },
                "period": {
                    "since": last24_since.isoformat(),
                    "until": last24_until.isoformat(),
                },
            }
        )
    except Exception:
        # Fail soft: do not break insights if 24h fetch fails
        pass

    return {
        "schema_version": "v1",
        "period": {
            "since": period_since.isoformat(),
            "until": period_until.isoformat(),
        },
        "findings": findings,
        "proposals": proposals,
    }
