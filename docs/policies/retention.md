# Data retention policy (AgingOS)

## Formål
Denne policyen definerer hvor lenge data beholdes i databasen, hva som kan slettes, og hvorfor.
Målet er å ha en forutsigbar default for feltpilot og en enkel måte å endre på senere uten å endre kode.

## Omfang
Gjelder følgende tabeller/data:
- `events` (rå events inn til systemet)
- `deviations` (persisterte avvik i OPEN/ACK/CLOSED)

Policyen gjelder både lokal utvikling og feltpilot med samme database-modell.

## Policy (minstekrav)

### Events
- **Default:** `events` beholdes i 30 dager.
- **Hvorfor:** hendelser er voluminøse og brukes primært til feilsøking/verifisering og kortsiktig analyse.

### Deviations
- **Default:** `deviations` beholdes i 180 dager.
- **Hvorfor:** avvik representerer hendelser av operasjonell betydning og er typisk lavere volum enn events.

### Backups
- Backups (`./backups/`) er lokale operatør-artefakter og omfattes ikke av automatisk sletting i applikasjonen.

## Hva er ikke implementert (per nå)
Denne repo-versjonen dokumenterer policyen, men har ikke en innebygd “retention job” som sletter data automatisk.
Sletting må derfor gjøres manuelt inntil det eventuelt bygges en egen jobb/kommando.

## Manuell sletting (operasjonelt)
Hvis du må slette data manuelt i feltpilot/utvikling:

### Slett gamle events (eksempel)
Bytt ut `<DAYS>` med antall dager du vil beholde (f.eks. 30):

```sql
DELETE FROM events
WHERE timestamp < (NOW() AT TIME ZONE 'utc') - INTERVAL '<DAYS> days';
```
### Slett gamle CLOSED deviations (eksempel)
Behold aktive avvik (OPEN/ACK). Bytt ut `<DAYS>` (f.eks. 180):

```sql
DELETE FROM deviations
WHERE status = 'CLOSED'
  AND last_seen_at < (NOW() AT TIME ZONE 'utc') - INTERVAL '<DAYS> days';
```

### Kjøring (lokalt) kan gjøres slik:
```bash
docker compose exec -T db psql -U agingos -d agingos -c "<SQL_HER>"
```
## Endringer
Hvis retention-default skal endres, skal følgende oppdateres samtidig:
- denne policyen (docs/policies/retention.md)
- README-seksjonen “Retention default + hvordan endre”
