# Wave 2.3 — Tenant Portal

> Parent: [Master Plan](../master_plan.md)
> Depends on: [Wave 2.2 — Admin Panel](wave2_2_admin_panel.md) (complete)
> Goal: Non-technical tenant users can define data models and manage data through a friendly web interface.

---

## Overview

A React single-page application for tenant users — the core low-code experience. Users log in with a tenant API key and get a friendly interface to create tables, define columns ("fields"), and manage data using a table view with a slide-out form panel.

Deployed at `forge-portal.lucas.engineering`.

---

## Tech Stack

Same as Admin Panel for consistency:

| Layer | Choice |
|-------|--------|
| Framework | React 18 + TypeScript |
| Build tool | Vite |
| Styling | Tailwind CSS |
| HTTP client | Fetch API |
| Routing | React Router v6 |
| Icons | Lucide React |
| Container | nginx:alpine |

---

## User-Facing Language

The portal uses approachable labels for column types and properties:

| Technical Term | Portal Label | Notes |
|---------------|-------------|-------|
| Column | Field | "Add a field" |
| Row | Record | "Add a record" |
| text | Text | Free-form text |
| integer | Number | Whole number |
| decimal | Decimal | Number with decimals |
| boolean | Yes / No | Toggle |
| date | Date | Calendar date |
| timestamp | Date & Time | Date with time |
| json | JSON | Advanced — shown last in picker |
| nullable | Required toggle | "Is this field required?" (inverted) |
| unique | Unique toggle | "Must values be unique?" |
| default | Default Value | "Pre-fill with..." |

---

## Pages & Layout

### Shell Layout
- **Top bar** (fixed, full width)
  - Forge logo (left)
  - Current database name (center-left)
  - Logout button (right)
- **Left sidebar** (240px, below top bar)
  - Database picker dropdown (if tenant has multiple databases)
  - Table list — all tables in the selected database
  - "New Table" button at bottom of list
- **Main content area** (right of sidebar)
  - Page content

### 1. Login (`/login`)
- Simple API key entry (same pattern as admin panel)
- On success, redirect to main view
- If tenant has one database, auto-select it
- If tenant has zero databases, show "Getting Started" empty state

### 2. Getting Started (empty state)
- Shown when tenant has no databases or no tables
- Friendly message: "Welcome! Let's set up your first table."
- "Create Database" button (if no database exists)
- "Create Your First Table" button (if database exists but no tables)

### 3. Data View (`/tables/:name`) — the main screen
This is the core experience. Split into two areas:

#### Table View (left/main area)
- **Header row**: field names, sortable (click to sort)
- **Data rows**: paginated, 25 rows per page
- **Row click** → opens slide-out detail panel
- **"Add Record" button** (top right) → opens slide-out with empty form
- **Search bar** (top) — filters across all text fields
- **Pagination** (bottom) — Previous / Next with total count
- **Empty state**: "No records yet. Click 'Add Record' to create your first one."

#### Slide-Out Detail Panel (right side, 400px)
- **Slides in from the right** when a row is clicked or "Add Record" is pressed
- **Form fields** — one input per field, type-appropriate:
  - Text → text input
  - Number/Decimal → number input
  - Yes/No → toggle switch
  - Date → date picker
  - Date & Time → datetime-local input
  - JSON → textarea with monospace font
- **"Save" button** — creates or updates the record
- **"Delete" button** — with confirmation (only on existing records)
- **"Close" (X) button** — closes the panel
- **Validation feedback** — inline errors under fields (required, type mismatch)
- **ID field** shown as read-only (not editable)

### 4. Schema Builder (`/tables/:name/settings`)
Accessed via a gear icon on the table header.

- **Table name** (editable — renames the table)
- **Fields list** — ordered list of all fields
  - Each field shows: name, type badge, required/unique indicators
  - Click to expand inline editing (name, type, required, unique, default)
  - Delete button (with confirmation, cannot delete `id`)
- **"Add Field" button** → inline form at bottom:
  - Field name input
  - Type dropdown (friendly names)
  - Required toggle
  - Unique toggle
  - Default value input
- **"Delete Table" button** (danger zone, requires typing table name)

### 5. New Table Dialog
- Modal dialog triggered from sidebar "New Table" button
- **Step 1**: Table name (friendly label, auto-generates slug)
- **Step 2**: Define initial fields
  - Pre-populated with a suggested "name" (text, required) field
  - Add more fields with the same type picker as schema builder
- **"Create" button** → calls API, adds to sidebar, navigates to data view

---

## API Integration

### Auth
Same pattern as admin panel — tenant API key in `localStorage`, sent as `X-API-Key` header.

### Key Endpoints Used

