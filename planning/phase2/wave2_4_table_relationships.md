# Wave 2.4 — Table Relationships

> Parent: [Master Plan](../master_plan.md)
> Depends on: [Wave 2.3 — Tenant Portal](wave2_3_tenant_portal.md) (complete)
> Goal: Users can create foreign key relationships between tables. Reference fields show as dropdowns in the portal and support navigation between parent/child records.

---

## Overview

Add a `reference` column type that creates a foreign key to another table's `id` column. This enables the core relational pattern — customers have contacts, orders have line items, projects have tasks. The portal renders reference fields as dropdowns and shows related child records on the parent detail view.

---

## Data Model Changes

### New column type: `reference`

| Platform Type | PG Type | Constraint |
|---------------|---------|------------|
| `reference` | `INTEGER` | `REFERENCES {target_table}(id)` |

### column_definition table — new field

| Column | Type | Notes |
|--------|------|-------|
| `reference_table` | VARCHAR | Target table name (nullable, only set for reference type) |

### DDL Generated

When creating a reference column:
```sql
ALTER TABLE contacts ADD COLUMN customer_id INTEGER REFERENCES customers(id);
```

When dropping a reference column, the FK constraint is automatically dropped with the column.

---

## API Changes

### Create Table / Alter Table — reference columns

Reference columns use type `reference` and require a `reference_table` field:

```json
// POST .../tables (create with reference)
{
  "name": "contacts",
  "columns": [
    {"name": "full_name", "type": "text", "nullable": false},
    {"name": "email", "type": "text"},
    {"name": "customer_id", "type": "reference", "reference_table": "customers"}
  ]
}

// PUT .../tables/contacts (add reference column)
{
  "add_columns": [
    {"name": "assigned_to", "type": "reference", "reference_table": "employees"}
  ]
}
```

### Table Schema Response — includes reference info

```json
// GET .../tables/contacts
{
  "name": "contacts",
  "columns": [
    {"name": "id", "type": "serial", "primary_key": true, ...},
    {"name": "full_name", "type": "text", ...},
    {"name": "email", "type": "text", ...},
    {
      "name": "customer_id",
      "type": "reference",
      "nullable": true,
      "reference_table": "customers",
      ...
    }
  ]
}
```

### Row Expansion — optional related data

```
GET .../tables/contacts/rows?expand=customer_id
```

```json
{
  "rows": [
    {
      "id": 1,
      "full_name": "Alice Smith",
      "customer_id": 5,
      "customer_id__expanded": {
        "id": 5,
        "name": "Acme Corp"
      }
    }
  ]
}
```

Expansion is optional (only when `?expand=` is provided) to keep default responses lightweight. Multiple expansions: `?expand=customer_id,assigned_to`.

### Related Records — child lookup

```
GET .../tables/customers/rows/5/related
```

```json
{
  "related": [
    {
      "table": "contacts",
      "column": "customer_id",
      "count": 3,
      "rows": [
        {"id": 1, "full_name": "Alice Smith", "email": "alice@acme.com", "customer_id": 5},
        {"id": 2, "full_name": "Bob Jones", "email": "bob@acme.com", "customer_id": 5},
        {"id": 3, "full_name": "Carol Lee", "email": "carol@acme.com", "customer_id": 5}
      ]
    }
  ]
}
```

This endpoint scans all tables in the same database for reference columns pointing to the given table and returns matching rows.

---

## Portal UX Changes

### Schema Builder — reference type in field picker

- Type dropdown includes "Reference" at the end of the list
- Selecting "Reference" reveals a second dropdown: "References which table?"
  - Populated from the list of tables in the same database (excluding the current table)
- Convention: field name auto-suggests `{target_table}_id` (e.g., selecting "customers" suggests "customer_id")

### Data View — reference columns render as dropdowns

- **On the data table**: reference columns show the referenced record's display value (first text column of the target table) instead of a raw ID
- **On the slide-out form**: reference fields render as a searchable dropdown
  - Dropdown options loaded from the target table (first 100 rows, showing first text column + id)
  - Type-to-search filters the dropdown
  - "Clear" option to set NULL (if nullable)
  - Click on the selected value navigates to that record's table/row

