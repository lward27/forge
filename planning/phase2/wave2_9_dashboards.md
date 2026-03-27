# Wave 2.9 — Dashboards

> Parent: [Master Plan](../master_plan.md)
> Depends on: [Wave 2.8 — Named Views & Forms](wave2_8_named_views_forms.md) (complete)
> Goal: Users can create named dashboards with resizable, draggable widgets — views, forms, and quick-add panels — arranged in a custom layout.

---

## Overview

A dashboard is a named, saved layout of **widgets** on a grid. Widgets can be:
- **View widget** — renders a table view (any named or default view from any table)
- **Form widget** — renders an empty "quick add" form for a specific table
- **Stat widget** — shows a count (e.g., "5 Active Customers") — simple but useful (future: charts)

Users drag widgets to position them and resize by dragging edges. The layout is saved as JSON config per dashboard. Multiple dashboards can be created and switched between. The home page (`/`) shows the default dashboard instead of "Select a table."

---

## Data Model

### `dashboard` table
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `database_id` | UUID | FK → tenant_database.id |
| `name` | VARCHAR | Dashboard name (e.g., "Sales Overview") |
| `is_default` | BOOLEAN | Shown on home page |
| `config` | JSON | Widget layout configuration |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### Config Structure

```json
{
  "widgets": [
    {
      "id": "w1",
      "type": "view",
      "title": "Active Customers",
      "table": "customers",
      "view_id": "uuid-of-named-view",
      "x": 0, "y": 0, "w": 6, "h": 4
    },
    {
      "type": "view",
      "id": "w2",
      "title": "Pending Orders",
      "table": "orders",
      "view_id": "uuid-of-pending-orders-view",
      "x": 6, "y": 0, "w": 6, "h": 4
    },
    {
      "type": "form",
      "id": "w3",
      "title": "New Contact",
      "table": "contacts",
      "x": 0, "y": 4, "w": 4, "h": 3
    },
    {
      "type": "stat",
      "id": "w4",
      "title": "Total Orders",
      "table": "orders",
      "x": 4, "y": 4, "w": 2, "h": 1
    }
  ],
  "grid_cols": 12
}
```

Grid uses 12 columns (like Bootstrap/Tailwind). Positions (`x`, `y`) and sizes (`w`, `h`) are in grid units. The portal renders the grid and handles drag/resize.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `.../dashboards` | Create a dashboard |
| `GET` | `.../dashboards` | List dashboards |
| `GET` | `.../dashboards/{id}` | Get dashboard config |
| `PUT` | `.../dashboards/{id}` | Update dashboard config/name |
| `DELETE` | `.../dashboards/{id}` | Delete dashboard |

Path prefix: `/tenants/{tid}/databases/{did}`

### Create Dashboard
```json
// POST .../dashboards
{
  "name": "Sales Overview",
  "is_default": true,
  "config": {
    "widgets": [],
    "grid_cols": 12
  }
}
```

---

## Widget Types

### View Widget
Renders a mini data table using a specific view's config (columns, sort, filters). Shows the first N rows that fit the widget height. Click on a row navigates to the record detail page. Click on the widget title navigates to the full table view.

### Form Widget
Renders an empty form for creating a new record in a table. On save, the record is created and the form resets. Useful for quick data entry without navigating away from the dashboard.

### Stat Widget
Shows a single number — the total row count for a table, optionally with a filter. Compact display: big number + label. Click navigates to the table.

---

## Portal Pages

### Dashboard Page (`/` or `/dashboards/:id`)

