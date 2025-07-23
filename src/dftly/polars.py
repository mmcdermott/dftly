"""Polars execution engine for dftly."""

from __future__ import annotations

from typing import Any, Dict, Mapping
import string

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
        expr = to_polars(args[0])
        for arg in args[1:]:
            expr = expr + to_polars(arg)
        return expr
    if typ == "SUBTRACT":
        left, right = args
        return to_polars(left) - to_polars(right)
    if typ == "COALESCE":
        return pl.coalesce([to_polars(arg) for arg in args])
    if typ == "AND":
        expr = to_polars(args[0])
        for arg in args[1:]:
            expr = expr & to_polars(arg)
        return expr
    if typ == "OR":
        expr = to_polars(args[0])
        for arg in args[1:]:
            expr = expr | to_polars(arg)
        return expr
    if typ == "NOT":
        (arg,) = args
        return ~to_polars(arg)
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
    if typ == "STRING_INTERPOLATE":
        pattern = args["pattern"]
        if isinstance(pattern, Literal):
            pattern = pattern.value
        inputs = args.get("inputs", {})
        if isinstance(inputs, Mapping):
            order = []
            fmt_parts = []
            for literal, field, _, _ in string.Formatter().parse(pattern):
                fmt_parts.append(literal)
                if field is not None:
                    fmt_parts.append("{}")
                    order.append(field)
            pattern = "".join(fmt_parts)
            exprs = [to_polars(inputs[field]) for field in order]
        else:
            exprs = []
        return pl.format(pattern, *exprs)
    if typ == "VALUE_IN_LITERAL_SET":
        value = to_polars(args["value"])
        set_arg = args["set"]
        if isinstance(set_arg, Expression) and set_arg.type == "COALESCE":
            items = set_arg.arguments
        else:
            items = set_arg
        set_vals = [v.value if isinstance(v, Literal) else None for v in items]
        return value.is_in(set_vals)
    if typ == "VALUE_IN_RANGE":
        value = to_polars(args["value"])
        expr = pl.lit(True)
        if "min" in args:
            min_expr = to_polars(args["min"])
            incl = args.get("min_inclusive", Literal(True)).value
            expr = expr & (value >= min_expr if incl else value > min_expr)
        if "max" in args:
            max_expr = to_polars(args["max"])
            incl = args.get("max_inclusive", Literal(True)).value
            expr = expr & (value <= max_expr if incl else value < max_expr)
        return expr
    if typ == "REGEX":
        pattern_node = args["regex"]
        if isinstance(pattern_node, Literal):
            pattern = pattern_node.value
        else:
            pattern = pattern_node
        inp = to_polars(args["input"])
        action = args.get("action")
        if isinstance(action, Literal):
            action = action.value
        if action == "EXTRACT":
            group = args.get("group", Literal(1))
            if isinstance(group, Literal):
                group_idx = group.value
            else:
                group_idx = group
            return inp.str.extract(pattern, group_idx)
        if action == "MATCH":
            return inp.str.contains(pattern)
        if action == "NOT_MATCH":
            return ~inp.str.contains(pattern)
        raise ValueError("Invalid REGEX action")

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
