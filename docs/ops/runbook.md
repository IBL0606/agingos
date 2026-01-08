# Runbook (steg-for-steg) — AgingOS

Dette dokumentet er skrevet for deg som ikke jobber med software til daglig.
Følg punktene i rekkefølge. Når du står i en install-/pilot-situasjon, bruk spesielt:
- **B) Feltprofil (pilot/HW)**
- **E) Go/No-Go verifisering (M1–M8)**

---

## Før du starter (må være på plass)

### 1) Du står i repo-root
Du må stå i mappen som inneholder `Makefile`.

### 2) Docker + Docker Compose virker
Kjør:

    docker version

Hvis du kjører **Windows + WSL**:
- Sørg for at Docker Desktop kjører i Windows.
- Slå på WSL-integrasjon i Docker Desktop (for riktig distro) og restart WSL ved behov.

Hvis du kjører **Linux (f.eks. mini-PC Ubuntu)**:
- `docker version` skal fungere i terminalen din.

### 3) Verktøy som trengs for testene
- `curl` (brukes i flere sjekker)
- `jq` (brukes av `make smoke`)
- `python3` (brukes av `make scenario`)
- `make`

Sjekk (valgfritt):

    jq --version
    python3 --version
    make --version

Hvis `jq` mangler (typisk på Ubuntu):

    sudo apt-get update && sudo apt-get install -y jq

Hvis `make scenario` feiler pga Python-moduler, installer disse på host:

    python3 -m pip install --user requests pyyaml

---

## A) Dev-profil (lokal)

### A1. Start systemet (bygger + starter + kjører migrasjoner)
Kjør:

    make up

Hva du skal forvente:
- Det kommer meldinger om at databasen blir klar og at migrasjoner kjøres.
- Kommandoen avslutter uten error.

### A2. Se logger (for å se at alt kjører)
Kjør:

    make logs

Stoppe loggvisning:
- Trykk `Ctrl + C` (det stopper bare loggstrømmen, ikke systemet).

### A3. Kjør en test (smoke test)
Kjør:

    make smoke

Hvis felt-auth er aktiv (API-key), kjør:

    AGINGOS_API_KEY="DIN_HEMMELIGE_NØKKEL" make smoke

Hvis du får 401/403:
- Nøkkelen er feil, eller du glemte `AGINGOS_API_KEY=...`.
- Sjekk at `.env` inneholder riktig `AGINGOS_API_KEYS=...` (feltprofil) og at du bruker samme nøkkel i smoke.

### A4. Stopp systemet
Kjør:

    make down

---

## B) Feltprofil (pilot/HW) — med API-key

> Feltprofilen er det dere bruker på mini-PC i pilot.  
> Kjør kommandoene på mini-PCen (der Docker kjører), med mindre det står noe annet.

### B1. Sett API-key (én gang)
Lag/oppdater `.env` i repo-root med:

    AGINGOS_AUTH_MODE=api_key
    AGINGOS_API_KEYS=DIN_HEMMELIGE_NØKKEL

Viktig:
- `.env` skal ikke committes til git.
- Bruk en lang, tilfeldig nøkkel (minimum ca. 32 tegn).

Mer om API-key og rotasjon (bytte nøkkel):
- `docs/ops/security-minimum.md`

### B2. Start feltprofil
Kjør:

    make field-up

### B3. Se logger (feltprofil)
Kjør:

    make field-logs

### B4. Test at API-key fungerer (smoke)
Kjør (på mini-PC):

    BASE_URL="http://localhost:8000" AGINGOS_API_KEY="DIN_HEMMELIGE_NØKKEL" make smoke

Hvis du kjører testen fra en annen maskin på LAN (ikke anbefalt første gang):
- Sett `BASE_URL` til mini-PCen sin IP/DNS, f.eks. `http://<MINIPC>:8000`.
- Merk: runbook/Go-No-Go forutsetter at dere også kan verifisere DB lokalt på mini-PC.

### B5. Stopp feltprofil
Kjør:

    make field-down

---