### Slide-out — related records section

When viewing a record, if other tables have reference columns pointing to this table:
- A "Related Records" section appears below the form fields
- Each related table shows as a collapsible section:
  - Header: "{table_name} ({count})"
  - List of related rows (compact view — first 2-3 columns)
  - "View all" link navigates to the related table with a filter applied
  - "Add {table_name}" button to create a new related record (pre-fills the FK)

---

## Implementation

### API Changes (forge repo)

```
platform/src/forge_platform/
├── models/
│   └── column_definition.py      (update: add reference_table field)
├── schemas/
│   ├── table.py                  (update: ColumnCreate adds reference_table)
│   └── row.py                    (update: expand param support)
├── services/
│   ├── table_service.py          (update: handle reference columns)
│   ├── row_service.py            (update: expand logic, related records)
│   └── postgres_service.py       (update: FK DDL, expand queries)
├── routers/
│   ├── tables.py                 (update: schema response includes reference_table)
│   └── rows.py                   (update: expand param, related endpoint)
```

### Portal Changes (forge-portal repo)

```
src/
├── components/
│   ├── FieldInput.tsx            (update: reference dropdown)
│   ├── ReferenceSelect.tsx       (new: searchable reference dropdown)
│   ├── RelatedRecords.tsx        (new: related records section in slide-out)
│   └── TypeBadge.tsx             (update: reference type color)
├── pages/
│   ├── DataViewPage.tsx          (update: display expanded references)
│   └── SchemaBuilderPage.tsx     (update: reference_table picker)
├── types/
│   └── index.ts                  (update: add reference types)
```

---

## Validation Rules

| Scenario | Behavior |
|----------|----------|
| Reference to nonexistent table | 400: "Referenced table 'foo' does not exist" |
| Reference to self | Allowed (self-referential FK, e.g., parent_id on categories) |
| Insert with invalid reference ID | PG returns FK violation → 400: "Referenced record does not exist" |
| Delete parent with existing children | PG returns FK violation → 400: "Cannot delete — referenced by N records in {table}" |
| Drop referenced table | 400: "Cannot delete table — referenced by column '{col}' in table '{table}'" |
| Reference column naming | Suggested `{table}_id` but not enforced |

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| FK constraint in PG | Real `REFERENCES` constraint | Database enforces integrity; no orphaned records |
| Expand via query param | `?expand=col1,col2` | Optional; keeps default responses fast |
| Related records endpoint | Dedicated `GET .../rows/{pk}/related` | Separate call avoids loading all relations on every row view |
| Reference dropdown | First text column as display | Convention: most tables have a "name" or "title" as first text field |
| Cascade behavior | No cascade (restrict delete) | Safer default; user must delete children first. Cascade can be added later |
| Display value | First non-PK text column | Simple heuristic; works for 90% of cases (name, title, label) |

---

## Acceptance Criteria

- [ ] `reference` type available in column creation (API + portal)
- [ ] Reference columns create real PG foreign key constraints
- [ ] `reference_table` stored in column_definition metadata
- [ ] Schema response includes `reference_table` for reference columns
- [ ] Portal schema builder shows table picker for reference type
- [ ] Portal data view shows display value (not raw ID) for reference columns
- [ ] Portal slide-out renders searchable dropdown for reference fields
- [ ] `?expand=col` returns expanded reference data inline
- [ ] `GET .../rows/{pk}/related` returns child records from referencing tables
- [ ] Portal slide-out shows "Related Records" section for parent records
- [ ] FK violation on insert returns friendly error
- [ ] FK violation on delete returns friendly error with count
- [ ] Cannot drop a table that is referenced by other tables
- [ ] Self-referential references work (parent_id → same table)
- [ ] Unit tests for reference DDL, expand, and related queries

---

## Next Wave

→ [Wave 2.5 — Portal Polish & UX](wave2_5_portal_polish.md)
