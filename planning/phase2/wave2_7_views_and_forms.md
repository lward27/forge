# Wave 2.7 — Views & Forms

> Parent: [Master Plan](../master_plan.md)
> Depends on: [Wave 2.6 — Display Fields & Detail Page](wave2_6_display_fields_and_detail_page.md)
> Goal: Each table has a default view and default form that auto-generate from the schema. Foundation for future custom named views/forms.

---

## Overview

When a table is created (or modified), the platform auto-generates:
- A **default view** — defines how the data table displays records (which columns, order, default sort)
- A **default form** — defines how the record detail page renders (which fields, order, sections, which related tables to show)

These are stored in the platform DB and served to the portal, which renders based on the configuration rather than hardcoding the schema. This decouples the UI layout from the raw schema and sets the stage for Wave 2.8 (multiple named views/forms).

---

## Concept

### View
A view configures the **list/table display** of records:
```json
{
  "id": "uuid",
  "table_name": "contacts",
  "name": "default",
  "is_default": true,
  "config": {
    "columns": [
      {"field": "full_name", "width": null, "visible": true},
      {"field": "email", "width": null, "visible": true},
      {"field": "customer_id", "width": null, "visible": true},
      {"field": "phone", "width": null, "visible": false}
    ],
    "default_sort": {"field": "full_name", "direction": "asc"},
    "page_size": 25
  }
}
```

### Form
A form configures the **record detail page**:
```json
{
  "id": "uuid",
  "table_name": "contacts",
  "name": "default",
  "is_default": true,
  "config": {
    "sections": [
      {
        "title": "Details",
        "fields": [
          {"field": "full_name", "visible": true},
          {"field": "email", "visible": true},
          {"field": "customer_id", "visible": true},
          {"field": "phone", "visible": true}
        ]
      }
    ],
    "related_tables": [
      {
        "table": "orders",
        "reference_column": "customer_id",
        "visible": true,
        "collapsed": false,
        "columns": ["product", "amount", "status"]
      }
    ]
  }
}
```

---

## Data Model

### `table_view` table
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `database_id` | UUID | FK → tenant_database.id |
| `table_name` | VARCHAR | Which table this view is for |
| `name` | VARCHAR | "default" for auto-generated, custom name for user-created |
| `is_default` | BOOLEAN | True for the auto-generated view |
| `config` | JSON | View configuration (columns, sort, page_size) |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### `table_form` table
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `database_id` | UUID | FK → tenant_database.id |
| `table_name` | VARCHAR | Which table this form is for |
| `name` | VARCHAR | "default" for auto-generated, custom name for user-created |
| `is_default` | BOOLEAN | True for the auto-generated form |
| `config` | JSON | Form configuration (sections, fields, related_tables) |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

---

## Auto-Generation Rules

### On Table Create
- Generate default view: all columns visible, ordered by ordinal, sort by `id` asc, page_size 25
- Generate default form: one "Details" section with all non-PK fields, all visible

### On Column Add
- Append new column to default view (visible: true)
- Append new field to the first section of default form (visible: true)

### On Column Drop
- Remove column from default view
- Remove field from default form

### On Related Table Created (reference column added elsewhere)
- Append related table to default form's `related_tables` (visible: true, collapsed: false, all columns)

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `.../tables/{name}/views` | List views for a table |
| `GET` | `.../tables/{name}/views/{view_id}` | Get a specific view |
| `PUT` | `.../tables/{name}/views/{view_id}` | Update a view's config |
| `GET` | `.../tables/{name}/forms` | List forms for a table |
| `GET` | `.../tables/{name}/forms/{form_id}` | Get a specific form |
| `PUT` | `.../tables/{name}/forms/{form_id}` | Update a form's config |

For Wave 2.7, there's only one view and one form per table (the default). The list endpoints return a single item. Wave 2.8 adds `POST` (create named) and `DELETE`.

---

## Portal Changes

### Data View Page
- Fetch the default view config: `GET .../tables/{name}/views?default=true`
- Render columns based on view config (only visible columns, in config order)
- Use config's `default_sort` and `page_size`

### Record Detail Page
- Fetch the default form config: `GET .../tables/{name}/forms?default=true`
- Render form sections based on config
- Render related tables based on config (only visible ones, respect `collapsed` and `columns`)

### View Customizer (new)
- Accessible from the data view header (e.g., gear icon or "Customize View" button)
- Slide-out or modal showing:
  - Column list with visibility toggles and drag-to-reorder
  - Default sort picker
  - Page size selector
- Changes save back via `PUT .../views/{id}`

### Form Customizer (new)
- Accessible from the record detail page header
- Slide-out or modal showing:
  - Section management (rename, reorder sections)
  - Field list per section with visibility toggles and drag-to-reorder
  - Related tables list with visibility toggles and column selection
- Changes save back via `PUT .../forms/{id}`

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Storage format | JSON config column | Flexible, schema-less; configs evolve without migrations |
| Auto-generation | On table create + on schema change | Default view/form always reflects current schema |
| Default names | "default" | Simple convention; Wave 2.8 adds named views/forms |
| Customization scope | Per-table (not per-user) | All tenant users see the same view/form. Per-user in Phase 4 |
| Related tables in form | Auto-discovered from FK references | No manual config needed; just toggle visibility |

---

## Acceptance Criteria

- [ ] `table_view` and `table_form` tables created in platform DB
- [ ] Default view auto-generated on table creation
- [ ] Default form auto-generated on table creation
- [ ] Default view/form updated when columns are added/dropped
- [ ] Default form updated when related tables are discovered
- [ ] `GET .../views` returns the default view config
- [ ] `PUT .../views/{id}` updates the view config
- [ ] `GET .../forms` returns the default form config
- [ ] `PUT .../forms/{id}` updates the form config
- [ ] Portal data view renders based on view config (column visibility, order, sort)
- [ ] Portal record detail renders based on form config (sections, fields, related tables)
- [ ] View customizer: toggle column visibility, reorder, set sort
- [ ] Form customizer: toggle field visibility, reorder, configure related tables

---

## Future: Wave 2.8 — Multiple Named Views & Forms

Extends this wave with:
- `POST .../views` — create a named view (e.g., "Sales Summary", "Admin View")
- `POST .../forms` — create a named form (e.g., "Quick Edit", "Full Detail")
- View/form picker in the portal UI
- Per-user default view preference
- View sharing between users

This is deferred to keep Wave 2.7 focused on the foundation.

---

## Next Phase

→ [Phase 3 — AI-Driven Interface](../../master_plan.md#phase-3--ai-driven-interface)
