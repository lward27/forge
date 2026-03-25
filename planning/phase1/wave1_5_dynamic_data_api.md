# Wave 1.5 — Dynamic Data API (CRUD)

> Parent: [Master Plan](../master_plan.md)
> Depends on: [Wave 1.4 — Schema Management](wave1_4_schema_management.md) (complete)
> Goal: Any table created via the DDL API can immediately be read/written via REST.

---

## Overview

Add generic CRUD endpoints that operate on any tenant table. Rather than generating per-table code, these endpoints use the schema definitions stored in the platform metadata DB (from Wave 1.4) to dynamically validate input and construct SQL queries. This is the core "low-code" capability — define a table, immediately get a working API.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `.../{table}/rows` | Insert a row |
| `GET` | `.../{table}/rows` | List rows (with filtering, sorting, pagination) |
| `GET` | `.../{table}/rows/{pk}` | Get a single row by primary key |
| `PUT` | `.../{table}/rows/{pk}` | Update a row |
| `DELETE` | `.../{table}/rows/{pk}` | Delete a row |
| `POST` | `.../{table}/rows/batch` | Bulk insert rows |

Full path prefix: `/tenants/{tid}/databases/{did}/tables/{table}`

### Request/Response Models

#### `POST .../{table}/rows`
```json
// Request — field names match column names
{
  "name": "Alice",
  "email": "alice@example.com",
  "is_active": true
}

// Response (201)
{
  "id": 1,
  "name": "Alice",
  "email": "alice@example.com",
  "is_active": true
}
```

#### `GET .../{table}/rows`
```
Query params:
  ?limit=20            (default 20, max 100)
  ?offset=0            (default 0)
  ?sort=name           (column name, prefix with - for desc: -name)
  ?filter=is_active:eq:true
  ?filter=name:like:Ali%

// Response (200)
{
  "rows": [
    {"id": 1, "name": "Alice", "email": "alice@example.com", "is_active": true},
    {"id": 2, "name": "Bob", "email": "bob@example.com", "is_active": false}
  ],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

#### `GET .../{table}/rows/{pk}`
```json
// Response (200)
{
  "id": 1,
  "name": "Alice",
  "email": "alice@example.com",
  "is_active": true
}
```

#### `PUT .../{table}/rows/{pk}`
```json
// Request — partial update (only fields provided are updated)
{
  "email": "alice.new@example.com"
}

// Response (200)
{
  "id": 1,
  "name": "Alice",
  "email": "alice.new@example.com",
  "is_active": true
}
```

#### `DELETE .../{table}/rows/{pk}`
```json
// Response (200)
{
  "id": 1,
  "deleted": true
}
```

#### `POST .../{table}/rows/batch`
```json
// Request
{
  "rows": [
    {"name": "Alice", "email": "alice@example.com", "is_active": true},
    {"name": "Bob", "email": "bob@example.com", "is_active": true}
  ]
}

