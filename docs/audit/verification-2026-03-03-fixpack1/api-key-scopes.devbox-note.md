# Devbox: api_key_scopes mappings (observed)

Observed rows in `public.api_key_scopes` (devbox):

- `966c44be82076d2c2ad29390d50c34034a35056007f29606f6457b02af023402` = sha256("dev-key-2") — ACTIVE, scope=default/default/default, role=operator.
- `__HASH__` — ACTIVE (placeholder row created by operator error; does not correspond to a real API key).
- `aaaaaaaa...` — ACTIVE (legacy/unknown devbox row).

Policy: **no data deletion** in this fixpack. Rows are documented as-is. Only the sha256("dev-key-2") mapping is expected to be used for devbox API calls.
