import uuid
from datetime import datetime, timezone

from sqlmodel import Session, select

from forge_platform.models.column_definition import ColumnDefinition
from forge_platform.models.table_definition import TableDefinition
from forge_platform.models.tenant_database import TenantDatabase
from forge_platform.schemas.table import ColumnCreate, PG_TYPE_MAP, TableCreate, TableAlter
from forge_platform.services import postgres_service


def create_table(
    session: Session,
    tenant_db: TenantDatabase,
    table_in: TableCreate,
) -> tuple[TableDefinition, list[ColumnDefinition]]:
    """Create a table in the tenant database and track in platform DB."""
    # Execute DDL in tenant database
    columns_dicts = [
        {
            "name": c.name,
            "type": c.type,
            "nullable": c.nullable,
            "unique": c.unique,
            "default": c.default,
            "reference_table": c.reference_table,
        }
        for c in table_in.columns
    ]
    postgres_service.create_table(
        pg_database=tenant_db.pg_database,
        pg_role=tenant_db.pg_role,
        table_name=table_in.name,
        columns=columns_dicts,
        pg_type_map=PG_TYPE_MAP,
    )

    # Track in platform DB
    table_def = TableDefinition(
        database_id=tenant_db.id,
        name=table_in.name,
    )
    session.add(table_def)
    session.flush()

    # Auto id column
    col_defs = [
        ColumnDefinition(
            table_id=table_def.id,
            name="id",
            column_type="serial",
            nullable=False,
            primary_key=True,
            unique=False,
            default_value=None,
            ordinal=0,
        )
    ]

    for i, col in enumerate(table_in.columns, start=1):
        col_defs.append(
            ColumnDefinition(
                table_id=table_def.id,
                name=col.name,
                column_type=col.type,
                nullable=col.nullable,
                primary_key=False,
                unique=col.unique,
                default_value=col.default,
                reference_table=col.reference_table,
                ordinal=i,
            )
        )

    for cd in col_defs:
        session.add(cd)

    session.commit()
    session.refresh(table_def)
    return table_def, col_defs


def list_tables(
    session: Session, database_id: uuid.UUID
) -> list[tuple[TableDefinition, list[ColumnDefinition]]]:
    """List all active tables for a database with their columns."""
    tables = session.exec(
        select(TableDefinition).where(
            TableDefinition.database_id == database_id,
            TableDefinition.status == "active",
        )
    ).all()

    result = []
    for t in tables:
        cols = _get_active_columns(session, t.id)
        result.append((t, cols))
    return result


def get_table(
    session: Session, database_id: uuid.UUID, table_name: str
) -> tuple[TableDefinition, list[ColumnDefinition]] | None:
    """Get a table definition by name."""
    table_def = session.exec(
        select(TableDefinition).where(
            TableDefinition.database_id == database_id,
            TableDefinition.name == table_name,
            TableDefinition.status == "active",
        )
    ).first()

    if table_def is None:
        return None

    cols = _get_active_columns(session, table_def.id)
    return table_def, cols


def alter_table(
    session: Session,
    tenant_db: TenantDatabase,
    table_name: str,
    alter_in: TableAlter,
) -> tuple[TableDefinition, list[ColumnDefinition]] | None:
    """Alter a table: add/drop columns."""
    result = get_table(session, tenant_db.id, table_name)
    if result is None:
        return None

    table_def, existing_cols = result
    existing_names = {c.name for c in existing_cols}

    # Validate drop_columns
    for col_name in alter_in.drop_columns:
        if col_name == "id":
            raise ValueError("Cannot drop primary key column 'id'")
        if col_name not in existing_names:
            raise ValueError(f"Column '{col_name}' does not exist")

    # Execute DDL: add columns
    if alter_in.add_columns:
        add_dicts = [
            {
                "name": c.name,
                "type": c.type,
                "nullable": c.nullable,
                "unique": c.unique,
                "default": c.default,
                "reference_table": c.reference_table,
            }
            for c in alter_in.add_columns
        ]
        postgres_service.add_columns(
            pg_database=tenant_db.pg_database,
            table_name=table_name,
            columns=add_dicts,
            pg_type_map=PG_TYPE_MAP,
        )

    # Execute DDL: drop columns
    if alter_in.drop_columns:
        postgres_service.drop_columns(
            pg_database=tenant_db.pg_database,
            table_name=table_name,
            column_names=alter_in.drop_columns,
        )

    # Update platform DB: add new column definitions
    max_ordinal = max(c.ordinal for c in existing_cols) if existing_cols else 0
    for i, col in enumerate(alter_in.add_columns, start=max_ordinal + 1):
        session.add(
            ColumnDefinition(
                table_id=table_def.id,
                name=col.name,
                column_type=col.type,
                nullable=col.nullable,
                primary_key=False,
                unique=col.unique,
                default_value=col.default,
                reference_table=col.reference_table,
                ordinal=i,
            )
        )

    # Update platform DB: mark dropped columns as deleted
    for col_name in alter_in.drop_columns:
        for col in existing_cols:
            if col.name == col_name:
                col.status = "deleted"
                session.add(col)

    # Update platform DB: reorder columns
    if alter_in.reorder_columns:
        col_map = {c.name: c for c in existing_cols}
        for reorder in alter_in.reorder_columns:
            if reorder.name in col_map:
                col_map[reorder.name].ordinal = reorder.ordinal
                session.add(col_map[reorder.name])

    table_def.updated_at = datetime.now(timezone.utc)
    session.add(table_def)
    session.commit()
    session.refresh(table_def)

    updated_cols = _get_active_columns(session, table_def.id)
    return table_def, updated_cols


def delete_table(
    session: Session,
    tenant_db: TenantDatabase,
    table_name: str,
) -> TableDefinition | None:
    """Drop a table from the tenant database."""
    result = get_table(session, tenant_db.id, table_name)
    if result is None:
        return None

    table_def, cols = result

    # Execute DDL
    postgres_service.drop_table(tenant_db.pg_database, table_name)

    # Mark as deleted in platform DB
    table_def.status = "deleted"
    table_def.updated_at = datetime.now(timezone.utc)
    session.add(table_def)

    for col in cols:
        col.status = "deleted"
        session.add(col)

    session.commit()
    session.refresh(table_def)
    return table_def


def _get_active_columns(
    session: Session, table_id: uuid.UUID
) -> list[ColumnDefinition]:
    """Get active columns for a table, ordered by ordinal."""
    return list(
        session.exec(
            select(ColumnDefinition)
            .where(
                ColumnDefinition.table_id == table_id,
                ColumnDefinition.status == "active",
            )
            .order_by(ColumnDefinition.ordinal)
        ).all()
    )
