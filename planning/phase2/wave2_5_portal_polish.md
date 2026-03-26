# Wave 2.5 — Portal Polish & UX

> Parent: [Master Plan](../master_plan.md)
> Depends on: [Wave 2.4 — Table Relationships](wave2_4_table_relationships.md)
> Goal: Refine the tenant portal based on real usage — search, export, bulk actions, responsive design, and better error handling.

---

## Overview

Wave 2.3 delivered the core portal experience. This wave polishes it into something production-worthy — adding features that users expect from a data management tool and fixing rough edges that become apparent through real usage.

---

## Features

### 1. Global Search
- **Search bar at top of data view** — already exists as a basic text filter
- **Upgrade**: search across ALL text fields simultaneously (not just the first one)
- Debounced input (300ms) to avoid excessive API calls
- Clear button to reset search
- Show "Searching..." indicator while loading

### 2. CSV Export
- **"Export" button** next to "Add Record" on the data view header
- Exports the current table (with active filters applied) as a CSV file
- Uses client-side generation — fetches all matching rows (up to 10,000) then generates CSV
- Download triggers automatically via browser
- Column headers use field names
- Respects current filter/sort state

### 3. Bulk Actions
- **Checkbox column** (leftmost) on the data table
- **"Select all" checkbox** in header (selects current page)
- **Bulk action bar** appears when rows are selected:
  - "Delete N records" button (with confirmation)
  - "Deselect all" button
- Count badge showing how many rows are selected

### 4. Column Reordering (Schema Builder)
- Drag-and-drop reordering of fields in the schema builder
- Updates the `ordinal` field on column definitions
- Reflected in data view column order
- **Note**: requires a new API endpoint or extension to `PUT .../tables/{name}` to accept ordinal updates

### 5. Inline Validation on Forms
- **Required field indicators** — already exists (red asterisk)
- **Real-time validation** as user types:
  - Number fields reject non-numeric input
  - Required fields show error on blur if empty
  - Unique constraint violation shown after save attempt (from API 409)
- **Error summary** at top of form if save fails
- **Success feedback** — brief green toast/flash after save

### 6. Responsive Design
- **Sidebar collapses** to icons-only on screens < 1024px
- **Hamburger menu** on mobile to toggle sidebar
- **Data table** becomes horizontally scrollable on small screens
- **Slide-out panel** becomes full-width overlay on mobile
- **Top bar** adjusts for mobile (smaller logo, compact layout)
- **Minimum supported width**: 375px (iPhone SE)

### 7. Loading & Error States
- **Skeleton loaders** — gray pulsing placeholders while tables load (instead of "Loading..." text)
- **Error boundary** — catch React rendering errors, show friendly "Something went wrong" page with retry
- **API error toasts** — brief notification at top-right when an API call fails
- **Empty state improvements** — contextual messages per page, with illustrations or icons
- **Optimistic UI** — show row deletion immediately, rollback on error

### 8. Toast Notifications
- Lightweight toast system (top-right corner)
- Auto-dismiss after 3 seconds
- Types: success (green), error (red), info (blue)
- Used for: record saved, record deleted, export complete, API errors

---

## API Changes Required

### Bulk Delete Endpoint
New endpoint on the Forge API:

```
POST /tenants/{tid}/databases/{did}/tables/{table}/rows/bulk-delete
```

```json
// Request
{
  "ids": [1, 3, 7, 12]
}

// Response (200)
{
  "deleted": 4
}
```

### Column Reorder
Extend `PUT .../tables/{name}` to accept ordinal updates:

```json
// Request — reorder only (no add/drop)
{
  "reorder_columns": [
    {"name": "email", "ordinal": 1},
    {"name": "name", "ordinal": 2},
    {"name": "phone", "ordinal": 3}
  ]
}
```

### Export Support
No new API endpoint needed — the portal fetches rows with `?limit=10000` and generates CSV client-side. However, we should add a `GET .../rows/count` endpoint or ensure the existing `total` in list responses is reliable for large datasets.

---

## Implementation

### New/Modified Files (forge-portal)

```
src/
├── components/
│   ├── Toast.tsx                 (new: toast notification system)
│   ├── ToastProvider.tsx         (new: context + container)
│   ├── Skeleton.tsx              (new: skeleton loader components)
│   ├── ErrorBoundary.tsx         (new: React error boundary)
│   ├── BulkActionBar.tsx         (new: selected rows action bar)
│   ├── DataTable.tsx             (update: checkboxes, reorder)
│   ├── SlideOutPanel.tsx         (update: responsive)
│   ├── TableSidebar.tsx          (update: collapsible)
│   ├── Layout.tsx                (update: responsive)
│   └── TopBar.tsx                (update: responsive + mobile menu)
├── pages/
│   ├── DataViewPage.tsx          (update: search, export, bulk, toasts)
│   └── SchemaBuilderPage.tsx     (update: drag reorder)
├── hooks/
│   └── useToast.ts               (new: toast hook)
└── utils/
    └── csv.ts                    (new: CSV generation utility)
```

### New/Modified Files (forge API)

```
platform/src/forge_platform/
├── routers/
│   └── rows.py                   (update: add bulk-delete endpoint)
├── services/
│   ├── row_service.py            (update: bulk delete)
│   ├── table_service.py          (update: reorder columns)
│   └── postgres_service.py       (update: bulk delete DML)
```

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| CSV export | Client-side generation | No server-side file generation needed; works with existing list endpoint |
| Export limit | 10,000 rows | Prevents browser memory issues; covers most use cases |
| Bulk delete | Dedicated endpoint (not N individual deletes) | Single transaction, much faster for large selections |
| Drag reorder | HTML5 drag-and-drop | No extra library needed; schema builder is simple enough |
| Toast system | Custom (not a library) | Keep bundle small; only need 3 toast types |
| Responsive breakpoint | 1024px sidebar collapse, 768px mobile | Standard breakpoints matching Tailwind defaults |
| Skeleton loaders | CSS animation (Tailwind `animate-pulse`) | No library needed; just gray rectangles with pulse |

---

## Acceptance Criteria

- [ ] Search filters across all text columns simultaneously
- [ ] Search is debounced (300ms)
- [ ] CSV export downloads current table with active filters
- [ ] CSV export handles up to 10,000 rows
- [ ] Bulk select via checkboxes on data table
- [ ] Bulk delete with confirmation dialog
- [ ] `POST .../rows/bulk-delete` endpoint works
- [ ] Column reorder via drag-and-drop in schema builder
- [ ] Reorder persisted via API (ordinal update)
- [ ] Form validation: required fields show error on blur
- [ ] Form save errors shown inline
- [ ] Toast notifications for success/error actions
- [ ] Skeleton loaders while data is loading
- [ ] Error boundary catches rendering crashes
- [ ] Sidebar collapses on screens < 1024px
- [ ] Slide-out panel goes full-width on mobile
- [ ] Data table is horizontally scrollable on small screens
- [ ] Works on 375px width (iPhone SE)

---

## Priority Order

If time is limited, implement in this order (highest impact first):

1. **Toast notifications** — improves every interaction
2. **Loading skeletons** — removes "Loading..." jank
3. **Search upgrade** — multi-column search
4. **CSV export** — most-requested data tool feature
5. **Bulk delete** — saves time on data cleanup
6. **Responsive design** — tablet/mobile support
7. **Form validation** — better error UX
8. **Column reorder** — nice-to-have

---

## Next Phase

→ [Phase 3 — AI-Driven Interface](../../master_plan.md#phase-3--ai-driven-interface)
