# Wave 2.6 — Display Fields & Record Detail Page

> Parent: [Master Plan](../master_plan.md)
> Depends on: [Wave 2.5 — Portal Polish](wave2_5_portal_polish.md) (complete)
> Goal: Reference columns show a human-readable display value. Clicking a record opens a full-page detail view instead of a slide-out.

---

## Overview

Two foundational improvements:
1. Each table gets a configurable **display field** — the column used to represent records wherever they're referenced (dropdowns, child tables, breadcrumbs). Set once, used everywhere.
2. Record detail becomes a **full-page form** with room for related child records displayed in a wider layout.

---

## Feature 1: Table Display Field

### Concept

Every table has a `display_field` — the column name used to represent records of that table in UI contexts. Defaults to the first non-PK text column on table creation. Configurable in the schema builder.

Examples:
- `customers` table → display_field = `name` → contacts show "Acme Corp" instead of "5"
- `products` table → display_field = `title` → order_items show "Widget Pro" instead of "12"

### Data Model Change

Add to `table_definition`:

| Column | Type | Notes |
|--------|------|-------|
| `display_field` | VARCHAR | Column name to use as display value. Defaults to first text column. |

### API Changes

**Table creation/response** — includes `display_field`:
```json
// POST .../tables
{
  "name": "customers",
  "columns": [...],
  "display_field": "name"  // optional, auto-detected if omitted
}

// GET .../tables/customers
{
  "name": "customers",
  "display_field": "name",
  "columns": [...]
}
```

**Update display field** — via existing ALTER endpoint:
```json
// PUT .../tables/customers
{
  "display_field": "company_name"
}
```

**Row list with references** — when a table has reference columns, the API automatically includes the display value:
```json
// GET .../tables/contacts/rows
{
  "rows": [
    {
      "id": 1,
      "full_name": "Alice",
      "customer_id": 5,
      "customer_id__display": "Acme Corp"
    }
  ]
}
```

The `__display` suffix is always included for reference columns (no `?expand` needed). This is a lightweight join — just fetches the display field value, not the full referenced record.

### Portal Changes

- **Data table**: reference columns show the `__display` value instead of the raw ID
- **Reference dropdown** (FieldInput): options show the display field value
- **Schema builder**: "Display Field" dropdown at the top of table settings, populated from the table's text columns
- **Auto-detection**: on table creation, if no display_field specified, use the first non-PK text column

---

## Feature 2: Full-Page Record Detail

### Concept

Clicking a row in the data table navigates to a dedicated record page at `/tables/{name}/records/{id}`. This replaces the slide-out panel for viewing/editing records. The slide-out is still used for "Add Record" (quick creation without losing context).

### Route

```
/tables/:tableName/records/:recordId
```

### Page Layout

```
┌────────────────────────────────────────────────────────────────┐
│  ← Back to {tableName}          Record #{id}      [Save] [Del]│
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌─────────────────────────────────┐                           │
│  │          Record Form            │                           │
│  │  name: [Alice Smith        ]    │                           │
│  │  email: [alice@acme.com    ]    │                           │
│  │  customer: [Acme Corp ▼    ]    │                           │
│  │  phone: [555-1234          ]    │                           │
│  └─────────────────────────────────┘                           │
│                                                                │
│  ┌─────────────────────────────────────────────────────────────┐
│  │  Related: Orders (3)                              [+ Add]  │
│  │  ┌──────┬──────────────┬──────────┬─────────┐              │
│  │  │ ID   │ Product      │ Amount   │ Status  │              │
│  │  ├──────┼──────────────┼──────────┼─────────┤              │
│  │  │ 101  │ Widget Pro   │ $49.99   │ shipped │              │
│  │  │ 102  │ Gizmo Plus   │ $24.50   │ pending │              │
│  │  │ 103  │ Doohickey    │ $5.00    │ pending │              │
│  │  └──────┴──────────────┴──────────┴─────────┘              │
│  └─────────────────────────────────────────────────────────────┘
│                                                                │
│  ┌─────────────────────────────────────────────────────────────┐
│  │  Related: Notes (1)                               [+ Add]  │
│  │  ...                                                        │
│  └─────────────────────────────────────────────────────────────┘
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### Key UX Details

- **Back button** returns to the table data view
- **Form fields** use the same `FieldInput` components (type-aware inputs)
- **Save button** at the top (always visible, not buried at the bottom)
- **Delete button** with confirmation
- **Related records** shown in full-width tables below the form
  - Each child table that references this table gets its own section
  - Sections are collapsible, expanded by default if ≤ 20 records
  - **"+ Add" button** on each related section creates a new child record with the FK pre-filled
  - Clicking a related record navigates to its detail page
  - Related tables show their columns (respecting display_field for any reference columns they have)

### Navigation Changes

- **Data table row click** → navigates to `/tables/{name}/records/{id}` (instead of opening slide-out)
- **"Add Record" button** → still opens slide-out for quick creation (stays on data view)
- **Related record click** → navigates to that record's detail page
- **"+ Add" on related section** → opens slide-out with FK pre-filled, stays on current page
- **Breadcrumbs**: Tables > {tableName} > Record #{id}

---

## Implementation

### API Changes (forge repo)

```
platform/src/forge_platform/
├── models/
│   └── table_definition.py      (update: add display_field)
├── schemas/
│   └── table.py                  (update: display_field in create/response/alter)
├── services/
│   ├── table_service.py          (update: auto-detect display_field, update on alter)
│   ├── row_service.py            (update: auto-join display values for reference cols)
│   └── postgres_service.py       (update: display value join query)
├── routers/
│   └── tables.py                 (update: include display_field in responses)
```

### Portal Changes (forge-portal repo)

```
src/
├── pages/
│   ├── DataViewPage.tsx          (update: row click → navigate, show __display values)
│   ├── RecordDetailPage.tsx      (new: full-page record form + related records)
│   └── SchemaBuilderPage.tsx     (update: display field picker)
├── components/
│   ├── RecordForm.tsx            (new: reusable form for detail page + slide-out)
│   ├── RelatedTable.tsx          (new: full-width related records table)
│   └── ReferenceSelect.tsx       (update: use display_field for option labels)
├── App.tsx                       (update: add RecordDetailPage route)
```

### Database Migration

```sql
ALTER TABLE table_definition ADD COLUMN display_field VARCHAR;
```

---

## Acceptance Criteria

- [ ] `table_definition` has `display_field` column
- [ ] Display field auto-detected on table creation (first non-PK text column)
- [ ] Display field configurable in schema builder settings
- [ ] `PUT .../tables/{name}` accepts `display_field` update
- [ ] Row list API includes `{ref_col}__display` for all reference columns
- [ ] Data table shows display value (not raw ID) for reference columns
- [ ] Reference dropdown shows display field values
- [ ] Row click navigates to `/tables/{name}/records/{id}`
- [ ] Record detail page shows form + related child tables
- [ ] Related tables show in full-width layout below the form
- [ ] "Add Record" from data view still uses slide-out
- [ ] "+ Add" on related section pre-fills FK and uses slide-out
- [ ] Clicking related record navigates to its detail page
- [ ] Save/Delete buttons at top of detail page
- [ ] Back button returns to data view

---

## Next Wave

→ [Wave 2.7 — Views & Forms](wave2_7_views_and_forms.md)
