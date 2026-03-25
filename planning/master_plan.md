# Forge — Master Plan

## Vision

An AI-driven low-code platform running entirely on Kubernetes that enables rapid prototyping and iteration of full-stack applications. Users interact via a clean UI and AI chat interface to define data models, manage data, and build applications — without writing code. Think "TrackVia meets Kubernetes meets AI."

The platform targets small/medium businesses with non-technical users who need custom data management apps with minimal onboarding.

---

## Core Technology Stack

| Layer              | Technology                        |
|--------------------|-----------------------------------|
| Orchestration      | Kubernetes                        |
| GitOps / Deploys   | ArgoCD (app-of-apps pattern)      |
| CI / Builds        | Tekton Pipelines + Kaniko         |
| Databases          | PostgreSQL (shared, DB-per-tenant)|
| Backend API        | Python FastAPI (Forge Control Plane) |
| Admin Frontend     | React + Vite (platform operator UI) |
| Tenant Frontend    | React + Vite (tenant self-service portal) |
| Container Registry | registry.lucas.engineering        |
| AI Interface       | Chat-based orchestrator (Phase 3) |

---

## Cluster Strategy

**Development:** Build on the existing lucas_engineering cluster where ArgoCD and Tekton are already running. The platform lives in its own namespace (`forge-platform`) and won't conflict with existing workloads in `apps-prod`.

**Final Deliverable:** A clean bootstrap script that can stand up the entire platform on a bare cluster from scratch. Deferred until the platform is mature enough to define its requirements.

---

## Architecture Overview

```
┌───────────────────────────┐  ┌───────────────────────────┐
│      Admin Panel          │  │     Tenant Portal         │
│  (Platform operator UI)   │  │  (Tenant self-service)    │
│  - Manage tenants         │  │  - Build data models      │
│  - Monitor resources      │  │  - Browse/edit data       │
│  - View usage & health    │  │  - Table + slide-out form │
└───────────┬───────────────┘  └───────────┬───────────────┘
            │                              │
            └──────────┬───────────────────┘
                       │  API key auth
┌──────────────────────▼──────────────────────────────────┐
│                Forge Control Plane                       │
│                  (FastAPI service)                       │
│                                                         │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────────┐  │
│  │   Tenant     │ │  Database    │ │   Schema         │  │
│  │   Manager    │ │  Manager     │ │   Manager        │  │
│  └─────────────┘ └──────────────┘ └──────────────────┘  │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────────┐  │
│  │  Dynamic    │ │    Auth      │ │   (Future:       │  │
│  │  Data API   │ │  (API keys)  │ │   AI Orchestr.)  │  │
│  └─────────────┘ └──────────────┘ └──────────────────┘  │
└──────────────────────┬──────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   ┌─────────┐  ┌───────────┐  ┌───────────────┐
   │Kubernetes│  │  Forge    │  │  Tenant DBs   │
   │  API     │  │  Postgres │  │  (on same PG) │
   └─────────┘  └───────────┘  └───────────────┘
```

---

## Phase 1 — Foundation: Forge Control Plane API (COMPLETE)

> **Goal:** A running FastAPI service that can create/destroy tenants and manage PostgreSQL schemas via REST API.

### Wave 1.1 — Platform Bootstrap (complete)
> Detailed plan: `planning/phase1/wave1_1_bootstrap.md`

Forge API + dedicated PostgreSQL running in `forge-platform` namespace, deployed via ArgoCD.

### Wave 1.2 — Tenant Management (complete)
> Detailed plan: `planning/phase1/wave1_2_tenant_management.md`

CRUD for tenants. Each tenant gets a k8s namespace with ResourceQuota, LimitRange, NetworkPolicy.

### Wave 1.3 — Database Provisioning (complete)
> Detailed plan: `planning/phase1/wave1_3_database_provisioning.md`

CRUD for tenant databases. Each database gets a PG database + role + K8s Secret with credentials.

### Wave 1.4 — Schema Management (complete)
> Detailed plan: `planning/phase1/wave1_4_schema_management.md`

