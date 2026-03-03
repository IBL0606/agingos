# Mobile demo: AgingOS Console

## Åpne på mobil

1. Start console lokalt (for eksempel via `docker compose up -d console`).
2. Finn maskinens LAN-IP (f.eks. `192.168.x.y`).
3. Åpne `http://<LAN-IP>:8080/` i mobilnettleser.

## iOS (Add to Home Screen)

1. Åpne Console i Safari.
2. Trykk **Del**.
3. Velg **Legg til på Hjem-skjerm**.
4. Start appen fra hjemskjermen for standalone-visning.

## Android

- **Install app** i Chrome krever normalt HTTPS (eller localhost).
- For demo på LAN uten HTTPS: bruk nettsiden i mobilnettleser.
- Alternativt bruk iOS Add to Home Screen-flyten for standalone-demo.

## Verifikasjon

Kjør:

```bash
curl -I http://localhost:8080/manifest.webmanifest
curl -I http://localhost:8080/icons/icon-192.svg
curl -I http://localhost:8080/icons/icon-512.svg
```

Forventet:

- HTTP 200 på alle kall.
- `Content-Type: application/manifest+json` for manifest.
- `Content-Type: image/svg+xml` for ikonene.

Manuell verifisering:

- Åpne siden på mobil og bekreft at riktig ikon vises ved «Legg til på Hjem-skjerm».
- Start fra hjemskjerm og bekreft standalone-opplevelse (uten vanlig browser chrome).

## Rescan for skjulte bidi-tegn

Kjør denne for å verifisere at repo ikke inneholder bidi-kontrolltegn (forventet `TOTAL 0`):

```bash
python - <<'PY'
from pathlib import Path
import re
pat = re.compile('[\u202A-\u202E\u2066-\u2069\u200E\u200F\u061C]')
count = 0
for p in Path('.').rglob('*'):
    if p.is_file() and '.git' not in p.parts:
        try:
            text = p.read_text(encoding='utf-8')
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if pat.search(line):
                print(f"{p}:{i}:{line.encode('unicode_escape').decode()}")
                count += 1
print('TOTAL', count)
PY
```

## Notat om PR-opprettelse

- Ikonene er lagt inn som SVG (tekstfiler) i stedet for PNG, fordi PR-verktøyet avviser binærfiler med meldingen «Binærfiler støttes ikke».