| Action | Endpoint |
|--------|----------|
| Validate key | `GET /tenants/{id}` |
| List databases | `GET /tenants/{id}/databases` |
| Create database | `POST /tenants/{id}/databases` |
| List tables | `GET /tenants/{id}/databases/{db_id}/tables` |
| Create table | `POST /tenants/{id}/databases/{db_id}/tables` |
| Get table schema | `GET /tenants/{id}/databases/{db_id}/tables/{name}` |
| Alter table | `PUT /tenants/{id}/databases/{db_id}/tables/{name}` |
| Drop table | `DELETE /tenants/{id}/databases/{db_id}/tables/{name}` |
| List rows | `GET .../tables/{name}/rows?limit=25&offset=0&sort=...&filter=...` |
| Create row | `POST .../tables/{name}/rows` |
| Get row | `GET .../tables/{name}/rows/{pk}` |
| Update row | `PUT .../tables/{name}/rows/{pk}` |
| Delete row | `DELETE .../tables/{name}/rows/{pk}` |

### Tenant Context
On login, the portal needs to know which tenant the key belongs to. Currently the API doesn't return tenant info from a key. Two options:

**Option A (recommended):** Add a `GET /auth/me` endpoint to the Forge API that returns the key's role and tenant_id. Simple addition.

**Option B:** The user enters their tenant ID along with the API key. Bad UX for non-technical users.

We'll implement Option A — a small API change.

---

## API Change Required: `GET /auth/me`

New endpoint on the Forge API:

```json
// GET /auth/me
// Response (200)
{
  "role": "tenant",
  "tenant_id": "uuid",
  "tenant_name": "my-company",
  "key_name": "Portal Access",
  "key_prefix": "forge_8C"
}
```

This lets the portal identify the tenant without the user knowing their tenant UUID.

---

## Project Structure (forge-portal repo)

```
forge-portal/
├── public/
│   └── favicon.svg
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/
│   │   └── client.ts                # API client (shared pattern from admin)
│   ├── context/
│   │   └── TenantContext.tsx         # Tenant + database context after login
│   ├── components/
│   │   ├── Layout.tsx                # Top bar + sidebar + content
│   │   ├── TopBar.tsx
│   │   ├── TableSidebar.tsx        # Database picker + table list
│   │   ├── DataTable.tsx             # Main data table view
│   │   ├── SlideOutPanel.tsx         # Slide-out detail/form panel
│   │   ├── RecordForm.tsx            # Dynamic form based on column defs
│   │   ├── FieldInput.tsx            # Type-aware input component
│   │   ├── Modal.tsx                 # Reusable modal
│   │   ├── ConfirmDialog.tsx
│   │   ├── TypeBadge.tsx             # Color-coded type label
│   │   └── EmptyState.tsx            # Friendly empty state component
│   ├── pages/
│   │   ├── LoginPage.tsx
│   │   ├── GettingStartedPage.tsx
│   │   ├── DataViewPage.tsx          # Table view + slide-out (main screen)
│   │   └── SchemaBuilderPage.tsx     # Field management for a table
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useApi.ts
│   │   └── useTenant.ts             # Access tenant context
│   └── types/
│       └── index.ts
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

## Deployment

Same pattern as admin panel:
- Own git repo (`forge-portal`)
- Helm chart in forge repo (`charts/forge-portal/`)
- ArgoCD Application in lucas_engineering root-app
- Tekton CI build entry
- Ingress at `forge-portal.lucas.engineering`
- Cloudflare Tunnel already configured

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Approachable labels | "Fields" / "Records" for columns/rows | Semi-technical users; tables stay as "tables" |
| Slide-out panel (not modal) | Right-side panel, 400px | Shows form alongside the table; user keeps context of where they are |
| Type-aware inputs | Different input per column type | Dates get date pickers, booleans get toggles, etc. |
| Schema builder inline | Edit fields in-place, not a separate wizard | Faster iteration; user sees changes immediately |
| New table wizard | 2-step modal (name → fields) | Guided experience; suggests a "name" field as starting point |
| `GET /auth/me` endpoint | Returns tenant context from API key | Portal doesn't need user to know their tenant UUID |
| Single database auto-select | Skip database picker if only one | Reduces friction for the common case |

---

## Acceptance Criteria

- [ ] Login with tenant API key works
- [ ] `GET /auth/me` endpoint added to Forge API
- [ ] Database auto-selected if tenant has exactly one
- [ ] Getting started page shown for empty state
- [ ] Table sidebar lists all tables
- [ ] New Table dialog: name + initial fields → creates table
- [ ] Data view: table with sortable columns, paginated
- [ ] Data view: "Add Record" opens slide-out with empty form
- [ ] Data view: Row click opens slide-out with populated form
- [ ] Slide-out: type-appropriate inputs for all field types
- [ ] Slide-out: Save creates/updates record
- [ ] Slide-out: Delete with confirmation
- [ ] Slide-out: Validation errors shown inline
- [ ] Schema builder: add fields with type picker
- [ ] Schema builder: remove fields (except id)
- [ ] Schema builder: delete table with confirmation
- [ ] Search/filter on data view
- [ ] Approachable terminology throughout (fields, records, friendly type names)
- [ ] Helpful empty states with call-to-action
- [ ] Dockerfile builds and serves via nginx
- [ ] Helm chart + ArgoCD + Tekton configured
- [ ] Ingress at `forge-portal.lucas.engineering` with TLS

---

## Next Wave

→ [Wave 2.4 — Portal Polish & UX](wave2_4_portal_polish.md)
