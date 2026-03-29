# Wave 3.3 — Templates, Chat Page & Dark Mode

> Parent: [Master Plan](../master_plan.md)
> Depends on: [Wave 3.2 — AI Refinement](wave3_2_iterative_refinement.md) (complete)
> Goal: Pre-built app templates, a dedicated AI chat page with conversation history, and dark mode across the platform.

---

## Feature 1: App Templates

### Concept

Templates are pre-defined configurations that create a complete data model (tables, columns, relationships, display fields) in one click. Available from:
- **Template gallery** in the tenant portal (new page)
- **AI chat** — user says "set up a CRM" and the AI deploys the CRM template

### Data Model

Templates are stored as JSON configs in the forge repo (not in the database). They're static, versioned with the codebase.

```
platform/src/forge_platform/templates/
├── __init__.py
├── crm.json
├── inventory.json
├── project_tracker.json
└── helpdesk.json
```

### Template Format
```json
{
  "name": "CRM",
  "description": "Customer relationship management — track companies, contacts, deals, and activities",
  "icon": "users",
  "tables": [
    {
      "name": "companies",
      "display_field": "company_name",
      "columns": [
        {"name": "company_name", "type": "text", "nullable": false},
        {"name": "industry", "type": "text"},
        {"name": "website", "type": "text"},
        {"name": "phone", "type": "text"},
        {"name": "annual_revenue", "type": "decimal"},
        {"name": "is_active", "type": "boolean", "default": "true"}
      ]
    },
    {
      "name": "contacts",
      "display_field": "full_name",
      "columns": [
        {"name": "full_name", "type": "text", "nullable": false},
        {"name": "email", "type": "text", "unique": true},
        {"name": "phone", "type": "text"},
        {"name": "job_title", "type": "text"},
        {"name": "company_id", "type": "reference", "reference_table": "companies"}
      ]
    },
    ...
  ]
}
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/templates` | List available templates |
| `POST` | `/tenants/{tid}/databases/{did}/deploy-template` | Deploy a template |

### AI Integration

New AI tool: `deploy_template`
- User: "Set up a CRM for me"
- AI: calls `deploy_template` with template name "crm"
- All tables created in sequence (respecting FK order)

### Portal — Template Gallery

New page at `/templates`:
- Grid of template cards (icon, name, description, table count)
- Click a template → confirmation dialog showing what will be created
- "Deploy" button → creates all tables
- Accessible from sidebar + home page empty state

### Starter Templates

1. **CRM** — companies, contacts, deals, activities
2. **Inventory** — products, categories, warehouses, stock_levels
3. **Project Tracker** — projects, tasks, team_members, time_entries
4. **Helpdesk** — tickets, customers, agents, comments

---

## Feature 2: Dedicated AI Chat Page

### Concept

A full-page chat experience at `/chat` with conversation history sidebar. Keeps the slide-out sidebar chat for quick contextual interactions.

### Page Layout
```
┌──────────────────────────────────────────────────────────────┐
│  Conversations        │  Chat                                │
│                        │                                      │
│  [+ New Chat]          │  ┌────────────────────────────────┐  │
│                        │  │ User: Set up a CRM for me      │  │
│  ● CRM Setup           │  │                                │  │
│  ● Invoice questions    │  │ Assistant: I've created the    │  │
│  ● Data analysis        │  │ following tables: ...          │  │
│                        │  │                                │  │
│                        │  │ User: Add a notes field to     │  │
│                        │  │ contacts                       │  │
│                        │  │                                │  │
│                        │  └────────────────────────────────┘  │
│                        │                                      │
│                        │  ┌──────────────────────┐ [Send]    │
│                        │  │ Ask me anything...    │           │
│                        │  └──────────────────────┘           │
└──────────────────────────────────────────────────────────────┘
```

### Key Features

- **Conversation list** (left panel): shows all conversations, sorted by last updated
- **Conversation titles**: auto-generated from the first user message (first ~50 chars)
- **New chat** button: starts a fresh conversation
- **Delete conversation**: swipe or right-click to delete
- **Full markdown rendering** (already implemented in sidebar chat)
- **Same AI tools** — shares the same backend as the sidebar chat

### Navigation

- `/chat` — shows the chat page (latest conversation or empty state)
- `/chat/:conversationId` — shows a specific conversation
- Sidebar nav: add "AI Chat" link with Bot icon
- The slide-out chat sidebar remains for quick interactions from any page

---

## Feature 3: Dark Mode

### Concept

Toggle between light and dark themes. Preference saved in localStorage. Uses Tailwind's `dark:` variant classes.

### Implementation

1. **Tailwind config**: enable `darkMode: 'class'` in `tailwind.config.js`
2. **Theme toggle**: button in the top bar (sun/moon icon)
3. **localStorage**: save preference as `forge_theme` = `'light' | 'dark'`
4. **Root class**: add/remove `dark` class on `<html>` element
5. **Apply dark variants** to key components:
   - Backgrounds: `bg-gray-50` → `dark:bg-gray-900`
   - Cards: `bg-white` → `dark:bg-gray-800`
   - Text: `text-gray-900` → `dark:text-gray-100`
   - Borders: `border-gray-200` → `dark:border-gray-700`
   - Inputs: adjusted for dark backgrounds

### Scope

Apply to:
- Tenant portal (all pages)
- Chat sidebar and chat page
- NOT admin panel (keep it light for now — can add later)

---

## Implementation

### API (forge repo)

```
platform/src/forge_platform/
├── templates/
│   ├── __init__.py               (template loader)
│   ├── crm.json
│   ├── inventory.json
│   ├── project_tracker.json
│   └── helpdesk.json
├── routers/
│   └── templates.py              (new: list + deploy endpoints)
├── services/
│   ├── template_service.py       (new: deploy logic)
│   └── ai_tools.py              (update: add deploy_template tool)
```

### Portal (forge-portal repo)

```
src/
├── components/
│   ├── ThemeToggle.tsx           (new: sun/moon button)
│   └── TopBar.tsx                (update: add theme toggle)
├── pages/
│   ├── ChatPage.tsx              (new: full-page chat with history)
│   └── TemplatePage.tsx          (new: template gallery)
├── hooks/
│   └── useTheme.ts              (new: dark mode hook)
├── App.tsx                       (update: routes, theme provider)
├── index.html                    (update: dark class on html)
├── tailwind.config.js            (update: darkMode: 'class')
```

---

## Acceptance Criteria

### Templates
- [ ] 4 template JSON files (CRM, inventory, project tracker, helpdesk)
- [ ] `GET /templates` lists available templates
- [ ] `POST .../deploy-template` creates all tables in order
- [ ] Template gallery page in portal with cards
- [ ] Deploy confirmation shows what will be created
- [ ] AI `deploy_template` tool works via chat
- [ ] Tables created with correct relationships and display fields

### Chat Page
- [ ] Dedicated chat page at `/chat`
- [ ] Conversation list sidebar with history
- [ ] Auto-generated conversation titles
- [ ] New chat / delete conversation
- [ ] Same AI capabilities as sidebar chat
- [ ] Sidebar nav link to chat page

### Dark Mode
- [ ] Theme toggle in top bar (sun/moon icon)
- [ ] Preference saved in localStorage
- [ ] Dark variants applied to all portal pages
- [ ] Chat panel styled for dark mode
- [ ] Smooth transition between themes

---

## Next Phase

→ [Phase 4 — Production Hardening](../../master_plan.md#phase-4--production-hardening--advanced-features)
