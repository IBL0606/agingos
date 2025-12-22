# Status flow test (AgingOS)

## Formål
Denne testen verifiserer statusflyten for persisterte avvik (Avvik v1):

- `OPEN` → `ACK` (bruker markerer sett)
- `ACK` → `CLOSED` via stale-closing (expire)
- Ny trigger etter `CLOSED` oppretter en ny `OPEN` (ny episode)

## Hva testen beviser
- At `ACK` er en aktiv status (ikke “arkiv”), og inngår i livssyklus/expire.
- At `CLOSED` ikke er aktivt avvik.
- At ny trigger etter `CLOSED` gir ny rad (ny episode).

## Hvordan kjøre
Kjør statusflyt-testen slik:

```bash
make statusflow
```

## Hvor testen ligger
- Testfil: `backend/tests/test_status_flow_open_ack_close_reopen.py`

## Forventet resultat
- Kommandoen returnerer exit code 0 (grønn).
- Ved ferdigstillelse føres “grønn status” i Master arbeidslogg.
