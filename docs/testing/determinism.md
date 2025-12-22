# Determinisme i tester (now-injection)

## Hvorfor
Regler og scheduler bruker “nå” (`now`) som del av evaluering (vinduer, expire, timestamps på avvik). For å gjøre tester og simuleringer deterministiske, må vi kunne kontrollere hva “nå” er.

## Mønster: `utcnow()` som én inngang
AgingOS bruker `backend/util/time.py:utcnow()` som eneste kilde til “nå” i runtime-kode.

- Produksjon: `utcnow()` returnerer `datetime.now(timezone.utc)`.
- Tester: `utcnow()` kan monkeypatches til en fast verdi.

Dette gir:
- Stabilitet i tester (ingen flakiness pga. wall clock).
- Reproduserbar simulering (samme input gir samme output).

## Minimal test (pytest) som setter now
Eksempel med `monkeypatch`:

```python
from datetime import datetime, timezone

from util import time as time_util

def test_fixed_now(monkeypatch):
    fixed = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(time_util, "utcnow", lambda: fixed)

    assert time_util.utcnow() == fixed
```

## Anbefaling
- Bruk `utcnow()` i runtime-kode (routes, scheduler, rule_engine).
- Unngå direkte `datetime.now(timezone.utc)` utenfor `util.time`.
