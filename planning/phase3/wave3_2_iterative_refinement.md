# Wave 3.2 — AI Iterative Refinement & Polish

> Parent: [Master Plan](../master_plan.md)
> Depends on: [Wave 3.1 — AI Chat Orchestrator](wave3_1_ai_orchestrator.md)
> Goal: Polish the AI experience and add admin UI for LLM management.

---

## Planned Improvements

### Admin Panel — LLM Management UI
- LLM Providers page: CRUD for providers (name, URL, key, model, pricing)
- Tenant detail page: assign/remove LLM providers
- AI Usage page: usage dashboard with cost per tenant, token counts, date filtering

### Chat Panel — Markdown Rendering
- Render AI responses as markdown (headers, bold, lists, code blocks, tables)
- Use a lightweight markdown renderer (e.g., `react-markdown`)
- Code blocks with syntax highlighting for SQL/JSON

### Chat Panel — UX Improvements
- Conversation history: load previous conversations from sidebar
- Conversation titles: auto-generate via LLM (short call after first exchange: "Generate a 3-5 word title"). Falls back to first message truncation if no LLM configured. Uses tenant's configured model — cost is ~$0.001 per title.
- Streaming responses (SSE): show AI output token-by-token as it generates
- Error recovery: retry failed messages
- Context awareness: AI knows which table/record the user is currently viewing

### AI Tool Improvements
- `update_row` tool: modify existing records
- `delete_rows` tool: delete records by filter
- `rename_table` tool: rename existing tables
- `drop_table` tool: delete tables (with confirmation prompt)
- `update_view` tool: modify existing named views
- `add_dashboard_widget` tool: add widget to existing dashboard

### Business Features
- Rate limiting per tenant (configurable max requests/day)
- Cost alerts when tenant approaches budget threshold
- Model comparison: A/B test different models per tenant

### UI/UX
- Dark mode toggle (Tailwind `dark:` classes, preference saved in localStorage)
- Applies to tenant portal, admin panel, and chat panel

---

## Priority Order

1. Admin LLM management UI
2. Markdown rendering in chat
3. Streaming responses
4. Additional AI tools
5. Conversation history UI
6. Rate limiting & cost alerts
