# Forge — Master Plan

## Vision

An AI-driven low-code platform running entirely on Kubernetes that enables rapid prototyping and iteration of full-stack applications. Users interact via a chat interface (not drag-and-drop) to spin up microservices, microfrontends, databases, and supporting infrastructure. Think "TrackVia meets Kubernetes meets AI."

---

## Core Technology Stack

| Layer              | Technology                        |
|--------------------|-----------------------------------|
| Orchestration      | Kubernetes                        |
| GitOps / Deploys   | ArgoCD (app-of-apps pattern)      |
| CI / Builds        | Tekton Pipelines + Kaniko         |
| Databases          | PostgreSQL (shared, DB-per-tenant)|
| Backend APIs       | Python FastAPI (generated)        |
| Frontends          | React (generated microfrontends)  |
| Container Registry | registry.lucas.engineering        |
| AI Interface       | Chat-based orchestrator (Phase 3) |

---

## Cluster Strategy

**Development:** Build on the existing lucas_engineering cluster where ArgoCD and Tekton are already running. The platform lives in its own namespace (`forge-platform`) and won't conflict with existing workloads in `apps-prod`.

**Final Deliverable:** A clean bootstrap script (Wave 1.6) that can stand up the entire platform on a bare cluster from scratch. This is built *after* Waves 1.1–1.2, once we know exactly what the platform needs from the cluster — informed by real experience rather than guesswork.

**Rationale:** Starting fresh would mean days of cluster plumbing before writing platform code. The existing cluster lets us iterate immediately. The bootstrap script proves the platform is portable and reproducible.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    AI Chat Interface                     │  ← Phase 3
│               (React frontend + LLM backend)            │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                Forge Control Plane                       │  ← Phase 1-2
│                  (FastAPI service)                       │
│                                                         │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────────┐  │
│  │   Tenant     │ │  Database    │ │   API Factory    │  │
│  │   Manager    │ │  Manager     │ │   (codegen)      │  │
│  └─────────────┘ └──────────────┘ └──────────────────┘  │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────────┐  │
│  │  Frontend   │ │  Pipeline    │ │   GitOps         │  │
│  │  Factory    │ │  Manager     │ │   Manager        │  │
│  └─────────────┘ └──────────────┘ └──────────────────┘  │
└──────────────────────┬──────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   ┌─────────┐  ┌───────────┐  ┌───────────┐
   │Kubernetes│  │  ArgoCD   │  │  Tekton   │
   │  API     │  │           │  │ Pipelines │
   └─────────┘  └───────────┘  └───────────┘
        │
        ▼
   ┌──────────────────────────────────────┐
   │         Tenant Namespaces            │
   │  ┌────────┐ ┌────────┐ ┌────────┐   │
   │  │tenant-a│ │tenant-b│ │tenant-c│   │
   │  │ - DB   │ │ - DB   │ │ - DB   │   │
   │  │ - APIs │ │ - APIs │ │ - APIs │   │
   │  │ - UIs  │ │ - UIs  │ │ - UIs  │   │
   │  └────────┘ └────────┘ └────────┘   │
   └──────────────────────────────────────┘
