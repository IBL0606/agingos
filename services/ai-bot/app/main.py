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
    Simple definition for MVP:
    Night is from 22:00 to 07:00 (UTC) spanning midnight.
    This is a placeholder; later we can make it per-home configurable/local-time aware.
    """
    start = now.replace(hour=22, minute=0, second=0, microsecond=0)
    end = now.replace(hour=7, minute=0, second=0, microsecond=0)

    # If we're before 07:00, night started yesterday at 22:00
    if now < end:
        start = start - timedelta(days=1)
    else:
        # If we're after 07:00, "last night" ended today at 07:00
        end = end

        # and started yesterday at 22:00
        start = start - timedelta(days=1)

    return start, end


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
        "features": {"insights": True, "proposals": True},
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