CRUD for tables and columns. 9 simplified types mapped to PG. Auto `id` PK on every table.

### Wave 1.5 — Dynamic Data API (complete)
> Detailed plan: `planning/phase1/wave1_5_dynamic_data_api.md`

Generic CRUD on any tenant table. Filtering, sorting, pagination, batch insert. 47 tests passing.

---

## Phase 2 — Platform UI & Auth

> **Goal:** Two React frontends — an Admin Panel for platform operators and a Tenant Portal for end users — backed by API key authentication. This makes the platform usable by non-technical users without touching APIs directly.

### Wave 2.1 — API Key Authentication
> Detailed plan: `planning/phase2/wave2_1_api_key_auth.md`

- API key model in platform DB (key, tenant_id, role, created_at, last_used_at)
- Two key roles: `admin` (platform operator) and `tenant` (scoped to one tenant)
- Middleware that validates `X-API-Key` header on all endpoints except `/health`
- `POST /auth/keys` — admin creates API keys (admin keys + tenant keys)
- `GET /auth/keys` — list keys (admin sees all, tenant sees own)
- `DELETE /auth/keys/{id}` — revoke a key
- Admin key auto-generated on first startup (printed to logs / stored in K8s Secret)
- Tenant endpoints automatically scoped — tenant key can only access its own data

**Deliverable:** All API endpoints are protected. Admin key manages the platform, tenant keys access tenant-scoped data.

### Wave 2.2 — Admin Panel
> Detailed plan: `planning/phase2/wave2_2_admin_panel.md`

Separate React app (own git repo) for platform operators.

- **Dashboard** — tenant count, database count, total tables, system health
- **Tenant list** — table view with create/delete actions
- **Tenant detail** — databases, tables, resource usage, API keys
- **API key management** — generate/revoke admin and tenant keys
- Clean, professional design (Tailwind CSS or similar)
- Deployed to cluster via ArgoCD at `admin.forge.lucas.engineering`

**Deliverable:** Platform operators can manage tenants and monitor the system through a web UI.

### Wave 2.3 — Tenant Portal
> Detailed plan: `planning/phase2/wave2_3_tenant_portal.md`

Separate React app (own git repo) for tenant users. The core low-code experience.

- **Login** — enter API key (no username/password for Phase 2)
- **Database picker** — if tenant has multiple databases
- **Table list sidebar** — all tables in the selected database
- **Data view** — table view (sortable, filterable, paginated)
  - Click row → slide-out detail panel with form editing
  - "Add record" button → slide-out form for new record
  - Inline delete with confirmation
- **Schema builder** — visual table/column management
  - Create table with friendly UI (not raw JSON)
  - Add/remove columns with type picker dropdown
  - Column properties: name, type, required, unique, default
- **UX principles for non-technical users:**
  - "Tables" presented as "Trackers" or "Sheets" (friendly naming TBD)
  - Column types shown as "Text", "Number", "Yes/No", "Date", etc.
  - No SQL or API jargon exposed in the UI
  - Helpful empty states ("No records yet — click 'Add' to create your first one")
- Deployed to cluster via ArgoCD at `app.forge.lucas.engineering`

**Deliverable:** Non-technical tenant users can define data models and manage data through a friendly web interface.

### Wave 2.4 — Tenant Portal Polish & UX
> Detailed plan: `planning/phase2/wave2_4_portal_polish.md`

Refinements based on real usage of Wave 2.3:

- **Search** across tables and records
- **Export** data (CSV download)
- **Bulk actions** — select multiple rows, delete/update in batch
- **Column reordering** via drag-and-drop
- **Field validation feedback** — inline errors on forms
- **Responsive design** — usable on tablet/mobile
- **Loading states and error handling** — skeleton loaders, friendly error messages

---

## Phase 3 — AI-Driven Interface

> **Goal:** Users describe what they want in natural language. The AI translates intent into platform API calls, enabling conversational app building.

### Wave 3.1 — Chat Interface & AI Orchestrator
> Detailed plan: `planning/phase3/wave3_1_ai_orchestrator.md`

