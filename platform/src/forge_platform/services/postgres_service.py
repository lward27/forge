import logging
import secrets

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from forge_platform.config import settings

logger = logging.getLogger(__name__)


def _parse_db_url():
    """Parse the platform DATABASE_URL into connection components."""
    from urllib.parse import urlparse

    parsed = urlparse(settings.database_url)
    return {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "user": parsed.username,
        "password": parsed.password,
    }


def _get_admin_connection(dbname: str = "postgres"):
    """Connect to a PG database as superuser for DDL operations."""
    params = _parse_db_url()
    conn = psycopg2.connect(**params, dbname=dbname)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    return conn


def generate_password() -> str:
    """Generate a secure random password."""
    return secrets.token_urlsafe(32)


def create_database(pg_database: str, pg_role: str, password: str) -> None:
    """Create a PG role and database, with proper access controls."""
    conn = _get_admin_connection()
    try:
        cur = conn.cursor()

        # Create role
        cur.execute(
            sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD {}").format(
                sql.Identifier(pg_role),
                sql.Literal(password),
            )
        )
        logger.info("Created PG role %s", pg_role)

        # Create database owned by the role
        cur.execute(
            sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(pg_database),
                sql.Identifier(pg_role),
            )
        )
        logger.info("Created PG database %s", pg_database)

        # Restrict access
        cur.execute(
            sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(
                sql.Identifier(pg_database),
            )
        )
        cur.execute(
            sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                sql.Identifier(pg_database),
                sql.Identifier(pg_role),
            )
        )
        logger.info("Configured access for %s on %s", pg_role, pg_database)

        cur.close()
    finally:
        conn.close()


def drop_database(pg_database: str, pg_role: str) -> None:
    """Drop a PG database and role, terminating active connections first."""
    conn = _get_admin_connection()
    try:
        cur = conn.cursor()

        # Terminate active connections
        cur.execute(
            sql.SQL(
                "SELECT pg_terminate_backend(pid) "
                "FROM pg_stat_activity "
                "WHERE datname = {} AND pid <> pg_backend_pid()"
            ).format(sql.Literal(pg_database))
        )
        logger.info("Terminated connections to %s", pg_database)

        # Drop database
        cur.execute(
            sql.SQL("DROP DATABASE IF EXISTS {}").format(
                sql.Identifier(pg_database),
            )
        )
        logger.info("Dropped PG database %s", pg_database)

        # Drop role
        cur.execute(
            sql.SQL("DROP ROLE IF EXISTS {}").format(
                sql.Identifier(pg_role),
            )
        )
        logger.info("Dropped PG role %s", pg_role)

        cur.close()
    finally:
        conn.close()


# ── Tenant DB DDL operations ──────────────────────────────────────────────


def create_table(
    pg_database: str,
    pg_role: str,
    table_name: str,
    columns: list[dict],
    pg_type_map: dict[str, str],
) -> None:
    """Create a table in a tenant database."""
    conn = _get_admin_connection(dbname=pg_database)
    try:
        cur = conn.cursor()

        # Build column definitions
        col_parts = [sql.SQL("id SERIAL PRIMARY KEY")]
        for col in columns:
            if col["type"] == "reference":
                # Reference column: INTEGER with FK constraint
                parts = [sql.Identifier(col["name"]), sql.SQL("INTEGER")]
                if not col.get("nullable", True):
                    parts.append(sql.SQL("NOT NULL"))
                parts.append(sql.SQL("REFERENCES"))
                parts.append(sql.Identifier(col["reference_table"]))
                parts.append(sql.SQL("(id)"))
            else:
                pg_type = pg_type_map[col["type"]]
                parts = [sql.Identifier(col["name"]), sql.SQL(pg_type)]
                if not col.get("nullable", True):
                    parts.append(sql.SQL("NOT NULL"))
                if col.get("unique", False):
                    parts.append(sql.SQL("UNIQUE"))
                if col.get("default") is not None:
                    parts.append(sql.SQL("DEFAULT"))
                    parts.append(sql.SQL(col["default"]))
            col_parts.append(sql.SQL(" ").join(parts))

        create_stmt = sql.SQL("CREATE TABLE {} ({})").format(
            sql.Identifier(table_name),
            sql.SQL(", ").join(col_parts),
        )
        cur.execute(create_stmt)
        logger.info("Created table %s in %s", table_name, pg_database)

        # Transfer ownership to tenant role
        cur.execute(
            sql.SQL("ALTER TABLE {} OWNER TO {}").format(
                sql.Identifier(table_name),
                sql.Identifier(pg_role),
            )
        )
        logger.info("Transferred ownership of %s to %s", table_name, pg_role)

        cur.close()
    finally:
        conn.close()


