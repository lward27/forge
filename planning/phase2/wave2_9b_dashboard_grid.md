# Wave 2.9b — Dashboard Grid (Drag & Drop + Resize)

> Parent: [Wave 2.9 — Dashboards](wave2_9_dashboards.md)
> Goal: Replace the manual +/- controls with proper drag-to-move and drag-to-resize using react-grid-layout.

---

## Overview

The current dashboard edit mode uses +/- buttons for width, height, and position — clunky and doesn't prevent overlaps. This refactor replaces it with `react-grid-layout`, which provides:

- **Drag to move** — grab anywhere on the widget header to reposition
- **Drag to resize** — grab the bottom-right corner to resize
- **Collision detection** — widgets push each other out of the way
- **Grid snapping** — widgets snap to the 12-column grid
- **Width constraints** — can't resize beyond available space
- **Responsive** — handles window resize

---

## Changes

### Add dependency
```
npm install react-grid-layout
npm install -D @types/react-grid-layout
```

### Portal files modified

```
src/
├── components/
│   ├── DashboardWidget.tsx       (simplify: remove +/- controls)
│   └── DashboardGrid.tsx         (new: react-grid-layout wrapper)
├── pages/
│   └── DashboardPage.tsx         (update: use DashboardGrid)
├── index.css                     (update: import react-grid-layout CSS)
```

### Key behavior
- In **view mode**: widgets are static (not draggable/resizable)
- In **edit mode**: widgets become draggable and resizable
- Layout changes auto-save to the API when exiting edit mode
- Widget config stores `x, y, w, h` — same format as current, directly compatible with react-grid-layout
- `minW: 2, minH: 1` prevents widgets from being too small

---

## Acceptance Criteria

- [ ] Widgets can be dragged to new positions
- [ ] Widgets can be resized by dragging bottom-right corner
- [ ] Widgets cannot overlap — collision pushes widgets down
- [ ] Widgets cannot exceed 12-column grid width
- [ ] Layout saves on exit from edit mode
- [ ] View mode: widgets are static
- [ ] Existing dashboard configs work without migration