- Chat panel integrated into the Tenant Portal (not a separate app)
- LLM integration (Claude API) for interpreting user intent
- Tool-use / function-calling to invoke Forge Control Plane APIs
- Conversation context: knows the tenant's current tables, columns, data
- Example flow:
  1. User: "I need a tracker for customer orders"
  2. AI: Creates `customers` table and `orders` table with appropriate columns
  3. User: "Add a status field to orders with options: pending, shipped, delivered"
  4. AI: Adds the column, suggests default value
  5. User: "Show me all pending orders"
  6. AI: Navigates to orders table with the filter applied

### Wave 3.2 — Iterative Refinement
> Detailed plan: `planning/phase3/wave3_2_iterative_refinement.md`

- "Add a phone number field to customers" → AI calls DDL API
- "Make email required" → AI understands column constraints
- Schema diffing and safe migration suggestions
- Undo support for recent AI actions

### Wave 3.3 — Templates & Patterns
> Detailed plan: `planning/phase3/wave3_3_templates.md`

- Pre-built application templates (CRM, inventory tracker, project manager, etc.)
- "Start from template" in the Tenant Portal
- User can customize via chat after applying a template

---

## Phase 4 — Production Hardening & Advanced Features

> **Goal:** Make the platform production-ready with security, observability, and advanced capabilities.

### Waves (detailed plans TBD):
- **4.1 — User Accounts & RBAC** — upgrade from API keys to full user accounts with roles
- **4.2 — Observability** — logging, metrics, tracing for the platform (Grafana stack)
- **4.3 — Custom Business Logic** — user-defined validation rules, computed fields, triggers
- **4.4 — Webhooks & Integrations** — event-driven triggers, external API connections
- **4.5 — Scheduled Jobs** — cron-like task execution for tenant workloads
- **4.6 — Multi-Cluster / Scaling** — support multiple k8s clusters, horizontal scaling
- **4.7 — Code Generation & Custom Services** — generate standalone FastAPI/React services for tenants who outgrow the dynamic API (original Phase 2 scope, deferred)

---

## Dependency Graph

```
Phase 1 (COMPLETE)
  Wave 1.1 (Bootstrap) → 1.2 (Tenants) → 1.3 (DB) → 1.4 (Schema) → 1.5 (CRUD)

Phase 2 (Current)
  Wave 2.1 (API Key Auth)
    ├→ Wave 2.2 (Admin Panel)
    └→ Wave 2.3 (Tenant Portal)
         └→ Wave 2.4 (Portal Polish)

Phase 3
  Wave 2.3 (Tenant Portal)
    └→ Wave 3.1 (AI Chat) → 3.2 (Refinement) → 3.3 (Templates)

Phase 4
  └→ Production hardening waves (independent, can be done in any order)
```

---

## Key Design Principles

1. **API-first** — every capability is an API call before it's a UI action
2. **GitOps-native** — all state is in Git; the cluster reflects Git, never the other way around
3. **Opinionated defaults, escape hatches available** — sensible defaults for 80% of cases, customization for the rest
4. **Tenant isolation** — namespaces, network policies, resource quotas from day one
5. **Non-technical user friendly** — no SQL, no API jargon in the UI; friendly naming and helpful empty states
6. **Schema-as-metadata** — table/column definitions stored in the platform DB so the system always knows what exists

---

## Project Structure

```
forge/                               ← platform backend + charts (github.com/lward27/forge.git)
├── planning/
│   ├── master_plan.md               ← this file
│   ├── phase1/                      ← complete
│   └── phase2/
├── platform/                        ← Forge control plane (FastAPI)
├── charts/
│   ├── forge-platform/              ← API Helm chart
│   └── forge-postgresql/            ← PG Helm chart

forge-admin/                         ← admin panel (separate git repo, TBD)
├── src/
├── Dockerfile
└── ...

forge-portal/                        ← tenant portal (separate git repo, TBD)
├── src/
├── Dockerfile
└── ...
```

---

## Next Steps

1. ~~Phase 1 — complete~~
2. Write detailed plan for **Wave 2.1 — API Key Authentication**
3. Build auth, then admin panel, then tenant portal
