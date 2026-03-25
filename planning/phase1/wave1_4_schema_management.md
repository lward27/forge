# Wave 1.4 — Schema Management (DDL API)

> Parent: [Master Plan](../master_plan.md)
> Depends on: [Wave 1.3 — Database Provisioning](wave1_3_database_provisioning.md) (complete)
> Goal: Full DDL management via API — create tables, columns, relationships, constraints.

---

## Overview

Add schema management endpoints that let tenants define tables, columns, and constraints in their provisioned databases. The platform executes DDL statements against the tenant's PG database and tracks all schema definitions in the platform metadata DB — so the system always knows what exists.

This is the "TrackVia-style low-code" foundation: users define their data model through API calls rather than writing SQL.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/tenants/{tid}/databases/{did}/tables` | Create a new table |
| `GET` | `/tenants/{tid}/databases/{did}/tables` | List all tables |
| `GET` | `/tenants/{tid}/databases/{did}/tables/{table}` | Get table details (columns, constraints) |
| `PUT` | `/tenants/{tid}/databases/{did}/tables/{table}` | Alter table (add/drop/modify columns) |
| `DELETE` | `/tenants/{tid}/databases/{did}/tables/{table}` | Drop table |

### Request/Response Models

#### `POST /tenants/{tid}/databases/{did}/tables`
```json
// Request
{
  "name": "customers",
  "columns": [
    {"name": "name", "type": "text", "nullable": false},
    {"name": "email", "type": "text", "nullable": false, "unique": true},
    {"name": "age", "type": "integer", "nullable": true},
    {"name": "balance", "type": "decimal", "nullable": true},
    {"name": "is_active", "type": "boolean", "nullable": false, "default": "true"},
    {"name": "created_at", "type": "timestamp", "nullable": false, "default": "now()"}
  ]
}

// Response (201)
{
  "name": "customers",
  "database_id": "uuid",
  "columns": [
    {"name": "id", "type": "serial", "nullable": false, "primary_key": true},
    {"name": "name", "type": "text", "nullable": false, ...},
    {"name": "email", "type": "text", "nullable": false, "unique": true, ...},
    ...
  ],
  "created_at": "2026-03-25T12:00:00Z"
}
```

**Note:** An `id SERIAL PRIMARY KEY` column is always auto-added. Users don't specify it.

#### `PUT /tenants/{tid}/databases/{did}/tables/{table}`
```json
// Request — add and drop columns in a single call
{
  "add_columns": [
    {"name": "phone", "type": "text", "nullable": true}
  ],
  "drop_columns": ["age"]
}

// Response (200) — returns full updated table definition
```

#### `GET /tenants/{tid}/databases/{did}/tables/{table}`
```json
// Response (200)
{
  "name": "customers",
  "database_id": "uuid",
  "columns": [
    {"name": "id", "type": "serial", "nullable": false, "primary_key": true, "unique": false, "default": null},
    {"name": "name", "type": "text", "nullable": false, "primary_key": false, "unique": false, "default": null},
    {"name": "email", "type": "text", "nullable": false, "primary_key": false, "unique": true, "default": null},
    {"name": "balance", "type": "decimal", "nullable": true, "primary_key": false, "unique": false, "default": null},
    {"name": "is_active", "type": "boolean", "nullable": false, "primary_key": false, "unique": false, "default": "true"},
    {"name": "created_at", "type": "timestamp", "nullable": false, "primary_key": false, "unique": false, "default": "now()"}
  ],
  "created_at": "2026-03-25T12:00:00Z"
}
```

---

## Type Mapping

Simplified types map to PostgreSQL types:

| Platform Type | PG Type | Notes |
|---------------|---------|-------|
| `text` | `TEXT` | Variable-length string |
| `integer` | `INTEGER` | 32-bit integer |
| `biginteger` | `BIGINT` | 64-bit integer |
| `decimal` | `NUMERIC(18,6)` | Fixed precision for money/quantities |
| `boolean` | `BOOLEAN` | true/false |
| `date` | `DATE` | Date only |
| `timestamp` | `TIMESTAMPTZ` | Date + time with timezone |
| `json` | `JSONB` | JSON with indexing support |
| `serial` | `SERIAL` | Auto-incrementing integer (PK only) |

---

## Platform Database Models

### `table_definition` table
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `database_id` | UUID | FK → tenant_database.id |
| `name` | VARCHAR | Table name, unique per database |
| `status` | VARCHAR | `active`, `deleted` |
| `created_at` | TIMESTAMP | Auto-set |
| `updated_at` | TIMESTAMP | Auto-updated |

### `column_definition` table
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `table_id` | UUID | FK → table_definition.id |
| `name` | VARCHAR | Column name |
| `column_type` | VARCHAR | Platform type (text, integer, etc.) |
| `nullable` | BOOLEAN | Default true |
| `primary_key` | BOOLEAN | Default false |
| `unique` | BOOLEAN | Default false |
| `default_value` | VARCHAR | SQL default expression (nullable) |
| `ordinal` | INTEGER | Column order |
| `status` | VARCHAR | `active`, `deleted` |
| `created_at` | TIMESTAMP | Auto-set |

---

## Implementation

### DDL Execution

DDL is executed against the **tenant's database** (not the platform DB) using the tenant's PG role credentials. The platform retrieves the connection info from the K8s Secret (or from the `tenant_database` record + stored credentials).

For simplicity in Phase 1, the platform connects as the `postgres` superuser to the tenant database for DDL. The tenant role owns the database, but CREATE TABLE as superuser then transfers ownership.

Actually, simpler: connect to the tenant DB **as the tenant role** so all objects are automatically owned by the tenant role. The platform retrieves the password from the K8s Secret in the tenant namespace.

**Decision:** Connect as `postgres` superuser to the tenant database. After creating each table, `ALTER TABLE ... OWNER TO {tenant_role}`. This avoids needing to read Secrets back from k8s and keeps the DDL execution path simple. The tenant role will have full ownership of all objects.

### SQL Generation

All DDL is generated using `psycopg2.sql` module for safe identifier quoting. Example for CREATE TABLE:

```sql
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    age INTEGER,
    balance NUMERIC(18,6),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE customers OWNER TO forge_t_demo_app_inventory_role;
