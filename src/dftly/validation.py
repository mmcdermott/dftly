"""Schema validation utilities for parsed dftly trees."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .nodes import Column, Expression


class SchemaValidationError(ValueError):
    """Raised when parsed nodes are incompatible with a provided schema."""


def validate_schema(parsed: Any, schema: Mapping[str, Any]) -> None:
    """Validate that all column references exist in the provided schema.

    Parameters
    ----------
    parsed:
        A parsed node or mapping of nodes produced by :func:`dftly.parse`
        or :func:`dftly.from_yaml`.
    schema:
        Mapping of column names to optional type strings.
    """

    if not isinstance(schema, Mapping):
        raise TypeError("schema must be a mapping of column names to types")

    _validate_node(parsed, schema, path=())


def _validate_node(node: Any, schema: Mapping[str, Any], path: Sequence[str]) -> None:
    if isinstance(node, Column):
        _validate_column(node, schema, path)
        return

    if isinstance(node, Expression):
        _validate_node(node.arguments, schema, (*path, f"expression:{node.type}"))
        return

    if isinstance(node, Mapping):
        for key, value in node.items():
            _validate_node(value, schema, (*path, str(key)))
        return

    if isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
        for index, value in enumerate(node):
            _validate_node(value, schema, (*path, str(index)))
        return


def _validate_column(
    column: Column, schema: Mapping[str, Any], path: Sequence[str]
) -> None:
    if column.name not in schema:
        location = _format_path(path)
        raise SchemaValidationError(
            f"Unknown column '{column.name}' referenced at {location}"
        )

    expected_type = schema[column.name]
    if expected_type is None:
        return

    if column.type is None:
        column.type = expected_type
        return

    if column.type != expected_type:
        location = _format_path(path)
        raise SchemaValidationError(
            f"Column '{column.name}' at {location} expected type {expected_type!r}"
            f" but found {column.type!r}"
        )


def _format_path(path: Sequence[str]) -> str:
    if not path:
        return "<root>"
    return " -> ".join(path)
