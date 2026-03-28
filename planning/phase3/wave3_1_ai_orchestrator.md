# Wave 3.1 — AI Chat Orchestrator

> Parent: [Master Plan](../master_plan.md)
> Depends on: [Phase 2](../phase2/) (complete)
> Goal: Tenant users interact with an AI assistant that can create tables, add fields, query data, create views, and build dashboards — all through natural conversation.

---

## Overview

Add an AI chat panel to the tenant portal. The AI assistant uses tool-calling (OpenAI function calling spec) to invoke Forge APIs on behalf of the user. LLM providers are configured and managed by the platform operator in the admin panel, with token usage tracked per tenant for billing.

---

## Architecture

```
┌──────────────────┐
│  Tenant Portal   │
│  (Chat Panel)    │
└────────┬─────────┘
         │ POST /ai/chat
         ▼
┌──────────────────────────────────────┐
│         Forge Control Plane          │
│                                      │
│  ┌────────────┐  ┌───────────────┐   │
│  │ AI Router  │→ │ LLM Service   │   │
│  │            │  │ (proxy to     │   │
│  │ - tool     │  │  configured   │   │
│  │   execution│  │  provider)    │   │
│  │ - context  │  │               │   │
│  │   building │  └───────┬───────┘   │
│  └────────────┘          │           │
│        │                 ▼           │
│        │          ┌─────────────┐    │
│        │          │ OpenAI-spec │    │
│        │          │ LLM API     │    │
│        │          │(Claude/GPT/ │    │
│        │          │ Llama/etc)  │    │
│        │          └─────────────┘    │
│        ▼                             │
│  ┌─────────────────┐                 │
│  │ Existing Forge   │                │
│  │ APIs (tables,    │                │
│  │ rows, views,     │                │
│  │ dashboards...)   │                │
│  └─────────────────┘                 │
└──────────────────────────────────────┘
```

