# docs/hw/go-no-go.md
# HW readiness – stoppkriterier og Go/No-Go (T-1001)
> Merk: Dette dokumentet er en stabil sjekkliste/mal. Resultatet av hver Go/No-Go-vurdering (dato, status, commit) logges i Master arbeidslogg. Oppdater denne filen kun når kriteriene endres.


## Formål
Dette dokumentet definerer objektive stoppkriterier før:
1) “Go” for pilotinstallasjon/utvidelse, og
2) eventuelle videre hardware-innkjøp utover Pilot #1.

**Dato og beslutning føres også i Master arbeidslogg for sporbarhet.**

---

## A) Objektive stoppkriterier (må oppfylles)

### 1) Kildekode og CI
- [ ] CI på `main` er grønn (samtlige checks pass) på tidspunkt for go/no-go.
- [ ] Lint/format og smoke/scenario pipeline er verifisert lokalt (samme commit som CI).

### 2) Scenario-/testdekning (minimum)
- [ ] Scenario-runner fungerer lokalt mot docker compose.
- [ ] Minimum **N=6** scenarier er definert og passerer (kan justeres):
  - [ ] “morning routine”
  - [ ] “evening routine”
  - [ ] “night bathroom visit”
  - [ ] “away / no activity”
  - [ ] “balcony door open long”
  - [ ] “assist button pressed”
- [ ] Dokumentert hvor scenarier ligger og hvordan de kjøres (kommandoer + forventet output).

### 3) Drift/observability
- [ ] Runbook for pilot-verifikasjon finnes (nettverk, logs, DB-sjekk, bølgeplan).
- [ ] “Definition of Done” for hver bølge er dokumentert (akzeptkriterier).
- [ ] Scheduler-feil isoleres (exceptions stopper ikke hele scheduler-loop).

### 4) Backup/restore (minimum før pilot)
- [ ] Backup-prosedyre er dokumentert (kommandoer/make-target).
- [ ] Restore er testet (dato + resultat):
  - backup tatt
  - ny tom DB
  - restore gjennomført
  - verifisert at data er tilgjengelig igjen

### 5) Retention og datakilde
- [ ] Beslutning: **AgingOS/DB er system-of-record**.
- [ ] HA Recorder settes til minimal historikk (kort retention + exclude for støy) for feilsøking, ikke primærlagring.
- [ ] Retention-policy for AgingOS er dokumentert (manuell eller automatisk).

### 6) Sikkerhet (pilot-minimum)
- [ ] Mini-PC har fast IP og er på LAN.
- [ ] TCP 8000 er kun tilgjengelig fra RPi (brannmurregel).
- [ ] Event-endepunkt beskyttes iht. pilotstandard (API-key eller nettverksperimeter, minst én av dem).

### 7) HA → AgingOS kontrakt (pilot)
- [ ] Event-format (category/payload/room) er dokumentert og konsistent.
- [ ] Rate-limit/debounce er definert for presence og environment.
- [ ] Det finnes en enkel måte å verifisere at events kommer inn og kan spores per rom/sensor.

---

## B) Go/No-Go – beslutningsseksjon

### Go/No-Go status
- Status: **GO / NO-GO**
- Dato (YYYY-MM-DD):
- Commit hash:
- Sign-off (navn/rolle):

### Avvik / kjente issues ved GO
Liste over aksepterte issues (maks 3–5), med mitigering:
- Issue:
  - Risiko:
  - Mitigering:
  - Owner:
  - Deadline:

---

## C) Minimum “GO”-kriterier per bølge (operativt)
Dette er operativ sjekkliste som brukes ved aktivering.

### Bølge 0 – Infrastruktur/pipeline (GO)
- [ ] Mini-PC: docker compose oppe
- [ ] Brannmur: kun RPi → 8000
- [ ] curl fra RPi til mini-PC fungerer
- [ ] Logging: ingest/requests synlige

### Bølge 1 – Kjerne (GO)
- [ ] FP2 stue/kjøkken events mottas (presence transitions)
- [ ] 3 dørkontakter events mottas (open/close)
- [ ] Assist event mottas
- [ ] FP300 bad: presence + environment mottas
- [ ] Stabilitet: 24h uten “manglende event” ved reelle triggere

### Bølge 2 – Dekning (GO)
- [ ] FP300 gang og soverom 1 inn
- [ ] Stabilitet: 48h
- [ ] Støy håndtert (exclude/noisy entities / rate-limit)

### Bølge 3 – Full dekning (GO, valgfritt)
- [ ] FP300 soverom 2 inn
- [ ] Stabilitet: 72h
- [ ] Dokumenterte “known issues” og mitigering

---

## D) Kontinuitet (hvis NO-GO)
Hvis status er NO-GO:
- [ ] Liste over blockers (konkrete feil + repro)
- [ ] Plan for lukking (eier + dato)
- [ ] Ny vurderingsdato
