# Wave 1.3 — Database Provisioning

> Parent: [Master Plan](../master_plan.md)
> Depends on: [Wave 1.2 — Tenant Management](wave1_2_tenant_management.md) (complete)
> Goal: API can provision and destroy PostgreSQL databases for tenants on the shared Forge PG instance.

---

## Overview

Add database lifecycle management to the Forge control plane. Each tenant can request one or more databases, which are created as separate PostgreSQL databases on the shared `forge-postgresql` instance. Credentials are generated per-database and stored as Kubernetes Secrets in the tenant's namespace.

---

## Design Decision: Shared PG, Database-per-Tenant

As decided in the master plan, we use **Option B** — a shared PostgreSQL instance with a separate database per tenant database request. This means:

- The Forge platform connects to `forge-postgresql` as the `postgres` superuser
- Each `POST /tenants/{id}/databases` creates a new PG database, a dedicated PG role (user), and a K8s Secret with the connection string
- Tenant workloads (future waves) connect using their own role, scoped to their database only
- The platform metadata DB (`forge_platform`) lives on the same PG instance but is not accessible to tenant roles

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/tenants/{tenant_id}/databases` | Provision a new database for the tenant |
| `GET` | `/tenants/{tenant_id}/databases` | List databases for a tenant |
| `GET` | `/tenants/{tenant_id}/databases/{db_id}` | Get database details |
| `DELETE` | `/tenants/{tenant_id}/databases/{db_id}` | Drop database and clean up |

### Request/Response Models

#### `POST /tenants/{tenant_id}/databases`
```json
// Request
{
  "name": "inventory"
}

// Response (201)
{
  "id": "uuid",
  "tenant_id": "uuid",
  "name": "inventory",
  "pg_database": "forge_t_my_app_inventory",
  "pg_role": "forge_t_my_app_inventory_role",
  "secret_name": "forge-db-inventory",
  "status": "active",
  "created_at": "2026-03-25T12:00:00Z"
}
```

#### `GET /tenants/{tenant_id}/databases`
```json
// Response (200)
{
  "databases": [
    {
      "id": "uuid",
      "tenant_id": "uuid",
      "name": "inventory",
      "pg_database": "forge_t_my_app_inventory",
      "pg_role": "forge_t_my_app_inventory_role",
      "secret_name": "forge-db-inventory",
      "status": "active",
      "created_at": "2026-03-25T12:00:00Z"
    }
  ]
}
```

#### `DELETE /tenants/{tenant_id}/databases/{db_id}`
```json
// Response (200)
{
  "id": "uuid",
  "name": "inventory",
  "status": "deleted"
}
```

---

## Platform Database Models

### `tenant_database` table
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK, auto-generated |
| `tenant_id` | UUID | FK → tenant.id |
| `name` | VARCHAR | Unique per tenant, user-friendly name |
| `pg_database` | VARCHAR | Actual PG database name (`forge_t_{tenant}_{name}`) |
| `pg_role` | VARCHAR | PG role name (`forge_t_{tenant}_{name}_role`) |
| `secret_name` | VARCHAR | K8s Secret name in tenant namespace |
| `status` | VARCHAR | `active`, `deleting`, `deleted` |
| `created_at` | TIMESTAMP | Auto-set |
| `updated_at` | TIMESTAMP | Auto-updated |

**Naming convention:** `forge_t_{tenant_name}_{db_name}` — prefixed to avoid collisions with system databases, underscores for PG compatibility.

---

## What Happens on `POST /tenants/{tenant_id}/databases`

### 1. Create PG Role
```sql
CREATE ROLE forge_t_myapp_inventory_role WITH LOGIN PASSWORD 'generated-password';
```

### 2. Create PG Database
```sql
CREATE DATABASE forge_t_myapp_inventory OWNER forge_t_myapp_inventory_role;
```

### 3. Restrict Access
```sql
REVOKE ALL ON DATABASE forge_t_myapp_inventory FROM PUBLIC;
GRANT ALL PRIVILEGES ON DATABASE forge_t_myapp_inventory TO forge_t_myapp_inventory_role;
```

### 4. Create K8s Secret in Tenant Namespace
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: forge-db-inventory
  namespace: forge-tenant-myapp
  labels:
    forge.lucas.engineering/tenant: myapp
    forge.lucas.engineering/managed-by: forge-platform
type: Opaque
stringData:
  DATABASE_URL: "postgresql://forge_t_myapp_inventory_role:generated-password@forge-postgresql.forge-platform.svc.cluster.local:5432/forge_t_myapp_inventory"
  POSTGRES_HOST: "forge-postgresql.forge-platform.svc.cluster.local"
  POSTGRES_PORT: "5432"
  POSTGRES_DB: "forge_t_myapp_inventory"
  POSTGRES_USER: "forge_t_myapp_inventory_role"
  POSTGRES_PASSWORD: "generated-password"
```

