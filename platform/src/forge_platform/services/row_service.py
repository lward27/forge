import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlmodel import Session

from forge_platform.models.column_definition import ColumnDefinition
from forge_platform.models.tenant_database import TenantDatabase
from forge_platform.schemas.row import VALID_OPERATORS, ParsedFilter, parse_filter
from forge_platform.services import postgres_service, table_service


def _enrich_display_values(
    session: Session,
    tenant_db: TenantDatabase,
    columns: list[ColumnDefinition],
    rows: list[dict],
) -> list[dict]:
    """Add __display values for reference columns."""
    if not rows:
        return rows

    ref_cols = [c for c in columns if c.column_type == "reference" and c.reference_table]
    if not ref_cols:
        return rows

    for ref_col in ref_cols:
        # Get the display_field for the referenced table
        ref_table_result = table_service.get_table(session, tenant_db.id, ref_col.reference_table)
        if ref_table_result is None:
            continue

        ref_table_def, _ = ref_table_result
        display_field = ref_table_def.display_field
        if not display_field:
            continue

        # Collect referenced IDs
        ref_ids = list({r[ref_col.name] for r in rows if r.get(ref_col.name) is not None})
        if not ref_ids:
            continue

        # Fetch display values
        display_map = postgres_service.fetch_display_values(
            pg_database=tenant_db.pg_database,
            table_name=ref_col.reference_table,
            display_field=display_field,
            ids=ref_ids,
        )

        # Attach to rows
        for row in rows:
            ref_id = row.get(ref_col.name)
            row[f"{ref_col.name}__display"] = display_map.get(ref_id) if ref_id else None

    return rows


def _get_table_context(
    session: Session, tenant_db: TenantDatabase, table_name: str
) -> tuple[list[ColumnDefinition], list[str]]:
    """Get column definitions and column names for a table."""
    result = table_service.get_table(session, tenant_db.id, table_name)
    if result is None:
        raise LookupError("Table not found")

    _, columns = result
    col_names = [c.name for c in columns]
    return columns, col_names


def _validate_input(
    data: dict[str, Any],
    columns: list[ColumnDefinition],
    is_insert: bool = True,
) -> dict[str, Any]:
    """Validate and coerce input data against column definitions."""
    col_map = {c.name: c for c in columns if c.status == "active"}
    writable_cols = {name: col for name, col in col_map.items() if name != "id"}

    # Reject unknown columns
    for key in data:
        if key == "id":
            raise ValueError("Cannot set 'id' column (auto-generated)")
        if key not in writable_cols:
            raise ValueError(
                f"Unknown column '{key}'. Valid columns: {', '.join(sorted(writable_cols))}"
            )

    # On insert, check required columns
    if is_insert:
        for name, col in writable_cols.items():
            if not col.nullable and col.default_value is None and name not in data:
                raise ValueError(
                    f"Column '{name}' is required (not nullable, no default)"
                )

    # Type coercion
    coerced = {}
    for key, value in data.items():
        col = writable_cols[key]
        if value is None:
            if not col.nullable:
                raise ValueError(f"Column '{key}' cannot be null")
            coerced[key] = None
            continue

        try:
            coerced[key] = _coerce_value(value, col.column_type, key)
        except (ValueError, TypeError) as e:
            raise ValueError(str(e))

    return coerced


def _coerce_value(value: Any, column_type: str, column_name: str) -> Any:
    """Coerce a value to the appropriate Python type for the column."""
    try:
        if column_type in ("text",):
            return str(value)
        elif column_type in ("reference",):
            return int(value)
        elif column_type in ("integer",):
            return int(value)
        elif column_type in ("biginteger",):
            return int(value)
        elif column_type in ("decimal",):
            return float(Decimal(str(value)))
        elif column_type in ("boolean",):
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                if value.lower() in ("true", "1", "yes"):
                    return True
                if value.lower() in ("false", "0", "no"):
                    return False
            raise ValueError("not a boolean")
        elif column_type in ("date", "timestamp"):
            return str(value)
        elif column_type in ("json",):
            return value  # psycopg2 handles dict/list → JSONB
        else:
            return value
    except (ValueError, TypeError, InvalidOperation):
        raise ValueError(
            f"Invalid value for column '{column_name}' ({column_type}): {value!r}"
        )


def _validate_filters(
    filter_strings: list[str],
    columns: list[ColumnDefinition],
) -> list[tuple[str, str, str]]:
    """Parse and validate filter strings. Returns list of (column, pg_op, value)."""
    col_names = {c.name for c in columns if c.status == "active"}
    result = []

    for f in filter_strings:
        parsed = parse_filter(f)
        if parsed.column not in col_names:
            raise ValueError(
                f"Cannot filter by '{parsed.column}'. "
                f"Valid columns: {', '.join(sorted(col_names))}"
            )
        pg_op = VALID_OPERATORS[parsed.operator]
        result.append((parsed.column, pg_op, parsed.value))

    return result


def insert_row(
    session: Session,
    tenant_db: TenantDatabase,
    table_name: str,
    data: dict[str, Any],
) -> dict:
    """Insert a row into a tenant table."""
    columns, col_names = _get_table_context(session, tenant_db, table_name)
    validated = _validate_input(data, columns, is_insert=True)

    return postgres_service.insert_row(
        pg_database=tenant_db.pg_database,
        table_name=table_name,
        data=validated,
        returning_columns=col_names,
    )


