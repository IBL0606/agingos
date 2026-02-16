
## Backup/Restore Procedure for AgingOS

### Backup

1. **Formål**: Sikre at databasen kan gjenopprettes til en tidligere tilstand.
2. **Kommando**:
```bash
make backup-db
```

**Forventet resultat**:
- En ny fil lagres i `./backups/`-mappen med navnet `agingos_<UTC-timestamp>.sql`.
- For eksempel: `agingos_20260208T090620Z.sql`.

**Valgfritt**: Sjekk de siste backup-filene:
```bash
ls -lh backups | tail -n 5
```

### Restore

1. **Formål**: Gjenopprette databasen fra en tidligere backup og tilbakestille systemet til ønsket tilstand.
2. **Kommando**:
```bash
make restore-db FILE=backups/agingos_<timestamp>.sql
```

**Forventet resultat**:
- Restore vil resettere databasen og gjenopprette den fra backup-filen. Det inkluderer å fjerne eksisterende data og gjenopprette tabeller og data fra filen.

**Verifikasjon etter restore**:

1) **DB Counts** (for å sammenligne med før-restore tilstand):
```bash
docker compose exec -T db psql -U agingos -d agingos -c "
select
  (select count(*) from events) as events,
  (select count(*) from episodes) as episodes,
  (select count(*) from deviations) as deviations,
  (select count(*) from proposals) as proposals,
  (select count(*) from monitor_modes) as monitor_modes;"
```
Forventede resultater:
```
events    | 11332
episodes  | 400
deviations| 44
proposals | 8
monitor_modes | 3
```

2) **API Health**:
```bash
BASE=http://127.0.0.1:8080
KEY=dev-key-2
curl -fsS -H "X-API-Key: " "/api/health" && echo
curl -fsS -H "X-API-Key: " "/api/ai/status" && echo
curl -fsS -H "X-API-Key: " "/api/proposals/miner_status" && echo
```
**Forventet resultat**:
- API status **OK**
- AI status **enabled** og **reachable**
- Proposals status viser ingen feil, og siste kjøring er vellykket.

### Feilsøking / Failure Modes

1. **Feil ved `docker compose exec ...`**:
- Sjekk at alle relevante containere kjører:
```bash
docker compose ps
```
- Se logger for eventuelle feil:
```bash
docker compose logs -f
```

2. **Restore feiler**:
- Hvis restore feiler, kan det skyldes en korrupt backup-fil. Forsikre deg om at `make backup-db` ble fullført uten feil før restore.
- Hvis restore pågår, men feiler underveis, kan du prøve å bruke en annen backup-fil.

3. **Restore overskriver data**:
- Merk at restore-skriptet **resetter databasen** og overskriver alle eksisterende data. Det er viktig å ha en ny backup tilgjengelig før restore hvis du er usikker på filens integritet.

### Oppdaterte Backup/Restore Bevis

**Backup-filen**: `backups/agingos_20260208T090620Z.sql`
- Filstørrelse: 3,3MB
- Backup ble laget med `make backup-db` og lagret i `./backups/`.

**DB counts** før og etter restore er konsistente (se resultatene fra verifikasjon ovenfor).

**API-status** etter restore:
- API returnerte **OK**
- Alle endepunkter svarte som forventet
# DB backup/restore (lokal)

## Formål
Dette er en enkel og robust oppskrift for å ta backup og restore av Postgres-databasen som kjører i Docker Compose, slik at du kan:
- gjenopprette en kjent tilstand
- dele en backup-fil ved behov

For en komplett “steg-for-steg” oppskrift (inkl. oppstart/stopp), se:
- `docs/ops/runbook.md`

---

## Hvor backup lagres
Backuper lagres i repo-root under:
- `./backups/`

Filnavn-format:
- `agingos_<UTC-timestamp>.sql` (UTC, f.eks. `agingos_20251225T120000Z.sql`)

---

## Backup (happy path)
Forutsetning:
- Systemet må kjøre (enten `make up` eller `make field-up`).

Kjør:

    make backup-db

Forventet resultat:
- Det kommer en ny fil i `./backups/`
- Kommandoen skriver normalt ut hvilken fil som ble laget

Valgfritt: se siste backupfiler:

    ls -lh backups | tail

---

## Restore (happy path)
VIKTIG:
- Restore overskriver databasen (det du restore’r inn erstatter nåværende state).
- `make restore-db` resetter schema før restore (DROP/CREATE), så dette er ment som en “start på nytt fra backup”.

Forutsetning:
- Systemet må kjøre (db må være oppe). Start med `make up` eller `make field-up`.

1) Finn ønsket backup-fil:

    ls -1 backups

2) Restore fra fil (velg en ekte fil fra lista):

    make restore-db FILE=backups/<din_fil>.sql

Forventet resultat:
- Kommandoen fullfører uten feil
- Data i databasen samsvarer med backup

Anbefaling:
- Hvis du er usikker: ta en ny backup først (`make backup-db`) før du restore’r.

---

## Verifikasjon (minimum)
Etter restore kan du sjekke at databasen svarer og at tabeller finnes.

1) List tabeller:

    docker compose exec -T db psql -U agingos -d agingos -c "\dt"

2) Enkle “telleprøver” (kan feile hvis tabellene ikke finnes i din versjon – da er det i seg selv et signal):

    docker compose exec -T db psql -U agingos -d agingos -c "select count(*) as events from events;"
    docker compose exec -T db psql -U agingos -d agingos -c "select count(*) as deviations from deviations;"

---

## Failure modes / feilsøking
- “docker compose exec …” feiler:
  - Sjekk at stacken kjører: `make up` (dev) eller `make field-up` (felt)
  - Sjekk logger: `make logs` eller `make field-logs`

- Restore feiler midt i:
  - Backup-filen kan være korrupt/ufullstendig. Prøv en annen fil.
  - Verifiser at `make backup-db` fullfører uten feil.

- Du husker ikke riktig FILE=…:
  - Kjør `make restore-db` uten `FILE=...` for å se usage og hvilke filer som finnes i `./backups/`.

---

## Dokumentasjon
- “Steg-for-steg for amatører”: `docs/ops/runbook.md`
- Detaljer/verifikasjon/feilsøking: denne filen (`docs/ops/backup-restore.md`)
