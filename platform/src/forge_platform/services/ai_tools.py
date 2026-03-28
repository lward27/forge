"""Tool definitions and execution for the AI assistant."""
import json
import uuid
from typing import Any

from sqlmodel import Session

from forge_platform.models.tenant_database import TenantDatabase
from forge_platform.schemas.table import ColumnCreate, TableCreate, TableAlter
from forge_platform.schemas.database import DatabaseCreate
from forge_platform.services import (
    database_service, table_service, row_service,
    view_form_service, dashboard_service,
)


# ── Tool Definitions (OpenAI function calling format) ─────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_tables",
            "description": "List all tables in the current database with their columns",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_table_schema",
            "description": "Get detailed schema for a specific table including columns, types, and relationships",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {"type": "string", "description": "Name of the table"},
                },
                "required": ["table_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_table",
            "description": "Create a new table with specified columns. An 'id' column is auto-added. For reference columns (foreign keys), set type to 'reference' and include reference_table.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Table name (lowercase, underscores)"},
                    "display_field": {"type": "string", "description": "Column to use as display name when referenced"},
                    "columns": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "type": {"type": "string", "enum": ["text", "integer", "decimal", "boolean", "date", "timestamp", "json", "reference"]},
                                "nullable": {"type": "boolean", "default": True},
                                "unique": {"type": "boolean", "default": False},
                                "default": {"type": "string"},
                                "reference_table": {"type": "string", "description": "Target table for reference type"},
                            },
                            "required": ["name", "type"],
                        },
                    },
                },
                "required": ["name", "columns"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_columns",
            "description": "Add new columns to an existing table",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {"type": "string"},
                    "columns": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "type": {"type": "string", "enum": ["text", "integer", "decimal", "boolean", "date", "timestamp", "json", "reference"]},
                                "nullable": {"type": "boolean", "default": True},
                                "unique": {"type": "boolean", "default": False},
                                "reference_table": {"type": "string"},
                            },
                            "required": ["name", "type"],
                        },
                    },
                },
                "required": ["table_name", "columns"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_rows",
            "description": "Search and filter rows in a table. Returns matching rows with pagination.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {"type": "string"},
                    "filters": {
                        "type": "array",
                        "items": {"type": "string", "description": "Filter in format 'column:operator:value'. Operators: eq, neq, gt, gte, lt, lte, like, in, isnull"},
                    },
                    "sort": {"type": "string", "description": "Column name. Prefix with - for descending."},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["table_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_row",
            "description": "Insert a new record into a table",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {"type": "string"},
                    "data": {"type": "object", "description": "Field name to value mapping"},
                },
                "required": ["table_name", "data"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "count_rows",
            "description": "Count rows in a table, optionally with a filter",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {"type": "string"},
                    "filters": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["table_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_view",
            "description": "Create a named view for a table with specific columns, sort, and filters",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {"type": "string"},
                    "view_name": {"type": "string"},
                    "visible_columns": {"type": "array", "items": {"type": "string"}},
                    "sort_field": {"type": "string"},
                    "sort_direction": {"type": "string", "enum": ["asc", "desc"]},
                },
                "required": ["table_name", "view_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_dashboard",
            "description": "Create a new dashboard with widgets",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "widgets": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string", "enum": ["view", "form", "stat"]},
                                "title": {"type": "string"},
                                "table": {"type": "string"},
                                "view_id": {"type": "string"},
                                "w": {"type": "integer", "default": 6},
                                "h": {"type": "integer", "default": 4},
                            },
                            "required": ["type", "title", "table"],
                        },
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "navigate",
            "description": "Navigate the user to a specific page in the portal",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Portal path, e.g., /tables/customers or /tables/customers/records/5 or /"},
                },
                "required": ["path"],
            },
        },
    },
]


# ── Tool Execution ────────────────────────────────────────────────────

def execute_tool(
    session: Session,
    tenant_db: TenantDatabase,
    tool_name: str,
    args: dict,
) -> dict:
    """Execute a tool call and return the result."""
    try:
        if tool_name == "list_tables":
            return _list_tables(session, tenant_db)
        elif tool_name == "get_table_schema":
            return _get_table_schema(session, tenant_db, args["table_name"])
        elif tool_name == "create_table":
            return _create_table(session, tenant_db, args)
        elif tool_name == "add_columns":
            return _add_columns(session, tenant_db, args)
        elif tool_name == "query_rows":
            return _query_rows(session, tenant_db, args)
        elif tool_name == "create_row":
            return _create_row(session, tenant_db, args)
        elif tool_name == "count_rows":
            return _count_rows(session, tenant_db, args)
        elif tool_name == "create_view":
            return _create_view(session, tenant_db, args)
        elif tool_name == "create_dashboard":
            return _create_dashboard(session, tenant_db, args)
        elif tool_name == "navigate":
            return {"action": "navigate", "path": args["path"]}
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    except Exception as e:
        return {"error": str(e)}


