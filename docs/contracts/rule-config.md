# Rule config (AgingOS) — v1

## Formål
Samle alle runtime-parametre for scheduler og regler (lookback, expire, terskler og tidsvinduer) i én struktur per regel, slik at slike verdier ikke hardkodes i regelkode.

## Kilde til sannhet
- Denne configen er “source of truth” for domeneparametre i regler og scheduler-policy.
- Regelkode skal ikke ha “magiske tall” for tidsvinduer/terskler (f.eks. nattvindu, follow-up minutter) uten at disse kommer fra config.

## Vinduskontrakt
Regler evaluerer events i vinduet **[since, until)**:
- `since` er inklusiv
- `until` er eksklusiv

Dette er implementert i queries i reglene (`timestamp >= since` og `timestamp < until`).

## Felter

### Scheduler (globalt)
| Felt | Type | Default | Effekt |
|---|---|---:|---|
| `scheduler.interval_minutes` | int | 1 | Hvor ofte scheduler kjører (i dag hardkodet til 1 min) |
| `scheduler.default_subject_key` | string | `default` | Default subject_key i persist-flow (hvis brukt) |

### Per regel (`rules.<RULE_ID>`)
| Felt | Type | Default | Effekt |
|---|---|---:|---|
| `enabled_in_scheduler` | bool | per regel (se nedenfor) | Om regelen kjøres i scheduler/persist-flow |
| `lookback_minutes` | int | 60 | Hvor langt tilbake scheduler/persist typisk evaluerer |
| `expire_after_minutes` | int | 60 | Når et OPEN/ACK avvik anses “stale” og kan lukkes hvis ikke sett i nye kjøringer |
| `params` | object | `{}` | Regelspesifikke parametre (terskler/tidsvinduer, kategorier, payload-regler) |

## Default-verdier (sim-baseline-v1)

### Globale defaults
- `lookback_minutes`: 60 (fra `DEFAULT_LOOKBACK_MINUTES`)
- `expire_after_minutes`: 60 (fra `DEFAULT_EXPIRE_AFTER_MINUTES`)
- `scheduler.interval_minutes`: 1 (fra `IntervalTrigger(minutes=1)` i scheduler)

### Scheduler-policy (baseline)
- R-001: **ikke** i scheduler/persist-flow (kun evaluate)
- R-002 og R-003: i scheduler/persist-flow

Dette uttrykkes via `enabled_in_scheduler` per regel.

## Eksempel-konfigurasjon (YAML)

```yaml
scheduler:
  interval_minutes: 1
  default_subject_key: "default"

defaults:
  lookback_minutes: 60
  expire_after_minutes: 60

rules:
  R-001:
    enabled_in_scheduler: false
    lookback_minutes: 60
    expire_after_minutes: 60
    params: {}

  R-002:
    enabled_in_scheduler: true
    lookback_minutes: 60
    expire_after_minutes: 60
    params:
      category: "door"
      payload_state_keys: ["state", "value"]
      trigger_value: "open"
      night_window:
        start_local_time: "23:00:00"
        end_local_time: "06:00:00"

  R-003:
    enabled_in_scheduler: true
    lookback_minutes: 60
    expire_after_minutes: 60
    params:
      door_category: "door"
      motion_category: "motion"
      payload_state_keys: ["state", "value"]
      door_name_keys: ["door", "name"]
      required_door_name: "front"
      door_open_value: "open"
      motion_on_value: "on"
      followup_minutes: 10