## C) Backup / restore (lokal)

### C1. Backup
Forutsetter at systemet kjører (`make up` eller `make field-up`).

Kjør:

    make backup-db

Hva som skjer:
- Det lages en SQL-fil i `./backups/`.

### C2. Restore
Forutsetter at systemet kjører (db må være oppe).

1) Se filer:

    ls -1 backups

2) Restore (velg en ekte fil fra lista):

    make restore-db FILE=backups/<filnavn>.sql

Viktig:
- Restore overskriver databasen.

Mer detaljer/verifikasjon:
- `docs/ops/backup-restore.md`

---

## D) Vanlige problemer (kort)

### “docker could not be found in this WSL 2 distro”
- Docker Desktop må kjøre i Windows.
- WSL-integrasjon må være slått på for din distro.
- Kjør i PowerShell: `wsl --shutdown` og åpne ny WSL-terminal.

### “jq: command not found” (smoke feiler)
Installer `jq`:
- Ubuntu: `sudo apt-get update && sudo apt-get install -y jq`

### Hvis noe feiler (generelt)
- Først: se logger
  - Dev: `make logs`
  - Felt: `make field-logs`
- Se etter ERROR/WARN-linjer og kopier ut 20–50 linjer rundt feilen.
- Mer detaljert guide: `docs/ops/logging.md`

---

## E) Go/No-Go verifisering (M1–M8) – copy/paste-oppskrifter

Denne seksjonen er den operative “oppskriften” for kriteriene i `docs/hw/go-no-go.md`.

### Før du begynner (variabler)
Bruk disse plassholderne:
- `<MINIPC>` = IP eller DNS-navn til mini-PC (f.eks. `192.168.1.50`)
- `API_KEY` = den samme nøkkelen som ligger i `.env`

Praktisk (på mini-PC):

    export API_KEY="DIN_HEMMELIGE_NØKKEL"
    export BASE_URL_LOCAL="http://localhost:8000"
    export BASE_URL_LAN="http://<MINIPC>:8000"

---

### E1) M1 – Nettverk og health (RPi → mini-PC)

Kjør dette **fra RPi** (eller samme nettsegment som RPi/HA):

    for i in $(seq 1 10); do
      curl -sS -o /dev/null -w "%{http_code}\n" "http://<MINIPC>:8000/health" || true
    done

**Pass (M1):**
- Du får `200` alle 10 gangene.

**Fail (M1):**
- Noe annet enn `200` eller timeout/refused.

---

### E2) M2 – Feltprofil kan startes deterministisk (på mini-PC)

1) Start feltprofil:

    make field-up

2) Følg logger:

    make field-logs

**Pass (M2):**
- `make field-up` fullfører uten error.
- Logger viser at backend kjører (typisk “Uvicorn running …”) og ingen kontinuerlige exceptions.

**Fail (M2):**
- `make field-up` feiler.
- Backend starter ikke, eller restarter/crasher gjentatte ganger.

---

### E3) M3 – Ingest ende-til-ende (HTTP → DB persist)

Kjør dette **på mini-PC**.

1) Kjør smoke mot lokal URL (sikrere enn LAN først):

    BASE_URL="$BASE_URL_LOCAL" AGINGOS_API_KEY="$API_KEY" make smoke

2) Verifiser at DB faktisk inneholder events:

    docker compose exec -T db psql -U agingos -d agingos -c "SELECT count(*) AS events_count FROM events;"

**Pass (M3):**
- Smoke passerer (“SUCCESS: Smoke test passed.”).
- `events_count` er > 0 etter smoke.

**Fail (M3):**
- Smoke feiler (ikke 2xx / uventet output).
- `events_count` forblir 0 (indikasjon på data-tap eller feil persist).

---

### E4) M4 – Bad input avvises (4xx) og DB endres ikke

Kjør dette **på mini-PC**.

1) Hent “før”-tall:

    docker compose exec -T db psql -U agingos -d agingos -c "SELECT count(*) AS before_count FROM events;"

