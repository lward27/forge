"""Build context prompt for the AI assistant."""
import uuid

from sqlmodel import Session

from forge_platform.services import table_service, view_form_service, dashboard_service


def build_context(
    session: Session,
    tenant_name: str,
    database_name: str,
    database_id: uuid.UUID,
) -> str:
    """Build a system prompt with current schema context."""
    lines = [
        "You are an AI assistant for Forge, a low-code data management platform.",
        f'The user is working in the "{database_name}" database for tenant "{tenant_name}".',
        "",
        "Current tables:",
    ]

    tables = table_service.list_tables(session, database_id)
    if not tables:
        lines.append("  (no tables yet)")
    else:
        for t, cols in tables:
            col_desc = []
            for c in cols:
                desc = f"{c.name} ({c.column_type})"
                if c.reference_table:
                    desc += f" → {c.reference_table}"
                if c.primary_key:
                    desc += " [PK]"
                if not c.nullable and not c.primary_key:
                    desc += " [required]"
                if c.unique:
                    desc += " [unique]"
                col_desc.append(desc)

            display = f" (display: {t.display_field})" if t.display_field else ""
            lines.append(f"  - {t.name}{display}: {', '.join(col_desc)}")

    # Views
    lines.append("")
    lines.append("Named views:")
    has_views = False
    for t, _ in tables:
        views = view_form_service.list_views(session, database_id, t.name)
        named = [v for v in views if not v.is_default]
        if named:
            has_views = True
            for v in named:
                lines.append(f"  - {t.name}: \"{v.name}\"")
    if not has_views:
        lines.append("  (none)")

    # Dashboards
    dashboards = dashboard_service.list_dashboards(session, database_id)
    lines.append("")
    lines.append("Dashboards:")
    if dashboards:
        for d in dashboards:
            widget_count = len(d.config.get("widgets", []))
            lines.append(f"  - \"{d.name}\" ({widget_count} widgets)")
    else:
        lines.append("  (none)")

    lines.extend([
        "",
        "Guidelines:",
        "- Use the provided tools to help the user. After making changes, explain what you did.",
        "- When creating tables, set an appropriate display_field (usually the main text column).",
        "- Reference columns should be named {table}_id by convention.",
        "- Available column types: text, integer, decimal, boolean, date, timestamp, json, reference.",
        "- For reference columns, always include reference_table.",
        "- Be concise and helpful.",
    ])

    return "\n".join(lines)
