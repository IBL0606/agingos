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
Postgres uses `timestamp with time zone` (`timestamptz`) for time columns.

- The API receives and returns timezone-aware UTC timestamps.
- The application passes UTC-aware datetimes directly to the DB driver.
- Comparisons and ordering in SQL are done on instants in time.


## Naive vs aware rules
- **Naive** datetime: no timezone info (`tzinfo=None`). Not allowed in API input.
- **Aware** datetime: has timezone info. Required for API input and used for API output.