def drop_table(pg_database: str, table_name: str) -> None:
    """Drop a table from a tenant database."""
    conn = _get_admin_connection(dbname=pg_database)
    try:
        cur = conn.cursor()
        cur.execute(
            sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(
                sql.Identifier(table_name),
            )
        )
        logger.info("Dropped table %s from %s", table_name, pg_database)
        cur.close()
    finally:
        conn.close()


def add_columns(
    pg_database: str,
    table_name: str,
    columns: list[dict],
    pg_type_map: dict[str, str],
) -> None:
    """Add columns to an existing table in a tenant database."""
    conn = _get_admin_connection(dbname=pg_database)
    try:
        cur = conn.cursor()
        for col in columns:
            parts = [
                sql.SQL("ALTER TABLE"),
                sql.Identifier(table_name),
                sql.SQL("ADD COLUMN"),
                sql.Identifier(col["name"]),
            ]
            if col["type"] == "reference":
                parts.append(sql.SQL("INTEGER"))
                if not col.get("nullable", True):
                    parts.append(sql.SQL("NOT NULL"))
                parts.append(sql.SQL("REFERENCES"))
                parts.append(sql.Identifier(col["reference_table"]))
                parts.append(sql.SQL("(id)"))
            else:
                pg_type = pg_type_map[col["type"]]
                parts.append(sql.SQL(pg_type))
                if not col.get("nullable", True):
                    parts.append(sql.SQL("NOT NULL"))
                if col.get("unique", False):
                    parts.append(sql.SQL("UNIQUE"))
                if col.get("default") is not None:
                    parts.append(sql.SQL("DEFAULT"))
                    parts.append(sql.SQL(col["default"]))
            cur.execute(sql.SQL(" ").join(parts))
            logger.info("Added column %s to %s.%s", col["name"], pg_database, table_name)
        cur.close()
    finally:
        conn.close()


def drop_columns(
    pg_database: str,
    table_name: str,
    column_names: list[str],
) -> None:
    """Drop columns from an existing table in a tenant database."""
    conn = _get_admin_connection(dbname=pg_database)
    try:
        cur = conn.cursor()
        for col_name in column_names:
            cur.execute(
                sql.SQL("ALTER TABLE {} DROP COLUMN {}").format(
                    sql.Identifier(table_name),
                    sql.Identifier(col_name),
                )
            )
            logger.info("Dropped column %s from %s.%s", col_name, pg_database, table_name)
        cur.close()
    finally:
        conn.close()


# ── Tenant DB DML operations ──────────────────────────────────────────────


def insert_row(
    pg_database: str,
    table_name: str,
    data: dict,
    returning_columns: list[str],
) -> dict:
    """Insert a row and return it with all columns."""
    conn = _get_admin_connection(dbname=pg_database)
    try:
        cur = conn.cursor()
        columns = list(data.keys())
        values = list(data.values())

        stmt = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING {}").format(
            sql.Identifier(table_name),
            sql.SQL(", ").join(sql.Identifier(c) for c in columns),
            sql.SQL(", ").join(sql.Placeholder() for _ in values),
            sql.SQL(", ").join(sql.Identifier(c) for c in returning_columns),
        )
        cur.execute(stmt, values)
        row = cur.fetchone()
        result = dict(zip(returning_columns, row))
        cur.close()
        return result
    finally:
        conn.close()


