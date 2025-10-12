"""Nodes relating to dates and times."""

from .base import BinaryOp
import polars as pl


class SetTime(BinaryOp):
    """This non-terminal node sets the time part of a date or datetime.

    Example:
        >>> from dftly.nodes import Literal
        >>> from datetime import date, time
        >>> node = SetTime(Literal(date(2023, 1, 1)), Literal(time(12, 10)))
        >>> node
        SetTime(Literal(datetime.date(2023, 1, 1)), Literal(datetime.time(12, 10)))
        >>> pl.select(node.polars_expr).item()
        datetime.datetime(2023, 1, 1, 12, 10)
    """

    KEY = "set_time"
    SYM = "@"

    @property
    def polars_expr(self) -> pl.Expr:
        date_expr = self.args[0].polars_expr
        time_expr = self.args[1].polars_expr
        return date_expr.dt.combine(time_expr)