```

---

## Phase 1 — Foundation: Forge Control Plane API

> **Goal:** A running FastAPI service that can create/destroy tenants and manage PostgreSQL schemas via REST API. No UI, no codegen — just the control plane talking to Kubernetes and PostgreSQL.

### Wave 1.1 — Platform Bootstrap
> Detailed plan: `planning/phase1/wave1_1_bootstrap.md`

- **Platform namespace** (`forge-platform`) — where the control plane itself lives
- **Platform database** — a PostgreSQL instance storing platform metadata: tenants, resources, audit log
- **Platform API skeleton** — FastAPI project structure, health checks, config, auth scaffold
- **Helm chart** for the Forge API (deployed via ArgoCD)
- **Tekton pipeline** for building the Forge API image

**Deliverable:** Forge API running in cluster, responding to health checks, connected to its own metadata DB.

### Wave 1.2 — Tenant Management
> Detailed plan: `planning/phase1/wave1_2_tenant_management.md`

- `POST /tenants` — creates a Kubernetes namespace, resource quotas, network policies, RBAC
- `GET /tenants` — list all tenants
- `GET /tenants/{id}` — tenant details + resource inventory
- `DELETE /tenants/{id}` — tears down namespace and all contained resources
- Platform DB tables: `tenant`, `tenant_resource` (tracks what was provisioned)
- Kubernetes client integration (official `kubernetes` Python library)

**Deliverable:** API can create isolated tenant namespaces with proper guardrails.

### Wave 1.3 — Database Provisioning
> Detailed plan: `planning/phase1/wave1_3_database_provisioning.md`

- `POST /tenants/{id}/databases` — creates a new database in the shared PG instance for the tenant
- `GET /tenants/{id}/databases` — list databases for tenant
- `DELETE /tenants/{id}/databases/{db_id}` — drop database and clean up
- Credentials management (Kubernetes Secrets)
- Connection pooling considerations (PgBouncer sidecar or shared)

**Design Decision — Isolation Model:**
- **Option A: Dedicated PG per tenant** — stronger isolation, more resource usage
- **Option B: Shared PG, database-per-tenant** — efficient, weaker isolation
- **Option C: Shared PG, schema-per-tenant** — most efficient, weakest isolation
- **Decision:** Start with **Option B** (database-per-tenant on shared PG). Migrate to dedicated instances for tenants that need it in later phases.

**Deliverable:** API can provision and destroy PostgreSQL databases for tenants.

### Wave 1.4 — Schema Management (DDL API)
> Detailed plan: `planning/phase1/wave1_4_schema_management.md`

- `POST /tenants/{id}/databases/{db_id}/tables` — create table
- `GET /tenants/{id}/databases/{db_id}/tables` — list tables
- `PUT /tenants/{id}/databases/{db_id}/tables/{table}` — alter table (add/drop/modify columns)
- `DELETE /tenants/{id}/databases/{db_id}/tables/{table}` — drop table
- Column types: map simplified types (text, number, decimal, boolean, date, datetime, json) → PG types
- Primary keys, foreign keys, unique constraints, indexes
- Migration tracking (store DDL history so changes are auditable and reversible)
- Platform DB tables: `table_definition`, `column_definition`, `constraint_definition`

**Deliverable:** Full DDL management via API — create tables, columns, relationships, constraints.

### Wave 1.5 — Dynamic Data API (CRUD)
> Detailed plan: `planning/phase1/wave1_5_dynamic_data_api.md`

- Generic CRUD endpoints that operate on any tenant table:
  - `POST /tenants/{id}/databases/{db_id}/tables/{table}/rows`
  - `GET /tenants/{id}/databases/{db_id}/tables/{table}/rows`
  - `GET /tenants/{id}/databases/{db_id}/tables/{table}/rows/{pk}`
  - `PUT /tenants/{id}/databases/{db_id}/tables/{table}/rows/{pk}`
  - `DELETE /tenants/{id}/databases/{db_id}/tables/{table}/rows/{pk}`
- Query filtering, sorting, pagination
- Input validation against stored schema definitions
- Bulk operations (batch insert/update)

**Deliverable:** Any table created via the DDL API can immediately be read/written via REST.

### Wave 1.6 — Cluster Bootstrap Script
> Detailed plan: `planning/phase1/wave1_6_cluster_bootstrap.md`

Built *after* Waves 1.1–1.2 are working, informed by what the platform actually needs.

- Shell script / Makefile that takes a bare Kubernetes cluster to a fully running Forge instance
- Installs prerequisites: ArgoCD, Tekton, ingress controller, cert-manager, storage classes
- Configures ArgoCD with the Forge app-of-apps
- Deploys the platform namespace, metadata DB, and control plane
- Validates the installation (health checks, smoke tests)
- Documents all cluster requirements and assumptions

**Deliverable:** `./bootstrap.sh` — one command to go from empty cluster to running Forge platform.

---

## Phase 2 — Code Generation & Deployment Pipeline

> **Goal:** The platform can generate, build, and deploy custom FastAPI services and React frontends from specifications — turning schema definitions into running applications.

### Wave 2.1 — API Factory (Backend Codegen)
> Detailed plan: `planning/phase2/wave2_1_api_factory.md`

- API specification model: define endpoints, request/response shapes, business logic hooks
- FastAPI code generator: takes spec → produces a complete FastAPI project
- Template engine for generating models, routes, tests, Dockerfile, Helm chart
- Generated code committed to a Git repo (one repo per service, or monorepo per tenant)
- `POST /tenants/{id}/services` — define and generate a new API service
- `GET /tenants/{id}/services` — list services
- `DELETE /tenants/{id}/services/{svc_id}` — tear down service

### Wave 2.2 — Pipeline Manager (Tekton Integration)
> Detailed plan: `planning/phase2/wave2_2_pipeline_manager.md`

- Dynamically create Tekton PipelineRuns for generated services
- Clone → Build (Kaniko) → Push to registry → trigger ArgoCD sync
- `POST /tenants/{id}/services/{svc_id}/builds` — trigger build
- `GET /tenants/{id}/services/{svc_id}/builds` — build history/status
- Webhook support for auto-build on Git push

### Wave 2.3 — GitOps Manager (ArgoCD Integration)
> Detailed plan: `planning/phase2/wave2_3_gitops_manager.md`

- Generate ArgoCD Application manifests for tenant services
- Register applications with ArgoCD (app-of-apps pattern per tenant)
- Sync status monitoring
- Rollback support via ArgoCD

### Wave 2.4 — Frontend Factory (React Codegen)
> Detailed plan: `planning/phase2/wave2_4_frontend_factory.md`

- UI specification model: pages, components, data bindings, navigation
- React code generator: takes spec → produces a microfrontend (Vite + React)
- Component library: tables, forms, detail views, dashboards (opinionated defaults)
- Wired to generated backend APIs automatically
- `POST /tenants/{id}/frontends` — define and generate a frontend
- Same build/deploy pipeline as backend services

---

## Phase 3 — AI-Driven Interface

> **Goal:** Users describe what they want in natural language. The AI translates intent into platform API calls, generating complete applications through conversation.

### Wave 3.1 — Chat Interface & AI Orchestrator
> Detailed plan: `planning/phase3/wave3_1_ai_orchestrator.md`

- React-based chat UI (the platform's own frontend)
- LLM integration (Claude API) for interpreting user intent
- Tool-use / function-calling to invoke Forge Control Plane APIs
- Conversation context: knows the tenant's current resources, schema, services
- Example flow:
  1. User: "I need an app to track customer orders"
  2. AI: Creates database, `customers` table, `orders` table with FK
  3. AI: Generates CRUD API for both tables
  4. AI: Generates React frontend with customer list, order form, dashboard
  5. AI: Triggers build + deploy
  6. AI: Returns URL to running app

### Wave 3.2 — Iterative Refinement
> Detailed plan: `planning/phase3/wave3_2_iterative_refinement.md`

- "Add a status field to orders" → AI calls DDL API + regenerates affected code
- "Make the dashboard show orders by month" → AI modifies frontend spec + redeploys
- Schema diffing and safe migration generation
- Preview environments (deploy to temp namespace before promoting)

### Wave 3.3 — Templates & Patterns
> Detailed plan: `planning/phase3/wave3_3_templates.md`

- Pre-built application templates (CRM, inventory tracker, project manager, etc.)
- User can start from template and customize via chat
- Community template sharing

---

## Phase 4 — Production Hardening & Advanced Features

> **Goal:** Make the platform production-ready with security, observability, and advanced capabilities.

### Waves (detailed plans TBD):
- **4.1 — Auth & RBAC** — tenant user management, role-based access to data and APIs
- **4.2 — Observability** — logging, metrics, tracing for generated services (Grafana stack)
- **4.3 — Custom Business Logic** — user-defined Python functions injected into generated APIs
- **4.4 — Webhooks & Integrations** — event-driven triggers, external API connections
- **4.5 — Scheduled Jobs** — cron-like task execution for tenant workloads
- **4.6 — Multi-Cluster / Scaling** — support multiple k8s clusters, horizontal scaling

---

## Dependency Graph

```
Wave 1.1 (Bootstrap)
  └→ Wave 1.2 (Tenants)
  │    └→ Wave 1.6 (Cluster Bootstrap Script) ← built after 1.2, informed by real needs
  │    └→ Wave 1.3 (DB Provisioning)
  │         └→ Wave 1.4 (Schema/DDL)
  │              └→ Wave 1.5 (Dynamic CRUD)
  │                   ├→ Wave 2.1 (API Factory)
  │                   │    └→ Wave 2.2 (Pipeline Manager)
  │                   │         └→ Wave 2.3 (GitOps Manager)
  │                   └→ Wave 2.4 (Frontend Factory) — depends on 2.2 + 2.3
  │                        └→ Wave 3.1 (AI Orchestrator)
  │                             └→ Wave 3.2 (Iterative Refinement)
  │                             └→ Wave 3.3 (Templates)
  │                                  └→ Phase 4 (Hardening)