def insert_rows_batch(
    pg_database: str,
    table_name: str,
    rows_data: list[dict],
    returning_columns: list[str],
) -> list[dict]:
    """Insert multiple rows in a single transaction."""
    conn = _get_admin_connection(dbname=pg_database)
    # Use a transaction (not autocommit) for batch
    conn.set_isolation_level(0)  # reset to default (transactional)
    try:
        cur = conn.cursor()
        results = []
        for data in rows_data:
            columns = list(data.keys())
            values = list(data.values())

            stmt = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING {}").format(
                sql.Identifier(table_name),
                sql.SQL(", ").join(sql.Identifier(c) for c in columns),
                sql.SQL(", ").join(sql.Placeholder() for _ in values),
                sql.SQL(", ").join(sql.Identifier(c) for c in returning_columns),
            )
            cur.execute(stmt, values)
            row = cur.fetchone()
            results.append(dict(zip(returning_columns, row)))

        conn.commit()
        cur.close()
        return results
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def select_rows(
    pg_database: str,
    table_name: str,
    columns: list[str],
    filters: list[tuple] | None = None,
    sort_column: str | None = None,
    sort_desc: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Select rows with filtering, sorting, and pagination. Returns (rows, total)."""
    conn = _get_admin_connection(dbname=pg_database)
    try:
        cur = conn.cursor()

        # Build WHERE clause
        where_parts = []
        where_values = []
        if filters:
            for col_name, pg_op, value in filters:
                if pg_op == "IS NULL":
                    if value.lower() == "true":
                        where_parts.append(
                            sql.SQL("{} IS NULL").format(sql.Identifier(col_name))
                        )
                    else:
                        where_parts.append(
                            sql.SQL("{} IS NOT NULL").format(sql.Identifier(col_name))
                        )
                elif pg_op == "IN":
                    in_values = [v.strip() for v in value.split(",")]
                    placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in in_values)
                    where_parts.append(
                        sql.SQL("{} IN ({})").format(sql.Identifier(col_name), placeholders)
                    )
                    where_values.extend(in_values)
                else:
                    where_parts.append(
                        sql.SQL("{} " + pg_op + " {}").format(
                            sql.Identifier(col_name), sql.Placeholder()
                        )
                    )
                    where_values.append(value)

        where_clause = sql.SQL("")
        if where_parts:
            where_clause = sql.SQL(" WHERE ") + sql.SQL(" AND ").join(where_parts)

        # Count total
        count_stmt = sql.SQL("SELECT COUNT(*) FROM {}").format(
            sql.Identifier(table_name)
        ) + where_clause
        cur.execute(count_stmt, where_values)
        total = cur.fetchone()[0]

        # Build SELECT
        select_stmt = sql.SQL("SELECT {} FROM {}").format(
            sql.SQL(", ").join(sql.Identifier(c) for c in columns),
            sql.Identifier(table_name),
        ) + where_clause

        if sort_column:
            direction = sql.SQL(" DESC") if sort_desc else sql.SQL(" ASC")
            select_stmt = select_stmt + sql.SQL(" ORDER BY ") + sql.Identifier(sort_column) + direction

        select_stmt = select_stmt + sql.SQL(" LIMIT {} OFFSET {}").format(
            sql.Literal(limit), sql.Literal(offset)
        )

        cur.execute(select_stmt, where_values)
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]
        cur.close()
        return rows, total
    finally:
        conn.close()


def select_row_by_pk(
    pg_database: str,
    table_name: str,
    columns: list[str],
    pk_value: int,
) -> dict | None:
    """Select a single row by primary key."""
    conn = _get_admin_connection(dbname=pg_database)
    try:
        cur = conn.cursor()
        stmt = sql.SQL("SELECT {} FROM {} WHERE {} = {}").format(
            sql.SQL(", ").join(sql.Identifier(c) for c in columns),
            sql.Identifier(table_name),
            sql.Identifier("id"),
            sql.Placeholder(),
        )
        cur.execute(stmt, [pk_value])
        row = cur.fetchone()
        cur.close()
        if row is None:
            return None
        return dict(zip(columns, row))
    finally:
        conn.close()


def update_row(
    pg_database: str,
    table_name: str,
    pk_value: int,
    data: dict,
    returning_columns: list[str],
) -> dict | None:
    """Update a row by primary key and return the updated row."""
    conn = _get_admin_connection(dbname=pg_database)
    try:
        cur = conn.cursor()
        set_parts = []
        values = []
        for col, val in data.items():
            set_parts.append(
                sql.SQL("{} = {}").format(sql.Identifier(col), sql.Placeholder())
            )
            values.append(val)

        values.append(pk_value)

        stmt = sql.SQL("UPDATE {} SET {} WHERE {} = {} RETURNING {}").format(
            sql.Identifier(table_name),
            sql.SQL(", ").join(set_parts),
            sql.Identifier("id"),
            sql.Placeholder(),
            sql.SQL(", ").join(sql.Identifier(c) for c in returning_columns),
        )
        cur.execute(stmt, values)
        row = cur.fetchone()
        cur.close()
        if row is None:
            return None
        return dict(zip(returning_columns, row))
    finally:
        conn.close()


def delete_row(
    pg_database: str,
    table_name: str,
    pk_value: int,
) -> bool:
    """Delete a row by primary key. Returns True if deleted."""
    conn = _get_admin_connection(dbname=pg_database)
    try:
        cur = conn.cursor()
        stmt = sql.SQL("DELETE FROM {} WHERE {} = {}").format(
            sql.Identifier(table_name),
            sql.Identifier("id"),
            sql.Placeholder(),
        )
        cur.execute(stmt, [pk_value])
        deleted = cur.rowcount > 0
        cur.close()
        return deleted
    finally:
        conn.close()


def fetch_display_values(
    pg_database: str,
    table_name: str,
    display_field: str,
    ids: list[int],
) -> dict[int, str]:
    """Fetch display field values for a list of IDs. Returns {id: display_value}."""
    if not ids:
        return {}
    conn = _get_admin_connection(dbname=pg_database)
    try:
        cur = conn.cursor()
        placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in ids)
        stmt = sql.SQL("SELECT id, {} FROM {} WHERE id IN ({})").format(
            sql.Identifier(display_field),
            sql.Identifier(table_name),
            placeholders,
        )
        cur.execute(stmt, ids)
        result = {row[0]: str(row[1]) if row[1] is not None else None for row in cur.fetchall()}
        cur.close()
        return result
    finally:
        conn.close()


def bulk_delete_rows(
    pg_database: str,
    table_name: str,
    ids: list[int],
) -> int:
    """Delete multiple rows by ID. Returns count deleted."""
    if not ids:
        return 0
    conn = _get_admin_connection(dbname=pg_database)
    try:
        cur = conn.cursor()
        placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in ids)
        stmt = sql.SQL("DELETE FROM {} WHERE {} IN ({})").format(
            sql.Identifier(table_name),
            sql.Identifier("id"),
            placeholders,
        )
        cur.execute(stmt, ids)
        deleted = cur.rowcount
        cur.close()
        return deleted
    finally:
        conn.close()


def expand_references(
    pg_database: str,
    rows: list[dict],
    expand_cols: list[dict],
) -> list[dict]:
    """Expand reference columns by fetching the referenced rows."""
    if not expand_cols or not rows:
        return rows

    conn = _get_admin_connection(dbname=pg_database)
    try:
        cur = conn.cursor()
        for col_info in expand_cols:
            col_name = col_info["name"]
            ref_table = col_info["reference_table"]

            # Collect all referenced IDs
            ref_ids = list({r[col_name] for r in rows if r.get(col_name) is not None})
            if not ref_ids:
                continue

            # Fetch referenced rows
            placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in ref_ids)
            stmt = sql.SQL("SELECT * FROM {} WHERE id IN ({})").format(
                sql.Identifier(ref_table), placeholders
            )
            cur.execute(stmt, ref_ids)
            col_names = [desc[0] for desc in cur.description]
            ref_rows = {r[0]: dict(zip(col_names, r)) for r in cur.fetchall()}

            # Attach expanded data
            for row in rows:
                ref_id = row.get(col_name)
                row[f"{col_name}__expanded"] = ref_rows.get(ref_id) if ref_id else None

        cur.close()
        return rows
    finally:
        conn.close()


def select_related_rows(
    pg_database: str,
    ref_table_name: str,
    ref_column: str,
    pk_value: int,
    limit: int = 50,
) -> list[dict]:
    """Select rows from a table where a reference column matches the given PK."""
    conn = _get_admin_connection(dbname=pg_database)
    try:
        cur = conn.cursor()
        stmt = sql.SQL("SELECT * FROM {} WHERE {} = {} LIMIT {}").format(
            sql.Identifier(ref_table_name),
            sql.Identifier(ref_column),
            sql.Placeholder(),
            sql.Literal(limit),
        )
        cur.execute(stmt, [pk_value])
        col_names = [desc[0] for desc in cur.description]
        rows = [dict(zip(col_names, r)) for r in cur.fetchall()]

        # Get count
        count_stmt = sql.SQL("SELECT COUNT(*) FROM {} WHERE {} = {}").format(
            sql.Identifier(ref_table_name),
            sql.Identifier(ref_column),
            sql.Placeholder(),
        )
        cur.execute(count_stmt, [pk_value])
        count = cur.fetchone()[0]

        cur.close()
        return {"count": count, "rows": rows}
    finally:
        conn.close()
