# Time and timezone policy (UTC)

## Policy: everything is UTC
All timestamps in AgingOS represent an instant in time and MUST be handled as UTC end-to-end.

This means:
- API input timestamps MUST be timezone-aware and in UTC (ISO 8601 with `Z` or `+00:00`).
- API output timestamps MUST be serialized as timezone-aware UTC (ISO 8601 with `Z`/`+00:00`).
- Internal rule evaluation uses UTC.
- Query windows use the contract `[since, until)` where `since` is inclusive and `until` is exclusive.

## Input requirements (strict)
A timestamp is rejected if it is “naive” (missing timezone information).

Accepted examples:
- `2025-12-22T10:00:00Z`
- `2025-12-22T10:00:00+00:00`

Rejected examples:
- `2025-12-22T10:00:00` (no timezone)

## Database note (current implementation)
The current Postgres schema uses `timestamp without time zone` for time columns. To keep the system consistent while enforcing strict UTC at the API boundary:
- Incoming UTC-aware timestamps are validated and then stored as **naive UTC** (timezone removed) in the database.
- When reading from the database, naive timestamps are interpreted as **UTC**.

This is a temporary adapter until the schema is migrated to `timestamp with time zone` (`timestamptz`).

## Naive vs aware rules
- **Naive** datetime: no timezone info (`tzinfo=None`). Not allowed in API input.
- **Aware** datetime: has timezone info. Required for API input and used for API output.

