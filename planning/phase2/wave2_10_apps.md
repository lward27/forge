# Wave 2.10 — Apps (Logical Table Grouping)

> Parent: [Master Plan](../master_plan.md)
> Goal: Tables can be organized into logical "Apps" within a single database, enabling cross-app references while keeping data models organized.

---

## Overview

An **App** is a named grouping of tables within a database. Instead of separate databases for CRM and ERP, a tenant has one database with `App: CRM` (companies, contacts, deals) and `App: ERP` (invoices, line_items, payments). Tables in different Apps can freely reference each other via foreign keys.

This solves the cross-database reference problem while giving tenants a clean way to organize multiple logical applications.

---

## Data Model

### `table_definition` — add `app_name` column
| Column | Type | Notes |
|--------|------|-------|
| `app_name` | VARCHAR | Nullable. Tables without an app are "ungrouped." |

No separate `app` table — Apps are implicitly created when a table is assigned one. This keeps it lightweight.

### API Changes

**Table creation** — optional `app_name`:
```json
// POST .../tables
{
  "name": "invoices",
  "app_name": "ERP",
  "columns": [...]
}
```

**Table response** — includes `app_name`:
```json
{
  "name": "invoices",
  "app_name": "ERP",
  "display_field": "invoice_number",
  "columns": [...]
}
```

**List tables** — can filter by app:
```
GET .../tables?app=ERP
```

**New endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `.../apps` | List all apps (derived from distinct app_names) |
| `PUT` | `.../tables/{name}` | Move table to a different app (via `app_name` in alter) |

### Template deployment — assigns app_name
When deploying a template, all tables get the template name as their `app_name`:
- Deploy "CRM" template → all tables get `app_name: "CRM"`
- Deploy "Inventory" template → all tables get `app_name: "Inventory"`

---

## Portal Changes

### Sidebar — grouped by App
```
┌──────────────────────┐
│ CRM                  │
│   companies          │
│   contacts           │
│   deals              │
│   activities         │
│                      │
│ ERP                  │
│   invoices           │
│   line_items         │
│   payments           │
│                      │
│ Ungrouped            │
│   notes              │
│                      │
│ [+ New Table]        │
│ Templates            │
│ AI Chat              │
└──────────────────────┘
```

- Apps are collapsible sections in the sidebar
- Tables within an App are indented
- Ungrouped tables shown at the bottom
- Schema builder: "App" dropdown to move a table between Apps

### Template deploy — auto-groups
When deploying a template, the dialog shows the App name that will be created.

### AI integration
- AI context includes App grouping
- `create_table` tool accepts optional `app_name`
- AI can suggest organizing ungrouped tables into Apps

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Storage | `app_name` column on table_definition | No separate table; apps are lightweight labels |
| Cross-app references | Just works (same database) | FK constraints work within a single PG database |
| App creation | Implicit (first table with that app_name) | No separate "create app" step; reduces friction |
| App deletion | Implicit (no tables left with that app_name) | Clean up happens naturally |
| Ungrouped tables | app_name = NULL | Backwards compatible with existing tables |

---

## Acceptance Criteria

- [ ] `app_name` column on `table_definition`
- [ ] Table create/alter accepts `app_name`
- [ ] Table response includes `app_name`
- [ ] `GET .../apps` lists distinct app names with table counts
- [ ] Sidebar groups tables by App
- [ ] Apps are collapsible in sidebar
- [ ] Template deploy sets `app_name` to template name
- [ ] Schema builder: App dropdown to move tables
- [ ] AI context includes App grouping
- [ ] Cross-app references work (FK between tables in different Apps)