```

### New/Modified Files

```
platform/src/forge_platform/
├── models/
│   ├── __init__.py              (update: export new models)
│   ├── table_definition.py      (new)
│   └── column_definition.py     (new)
├── routers/
│   └── tables.py                (new: CRUD endpoints)
├── schemas/
│   └── table.py                 (new: request/response models)
├── services/
│   ├── table_service.py         (new: business logic)
│   └── postgres_service.py      (update: add DDL methods for tenant DBs)
├── app.py                       (update: include tables router)
```

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Auto `id` column | Always add `id SERIAL PRIMARY KEY` | Consistent, every table has a standard PK for CRUD in Wave 1.5 |
| DDL connection | `postgres` superuser → tenant DB | Simple; avoids reading Secrets back; OWNER TO for proper ownership |
| Schema tracking | Dual storage (PG catalog + platform DB) | Platform DB is source of truth for API; PG catalog is source of truth for execution |
| Column modification | Add/drop only in Phase 1 | ALTER TYPE is complex (casts, data loss); defer to later |
| Table names | Validated, lowercase, no reserved words | Prevent SQL injection and PG conflicts |

---

## Error Handling

| Scenario | HTTP Status | Response |
|----------|-------------|----------|
| Tenant not found | 404 | `{"detail": "Tenant not found"}` |
| Database not found | 404 | `{"detail": "Database not found"}` |
| Table not found | 404 | `{"detail": "Table not found"}` |
| Duplicate table name | 409 | `{"detail": "Table 'foo' already exists"}` |
| Invalid table name | 422 | Pydantic validation error |
| Invalid column type | 422 | `{"detail": "Invalid column type 'foo'. Valid types: ..."}` |
| Drop column that doesn't exist | 400 | `{"detail": "Column 'foo' does not exist"}` |
| Drop the `id` column | 400 | `{"detail": "Cannot drop primary key column 'id'"}` |

---

## Acceptance Criteria

- [ ] `POST .../tables` creates table in tenant DB with auto `id` column
- [ ] `POST .../tables` validates column types against type map
- [ ] `POST .../tables` returns 409 for duplicate table names
- [ ] `POST .../tables` supports nullable, unique, and default for columns
- [ ] `GET .../tables` lists all active tables for a database
- [ ] `GET .../tables/{name}` returns full table definition with columns
- [ ] `PUT .../tables/{name}` can add new columns
- [ ] `PUT .../tables/{name}` can drop existing columns
- [ ] `PUT .../tables/{name}` returns 400 when dropping nonexistent or PK column
- [ ] `DELETE .../tables/{name}` drops the table from tenant DB
- [ ] Table and column definitions tracked in platform metadata DB
- [ ] Table ownership transferred to tenant PG role
- [ ] Unit tests for table service logic and type mapping

---

## Next Wave

→ [Wave 1.5 — Dynamic Data API (CRUD)](wave1_5_dynamic_data_api.md)
