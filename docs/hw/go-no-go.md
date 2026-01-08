# HW readiness – Go/No-Go (Pilot #1) – brutalt konkret (T-1001)

Status: **NORMATIVE**  
Formål: Dette dokumentet definerer **binære** kriterier for å avgjøre om vi (a) fortsetter, (b) pauser for å fikse, eller (c) stopper pilot / fryser videre investering.  
**Hvis et punkt feiler, er beslutningen forhåndsdefinert. Ingen diskusjon.**

Sporbarhet:
- Beslutning logges i `docs/project/master-log.md` (dato + status + begrunnelse + lenker)

Grunnlag:
- Runbook (oppskrifter/verifisering): `docs/ops/runbook.md`
- Backup/restore (detaljer): `docs/ops/backup-restore.md`
- Longrun-simulering: `docs/ops/longrun-sim.md`
- Stopp-kriterier (overordnet): `docs/project/stop-criteria.md`
- Event-kontrakt: `docs/contracts/event-v1.md`
- HA→Event mapping: `docs/mapping/sensor-event-mapping.md`, `docs/mapping/ha-mini-plan-p1.md`

---

## 0) Definisjoner (brukes i beslutningen)

- **GO** = Vi kan fortsette til neste bølge / utvide pilot-scope.
- **NO-GO (PAUSE)** = Vi pauser utvidelse. Vi kan ha HW stående, men **ingen nye sensorer/rom** før avviket er lukket og re-verifisert.
- **NO-GO (STOP)** = Vi stopper pilot og fryser videre investering. Ikke gå videre før det foreligger en ny plan (arkitektur/kontrakt/implementasjon).

---

## 1) Beslutningsregel (ingen diskusjon)

1. Hvis **én** STOP-trigger (S*) er true → **NO-GO (STOP)**.
2. Ellers, hvis **én** PAUSE-trigger (P*) er true → **NO-GO (PAUSE)**.
3. Ellers, hvis alle MUST-PASS (M*) er grønne → **GO**.

---

## 2) STOP-triggere (S*) – stopper pilot / fryser videre investering

Dette er “hard fails” som betyr at pilot ikke er trygg/nyttig å fortsette med.

- **S1 Data-tap:** `POST /event` returnerer 2xx, men event finnes ikke i DB etterpå (eller forsvinner etter restart).
- **S2 Uautorisert eksponering:** AgingOS er tilgjengelig fra Internett eller fra uønsket nettsegment (brudd på perimeter/ACL).
- **S3 Kontraktsbrudd:** Event v1-kontrakten er ikke konsistent (felt mangler/endres) slik at downstream-regler/evaluering blir upålitelig.
- **S4 Tidsfeil som ødelegger logikk:** timestamps lagres/pars(es) ikke som UTC timezone-aware, eller regelvindu oppfører seg inkonsistent på samme input.
- **S5 Stabilitet:** Backend-containeren crasher/restarter gjentatte ganger (≥3 restarts i løpet av 24h) uten at det er en kjent/akseptert root cause med mitigering.
- **S6 Driftssikkerhet:** Backup/restore kan ikke gjennomføres etter dokumentert prosedyre (backup feiler, eller restore gir ikke samme data tilbake).

---

## 3) PAUSE-triggere (P*) – pause utvidelse, fikse først

Dette er “soft fails” som normalt er løsbart, men som må lukkes før vi utvider scope.

- **P1 Nettverk/tilgang:** RPi kan ikke nå mini-PC på forventet måte (routing, brannmur, DNS/IP), men det er en ren konfig-/infra-feil.
- **P2 Observability mangler:** Vi kan ikke verifisere ingest, feil og DB-status på 5 minutter (mangler logs/kommandoer/runbook).
- **P3 Støy/volum:** Event-strøm er så noisy at logs/DB vokser ukontrollert (f.eks. spam fra noisy entity) og det finnes ikke ekskludering/rate-limit.
- **P4 Funktionell inkonsistens:** Enkelte sensorer trigger ikke som forventet (feil entity_id, mapping, HA-automatisering), men selve backend/kontrakt er OK.
- **P5 Latency/ytelse:** Responstid på `POST /event` eller evaluering er merkbart treg i normal bruk (indikasjon på behov for tuning/ressurser).

---

## 4) MUST-PASS (M*) – hva som må fungere for å fortsette

**Regel:** Et MUST-PASS som feiler gir minst **NO-GO (PAUSE)**. Hvis feilen også treffer en STOP-trigger, blir beslutningen **NO-GO (STOP)**.

> **Oppskrifter/kommandoer:** Alle verifikasjoner (M1–M8) har copy/paste-oppskrifter i `docs/ops/runbook.md` (seksjon **E**).
> Go/No-Go eier terskler og konsekvens; runbook eier “hvordan”.