The Forge API acts as a proxy — it receives the chat message, adds context (tenant's tables, schema), sends to the LLM with tool definitions, executes any tool calls, and returns the result.

---

## Data Model

### `llm_provider` table (admin-managed)
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `name` | VARCHAR | Display name ("Claude Sonnet", "GPT-4o", "Llama 3.1") |
| `api_url` | VARCHAR | Base URL (e.g., `https://api.anthropic.com/v1`) |
| `api_key_encrypted` | VARCHAR | Encrypted API key |
| `model` | VARCHAR | Model identifier (e.g., `claude-sonnet-4-20250514`) |
| `pricing_input` | DECIMAL | Cost per 1M input tokens (for billing) |
| `pricing_output` | DECIMAL | Cost per 1M output tokens |
| `is_active` | BOOLEAN | Can be assigned to tenants |
| `created_at` | TIMESTAMP | |

### `tenant_llm_config` table
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | FK → tenant.id |
| `provider_id` | UUID | FK → llm_provider.id |
| `is_active` | BOOLEAN | |
| `created_at` | TIMESTAMP | |

### `ai_usage` table (token tracking)
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | FK → tenant.id |
| `provider_id` | UUID | FK → llm_provider.id |
| `input_tokens` | INTEGER | Tokens in the prompt |
| `output_tokens` | INTEGER | Tokens in the response |
| `cost_input` | DECIMAL | Calculated cost (input_tokens * pricing) |
| `cost_output` | DECIMAL | Calculated cost (output_tokens * pricing) |
| `created_at` | TIMESTAMP | |

### `ai_conversation` table
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | FK → tenant.id |
| `database_id` | UUID | FK → tenant_database.id |
| `messages` | JSON | Array of {role, content, tool_calls, tool_results} |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

---

## API Endpoints

### Admin Panel — LLM Provider Management

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/admin/llm-providers` | Create an LLM provider |
| `GET` | `/admin/llm-providers` | List all providers |
| `PUT` | `/admin/llm-providers/{id}` | Update provider config |
| `DELETE` | `/admin/llm-providers/{id}` | Delete provider |
| `POST` | `/admin/tenants/{tid}/llm` | Assign a provider to a tenant |
| `DELETE` | `/admin/tenants/{tid}/llm/{id}` | Remove provider from tenant |
| `GET` | `/admin/ai-usage` | Usage report (filterable by tenant, date range) |

### Tenant Portal — AI Chat

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/ai/chat` | Send a message, get AI response + executed actions |
| `GET` | `/ai/conversations` | List conversations for this tenant |
| `GET` | `/ai/conversations/{id}` | Get conversation history |
| `DELETE` | `/ai/conversations/{id}` | Delete a conversation |

### Chat Request/Response

```json
// POST /ai/chat
{
  "conversation_id": "uuid or null for new",
  "message": "Create a table for tracking invoices with customer, amount, due date, and status"
}

// Response
{
  "conversation_id": "uuid",
  "response": "I've created an 'invoices' table with the following fields:\n- customer_id (reference to customers)\n- amount (decimal)\n- due_date (date)\n- status (text)\n\nYou can start adding invoices now!",
  "actions_taken": [
    {"tool": "create_table", "args": {"name": "invoices", ...}, "result": "success"}
  ],
  "usage": {
    "input_tokens": 1250,
    "output_tokens": 180
  }
}
```

---

## Tool Definitions

The AI gets these tools (OpenAI function calling format):

### Schema Tools
| Tool | Description |
|------|-------------|
| `list_tables` | List all tables in the current database |
| `get_table_schema` | Get columns and relationships for a table |
| `create_table` | Create a new table with columns |
| `add_columns` | Add columns to an existing table |
| `drop_columns` | Remove columns from a table |

### Data Tools
| Tool | Description |
|------|-------------|
| `query_rows` | Search/filter rows in a table |
| `create_row` | Insert a record |
| `update_row` | Update a record |
| `delete_row` | Delete a record |
| `count_rows` | Get row count (with optional filter) |

### View & Dashboard Tools
| Tool | Description |
|------|-------------|
| `create_view` | Create a named view with columns, sort, filters |
| `create_form` | Create a named form |
| `create_dashboard` | Create a dashboard |
| `add_dashboard_widget` | Add a widget to a dashboard |

### Navigation Tools
| Tool | Description |
|------|-------------|
| `navigate_to_table` | Tell the portal to navigate to a table |
| `navigate_to_record` | Navigate to a specific record |
| `navigate_to_dashboard` | Navigate to a dashboard |

---

## Context Building

Before each LLM call, the system builds a context prompt:

```
You are an AI assistant for Forge, a low-code data management platform.
The user is working in the "{database_name}" database for tenant "{tenant_name}".

Current tables:
- customers (fields: id, company_name, industry, website, annual_revenue, is_active)
  - display_field: company_name
  - referenced by: contacts.customer_id, orders.customer_id
- contacts (fields: id, full_name, email, phone, job_title, customer_id → customers)
  - display_field: full_name
- ... (all tables with their schemas)

Available views:
- customers: "Default View", "Active Customers"
- orders: "Default View", "Pending Orders"

Dashboards:
- "CRM Overview" (3 widgets)

Use the provided tools to help the user. After making changes, explain what you did.
When creating tables, always set appropriate display_field.
Reference columns should be named {table}_id by convention.
```

---

## LLM Proxy Service

The Forge API proxies to the LLM provider using the OpenAI Chat Completions spec:

```python
# All providers use the same format
POST {provider.api_url}/chat/completions
Headers:
  Authorization: Bearer {provider.api_key}
  Content-Type: application/json

Body:
{
  "model": "{provider.model}",
  "messages": [...],
  "tools": [...],
  "tool_choice": "auto"
}
```

**Provider-specific adapters** may be needed for:
- **Anthropic**: Uses `/v1/messages` not `/v1/chat/completions`, different format
- **OpenAI**: Standard format, works directly
- **Ollama/vLLM**: Standard format, no auth needed
- **Groq**: Standard format

The service detects the provider type from the API URL and adapts the request format accordingly.

---

## Implementation

### API (forge repo)

```
platform/src/forge_platform/
├── models/
│   ├── llm_provider.py           (new)
│   ├── tenant_llm_config.py      (new)
│   ├── ai_usage.py               (new)
│   └── ai_conversation.py        (new)
├── routers/
│   ├── admin_llm.py              (new: provider management)
│   └── ai_chat.py                (new: chat endpoint)
├── services/
│   ├── llm_service.py            (new: proxy + tool execution)
│   ├── ai_tools.py               (new: tool definitions + execution)
│   └── ai_context.py             (new: context builder)
```

### Portal (forge-portal repo)

```
src/
├── components/
│   ├── ChatPanel.tsx             (new: slide-out chat panel)
│   ├── ChatMessage.tsx           (new: message bubble)
│   └── ChatInput.tsx             (new: input + send button)
├── pages/
│   └── (all pages)               (update: add chat toggle button)
```

### Admin Panel (forge-admin repo)

```
src/
├── pages/
│   ├── LLMProvidersPage.tsx      (new: CRUD for providers)
│   ├── TenantDetailPage.tsx      (update: assign LLM provider)
│   └── AIUsagePage.tsx           (new: usage/billing dashboard)
```

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LLM spec | OpenAI Chat Completions API | Industry standard; supported by Claude, GPT, Llama, Mistral, Groq |
| Provider management | Admin panel only | Business control over costs and model selection |
| Token tracking | Per-request in `ai_usage` table | Enables pass-through billing |
| Tool execution | Server-side (not client-side) | Secure; tenant API key permissions enforced |
| Conversation storage | JSON messages in DB | Simple; supports multi-turn context |
| Anthropic adapter | Detect from URL, transform request | Claude uses different format but same capabilities |
| Context building | Dynamic from current schema | AI always knows current state; no stale context |
| Navigation tools | Return instructions to portal | AI can't navigate directly; tells portal what to show |

---

## Acceptance Criteria

- [ ] LLM providers CRUD in admin panel
- [ ] Assign/remove providers per tenant
- [ ] Chat panel in tenant portal (slide-out)
- [ ] `POST /ai/chat` sends message to configured LLM with tools
- [ ] AI can create tables, add fields, query data
- [ ] AI can create views, forms, dashboards
- [ ] Tool calls executed against Forge APIs
- [ ] Actions shown in chat response
- [ ] Token usage tracked per request
- [ ] Usage dashboard in admin panel
- [ ] Multi-turn conversations persisted
- [ ] Works with OpenAI, Anthropic (adapter), and Ollama
- [ ] Context includes current schema, views, dashboards

---

## Security Notes

- LLM API keys encrypted at rest in platform DB
- Tenant API key permissions enforced on tool execution (tenant can only modify own data)
- Chat messages stored per-tenant (not cross-visible)
- Token usage rate limiting (configurable per tenant) — future wave

---

## Next Wave

→ [Wave 3.2 — Iterative Refinement](wave3_2_iterative_refinement.md)