```
┌─────────────────────────────────────────────────────────────────┐
│  [Dashboard Picker ▼]  "Sales Overview"    [+ Widget] [Edit] [⚙]│
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────┐  ┌──────────────────────┐             │
│  │ Active Customers     │  │ Pending Orders        │             │
│  │ ┌────┬────┬────────┐ │  │ ┌────┬────┬─────────┐│             │
│  │ │Name│Ind.│Revenue │ │  │ │Date│Amt │Status   ││             │
│  │ ├────┼────┼────────┤ │  │ ├────┼────┼─────────┤│             │
│  │ │Glob│Mfg │$5M     │ │  │ │3/10│$600│pending  ││             │
│  │ │Init│Tech│$2.5M   │ │  │ │3/15│$50 │pending  ││             │
│  │ │Umbr│Phar│$12M    │ │  │ │3/20│$330│pending  ││             │
│  │ └────┴────┴────────┘ │  │ └────┴────┴─────────┘│             │
│  └──────────────────────┘  └──────────────────────┘             │
│                                                                  │
│  ┌──────────────┐  ┌─────┐  ┌─────┐                            │
│  │ New Contact   │  │  5  │  │  8  │                            │
│  │ Name: [     ] │  │Cust.│  │Ord. │                            │
│  │ Email:[     ] │  └─────┘  └─────┘                            │
│  │ [Save]        │                                               │
│  └──────────────┘                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Edit Mode
Toggle via "Edit" button. In edit mode:
- Widgets show drag handles and resize handles
- Widgets can be moved by dragging
- Widgets can be resized by dragging bottom-right corner
- "Remove" (X) button appears on each widget
- Layout changes auto-save on exit from edit mode

### Add Widget Dialog
"+ Widget" button opens a modal:
1. Pick widget type: View, Form, or Stat
2. Pick table
3. If View: pick which view (default or named)
4. Enter widget title
5. Click Add — widget appears at the next available position

---

## Implementation

### API (forge repo)

```
platform/src/forge_platform/
├── models/
│   └── dashboard.py              (new: Dashboard SQLModel)
├── routers/
│   └── dashboards.py             (new: CRUD endpoints)
├── services/
│   └── dashboard_service.py      (new: business logic)
├── app.py                        (update: register router + model)
```

### Portal (forge-portal repo)

For the grid layout with drag/resize, we'll use a lightweight approach:
- CSS Grid for the layout (12-column grid)
- Custom drag handlers (HTML5 drag API) for moving widgets
- Mouse event handlers for resizing

No external library needed — the grid is simple enough.

```
src/
├── components/
│   ├── DashboardGrid.tsx         (new: renders widget grid)
│   ├── DashboardWidget.tsx       (new: widget wrapper with drag/resize)
│   ├── ViewWidget.tsx            (new: mini data table)
│   ├── FormWidget.tsx            (new: quick-add form)
│   ├── StatWidget.tsx            (new: count display)
│   ├── AddWidgetDialog.tsx       (new: widget type/table/view picker)
│   └── DashboardPicker.tsx       (new: dashboard selector dropdown)
├── pages/
│   ├── DashboardPage.tsx         (new: main dashboard page)
│   └── GettingStartedPage.tsx    (update: show dashboard if exists)
├── App.tsx                       (update: route / to DashboardPage)
├── types/
│   └── index.ts                  (update: dashboard types)
```

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Grid system | 12-column CSS Grid | Standard, flexible, matches common layouts |
| Drag/resize | Custom HTML5 drag + mouse events | No library dependency; grid snapping is simple |
| Widget sizing | Grid units (not pixels) | Responsive; widgets scale with container |
| View widget rendering | Reuse existing data table logic | Consistent look; fetches rows with view config |
| Form widget | Reuse existing FieldInput components | Consistent look; same validation |
| Default dashboard | First created dashboard marked default | Shown on home page |
| Edit mode toggle | Explicit button | Prevents accidental moves; clear UX |
| Auto-save on exit edit mode | PUT dashboard config | No "Save" button clutter in edit mode |

---

## Acceptance Criteria

- [ ] `dashboard` model and table created
- [ ] CRUD API for dashboards (POST/GET/PUT/DELETE)
- [ ] Dashboard page renders a grid of widgets
- [ ] View widget shows rows from a table view (columns, sort, filters from view config)
- [ ] Form widget shows empty form, creates record on save, resets
- [ ] Stat widget shows row count for a table
- [ ] "Add Widget" dialog: pick type, table, view, title
- [ ] Edit mode: drag widgets to reposition on grid
- [ ] Edit mode: resize widgets by dragging corner
- [ ] Edit mode: remove widgets
- [ ] Layout auto-saves when exiting edit mode
- [ ] Dashboard picker dropdown for switching between dashboards
- [ ] Create/delete/rename dashboards
- [ ] Default dashboard shown on home page (/)
- [ ] Widget titles link to full table view
- [ ] View widget row click navigates to record detail

---

## AI Integration Preview

With dashboards, the AI can:
- "Create a sales dashboard" → creates dashboard with customer view, pending orders view, and new order form
- "Add a widget showing overdue invoices" → creates a named view with filter + adds view widget
- "Show me a summary of this month's activity" → stat widgets for key metrics

---

## Next Phase

→ [Phase 3 — AI-Driven Interface](../../master_plan.md#phase-3--ai-driven-interface)
