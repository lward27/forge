"""Deploy templates — creates all tables in FK order."""
import logging

from sqlmodel import Session

from forge_platform.models.tenant_database import TenantDatabase
from forge_platform.schemas.table import ColumnCreate, TableCreate
from forge_platform.services import table_service
from forge_platform.templates import get_template, list_templates

logger = logging.getLogger(__name__)


def deploy_template(
    session: Session,
    tenant_db: TenantDatabase,
    template_id: str,
) -> dict:
    """Deploy a template — creates all tables in order."""
    template = get_template(template_id)
    if template is None:
        raise ValueError(f"Template '{template_id}' not found")

    created_tables = []
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
        )

        t, cols = table_service.create_table(session, tenant_db, table_in)
        created_tables.append(t.name)
        logger.info("Template '%s': created table %s", template_id, t.name)

    return {
        "template": template["name"],
        "tables_created": created_tables,
    }
