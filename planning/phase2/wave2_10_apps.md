# Wave 2.10 — Apps (Logical Table Grouping) + Enhanced Templates

> Parent: [Master Plan](../master_plan.md)
> Goal: Tables can be organized into logical "Apps" within a single database. Templates deploy complete apps — tables, views, forms, and a dashboard — in one click.

---

## Overview

An **App** is a named grouping of tables within a database. Instead of separate databases for CRM and ERP, a tenant has one database with `App: CRM` (companies, contacts, deals) and `App: ERP` (invoices, line_items, payments). Tables in different Apps can freely reference each other via foreign keys.

**Templates become full App packages** — deploying a template creates not just tables, but also named views, named forms, and a pre-built dashboard, all organized under an App.

---

## Data Model

### `table_definition` — add `app_name` column
| Column | Type | Notes |
|--------|------|-------|
| `app_name` | VARCHAR | Nullable. Tables without an app are "ungrouped." |

No separate `app` table — Apps are implicitly created when a table is assigned one.

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
| `GET` | `.../apps` | List all apps (derived from distinct app_names) with table counts |
| `PUT` | `.../tables/{name}` | Move table to a different app (via `app_name` in alter) |

---

## Enhanced Template Format

Templates expand from "just tables" to a complete App package:

```json
{
  "name": "CRM",
  "description": "Customer relationship management",
  "icon": "users",
  "tables": [ ... ],
  "views": [
    {
      "table": "companies",
      "name": "Active Companies",
      "config": {
        "columns": [
          {"field": "id", "visible": false, "width": null},
          {"field": "company_name", "visible": true, "width": null},
          {"field": "industry", "visible": true, "width": null},
          {"field": "annual_revenue", "visible": true, "width": null},
          {"field": "is_active", "visible": false, "width": null}
        ],
        "default_sort": {"field": "company_name", "direction": "asc"},
        "default_filters": [{"column": "is_active", "operator": "eq", "value": "true"}],
        "page_size": 25
      }
    },
    {
      "table": "deals",
      "name": "Open Deals",
      "config": {
        "columns": [
          {"field": "deal_name", "visible": true, "width": null},
          {"field": "amount", "visible": true, "width": null},
          {"field": "stage", "visible": true, "width": null},
          {"field": "close_date", "visible": true, "width": null},
          {"field": "company_id", "visible": true, "width": null}
        ],
        "default_sort": {"field": "close_date", "direction": "asc"},
        "page_size": 25
      }
    }
  ],
  "forms": [
    {
      "table": "companies",
      "name": "Quick Add",
      "config": {
        "sections": [
          {
            "title": "Essentials",
            "fields": [
              {"field": "company_name", "visible": true},
              {"field": "industry", "visible": true},
              {"field": "phone", "visible": true}
            ]
          }
        ],
        "related_tables": []
      }
    }
  ],
  "dashboard": {
    "name": "CRM Dashboard",
    "widgets": [
      {"type": "stat", "title": "Companies", "table": "companies", "w": 3, "h": 2},
      {"type": "stat", "title": "Contacts", "table": "contacts", "w": 3, "h": 2},
      {"type": "stat", "title": "Deals", "table": "deals", "w": 3, "h": 2},
      {"type": "stat", "title": "Activities", "table": "activities", "w": 3, "h": 2},
      {"type": "view", "title": "Active Companies", "table": "companies", "view_name": "Active Companies", "w": 6, "h": 4},
      {"type": "view", "title": "Open Deals", "table": "deals", "view_name": "Open Deals", "w": 6, "h": 4},
      {"type": "form", "title": "Log Activity", "table": "activities", "w": 4, "h": 4}
    ]
  }
}
```

### Deploy Order

When deploying a template:
1. Create all tables (in FK order, as today)
2. Set `app_name` on all tables
3. Create named views (link `view_name` references to view IDs for dashboard)
4. Create named forms
5. Create the dashboard with widgets (resolve `view_name` to `view_id`)

---

## Portal Changes

### Sidebar — grouped by App
```
┌──────────────────────┐
│ ▼ CRM                │
│    companies          │
│    contacts           │
│    deals              │
│    activities         │
│                       │
│ ▶ ERP                 │
│                       │
│ Ungrouped             │
│    notes              │
│                       │
│ [+ New Table]         │
│ Templates             │
│ AI Chat               │
└───────────────────────┘
```

- Apps are collapsible sections (▼ expanded, ▶ collapsed)
- Tables within an App are indented
- Ungrouped tables shown at the bottom under "Ungrouped" (or hidden if none)
- Schema builder: "App" dropdown to move a table between Apps

### Template gallery — shows what you get
Template cards show:
- Table count
- View count
- Form count
- "Includes dashboard" badge

Deploy confirmation shows the full manifest — tables, views, forms, dashboard.

### AI integration
- AI context includes App grouping
- `create_table` tool accepts optional `app_name`
- `deploy_template` tool creates the full package (tables + views + forms + dashboard)
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
| Template scope | Tables + views + forms + dashboard | Deploy a complete, ready-to-use app in one click |
| Dashboard view references | Resolved at deploy time | Template uses `view_name`, deploy resolves to `view_id` |

---

## Acceptance Criteria

### Apps
- [ ] `app_name` column on `table_definition`
- [ ] Table create/alter accepts `app_name`
- [ ] Table response includes `app_name`
- [ ] `GET .../apps` lists distinct app names with table counts
- [ ] Sidebar groups tables by App (collapsible)
- [ ] Schema builder: App dropdown to move tables
- [ ] AI context includes App grouping
- [ ] Cross-app references work (FK between tables in different Apps)

### Enhanced Templates
- [ ] Template JSON includes `views`, `forms`, `dashboard` sections
- [ ] Deploy creates named views for each template view
- [ ] Deploy creates named forms for each template form
- [ ] Deploy creates a dashboard with widgets (view_name resolved to view_id)
- [ ] Deploy sets `app_name` on all created tables
- [ ] Template gallery shows view/form/dashboard counts
- [ ] AI `deploy_template` tool creates the full package
- [ ] All 4 templates updated with views, forms, and dashboards
