import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


VALID_TYPES = {
    "text", "integer", "biginteger", "decimal", "boolean",
    "date", "timestamp", "json", "serial", "reference",
}

PG_TYPE_MAP = {
    "text": "TEXT",
    "integer": "INTEGER",
    "biginteger": "BIGINT",
    "decimal": "NUMERIC(18,6)",
    "boolean": "BOOLEAN",
    "date": "DATE",
    "timestamp": "TIMESTAMPTZ",
    "json": "JSONB",
    "serial": "SERIAL",
}

# Reserved PG words that can't be used as table/column names
RESERVED_NAMES = {
    "id", "table", "column", "index", "select", "insert", "update", "delete",
    "from", "where", "order", "group", "by", "join", "on", "create", "drop",
    "alter", "grant", "revoke", "user", "role", "database", "schema", "primary",
    "foreign", "key", "constraint", "null", "not", "default", "check", "unique",
    "references", "cascade", "limit", "offset", "and", "or", "in", "between",
    "like", "is", "as", "all", "any", "exists", "having", "union", "except",
    "intersect", "case", "when", "then", "else", "end", "true", "false",
}


class ColumnCreate(BaseModel):
    name: str
    type: str
    nullable: bool = True
    unique: bool = False
    default: Optional[str] = None
    reference_table: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[a-z][a-z0-9_]*$", v) or len(v) < 2 or len(v) > 63:
            raise ValueError(
                "Column name must be 2-63 chars, lowercase alphanumeric with underscores"
            )
        if v in RESERVED_NAMES:
            raise ValueError(f"'{v}' is a reserved name and cannot be used")
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in VALID_TYPES:
            raise ValueError(
                f"Invalid column type '{v}'. Valid types: {', '.join(sorted(VALID_TYPES))}"
            )
        return v


class TableCreate(BaseModel):
    name: str
    columns: list[ColumnCreate]

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[a-z][a-z0-9_]*$", v) or len(v) < 2 or len(v) > 63:
            raise ValueError(
                "Table name must be 2-63 chars, lowercase alphanumeric with underscores"
            )
        if v in RESERVED_NAMES:
            raise ValueError(f"'{v}' is a reserved name and cannot be used")
        return v


class TableAlter(BaseModel):
    add_columns: list[ColumnCreate] = []
    drop_columns: list[str] = []


class ColumnResponse(BaseModel):
    name: str
    type: str
    nullable: bool
    primary_key: bool
    unique: bool
    default: Optional[str]
    reference_table: Optional[str] = None


class TableResponse(BaseModel):
    name: str
    database_id: uuid.UUID
    columns: list[ColumnResponse]
    created_at: datetime


class TableListResponse(BaseModel):
    tables: list[TableResponse]


class TableDeleteResponse(BaseModel):
    name: str
    status: str
