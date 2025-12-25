# DB backup/restore (lokal)

## Formål
Gi en enkel og robust lokal prosedyre for å ta backup og restore av Postgres-databasen som kjører i `docker compose`, slik at feltpilot/utvikling kan:
- gjenopprette en kjent tilstand
- dele en reproduksjon (backup-fil) ved behov

## Hvor backup lagres
Backuper lagres i repo-root under:
- `./backups/`

Filnavn-format:
- `agingos_<UTC-timestamp>.sql` (UTC, f.eks. `agingos_20251225T120000Z.sql`)

## Backup (happy path)
Forutsetninger:
- `docker compose`-stacken kjører (`make up`)
- db-service heter `db` (som i `docker-compose.yml`)
- database: `agingos`, bruker: `agingos`

Kjør:
```bash
make backup-db
```
Forventet resultat:
- ny fil i ./backups/
- kommandoen skriver ut hvilken fil som ble laget

## Restore (happy path)

VIKTIG:
- Restore overskriver data i databasen (det du restore’r inn erstatter nåværende state).
- `make restore-db` resetter schema ved å kjøre `DROP SCHEMA public CASCADE; CREATE SCHEMA public;` før restore.


1. Finn ønsket backup-fil:
```bash
ls -1 backups
```
2. Restore fra fil:
```bash
make restore-db FILE=backups/<din_fil>.sql
```
Forventet resultat:
- psql returnerer uten feil
- data i DB samsvarer med backup

## Verifikasjon (minimum)
Etter restore, verifiser at DB svarer og at tabeller finnes:
1. List tabeller:
```bash
docker compose exec -T db psql -U agingos -d agingos -c "\dt"
```
2. Sample counts (tilpass ved behov):
```bash
docker compose exec -T db psql -U agingos -d agingos -c "select count(*) as events from events;"
docker compose exec -T db psql -U agingos -d agingos -c "select count(*) as deviations from deviations;"
```
## Failure modes / feilsøking
- docker compose exec ... feiler: sjekk at stacken kjører (make up) og at db-service er oppe.
- Auth/DB-navn feil: verifiser docker-compose.yml (bruker, passord, db).
- Restore feiler midt i: backup-filen kan være korrupt eller ufullstendig. Prøv en annen fil og verifiser at make backup-db fullfører uten feil.
- Du vil se tilgjengelige backuper:
    - make restore-db uten FILE=... lister tilgjengelige filer og viser korrekt usage.

## Dokumentasjon
Kommandoer og “happy path” står i README.md.
Detaljer, verifikasjon og feilsøking står i denne filen: docs/ops/backup-restore.md.

