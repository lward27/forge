import uuid
from datetime import datetime, timezone

from sqlmodel import Session, select

from forge_platform.models.column_definition import ColumnDefinition
from forge_platform.models.table_form import TableForm
from forge_platform.models.table_view import TableView


def generate_default_view(
    session: Session,
    database_id: uuid.UUID,
    table_name: str,
    columns: list[ColumnDefinition],
) -> TableView:
    """Create or replace the default view for a table."""
    # Delete existing default
    existing = session.exec(
        select(TableView).where(
            TableView.database_id == database_id,
            TableView.table_name == table_name,
            TableView.is_default == True,  # noqa: E712
        )
    ).first()

    config = {
        "columns": [
            {"field": c.name, "visible": True, "width": None}
            for c in columns
            if c.status == "active"
        ],
        "default_sort": {"field": "id", "direction": "asc"},
        "page_size": 25,
    }

    if existing:
        existing.config = config
        existing.updated_at = datetime.now(timezone.utc)
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    view = TableView(
        database_id=database_id,
        table_name=table_name,
        name="default",
        is_default=True,
        config=config,
    )
    session.add(view)
    session.commit()
    session.refresh(view)
    return view


def generate_default_form(
    session: Session,
    database_id: uuid.UUID,
    table_name: str,
    columns: list[ColumnDefinition],
    related_tables: list[dict] | None = None,
) -> TableForm:
    """Create or replace the default form for a table."""
    existing = session.exec(
        select(TableForm).where(
            TableForm.database_id == database_id,
            TableForm.table_name == table_name,
            TableForm.is_default == True,  # noqa: E712
        )
    ).first()

    config = {
        "sections": [
            {
                "title": "Details",
                "fields": [
                    {"field": c.name, "visible": True}
                    for c in columns
                    if c.status == "active" and not c.primary_key
                ],
            }
        ],
        "related_tables": related_tables or [],
    }

    if existing:
        existing.config = config
        existing.updated_at = datetime.now(timezone.utc)
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    form = TableForm(
        database_id=database_id,
        table_name=table_name,
        name="default",
        is_default=True,
        config=config,
    )
    session.add(form)
    session.commit()
    session.refresh(form)
    return form


def get_default_view(
    session: Session, database_id: uuid.UUID, table_name: str
) -> TableView | None:
    return session.exec(
        select(TableView).where(
            TableView.database_id == database_id,
            TableView.table_name == table_name,
            TableView.is_default == True,  # noqa: E712
        )
    ).first()


def get_default_form(
    session: Session, database_id: uuid.UUID, table_name: str
) -> TableForm | None:
    return session.exec(
        select(TableForm).where(
            TableForm.database_id == database_id,
            TableForm.table_name == table_name,
            TableForm.is_default == True,  # noqa: E712
        )
    ).first()


def get_view(session: Session, view_id: uuid.UUID) -> TableView | None:
    return session.get(TableView, view_id)


def get_form(session: Session, form_id: uuid.UUID) -> TableForm | None:
    return session.get(TableForm, form_id)


def update_view(
    session: Session, view_id: uuid.UUID, config: dict
) -> TableView | None:
    view = session.get(TableView, view_id)
    if view is None:
        return None
    view.config = config
    view.updated_at = datetime.now(timezone.utc)
    session.add(view)
    session.commit()
    session.refresh(view)
    return view


def update_form(
    session: Session, form_id: uuid.UUID, config: dict
) -> TableForm | None:
    form = session.get(TableForm, form_id)
    if form is None:
        return None
    form.config = config
    form.updated_at = datetime.now(timezone.utc)
    session.add(form)
    session.commit()
    session.refresh(form)
    return form


def discover_related_tables(
    session: Session, database_id: uuid.UUID, table_name: str
) -> list[dict]:
    """Find all tables in this database that have reference columns pointing to table_name."""
    from forge_platform.services import table_service

    all_tables = table_service.list_tables(session, database_id)
    related = []
    for tbl_def, cols in all_tables:
        for col in cols:
            if col.column_type == "reference" and col.reference_table == table_name:
                related.append({
                    "table": tbl_def.name,
                    "reference_column": col.name,
                    "visible": True,
                    "collapsed": False,
                })
    return related
