# Wave 1.2 — Tenant Management

> Parent: [Master Plan](../master_plan.md)
> Depends on: [Wave 1.1 — Platform Bootstrap](wave1_1_bootstrap.md) (complete)
> Goal: API can create, list, inspect, and delete isolated tenant namespaces with proper guardrails.

---

## Overview

Add tenant lifecycle management to the Forge control plane. A "tenant" maps to a Kubernetes namespace with resource quotas, network policies, and RBAC. All tenant resources are tracked in the platform metadata database.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/tenants` | Create a new tenant (namespace + guardrails) |
| `GET` | `/tenants` | List all tenants |
| `GET` | `/tenants/{tenant_id}` | Get tenant details + resource inventory |
| `DELETE` | `/tenants/{tenant_id}` | Tear down tenant and all contained resources |

### Request/Response Models

#### `POST /tenants`
```json
// Request
{
  "name": "my-app",
  "display_name": "My Application",
  "resource_limits": {          // optional, defaults applied
    "cpu": "2",
    "memory": "4Gi",
    "storage": "20Gi"
  }
}

// Response (201)
{
  "id": "uuid",
  "name": "my-app",
  "display_name": "My Application",
  "namespace": "forge-tenant-my-app",
  "status": "active",
  "resource_limits": { "cpu": "2", "memory": "4Gi", "storage": "20Gi" },
  "created_at": "2026-03-24T18:00:00Z"
}
```

#### `GET /tenants`
```json
// Response (200)
{
  "tenants": [
    {
      "id": "uuid",
      "name": "my-app",
      "display_name": "My Application",
      "namespace": "forge-tenant-my-app",
      "status": "active",
      "created_at": "2026-03-24T18:00:00Z"
    }
  ]
}
```

#### `GET /tenants/{tenant_id}`
```json
// Response (200)
{
  "id": "uuid",
  "name": "my-app",
  "display_name": "My Application",
  "namespace": "forge-tenant-my-app",
  "status": "active",
  "resource_limits": { "cpu": "2", "memory": "4Gi", "storage": "20Gi" },
  "created_at": "2026-03-24T18:00:00Z",
  "resources": {
    "databases": 0,
    "services": 0,
    "frontends": 0
  }
}
```

#### `DELETE /tenants/{tenant_id}`
```json
// Response (200)
{
  "id": "uuid",
  "name": "my-app",
  "status": "deleted"
}
```

---

## Platform Database Models

### `tenant` table
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK, auto-generated |
| `name` | VARCHAR | Unique, slug format (lowercase, hyphens) |
| `display_name` | VARCHAR | Human-readable name |
| `namespace` | VARCHAR | Kubernetes namespace (`forge-tenant-{name}`) |
| `status` | VARCHAR | `active`, `deleting`, `deleted` |
| `resource_limits` | JSON | CPU, memory, storage limits |
| `created_at` | TIMESTAMP | Auto-set |
| `updated_at` | TIMESTAMP | Auto-updated |

---

## Kubernetes Resources Created Per Tenant

When `POST /tenants` is called, the API creates:

### 1. Namespace
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: forge-tenant-{name}
  labels:
    forge.lucas.engineering/tenant: "{name}"
    forge.lucas.engineering/managed-by: forge-platform
```

### 2. ResourceQuota
```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: tenant-quota
  namespace: forge-tenant-{name}
spec:
  hard:
    requests.cpu: "{cpu}"
    requests.memory: "{memory}"
    persistentvolumeclaims: "10"
    requests.storage: "{storage}"
```

### 3. LimitRange (default pod limits)
```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: tenant-limits
  namespace: forge-tenant-{name}
spec:
  limits:
  - default:
      cpu: "500m"
      memory: "256Mi"
    defaultRequest:
      cpu: "100m"
      memory: "128Mi"
    type: Container
```

### 4. NetworkPolicy (isolate tenant namespaces)
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: tenant-isolation
  namespace: forge-tenant-{name}
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: forge-tenant-{name}
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: forge-platform
  egress:
  - {}  # allow all egress for now; tighten in Phase 4