def _list_tables(session, tenant_db):
    tables = table_service.list_tables(session, tenant_db.id)
    return {
        "tables": [
            {
                "name": t.name,
                "display_field": t.display_field,
                "columns": [
                    {"name": c.name, "type": c.column_type, "reference_table": c.reference_table}
                    for c in cols
                ],
            }
            for t, cols in tables
        ]
    }


def _get_table_schema(session, tenant_db, table_name):
    result = table_service.get_table(session, tenant_db.id, table_name)
    if result is None:
        return {"error": f"Table '{table_name}' not found"}
    t, cols = result
    return {
        "name": t.name,
        "display_field": t.display_field,
        "columns": [
            {
                "name": c.name,
                "type": c.column_type,
                "nullable": c.nullable,
                "unique": c.unique,
                "primary_key": c.primary_key,
                "reference_table": c.reference_table,
            }
            for c in cols
        ],
    }


def _create_table(session, tenant_db, args):
    columns = [
        ColumnCreate(
            name=c["name"],
            type=c["type"],
            nullable=c.get("nullable", True),
            unique=c.get("unique", False),
            default=c.get("default"),
            reference_table=c.get("reference_table"),
        )
        for c in args["columns"]
    ]
    table_in = TableCreate(
        name=args["name"],
        columns=columns,
        display_field=args.get("display_field"),
    )
    t, cols = table_service.create_table(session, tenant_db, table_in)
    return {"success": True, "table": t.name, "columns": [c.name for c in cols]}


def _add_columns(session, tenant_db, args):
    columns = [
        ColumnCreate(
            name=c["name"],
            type=c["type"],
            nullable=c.get("nullable", True),
            unique=c.get("unique", False),
            reference_table=c.get("reference_table"),
        )
        for c in args["columns"]
    ]
    alter_in = TableAlter(add_columns=columns)
    result = table_service.alter_table(session, tenant_db, args["table_name"], alter_in)
    if result is None:
        return {"error": f"Table '{args['table_name']}' not found"}
    t, cols = result
    return {"success": True, "table": t.name, "columns": [c.name for c in cols]}


def _query_rows(session, tenant_db, args):
    rows, total = row_service.list_rows(
        session, tenant_db, args["table_name"],
        filters=args.get("filters"),
        sort=args.get("sort"),
        limit=args.get("limit", 20),
    )
    return {"rows": rows, "total": total}


def _create_row(session, tenant_db, args):
    row = row_service.insert_row(session, tenant_db, args["table_name"], args["data"])
    return {"success": True, "row": row}


def _count_rows(session, tenant_db, args):
    _, total = row_service.list_rows(
        session, tenant_db, args["table_name"],
        filters=args.get("filters"),
        limit=1,
    )
    return {"count": total}


def _create_view(session, tenant_db, args):
    table_name = args["table_name"]
    # Build view config
    config: dict[str, Any] = {
        "columns": [],
        "default_sort": {"field": "id", "direction": "asc"},
        "page_size": 25,
    }

    # Get table schema for column list
    result = table_service.get_table(session, tenant_db.id, table_name)
    if result is None:
        return {"error": f"Table '{table_name}' not found"}
    _, cols = result

    visible = set(args.get("visible_columns", []))
    config["columns"] = [
        {"field": c.name, "visible": c.name in visible if visible else True, "width": None}
        for c in cols
    ]

    if args.get("sort_field"):
        config["default_sort"] = {
            "field": args["sort_field"],
            "direction": args.get("sort_direction", "asc"),
        }

    view = view_form_service.create_named_view(
        session, tenant_db.id, table_name, args["view_name"], config
    )
    return {"success": True, "view_id": str(view.id), "name": view.name}


def _create_dashboard(session, tenant_db, args):
    widgets = []
    x = 0
    y = 0
    for i, w in enumerate(args.get("widgets", [])):
        width = w.get("w", 6)
        height = w.get("h", 4)
        if x + width > 12:
            x = 0
            y += height
        widgets.append({
            "id": f"w{i}",
            "type": w["type"],
            "title": w["title"],
            "table": w["table"],
            "view_id": w.get("view_id"),
            "x": x, "y": y,
            "w": width, "h": height,
        })
        x += width

    d = dashboard_service.create_dashboard(
        session,
        database_id=tenant_db.id,
        name=args["name"],
        is_default=False,
        config={"widgets": widgets, "grid_cols": 12},
    )
    return {"success": True, "dashboard_id": str(d.id), "name": d.name}
