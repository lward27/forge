from typing import Any, Optional

from pydantic import BaseModel


class RowCreate(BaseModel):
    model_config = {"extra": "allow"}


class RowUpdate(BaseModel):
    model_config = {"extra": "allow"}


class RowBatchCreate(BaseModel):
    rows: list[dict[str, Any]]


class RowResponse(BaseModel):
    model_config = {"extra": "allow"}


class RowListResponse(BaseModel):
    rows: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


class RowDeleteResponse(BaseModel):
    id: int
    deleted: bool = True


class RowBatchResponse(BaseModel):
    inserted: int
    rows: list[dict[str, Any]]


# Filter parsing

VALID_OPERATORS = {
    "eq": "=",
    "neq": "!=",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "like": "LIKE",
    "in": "IN",
    "isnull": "IS NULL",
}


class ParsedFilter:
    def __init__(self, column: str, operator: str, value: str):
        self.column = column
        self.operator = operator
        self.value = value


def parse_filter(filter_str: str) -> ParsedFilter:
    """Parse a filter string like 'column:op:value'."""
    parts = filter_str.split(":", 2)
    if len(parts) < 3:
        raise ValueError(
            f"Invalid filter format: '{filter_str}'. Expected 'column:operator:value'"
        )

    column, op, value = parts
    if op not in VALID_OPERATORS:
        raise ValueError(
            f"Invalid operator '{op}'. Valid operators: {', '.join(sorted(VALID_OPERATORS))}"
        )

    return ParsedFilter(column=column, operator=op, value=value)
