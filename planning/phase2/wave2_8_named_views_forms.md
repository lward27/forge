# Wave 2.8 — Multiple Named Views & Forms

> Parent: [Master Plan](../master_plan.md)
> Depends on: [Wave 2.7 — Views & Forms](wave2_7_views_and_forms.md) (complete)
> Goal: Users can create, name, and switch between multiple views and forms per table.

---

## Overview

Wave 2.7 introduced one auto-generated default view and form per table. This wave extends that to support **multiple named views and forms** — each with its own configuration. Users can create a "Sales Summary" view that only shows certain columns sorted by revenue, or a "Quick Edit" form that hides optional fields.

The default view/form remains auto-generated and always reflects the current schema. Named views/forms are user-created and don't auto-update (they're intentionally frozen configurations).

---

## Concepts

### Named View
A saved configuration for displaying a table's data:
- Custom name (e.g., "Active Customers", "Recent Orders")
- Column visibility and order
- Default sort and direction
- Default filters (pre-applied on load)
- Page size

### Named Form
A saved configuration for viewing/editing a record:
- Custom name (e.g., "Quick Edit", "Full Detail", "Customer Overview")
- Field visibility and order per section
- Section titles and grouping
- Related table visibility and configuration

---

## API Changes

### New Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `.../tables/{name}/views` | Create a named view |
| `DELETE` | `.../tables/{name}/views/{view_id}` | Delete a named view |
| `POST` | `.../tables/{name}/forms` | Create a named form |
| `DELETE` | `.../tables/{name}/forms/{form_id}` | Delete a named form |

Existing `GET` and `PUT` endpoints from Wave 2.7 continue to work. The `GET .../views` endpoint now returns all views (default + named).

### Create View
```json
// POST .../tables/customers/views
{
  "name": "Active Customers",
  "config": {
    "columns": [
      {"field": "company_name", "visible": true, "width": null},
      {"field": "industry", "visible": true, "width": null},
      {"field": "annual_revenue", "visible": true, "width": null},
      {"field": "is_active", "visible": false, "width": null}
    ],
    "default_sort": {"field": "annual_revenue", "direction": "desc"},
    "default_filters": [
      {"column": "is_active", "operator": "eq", "value": "true"}
    ],
    "page_size": 50
  }
}

// Response (201)
{
  "id": "uuid",
  "table_name": "customers",
  "name": "Active Customers",
  "is_default": false,
  "config": { ... },
  "created_at": "..."
}
```

### View Config Extension — default_filters

Views can now include pre-applied filters:
```json
"default_filters": [
  {"column": "status", "operator": "eq", "value": "pending"},
  {"column": "total_amount", "operator": "gte", "value": "100"}
]
```

These are applied automatically when the view loads. Users can add additional filters on top.

---

## Portal Changes

### View Picker (Data View Page)
- **View selector dropdown** in the header, next to the table name
- Shows: "Default View" + all named views
- Selecting a view reloads the data with that view's config (columns, sort, filters, page size)
- **"Save as New View" button** in the view customizer — saves current customization as a named view
- **"Delete View" button** on named views (not on default)

### Form Picker (Record Detail Page)
- **Form selector dropdown** in the header
- Shows: "Default Form" + all named forms
- Selecting a form re-renders the record with that form's field/section/related config
- **"Save as New Form" button** in the form customizer
- **"Delete Form" button** on named forms (not on default)

### Create Flow
1. User customizes the default view (hides columns, sorts, etc.)
2. Clicks "Save as New View"
3. Enters a name (e.g., "Active Customers")
4. View is saved and appears in the dropdown
5. Default view reverts to its auto-generated state

### URL Integration
The selected view/form ID is stored in the URL query param so it's shareable:
- `/tables/customers?view=uuid`
- `/tables/customers/records/5?form=uuid`

---

## Implementation

### API Changes (forge repo)

```
platform/src/forge_platform/
├── schemas/
│   └── view_form.py              (new: create/response schemas)
├── services/
│   └── view_form_service.py      (update: create, delete, list all)
├── routers/
│   └── views_forms.py            (update: POST, DELETE endpoints, list returns all)
```

### Portal Changes (forge-portal repo)

```
src/
├── components/
│   ├── ViewPicker.tsx            (new: dropdown to select view)
│   ├── FormPicker.tsx            (new: dropdown to select form)
│   ├── ViewCustomizer.tsx        (update: "Save as New View" button)
│   └── FormCustomizer.tsx        (update: "Save as New Form" button)
├── pages/
│   ├── DataViewPage.tsx          (update: view picker, URL params, default_filters)
│   └── RecordDetailPage.tsx      (update: form picker, URL params)
```

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Default view behavior | Auto-regenerates on schema change | Always reflects current schema; named views are frozen |
| Named view on schema change | Keeps config as-is; missing columns ignored | User intent preserved; they can update manually |
| Default filters in views | Applied on load, user can add more | Pre-filtered views are the primary use case for named views |
| URL params for view/form | `?view=uuid` / `?form=uuid` | Shareable, bookmarkable, works with browser back |
| Delete protection | Cannot delete the default view/form | Default always exists as a fallback |
| Duplicate prevention | Names must be unique per table | Avoid confusion in the dropdown |

---

## Acceptance Criteria

- [ ] `POST .../views` creates a named view
- [ ] `POST .../forms` creates a named form
- [ ] `DELETE .../views/{id}` deletes a named view (not default)
- [ ] `DELETE .../forms/{id}` deletes a named form (not default)
- [ ] `GET .../views` returns default + all named views
- [ ] `GET .../forms` returns default + all named forms
- [ ] View config supports `default_filters`
- [ ] Portal: view picker dropdown on data view page
- [ ] Portal: form picker dropdown on record detail page
- [ ] Selecting a named view applies its column/sort/filter config
- [ ] Selecting a named form applies its field/section/related config
- [ ] "Save as New View" in view customizer
- [ ] "Save as New Form" in form customizer
- [ ] Delete button on named views/forms (not default)
- [ ] View/form selection persisted in URL query params
- [ ] Named views with default_filters auto-apply on load

---

## AI Integration (Phase 3 Preview)

With named views/forms, the AI can:
- "Show me overdue orders" → creates a named view "Overdue Orders" with filter `status:eq:pending` + sort by `order_date asc`
- "Create a quick-add form for contacts" → creates a named form "Quick Add" with only required fields visible
- "Make a dashboard for customer health" → creates views for different customer segments

---

## Next Phase

→ [Phase 3 — AI-Driven Interface](../../master_plan.md#phase-3--ai-driven-interface)