def insert_rows_batch(
    session: Session,
    tenant_db: TenantDatabase,
    table_name: str,
    rows_data: list[dict[str, Any]],
) -> list[dict]:
    """Insert multiple rows into a tenant table."""
    columns, col_names = _get_table_context(session, tenant_db, table_name)

    validated_rows = []
    for i, data in enumerate(rows_data):
        try:
            validated_rows.append(_validate_input(data, columns, is_insert=True))
        except ValueError as e:
            raise ValueError(f"Row {i}: {e}")

    return postgres_service.insert_rows_batch(
        pg_database=tenant_db.pg_database,
        table_name=table_name,
        rows_data=validated_rows,
        returning_columns=col_names,
    )


def list_rows(
    session: Session,
    tenant_db: TenantDatabase,
    table_name: str,
    filters: list[str] | None = None,
    sort: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """List rows with filtering, sorting, and pagination."""
    columns, col_names = _get_table_context(session, tenant_db, table_name)

    # Parse filters
    parsed_filters = None
    if filters:
        parsed_filters = _validate_filters(filters, columns)

    # Parse sort
    sort_column = None
    sort_desc = False
    if sort:
        if sort.startswith("-"):
            sort_desc = True
            sort_column = sort[1:]
        else:
            sort_column = sort

        if sort_column not in {c.name for c in columns}:
            raise ValueError(
                f"Cannot sort by '{sort_column}'. "
                f"Valid columns: {', '.join(sorted(c.name for c in columns))}"
            )

    rows, total = postgres_service.select_rows(
        pg_database=tenant_db.pg_database,
        table_name=table_name,
        columns=col_names,
        filters=parsed_filters,
        sort_column=sort_column,
        sort_desc=sort_desc,
        limit=limit,
        offset=offset,
    )

    # Auto-join display values for reference columns
    rows = _enrich_display_values(session, tenant_db, columns, rows)

    return rows, total


def get_row(
    session: Session,
    tenant_db: TenantDatabase,
    table_name: str,
    pk_value: int,
) -> dict | None:
    """Get a single row by primary key."""
    columns, col_names = _get_table_context(session, tenant_db, table_name)

    row = postgres_service.select_row_by_pk(
        pg_database=tenant_db.pg_database,
        table_name=table_name,
        columns=col_names,
        pk_value=pk_value,
    )
    if row is None:
        return None

    enriched = _enrich_display_values(session, tenant_db, columns, [row])
    return enriched[0]


def update_row(
    session: Session,
    tenant_db: TenantDatabase,
    table_name: str,
    pk_value: int,
    data: dict[str, Any],
) -> dict | None:
    """Update a row by primary key."""
    columns, col_names = _get_table_context(session, tenant_db, table_name)
    validated = _validate_input(data, columns, is_insert=False)

    if not validated:
        raise ValueError("No valid columns provided for update")

    return postgres_service.update_row(
        pg_database=tenant_db.pg_database,
        table_name=table_name,
        pk_value=pk_value,
        data=validated,
        returning_columns=col_names,
    )


def delete_row(
    session: Session,
    tenant_db: TenantDatabase,
    table_name: str,
    pk_value: int,
) -> bool:
    """Delete a row by primary key."""
    # Verify table exists
    _get_table_context(session, tenant_db, table_name)

    return postgres_service.delete_row(
        pg_database=tenant_db.pg_database,
        table_name=table_name,
        pk_value=pk_value,
    )


def bulk_delete_rows(
    session: Session,
    tenant_db: TenantDatabase,
    table_name: str,
    ids: list[int],
) -> int:
    """Delete multiple rows by IDs."""
    _get_table_context(session, tenant_db, table_name)

    return postgres_service.bulk_delete_rows(
        pg_database=tenant_db.pg_database,
        table_name=table_name,
        ids=ids,
    )


def expand_rows(
    session: Session,
    tenant_db: TenantDatabase,
    table_name: str,
    rows: list[dict],
    expand: list[str],
) -> list[dict]:
    """Expand reference columns on a list of rows."""
    columns, _ = _get_table_context(session, tenant_db, table_name)
    ref_cols = [
        {"name": c.name, "reference_table": c.reference_table}
        for c in columns
        if c.column_type == "reference" and c.reference_table and c.name in expand
    ]
    if not ref_cols:
        return rows

    return postgres_service.expand_references(
        pg_database=tenant_db.pg_database,
        rows=rows,
        expand_cols=ref_cols,
    )


def get_related_records(
    session: Session,
    tenant_db: TenantDatabase,
    table_name: str,
    pk_value: int,
) -> list[dict]:
    """Find all tables with reference columns pointing to this table and return matching rows."""
    # Get all tables in this database
    all_tables = table_service.list_tables(session, tenant_db.id)

    related = []
    for tbl_def, cols in all_tables:
        for col in cols:
            if col.column_type == "reference" and col.reference_table == table_name:
                result = postgres_service.select_related_rows(
                    pg_database=tenant_db.pg_database,
                    ref_table_name=tbl_def.name,
                    ref_column=col.name,
                    pk_value=pk_value,
                )
                related.append({
                    "table": tbl_def.name,
                    "column": col.name,
                    "count": result["count"],
                    "rows": result["rows"],
                })
    return related
