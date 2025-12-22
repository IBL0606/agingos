# Event v1 contract

## Fields

### `id`
- Type: UUID
- Meaning: Unique event identifier.

### `timestamp`
- Type: datetime (ISO 8601 string in API)
- Meaning: The instant when the event occurred.

#### Requirements (strict)
- MUST be timezone-aware UTC.
- MUST be ISO 8601 with `Z` or `+00:00`.

Accepted:
- `2025-12-22T10:00:00Z`
- `2025-12-22T10:00:00+00:00`

Rejected:
- `2025-12-22T10:00:00` (no timezone / naive)

### `category`
- Type: string
- Meaning: Event category (e.g. `motion`, `door`).

### `payload`
- Type: object
- Meaning: Category-specific payload.

## API examples

### POST /event (valid)
{"id":"00000000-0000-0000-0000-000000000002","timestamp":"2025-12-22T10:00:00Z","category":"motion","payload":{}}

### POST /event (invalid – naive timestamp)
{"id":"00000000-0000-0000-0000-000000000001","timestamp":"2025-12-22T10:00:00","category":"motion","payload":{}}
