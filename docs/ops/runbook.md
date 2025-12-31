# Runbook (steg-for-steg) — AgingOS

Dette dokumentet er skrevet for deg som ikke jobber med software til daglig.
Følg punktene i rekkefølge.

## Før du starter (må være på plass)
1) Docker virker i WSL:
   - Kjør: `docker version`
   - Hvis den feiler: slå på WSL-integrasjon i Docker Desktop (Windows) og restart WSL.

2) Du står i repo-root (mappen som inneholder `Makefile`).

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

### B4. Test at API-key fungerer
Kjør:

    AGINGOS_API_KEY="DIN_HEMMELIGE_NØKKEL" make smoke

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

### Hvis noe feiler (generelt)
- Først: se logger
  - Dev: `make logs`
  - Felt: `make field-logs`
- Se etter ERROR/WARN-linjer og kopier ut 20–50 linjer rundt feilen.
- Mer detaljert guide: `docs/ops/logging.md`
