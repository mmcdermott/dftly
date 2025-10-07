"""Polars execution engine for dftly."""

from __future__ import annotations

from typing import Any, Dict, Mapping
import string
from datetime import datetime, timezone
from dateutil import parser as dtparser

try:
    import polars as pl
except ModuleNotFoundError as exc:  # pragma: no cover - import guard
    raise ModuleNotFoundError(
        "Polars is required for the dftly.polars module. Install with 'dftly[polars]'"
    ) from exc

from .expressions import ExpressionRegistry
from .nodes import Column, Expression, Literal


_CLOCK_TIME = object()


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
    "duration": pl.Duration,
    "time": _CLOCK_TIME,
    "clock_time": _CLOCK_TIME,
    "clock-time": _CLOCK_TIME,
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


def _ensure_naive_datetime(dt: datetime) -> datetime:
    """Return a timezone-naive datetime in UTC for subtraction or casting."""

    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _expr_to_polars(expr: Expression) -> pl.Expr:
    return ExpressionRegistry.to_polars(expr, to_polars, pl=pl)

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

    base_datetime = pl.datetime(year, month, day, 0, 0, 0)

    if isinstance(time, Mapping):

        def _component(name: str) -> pl.Expr:
            node = time.get(name)
            return to_polars(node) if node is not None else pl.lit(0)

        hour = _component("hour")
        minute = _component("minute")
        second = _component("second")
        return pl.datetime(year, month, day, hour, minute, second)

    return base_datetime + to_polars(time)


__all__ = ["to_polars", "map_to_polars"]