```

---

## Implementation

### New/Modified Files

```
platform/src/forge_platform/
├── models/
│   ├── __init__.py          (update: export Tenant)
│   └── tenant.py            (new: Tenant SQLModel)
├── routers/
│   ├── __init__.py
│   └── tenants.py           (new: CRUD endpoints)
├── services/
│   ├── __init__.py           (new)
│   ├── tenant_service.py     (new: business logic)
│   └── kubernetes_service.py (new: k8s API client)
├── schemas/
│   ├── __init__.py           (new)
│   └── tenant.py             (new: request/response Pydantic models)
├── app.py                    (update: include tenants router)
└── config.py                 (update: add default resource limits)
```

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Namespace naming | `forge-tenant-{name}` | Prevents collisions with system namespaces; easy to identify |
| K8s client | `kubernetes` Python library (official) | Well-maintained, typed, matches existing ecosystem |
| UUID for tenant IDs | UUID4 | Avoids sequential ID guessing; standard for APIs |
| Service layer | Separate from routers | Clean separation of HTTP handling vs business logic vs k8s calls |
| Tenant deletion | Soft delete in DB + hard delete namespace | Audit trail in DB; namespace is actually removed |

### Kubernetes RBAC for the Platform

The Forge platform pod needs permissions to create/delete namespaces and resources in tenant namespaces. Add to the forge-platform Helm chart:

```
charts/forge-platform/templates/
├── serviceaccount.yaml
├── clusterrole.yaml
└── clusterrolebinding.yaml
```

#### ClusterRole (platform needs cluster-wide namespace management)
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: forge-platform
rules:
- apiGroups: [""]
  resources: ["namespaces"]
  verbs: ["create", "get", "list", "delete"]
- apiGroups: [""]
  resources: ["resourcequotas", "limitranges"]
  verbs: ["create", "get", "list", "delete"]
- apiGroups: ["networking.k8s.io"]
  resources: ["networkpolicies"]
  verbs: ["create", "get", "list", "delete"]
```

> This ClusterRole will be extended in later waves as more resource types are managed.

### Dependencies

Add to `requirements.txt`:
```
kubernetes>=30.0.0
```

---

## Acceptance Criteria

- [ ] `POST /tenants` creates namespace, ResourceQuota, LimitRange, NetworkPolicy
- [ ] `POST /tenants` returns 409 if tenant name already exists
- [ ] `POST /tenants` validates name format (lowercase, alphanumeric + hyphens)
- [ ] `GET /tenants` returns list of all active tenants
- [ ] `GET /tenants/{id}` returns tenant details
- [ ] `GET /tenants/{id}` returns 404 for nonexistent tenant
- [ ] `DELETE /tenants/{id}` removes the Kubernetes namespace
- [ ] `DELETE /tenants/{id}` marks tenant as `deleted` in platform DB
- [ ] `DELETE /tenants/{id}` returns 404 for nonexistent tenant
- [ ] Tenant namespace has resource quotas enforced
- [ ] Tenant namespaces are network-isolated from each other
- [ ] Platform pod has proper RBAC (ServiceAccount + ClusterRole + ClusterRoleBinding)
- [ ] Unit tests for tenant service logic
- [ ] Integration test: create tenant → verify namespace exists → delete → verify gone

---

## Error Handling

| Scenario | HTTP Status | Response |
|----------|-------------|----------|
| Invalid tenant name | 400 | `{"detail": "Name must be lowercase alphanumeric with hyphens"}` |
| Duplicate tenant name | 409 | `{"detail": "Tenant 'foo' already exists"}` |
| Tenant not found | 404 | `{"detail": "Tenant not found"}` |
| K8s API failure | 500 | `{"detail": "Failed to create namespace: ..."}` |

---

## Next Wave

→ [Wave 1.3 — Database Provisioning](wave1_3_database_provisioning.md)
