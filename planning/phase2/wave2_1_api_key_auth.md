# Wave 2.1 — API Key Authentication

> Parent: [Master Plan](../master_plan.md)
> Depends on: [Phase 1](../phase1/) (complete)
> Goal: All API endpoints are protected. Admin key manages the platform, tenant keys access tenant-scoped data.

---

## Overview

Add API key authentication to the Forge control plane. Two roles: `admin` (platform operator, full access) and `tenant` (scoped to a single tenant's data). Keys are validated via middleware on every request. An admin key is auto-generated on first startup.

---

## API Key Model

### `api_key` table
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `key_hash` | VARCHAR | SHA-256 hash of the key (never store plaintext) |
| `key_prefix` | VARCHAR(8) | First 8 chars of the key (for identification in UI) |
| `tenant_id` | UUID | FK → tenant.id, NULL for admin keys |
| `role` | VARCHAR | `admin` or `tenant` |
| `name` | VARCHAR | Human-readable label ("Alice's key", "CI pipeline") |
| `is_active` | BOOLEAN | Soft revocation |
| `created_at` | TIMESTAMP | Auto-set |
| `last_used_at` | TIMESTAMP | Updated on each request |

**Key format:** `forge_` + 48 random URL-safe characters (e.g., `forge_a1b2c3d4...`). The `forge_` prefix makes keys easily identifiable in logs and config.

---

## Auth Middleware

All requests except `/health` and `/ready` require a valid `X-API-Key` header.

### Logic:
1. Extract `X-API-Key` from request headers
2. Hash the key with SHA-256
3. Look up the hash in the `api_key` table
4. If not found or `is_active=false` → 401 Unauthorized
5. Update `last_used_at`
6. Attach the key's `role` and `tenant_id` to the request state
7. For `tenant` role keys: verify the request path's `tenant_id` matches the key's `tenant_id`

### Endpoint access rules:

| Endpoint Pattern | Admin | Tenant |
|-----------------|-------|--------|
| `POST /tenants` | yes | no |
| `GET /tenants` | yes | no |
| `GET /tenants/{id}` | yes | yes (own only) |
| `DELETE /tenants/{id}` | yes | no |
| `/tenants/{id}/databases/**` | yes | yes (own only) |
| `/tenants/{id}/**/tables/**` | yes | yes (own only) |
| `/tenants/{id}/**/rows/**` | yes | yes (own only) |
| `POST /auth/keys` | yes | no |
| `GET /auth/keys` | yes | yes (own only) |
| `DELETE /auth/keys/{id}` | yes | no |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/keys` | Create an API key (admin only) |
| `GET` | `/auth/keys` | List API keys |
| `DELETE` | `/auth/keys/{id}` | Revoke a key (admin only) |

### `POST /auth/keys`
```json
// Request
{
  "name": "Alice's key",
  "role": "tenant",
  "tenant_id": "uuid"  // required for tenant role, omitted for admin
}

// Response (201) — the plaintext key is returned ONCE, never stored
{
  "id": "uuid",
  "key": "forge_a1b2c3d4e5f6...",
  "key_prefix": "forge_a1",
  "name": "Alice's key",
  "role": "tenant",
  "tenant_id": "uuid",
  "created_at": "2026-03-25T12:00:00Z"
}
```

### `GET /auth/keys`
```json
// Response (200) — no plaintext keys, only prefixes
{
  "keys": [
    {
      "id": "uuid",
      "key_prefix": "forge_a1",
      "name": "Alice's key",
      "role": "tenant",
      "tenant_id": "uuid",
      "is_active": true,
      "created_at": "2026-03-25T12:00:00Z",
      "last_used_at": "2026-03-25T14:30:00Z"
    }
  ]
}
```

---

## Bootstrap Admin Key

On first startup (no API keys exist in DB), the platform auto-generates an admin key and:
1. Prints it to stdout/logs: `[FORGE] Initial admin API key: forge_xxxx...`
2. Stores it as a K8s Secret `forge-admin-key` in the `forge-platform` namespace

This ensures the platform is never in an "unlocked" state after the first request.

---

## Implementation

### New/Modified Files

```
platform/src/forge_platform/
├── models/
│   ├── __init__.py              (update: export ApiKey)
│   └── api_key.py               (new: ApiKey SQLModel)
├── routers/
│   └── auth.py                  (new: key management endpoints)
├── schemas/
│   └── auth.py                  (new: request/response models)
├── services/
│   ├── auth_service.py          (new: key generation, hashing, validation)
│   └── kubernetes_service.py    (update: create admin key secret)
├── middleware/
│   ├── __init__.py              (new)
│   └── auth.py                  (new: API key middleware)
├── app.py                       (update: add middleware + auth router + bootstrap)
```

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Key storage | SHA-256 hash only | Plaintext key returned once on creation, never stored or retrievable |
| Key format | `forge_` + 48 chars | Prefix makes keys identifiable; 48 chars = 288 bits of entropy |
| Middleware approach | FastAPI dependency | Cleaner than raw ASGI middleware; easy to skip for health endpoints |
| Tenant scoping | Compare path `tenant_id` with key's `tenant_id` | Simple, no complex policy engine needed |
| Bootstrap key | Auto-generate + K8s Secret | Platform is secure by default; admin can retrieve key from Secret |

---

## Error Handling

| Scenario | HTTP Status | Response |
|----------|-------------|----------|
| Missing X-API-Key header | 401 | `{"detail": "API key required"}` |
| Invalid API key | 401 | `{"detail": "Invalid API key"}` |
| Revoked API key | 401 | `{"detail": "API key has been revoked"}` |
| Tenant key accessing another tenant | 403 | `{"detail": "Access denied"}` |
| Tenant key on admin-only endpoint | 403 | `{"detail": "Admin access required"}` |
| Create tenant key without tenant_id | 400 | `{"detail": "tenant_id required for tenant role keys"}` |

---

## Acceptance Criteria

- [ ] All endpoints except `/health` and `/ready` require valid API key
- [ ] Admin key auto-generated on first startup, stored in K8s Secret
- [ ] Admin keys have full access to all endpoints
- [ ] Tenant keys can only access their own tenant's data
- [ ] Tenant keys cannot create tenants or manage API keys
- [ ] `POST /auth/keys` creates a key, returns plaintext once
- [ ] `GET /auth/keys` lists keys without plaintext (only prefix)
- [ ] `DELETE /auth/keys/{id}` revokes a key (soft delete via `is_active=false`)
- [ ] Key hash stored in DB, never plaintext
- [ ] `last_used_at` updated on each authenticated request
- [ ] Existing tests updated to include API key in requests
- [ ] New unit tests for auth middleware and key management

---

## Next Wave

→ [Wave 2.2 — Admin Panel](wave2_2_admin_panel.md)
