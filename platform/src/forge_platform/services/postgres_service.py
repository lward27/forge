import logging
import secrets

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from forge_platform.config import settings

logger = logging.getLogger(__name__)


def _get_admin_connection():
    """Connect to the 'postgres' maintenance DB as superuser for DDL operations."""
    # Parse the platform DATABASE_URL to extract host/port/user/password,
    # then connect to the 'postgres' DB instead of 'forge_platform'
    from urllib.parse import urlparse

    parsed = urlparse(settings.database_url)
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        dbname="postgres",
    )
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
