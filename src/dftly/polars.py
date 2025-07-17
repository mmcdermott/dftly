"""Polars execution engine for dftly."""

from __future__ import annotations

from typing import Any, Dict, Mapping

try:
    import polars as pl
except ModuleNotFoundError as exc:  # pragma: no cover - import guard
    raise ModuleNotFoundError(
        "Polars is required for the dftly.polars module. Install with 'dftly[polars]'"
    ) from exc

from .nodes import Column, Expression, Literal


_TYPE_MAP: dict[str, Any] = {
    "int": int,
    "integer": int,
    "float": float,
    "double": float,
    "bool": bool,
    "boolean": bool,
    "str": str,
    "string": str,
    "date": pl.Date,
    "datetime": pl.Datetime,
}


def to_polars(node: Any) -> pl.Expr:
    """Convert a dftly node to a polars expression."""
    if isinstance(node, Literal):
        return pl.lit(node.value)
    if isinstance(node, Column):
        return pl.col(node.name)
    if isinstance(node, Expression):
        return _expr_to_polars(node)
    raise TypeError(f"Unsupported node type: {type(node).__name__}")


def map_to_polars(mapping: Mapping[str, Any]) -> Dict[str, pl.Expr]:
    """Convert a mapping of dftly nodes to polars expressions."""
    return {k: to_polars(v) for k, v in mapping.items()}


def _expr_to_polars(expr: Expression) -> pl.Expr:
    typ = expr.type.upper()
    args = expr.arguments

    if typ == "ADD":
        return sum(to_polars(arg) for arg in args)
    if typ == "SUBTRACT":
        left, right = args
        return to_polars(left) - to_polars(right)
    if typ == "TYPE_CAST":
        inp = to_polars(args["input"])
        out_type = args["output_type"].value
        dtype = _TYPE_MAP.get(out_type.lower(), out_type)
        return inp.cast(dtype)
    if typ == "CONDITIONAL":
        return (
            pl.when(to_polars(args["if"]))
            .then(to_polars(args["then"]))
            .otherwise(to_polars(args["else"]))
        )
    if typ == "RESOLVE_TIMESTAMP":
        return _resolve_timestamp(args)

    raise ValueError(f"Unsupported expression type: {expr.type}")


def _resolve_timestamp(args: Mapping[str, Any]) -> pl.Expr:
    date = args["date"]
    time = args["time"]

    if isinstance(date, Mapping):
        year = to_polars(date["year"])
        month = to_polars(date["month"])
        day = to_polars(date["day"])
    else:
        date_expr = to_polars(date)
        year = date_expr.dt.year()
        month = date_expr.dt.month()
        day = date_expr.dt.day()

    hour = to_polars(time["hour"])
    minute = to_polars(time["minute"])
    second = to_polars(time["second"])

    return pl.datetime(year, month, day, hour, minute, second)


__all__ = ["to_polars", "map_to_polars"]
