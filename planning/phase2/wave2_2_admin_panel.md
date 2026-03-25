# Wave 2.2 — Admin Panel

> Parent: [Master Plan](../master_plan.md)
> Depends on: [Wave 2.1 — API Key Authentication](wave2_1_api_key_auth.md) (complete)
> Goal: Platform operators can manage tenants and monitor the system through a web UI.

---

## Overview

A React single-page application for platform operators. The admin panel provides a dashboard, tenant management, and API key management — backed by the Forge Control Plane API using an admin API key. Deployed as its own service in the `forge-platform` namespace at `admin.forge.lucas.engineering`.

---

## Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Framework | React 18 + TypeScript | Specified in master plan; industry standard |
| Build tool | Vite | Fast dev server, optimized builds |
| Styling | Tailwind CSS | Utility-first, professional look with minimal custom CSS |
| HTTP client | Fetch API (native) | No extra dependency needed; simple API calls |
| Routing | React Router v6 | Standard SPA routing |
| State | React Context + hooks | Simple enough for an admin panel; no Redux needed |
| Icons | Lucide React | Clean, consistent icon set |
| Container | nginx:alpine | Serve static build, reverse proxy API calls |

---

## Pages & Layout

### Shell Layout
- **Sidebar** (fixed left, 240px)
  - Forge logo / wordmark
  - Navigation links: Dashboard, Tenants, API Keys
  - System health indicator (green dot if `/health` returns ok)
- **Main content area** (right of sidebar)
  - Page header with breadcrumbs
  - Page content

### 1. Dashboard (`/`)
- **Stat cards** (top row):
  - Total tenants (active)
  - Total databases
  - Total tables
  - API keys issued
- **Recent activity** (placeholder for now — just shows tenant list)
- Quick action: "Create Tenant" button

### 2. Tenants List (`/tenants`)
- **Table view** with columns: Name, Display Name, Namespace, Databases, Status, Created
- **Create Tenant** button → modal dialog with name + display name fields
- **Row click** → navigates to tenant detail
- **Delete** button per row with confirmation dialog

### 3. Tenant Detail (`/tenants/:id`)
- **Header**: tenant name, namespace, status, created date
- **Resource limits** card: CPU, memory, storage
- **Databases section**:
  - Table of databases: Name, PG Database, Status, Created
  - "Create Database" button → modal
  - Delete button per database
- **Tables section** (per database):
  - Expandable: click a database to see its tables
  - Table listing: Name, Columns count, Created
- **API Keys section**:
  - Keys scoped to this tenant
  - "Generate Key" button → shows plaintext key once in a copy-able dialog
- **Danger zone**: Delete tenant button (with "type tenant name to confirm" pattern)

### 4. API Keys (`/keys`)
- **Table view**: Prefix, Name, Role, Tenant, Active, Created, Last Used
- **Create Key** button → modal with name, role (dropdown), tenant (dropdown, shown if role=tenant)
- **Revoke** button per key with confirmation
- Key creation shows the plaintext key **once** in a modal with a copy button

---

## API Integration

The admin panel talks to the Forge API. The API key is stored in the browser's `localStorage` after initial entry.

### Auth Flow
1. On load, check `localStorage` for `forge_admin_key`
2. If not found → show a simple "Enter Admin API Key" screen
3. Validate the key by calling `GET /tenants` — if 401/403, clear and re-prompt
4. On success, store in localStorage and proceed to dashboard

### API Base URL
Configured via environment variable at build time: `VITE_API_URL`
- Development: `http://localhost:8000`
- Production: `https://forge.lucas.engineering` (same cluster, different ingress)

### CORS
The Forge API needs CORS headers added for the admin panel's origin (`admin.forge.lucas.engineering`). This is a small change to the FastAPI app.

---

## Deployment

### Dockerfile
```dockerfile
# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# Serve stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### nginx.conf
```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

### Helm Chart
New chart in the forge repo: `charts/forge-admin/`
- Deployment (nginx container)
- Service (ClusterIP, port 80)
- Ingress at `admin.forge.lucas.engineering`

### ArgoCD
New Application in `lucas_engineering` root-app for `forge-admin`.

### Tekton
Build config added to `tekton-ci/values.yaml` with `VITE_API_URL` build arg.

---

## Project Structure (forge-admin repo)

```
forge-admin/
├── public/
│   └── favicon.svg
├── src/
│   ├── main.tsx                    # React entry point
│   ├── App.tsx                     # Router + layout shell
│   ├── api/
│   │   └── client.ts              # API client (fetch wrapper with auth header)
│   ├── components/
│   │   ├── Layout.tsx              # Sidebar + main content shell
│   │   ├── Sidebar.tsx             # Navigation sidebar
│   │   ├── StatCard.tsx            # Dashboard stat card
│   │   ├── DataTable.tsx           # Reusable table component
│   │   ├── Modal.tsx               # Reusable modal dialog
│   │   ├── ConfirmDialog.tsx       # Delete confirmation
│   │   └── CopyableKey.tsx         # API key display with copy button
│   ├── pages/
│   │   ├── LoginPage.tsx           # API key entry
│   │   ├── DashboardPage.tsx       # Stats overview
│   │   ├── TenantsPage.tsx         # Tenant list
│   │   ├── TenantDetailPage.tsx    # Single tenant detail
│   │   └── ApiKeysPage.tsx         # API key management
│   ├── hooks/
│   │   ├── useAuth.ts             # Auth context + localStorage
│   │   └── useApi.ts              # API call hook with loading/error states
│   └── types/
│       └── index.ts               # TypeScript interfaces matching API responses
├── index.html
├── tailwind.config.js
├── tsconfig.json
├── vite.config.ts
├── package.json
├── Dockerfile
├── nginx.conf
└── .gitignore
```

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Separate repo | Yes (`forge-admin`) | Independent deployment lifecycle; different build pipeline (Node vs Python) |
| Auth storage | localStorage | Simple; admin key is long-lived; no session management needed |
| No login system | API key entry only | Phase 2 scope; full user accounts in Phase 4 |
| Tailwind CSS | Utility-first | Fast to build professional UI without custom design system |
| No component library (MUI, etc.) | Custom with Tailwind | Keeps bundle small; admin panel is simple enough |
| CORS on API | Allow admin panel origin | Required for browser-based API calls from different subdomain |

---

## CORS Change (Forge API)

Small update to `platform/src/forge_platform/app.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://admin.forge.lucas.engineering",
        "https://app.forge.lucas.engineering",
        "http://localhost:5173",  # Vite dev server
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Acceptance Criteria

- [ ] Login screen accepts admin API key and validates against the API
- [ ] Dashboard shows tenant count, database count, table count, key count
- [ ] Tenants list page shows all tenants with create/delete actions
- [ ] Tenant detail page shows databases, tables, and tenant-scoped API keys
- [ ] Create tenant modal works (name + display name)
- [ ] Create database modal works (name)
- [ ] API keys page shows all keys with create/revoke actions
- [ ] Create key modal supports admin and tenant roles
- [ ] Plaintext key shown once on creation with copy button
- [ ] Delete/revoke actions have confirmation dialogs
- [ ] Responsive sidebar navigation
- [ ] CORS configured on Forge API
- [ ] Dockerfile builds and serves via nginx
- [ ] Helm chart deploys to `forge-platform` namespace
- [ ] Ingress at `admin.forge.lucas.engineering` with TLS
- [ ] Tekton build pipeline configured

---

## Next Wave

→ [Wave 2.3 — Tenant Portal](wave2_3_tenant_portal.md)