```

---

## Key Design Principles

1. **API-first** — every capability is an API call before it's a UI action
2. **GitOps-native** — all state is in Git; the cluster reflects Git, never the other way around
3. **Opinionated defaults, escape hatches available** — sensible defaults for 80% of cases, customization for the rest
4. **Tenant isolation** — namespaces, network policies, resource quotas from day one
5. **Immutable deployments** — no SSH, no kubectl-edit-in-place; everything flows through the pipeline
6. **Schema-as-metadata** — table/column definitions stored in the platform DB so the system always knows what exists

---

## Project Structure

```
forge/                               ← this repo (will get its own git repo)
├── planning/
│   ├── master_plan.md               ← this file
│   ├── phase1/
│   │   ├── wave1_1_bootstrap.md
│   │   ├── wave1_2_tenant_management.md
│   │   ├── wave1_3_database_provisioning.md
│   │   ├── wave1_4_schema_management.md
│   │   ├── wave1_5_dynamic_data_api.md
│   │   └── wave1_6_cluster_bootstrap.md
│   ├── phase2/
│   │   ├── wave2_1_api_factory.md
│   │   ├── wave2_2_pipeline_manager.md
│   │   ├── wave2_3_gitops_manager.md
│   │   └── wave2_4_frontend_factory.md
│   └── phase3/
│       ├── wave3_1_ai_orchestrator.md
│       ├── wave3_2_iterative_refinement.md
│       └── wave3_3_templates.md
├── platform/                        ← Forge control plane source code
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/
│   │   ├── models/
│   │   ├── services/
│   │   └── ...
│   ├── Dockerfile
│   ├── requirements.txt
│   └── tests/
├── charts/
│   └── forge-platform/              ← Helm chart for the control plane
└── bootstrap/                       ← cluster bootstrap scripts (Wave 1.6)
    ├── bootstrap.sh
    └── prerequisites/
```

---

## Next Steps

1. Review this master plan — align on scope and design decisions
2. Write detailed plan for **Wave 1.1 — Platform Bootstrap**
3. Start building the Forge control plane
