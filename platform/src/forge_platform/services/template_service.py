"""Deploy templates — creates tables, views, forms, and dashboard."""
import logging

from sqlmodel import Session

from forge_platform.models.tenant_database import TenantDatabase
from forge_platform.schemas.table import ColumnCreate, TableCreate
from forge_platform.services import table_service, view_form_service, dashboard_service
from forge_platform.templates import get_template, list_templates

logger = logging.getLogger(__name__)


def deploy_template(
    session: Session,
    tenant_db: TenantDatabase,
    template_id: str,
) -> dict:
    """Deploy a full template — tables, views, forms, and dashboard."""
    template = get_template(template_id)
    if template is None:
        raise ValueError(f"Template '{template_id}' not found")

    app_name = template["name"]
    created_tables = []
    created_views = []
    created_forms = []
    created_dashboard = None

    # 1. Create all tables (in FK order)
    for table_def in template["tables"]:
        columns = [
            ColumnCreate(
                name=c["name"],
                type=c["type"],
                nullable=c.get("nullable", True),
                unique=c.get("unique", False),
                default=c.get("default"),
                reference_table=c.get("reference_table"),
            )
            for c in table_def["columns"]
        ]

        table_in = TableCreate(
            name=table_def["name"],
            columns=columns,
            display_field=table_def.get("display_field"),
            app_name=app_name,
        )

        t, cols = table_service.create_table(session, tenant_db, table_in)
        created_tables.append(t.name)
        logger.info("Template '%s': created table %s", template_id, t.name)

    # 2. Create named views
    view_name_to_id = {}
    for view_def in template.get("views", []):
        view = view_form_service.create_named_view(
            session,
            tenant_db.id,
            view_def["table"],
            view_def["name"],
            view_def["config"],
        )
        view_name_to_id[view_def["name"]] = str(view.id)
        created_views.append(f"{view_def['table']}/{view_def['name']}")
        logger.info("Template '%s': created view %s on %s", template_id, view_def["name"], view_def["table"])

    # 3. Create named forms
    for form_def in template.get("forms", []):
        view_form_service.create_named_form(
            session,
            tenant_db.id,
            form_def["table"],
            form_def["name"],
            form_def["config"],
        )
        created_forms.append(f"{form_def['table']}/{form_def['name']}")
        logger.info("Template '%s': created form %s on %s", template_id, form_def["name"], form_def["table"])

    # 4. Create dashboard
    dash_def = template.get("dashboard")
    if dash_def:
        widgets = []
        x = 0
        y = 0
        for i, w in enumerate(dash_def.get("widgets", [])):
            width = w.get("w", 6)
            height = w.get("h", 4)
            if x + width > 12:
                x = 0
                y += height

            widget = {
                "id": f"w{i}",
                "type": w["type"],
                "title": w["title"],
                "table": w["table"],
                "view_id": view_name_to_id.get(w.get("view_name")) if w.get("view_name") else None,
                "x": x, "y": y,
                "w": width, "h": height,
            }
            widgets.append(widget)
            x += width

        d = dashboard_service.create_dashboard(
            session,
            database_id=tenant_db.id,
            name=dash_def["name"],
            is_default=False,
            config={"widgets": widgets, "grid_cols": 12},
        )
        created_dashboard = d.name
        logger.info("Template '%s': created dashboard %s", template_id, d.name)

    return {
        "template": template["name"],
        "app_name": app_name,
        "tables_created": created_tables,
        "views_created": created_views,
        "forms_created": created_forms,
        "dashboard_created": created_dashboard,
    }
