# docs/hw/pilot-bom.md
# Pilot #1 – BOM (Bill of Materials) og begrunnelse

## Formål
Denne BOM-en dekker innkjøp for Pilot #1 basert på besluttet arkitektur:
- RPi/HA fungerer som sensorhub (eksisterende enhet)
- Mini-PC kjører AgingOS + PostgreSQL (Docker Compose)
- Sensorpakke er valgt for informasjonsverdi til AgingOS og lav driftsfriksjon

## Kort begrunnelse
- **FP2 (stue/kjøkken):** multi-zone der det gir reell verdi (åpent areal).
- **FP300 (øvrige rom):** batteridrevet, kombinert presence + miljø (reduserer antall sensorer og kabling).
- **Zigbee Door/Window:** stabilt, lavt strømforbruk, én radiostack (Zigbee) for dør-signaler.
- **Assist-knapp:** eksplisitt bruker-initiert event (logging/software), gir høy forklaringsverdi.
- **Mini-PC + UPS:** skiller produktlaget (AgingOS/DB) fra HA og øker driftsstabilitet.

## Innkjøpsliste (Pilot #1)

### A) Compute og drift
1) **Mini-PC (x86)** – 1 stk
   - Intel N100/N150
   - 16 GB RAM
   - 512 GB SSD
   - Bruk: AgingOS + Postgres (Docker Compose)

2) **UPS** – 1 stk
   - 650 VA-klasse (eller tilsvarende)
   - Bruk: beskytte mini-PC mot strømblipp for å redusere DB/FS-korrupsjon

3) **Ekstern SSD (backupdisk)** – 1 stk
   - 1 TB
   - Bruk: pg_dump/backups + eksport/artefakter

4) **Ethernet Cat6** – 1–2 stk
   - Mini-PC bør stå kablet.

### B) Sensorer
5) **Aqara FP2** – 1 stk
   - Plassering: stue/kjøkken

6) **Aqara FP300** – 4 stk
   - Plassering: gang, bad, soverom 1, soverom 2
   - Merk: aktiveres i bølger

7) **Aqara Temperature/Humidity T1** – 1 stk
   - Plassering: stue/kjøkken
   - Begrunnelse: stue/kjøkken har FP2 (uten miljømåling i samme grad som FP300-pakken i pilot)

8) **Aqara Door/Window Sensor (Zigbee)** – 3 stk
   - Plassering: inngangsdør, baderomsdør, balkongdør

9) **Aqara Wireless Mini Switch** – 1 stk
   - Bruk: assist-knapp (logging/software)

### C) Zigbee radio (hvis ikke allerede på plass)
10) **Zigbee USB-dongle** – 1 stk
    - Plasseres på RPi (HA)
11) **USB-forlenger** – 1 stk
    - Anbefalt for bedre radioforhold (flytte dongle bort fra støy)

### D) Batterier og småmateriell
- FP300: CR2450 (2 per enhet) + reserve
- Door/Window: batteritype iht. produkt
- Mini Switch: batteritype iht. produkt
- T1: CR2032 + reserve
- Festemateriell (tape/skruer) ved behov

## Eksisterende utstyr (forutsetninger)
- Raspberry Pi med Home Assistant (i dag på SD, planlagt oppgradert til SSD)
- Router/switch med LAN-tilkobling der mini-PC skal stå
- Stabil strømforsyning til RPi

## Aktiveringsplan (bølger)
- **Bølge 0:** Infrastruktur/pipeline
- **Bølge 1:** FP2 stue/kjøkken + 3 dører + assist + FP300 bad
- **Bølge 2:** FP300 gang + FP300 soverom 1
- **Bølge 3:** FP300 soverom 2

## Notater / beslutninger
- Soveromsdører står normalt åpne → dørkontakt på soverom er utelatt.
- Balkongdør er inkludert pga. høy informasjonsverdi (sikkerhet/kontekst).
- Aqara-app aksepteres som serviceverktøy for oppsett, ikke som runtime-krav.