### 5. Update Tenant NetworkPolicy

The tenant namespace needs to reach `forge-postgresql` in the `forge-platform` namespace. The existing network policy from Wave 1.2 already allows egress to anywhere, so no change needed for now. (Phase 4 will tighten egress rules.)

---

## What Happens on `DELETE /tenants/{tenant_id}/databases/{db_id}`

1. Terminate active connections to the database
2. `DROP DATABASE forge_t_myapp_inventory;`
3. `DROP ROLE forge_t_myapp_inventory_role;`
4. Delete K8s Secret from tenant namespace
5. Mark as `deleted` in platform DB

---

## Implementation

### New/Modified Files

```
platform/src/forge_platform/
├── models/
│   ├── __init__.py              (update: export TenantDatabase)
│   └── tenant_database.py       (new: TenantDatabase SQLModel)
├── routers/
│   └── databases.py             (new: CRUD endpoints)
├── schemas/
│   └── database.py              (new: request/response models)
├── services/
│   ├── database_service.py      (new: business logic)
│   └── postgres_service.py      (new: raw PG operations via psycopg2)
│   └── kubernetes_service.py    (update: add create/delete secret)
├── app.py                       (update: include databases router)
```

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| PG connection for DDL | Direct psycopg2 with autocommit | `CREATE DATABASE` can't run inside a transaction; SQLModel/SQLAlchemy won't work for this |
| Password generation | `secrets.token_urlsafe(32)` | Secure, no special chars that break connection strings |
| Secret per database | One K8s Secret per tenant database | Clean mapping; tenant workloads reference by secret name |
| PG naming | `forge_t_{tenant}_{db}` | Underscores (PG-friendly), prefixed to avoid collisions, `t_` to indicate tenant-owned |
| Platform PG connection | Reuse `DATABASE_URL` from config, swap to `postgres` DB for DDL | No new config needed; connect to default `postgres` DB for CREATE/DROP DATABASE |

### RBAC Update

The platform ClusterRole needs permission to manage Secrets in tenant namespaces:

```yaml
# Add to existing clusterrole.yaml
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["create", "get", "list", "delete"]
```

---

## Error Handling

| Scenario | HTTP Status | Response |
|----------|-------------|----------|
| Tenant not found | 404 | `{"detail": "Tenant not found"}` |
| Database not found | 404 | `{"detail": "Database not found"}` |
| Duplicate database name | 409 | `{"detail": "Database 'foo' already exists for this tenant"}` |
| Invalid database name | 400 | `{"detail": "Name must be lowercase alphanumeric with underscores"}` |
| PG connection failure | 500 | `{"detail": "Failed to connect to PostgreSQL"}` |

---

## Acceptance Criteria

- [ ] `POST /tenants/{id}/databases` creates PG database, role, and K8s Secret
- [ ] `POST /tenants/{id}/databases` returns 409 for duplicate name within tenant
- [ ] `POST /tenants/{id}/databases` returns 404 for nonexistent tenant
- [ ] `POST /tenants/{id}/databases` validates name format
- [ ] `GET /tenants/{id}/databases` lists databases for a tenant
- [ ] `GET /tenants/{id}/databases/{db_id}` returns database details
- [ ] `DELETE /tenants/{id}/databases/{db_id}` drops PG database and role
- [ ] `DELETE /tenants/{id}/databases/{db_id}` deletes K8s Secret from tenant namespace
- [ ] Tenant role can only access its own database (not `forge_platform` or other tenant DBs)
- [ ] Generated credentials in K8s Secret are valid (can connect)
- [ ] Tenant detail endpoint (`GET /tenants/{id}`) now shows correct database count
- [ ] Unit tests for database service logic

---

## Security Notes

- Tenant PG roles have `LOGIN` but no `SUPERUSER`, `CREATEDB`, or `CREATEROLE`
- `REVOKE ALL FROM PUBLIC` ensures no cross-tenant access
- Passwords are 32-byte random tokens, never logged
- K8s Secrets are in the tenant's namespace — other tenants can't read them (RBAC + NetworkPolicy)
- The platform connects as `postgres` superuser only for DDL operations

---

## Next Wave

→ [Wave 1.4 — Schema Management (DDL API)](wave1_4_schema_management.md)
