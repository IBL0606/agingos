# Mobile demo: AgingOS Console

## Åpne på mobil

1. Start console lokalt (for eksempel via `docker compose up -d console`).
2. Finn maskinens LAN-IP (f.eks. `192.168.x.y`).
3. Åpne `http://<LAN-IP>:8080/` i mobilnettleser.

## iOS (Add to Home Screen)

1. Åpne Console i Safari.
2. Trykk **Del**.
3. Velg **Legg til på Hjem-skjerm**.
4. Start appen fra hjemskjermen for standalone-visning.

## Android

- **Install app** i Chrome krever normalt HTTPS (eller localhost).
- For demo på LAN uten HTTPS: bruk nettsiden i mobilnettleser.
- Alternativt bruk iOS Add to Home Screen-flyten for standalone-demo.

## Verifikasjon

Kjør:

```bash
curl -I http://localhost:8080/manifest.webmanifest
```

Forventet:

- HTTP 200
- `Content-Type: application/manifest+json` (eventuelt med charset)

Manuell verifisering:

- Åpne siden på mobil og bekreft at riktig ikon vises ved «Legg til på Hjem-skjerm».
- Start fra hjemskjerm og bekreft standalone-opplevelse (uten vanlig browser chrome).


## Notat om PR-opprettelse

- Ikonene er lagt inn som SVG (tekstfiler) i stedet for PNG, fordi PR-verktøyet avviser binærfiler med meldingen «Binærfiler støttes ikke».
