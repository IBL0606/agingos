# Security minimum (feltpilot) — AgingOS

## Hurtigguide (30 sek)
API-key er et hemmelig passord som Home Assistant (HA) må sende med hver event.

1) Sett nøkkel i `.env` (repo-root):
   
    AGINGOS_AUTH_MODE=api_key
    AGINGOS_API_KEYS=DIN_HEMMELIGE_NØKKEL

2) Start feltprofil:

    make field-up

3) HA får lov til å poste events når den sender headeren:

    X-API-Key: DIN_HEMMELIGE_NØKKEL

Bytte nøkkel (rotasjon, kort):
- Sett begge: `AGINGOS_API_KEYS=GAMMEL,NY` → restart backend
- Bytt HA til NY
- Fjern GAMMEL → restart backend

Viktig:
- Ikke legg nøkkelen i git, README eller logger.

---

## Formål
Etablere et minimum av tilgangskontroll før feltpilot/reell bruk, uten tung IAM.

Dette dokumentet beskriver:
- valgt mekanisme
- hvordan den settes opp (how to set)
- rotasjon (key rotation)

## Valgt mekanisme: API key i header (X-API-Key)

Klient må sende en API key i HTTP-header:
- `X-API-Key: <key>`

Backend validerer at nøkkelen finnes i en tillatt liste konfigurert via environment variables.

## Konfigurasjon (how to set)

### Environment variables
- `AGINGOS_AUTH_MODE=api_key|off`
  - `api_key`: krev API key
  - `off`: ingen auth (kun lokal dev)

- `AGINGOS_API_KEYS=<key1>,<key2>,...`
  - Komma-separert liste over gyldige nøkler (støtter overlapp ved rotasjon)

### Minimumskrav
- Feltpilot/produksjon:
  - `AGINGOS_AUTH_MODE=api_key`
  - `AGINGOS_API_KEYS` må være satt med minst én nøkkel

- Lokal utvikling:
  - `AGINGOS_AUTH_MODE=off` kan brukes

## Rotasjon (key rotation)

Anbefalt prosedyre (uten funksjonell nedetid utover restart):

1. Generer ny nøkkel (sterk tilfeldig verdi; minimum 32 bytes).
2. Konfigurer overlapp ved å sette både gammel og ny nøkkel:
   - `AGINGOS_API_KEYS=old_key,new_key`
3. Restart backend.
4. Oppdater klient(er) til å bruke ny nøkkel.
5. Fjern gammel nøkkel fra `AGINGOS_API_KEYS`.
6. Restart backend.

Prinsipper:
- Nøkler skal behandles som secrets (ikke commit, ikke i README, ikke i logger).
- Logger skal aldri skrive `X-API-Key` eller andre autentiseringsdata.

## Operasjonelle minimumstiltak (feltpilot)

- Ikke eksponer API på offentlig internett uten HTTPS og nettverkskontroll (proxy/VPN).
- Sørg for at request-logging ikke logger headers ukritisk.
- Bruk kort rotasjonsvindu og hold antall aktive nøkler lavt.

## Avgrensning
Dette er et minimum og erstatter ikke:
- RBAC/brukerhåndtering
- OAuth/OIDC
- rate limiting / WAF