### M1 Nettverk og health (RPi → mini-PC)
- **Pass:** `GET /health` gir `200` **10/10** ganger fra riktig klient (RPi/LAN-segment).
- **Fail:** P1 → **NO-GO (PAUSE)** (med mindre eksponert mot Internett → S2 → **NO-GO (STOP)**).
- Verifisering: Runbook §E1 (M1).

### M2 Feltprofil kan startes deterministisk
- **Pass:** `make field-up` fullfører uten feil; DB blir “ready”; migrasjoner kjører; backend er oppe.
- **Fail:** **NO-GO (PAUSE)**. Hvis det innebærer gjentatte crashes/restarts → S5 → **NO-GO (STOP)**.
- Verifisering: Runbook §E2 (M2).

### M3 Ingest fungerer ende-til-ende (HTTP → persist i DB)
- **Pass:** Smoke-test passerer og DB viser at events faktisk er lagret (count > 0 etter smoke).
- **Fail:** **NO-GO (STOP)** hvis data-tap (S1) eller kontraktsbrudd (S3). Ellers **NO-GO (PAUSE)**.
- Verifisering: Runbook §E3 (M3).

### M4 Kontrakten håndheves (bad input avvises)
- **Pass:** Ugyldig request mot `POST /event` gir 4xx (typisk 422), og DB endres ikke.
- **Fail:** **NO-GO (STOP)** (S3).
- Verifisering: Runbook §E4 (M4).

### M5 Persistens over restart
- **Pass:** Event-data finnes fortsatt etter `field-down` → `field-up` (DB-count er fortsatt > 0 / forventet).
- **Fail:** **NO-GO (STOP)** (S1).
- Verifisering: Runbook §E5 (M5).

### M6 Regelflyt/evaluering er kjørbar og stabil
- **Pass:** `make scenario-reset` + `make scenario` fullfører deterministisk og gir forventet resultat.
- **Fail:** **NO-GO (PAUSE)**. Hvis feilen skyldes tidsfeil/UTC-problemer → S4 → **NO-GO (STOP)**.
- Verifisering: Runbook §E6 (M6).

### M7 Backup/restore er bevist
- **Pass:** `make backup-db` lager fil, og `make restore-db` gir forventet data tilbake (minst “events finnes igjen”).
- **Fail:** **NO-GO (STOP)** (S6).
- Verifisering: Runbook §E7 (M7).

### M8 Perimeter/tilgang er riktig
- **Pass:** Port 8000 kan nås fra forventet klient/segment (RPi/LAN) og **ikke** fra uønskede klienter/segment/Internett.
- **Fail:** **NO-GO (STOP)** hvis eksponert (S2). Ellers **NO-GO (PAUSE)**.
- Verifisering: Runbook §E8 (M8).

---

## 5) Operativ bølgeplan (fortsett kun når forrige bølge er GO)

Dette er praktisk sjekkliste for installasjonssekvens. **Bølge X kan ikke påbegynnes før M1–M8 er GO og forrige bølge er verifisert.**

### Bølge 0 – Infrastruktur (GO)
- [ ] `make field-up` er oppe på mini-PC
- [ ] Brannmur/ACL: kun forventede klienter (minst RPi/LAN) → 8000
- [ ] Smoke er grønn mot `BASE_URL=http://<MINIPC>:8000`
- [ ] Ingest kan verifiseres (logs/DB) på ≤5 minutter (observability)

### Bølge 1 – Kjerne (GO)
- [ ] FP2 (stue/kjøkken): kun transitions (presence) kommer inn i AgingOS
- [ ] Ytterdør: open/close kommer inn (stabil `entity_id`)
- [ ] Assist-event kommer inn (knapp eller simulert)
- [ ] FP300 (bad): presence + environment kommer inn iht. mapping
- [ ] Stabilitet: **24h** uten crash/restarts og uten “manglende event” ved reelle triggere

### Bølge 2 – Dekning (GO)
- [ ] FP300 (gang) og (soverom 1) inn
- [ ] Stabilitet: **48h** uten crash/restarts og uten ukontrollert støy
- [ ] Støy håndtert (exclude/noisy entities / rate-limit dokumentert)

### Bølge 3 – Full dekning (valgfritt)
- [ ] FP300 (soverom 2) inn
- [ ] Stabilitet: **72h**
- [ ] “Known issues” dokumentert med mitigering

---

## 6) Go/No-Go – beslutningsseksjon (fylles ut ved vurdering)

### Go/No-Go status
- Status: **GO / NO-GO (PAUSE) / NO-GO (STOP)**
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

## 7) Kontinuitet (hvis NO-GO)

Hvis status er NO-GO:
- [ ] Liste over blockers (konkrete feil + repro)
- [ ] Hvilken trigger slo inn (S* / P* / M*) og hvorfor
- [ ] Plan for lukking (eier + dato)
- [ ] Ny vurderingsdato