2) Send ugyldig payload (tom JSON) til `/event`:

    curl -sS -o /dev/null -w "%{http_code}\n" \
      -H "Content-Type: application/json" \
      -H "X-API-Key: $API_KEY" \
      -d '{}' \
      "$BASE_URL_LOCAL/event"

Forventet er typisk `422` (FastAPI validering).

3) Hent “etter”-tall:

    docker compose exec -T db psql -U agingos -d agingos -c "SELECT count(*) AS after_count FROM events;"

**Pass (M4):**
- HTTP status er 4xx (typisk 422).
- `after_count` == `before_count`.

**Fail (M4):**
- Status er 2xx (aksepterer invalid data), eller DB-count øker.

---

### E5) M5 – Persistens over restart

Kjør dette **på mini-PC**.

1) Sikre at DB har data (hvis ikke, kjør smoke først):

    BASE_URL="$BASE_URL_LOCAL" AGINGOS_API_KEY="$API_KEY" make smoke

2) Notér count:

    docker compose exec -T db psql -U agingos -d agingos -c "SELECT count(*) AS before_count FROM events;"

3) Restart feltprofil:

    make field-down
    make field-up

4) Verifiser count igjen:

    docker compose exec -T db psql -U agingos -d agingos -c "SELECT count(*) AS after_count FROM events;"

**Pass (M5):**
- `after_count` er fortsatt > 0 (og typisk lik `before_count`).

**Fail (M5):**
- Count går til 0 eller data “forsvinner”.

---

### E6) M6 – Regelflyt/evaluering (scenario) er kjørbar og stabil

Kjør dette **på mini-PC**.

1) Resett scenario-tabeller:

    make scenario-reset

2) Kjør scenario:

    BASE_URL="$BASE_URL_LOCAL" AGINGOS_API_KEY="$API_KEY" make scenario

**Pass (M6):**
- Kommandoene fullfører uten error, og scenario gir forventet output (ingen “uventede avvik”).

**Fail (M6):**
- Scenario feiler pga dependencies (python/requests/yaml) eller uventet oppførsel.
  - Hvis feilen er ren dependency (mangler `requests`), installer:
    `python3 -m pip install --user requests pyyaml`

---

### E7) M7 – Backup/restore er bevist

Kjør dette **på mini-PC**.

1) Lag backup:

    make backup-db

2) Verifiser at fil finnes:

    ls -1 backups | tail -n 5

3) Restore (bruk et faktisk filnavn fra lista):

    make restore-db FILE=backups/<filnavn>.sql

4) Verifiser at events fortsatt finnes:

    docker compose exec -T db psql -U agingos -d agingos -c "SELECT count(*) AS events_count FROM events;"

**Pass (M7):**
- Backup-fil blir laget.
- Restore fullfører.
- `events_count` er > 0 etterpå (forutsatt at det var data før backup).

**Fail (M7):**
- Backup eller restore feiler, eller data mangler etter restore.

---

### E8) M8 – Perimeter/tilgang er riktig

Dette verifiserer at port 8000 kun er tilgjengelig fra forventede klienter/segment.

**Del 1 – “allowed” (RPi/LAN):**  
Kjør fra RPi (eller et godkjent LAN-segment):

    curl -sS -o /dev/null -w "%{http_code}\n" "http://<MINIPC>:8000/health"

Forventet: `200`.

**Del 2 – “not allowed”:**  
Kjør fra en uønsket klient/segment (eksempel: annen VLAN, gjestenett, eller telefon på mobilnett). Forsøk samme:

    curl -m 3 -sS -o /dev/null -w "%{http_code}\n" "http://<MINIPC>:8000/health" || true

**Pass (M8):**
- Godkjent klient får `200`.
- Uønsket klient får timeout/refused/ikke-200.

**Fail (M8):**
- Uønsket klient får `200` (indikasjon på eksponering eller for åpen perimeter).

Tips ved fail:
- Verifiser brannmur/ACL på mini-PC og nettverk (router/switch).
- Målet er “default deny” utenfor forventet segment.