// Response (201)
{
  "inserted": 2,
  "rows": [
    {"id": 1, "name": "Alice", "email": "alice@example.com", "is_active": true},
    {"id": 2, "name": "Bob", "email": "bob@example.com", "is_active": true}
  ]
}
```

---

## Filter Syntax

Filters use a simple `column:operator:value` format passed as query parameters:

| Operator | SQL | Example |
|----------|-----|---------|
| `eq` | `=` | `?filter=is_active:eq:true` |
| `neq` | `!=` | `?filter=status:neq:deleted` |
| `gt` | `>` | `?filter=age:gt:18` |
| `gte` | `>=` | `?filter=balance:gte:100.00` |
| `lt` | `<` | `?filter=age:lt:65` |
| `lte` | `<=` | `?filter=balance:lte:1000.00` |
| `like` | `LIKE` | `?filter=name:like:Ali%` |
| `in` | `IN` | `?filter=status:in:active,pending` |
| `isnull` | `IS NULL` | `?filter=phone:isnull:true` |

Multiple `?filter=` params are ANDed together.

---

## Input Validation

The platform validates all input against the stored column definitions:

- **Unknown columns** are rejected (400)
- **Non-nullable columns** without defaults must be provided on INSERT (400)
- **Type coercion**: values are cast to the column's PG type; invalid casts return 400
- **Unique constraint violations** return 409
- **The `id` column** is never accepted in INSERT/UPDATE payloads (auto-generated)

---

## Implementation

### Query Execution

All data queries execute against the **tenant's database** using the `postgres` superuser connection (same pattern as Wave 1.4 DDL). Queries are constructed dynamically using `psycopg2.sql` for safe identifier/value handling.

### New/Modified Files

```
platform/src/forge_platform/
├── routers/
│   └── rows.py                  (new: CRUD endpoints)
├── schemas/
│   └── row.py                   (new: request/response models)
├── services/
│   ├── row_service.py           (new: business logic + validation)
│   └── postgres_service.py      (update: add DML methods)
├── app.py                       (update: include rows router)
```

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Query builder | `psycopg2.sql` with dynamic construction | Safe parameterized queries; no ORM overhead for dynamic tables |
| Validation source | Platform metadata DB (`column_definition`) | Single source of truth; already populated by Wave 1.4 |
| Response format | Plain JSON dicts (not typed models) | Columns are dynamic; can't use static Pydantic models |
| Partial updates | PUT with partial body | Simpler than PATCH; only provided fields are SET |
| Pagination | `limit` + `offset` with `total` count | Standard REST pattern; total enables UI pagination |
| Batch insert | Single transaction | All-or-nothing; fail fast on first error |
| Filter parsing | Custom `column:op:value` syntax | Simple, URL-friendly, covers common query patterns |
| Connection per request | Open/close per request from pool | Keeps it simple for Phase 1; connection pooling in Phase 4 |

---

## Error Handling

| Scenario | HTTP Status | Response |
|----------|-------------|----------|
| Table not found | 404 | `{"detail": "Table not found"}` |
| Row not found | 404 | `{"detail": "Row not found"}` |
| Unknown column in body | 400 | `{"detail": "Unknown column 'foo'. Valid columns: ..."}` |
| Missing required column | 400 | `{"detail": "Column 'name' is required (not nullable, no default)"}` |
| Type validation failure | 400 | `{"detail": "Invalid value for column 'age' (integer): 'abc'"}` |
| Unique constraint violation | 409 | `{"detail": "Duplicate value for unique column 'email'"}` |
| Invalid filter syntax | 400 | `{"detail": "Invalid filter: ..."}` |
| Invalid sort column | 400 | `{"detail": "Cannot sort by 'foo'. Valid columns: ..."}` |

---

## Acceptance Criteria

- [ ] `POST .../rows` inserts a row and returns it with auto-generated `id`
- [ ] `POST .../rows` validates required (non-nullable, no default) columns
- [ ] `POST .../rows` rejects unknown columns
- [ ] `POST .../rows` rejects `id` in request body
- [ ] `POST .../rows` returns 409 on unique constraint violation
- [ ] `GET .../rows` returns paginated results with `total`, `limit`, `offset`
- [ ] `GET .../rows` supports `?sort=column` and `?sort=-column`
- [ ] `GET .../rows` supports `?filter=column:op:value` for all operators
- [ ] `GET .../rows` supports multiple filters (ANDed)
- [ ] `GET .../rows/{pk}` returns a single row
- [ ] `GET .../rows/{pk}` returns 404 for nonexistent row
- [ ] `PUT .../rows/{pk}` partial updates only provided fields
- [ ] `PUT .../rows/{pk}` returns 404 for nonexistent row
- [ ] `DELETE .../rows/{pk}` removes the row
- [ ] `DELETE .../rows/{pk}` returns 404 for nonexistent row
- [ ] `POST .../rows/batch` inserts multiple rows in a single transaction
- [ ] All SQL uses parameterized queries (no injection)
- [ ] Unit tests for row service, validation, and filter parsing

---

## Security Notes

- All identifiers (table names, column names) are quoted via `psycopg2.sql.Identifier`
- All values are parameterized via `psycopg2.sql.Literal` or `%s` placeholders
- Filter values are parameterized, never interpolated
- The `id` column is read-only (auto-increment)

---

## Phase 1 Completion

With Wave 1.5 complete, the Phase 1 foundation is done:
- **1.1** Platform bootstrap (API + DB)
- **1.2** Tenant management (namespaces)
- **1.3** Database provisioning (PG databases)
- **1.4** Schema management (tables/columns)
- **1.5** Dynamic data API (CRUD)

A user can create a tenant, provision a database, define tables, and immediately read/write data — all through REST APIs. This is the "low-code database" core that Phase 2 (code generation) and Phase 3 (AI interface) build on.

---

## Next Phase

→ [Phase 2 — Code Generation & Deployment Pipeline](../../master_plan.md#phase-2--code-generation--deployment-pipeline)
