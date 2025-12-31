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
