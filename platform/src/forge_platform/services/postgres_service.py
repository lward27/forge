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
            pg_type = pg_type_map[col["type"]]
            parts = [
                sql.SQL("ALTER TABLE"),
                sql.Identifier(table_name),
                sql.SQL("ADD COLUMN"),
                sql.Identifier(col["name"]),
                sql.SQL(pg_type),
            ]
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
