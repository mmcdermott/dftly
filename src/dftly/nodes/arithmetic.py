"""This module defines arithmetic non-terminal nodes.

As non-terminals, all args and kwargs to these nodes must be other nodes.
"""

from .base import ArgsOnlyFn, BinaryOp
from .base import Literal  # noqa: F401
import polars as pl


class Add(ArgsOnlyFn):
    """This non-terminal node represents the addition of multiple expressions.

    Example:
        >>> pl.select(Add(Literal(1), Literal(2), Literal(3)).polars_expr).item()
        6
    """

    KEY = "add"
    SYM = "+"
    pl_fn = pl.sum_horizontal


class Subtract(BinaryOp):
    """This non-terminal node represents the difference between the two inputs x, y -> x - y.

    Example:
        >>> pl.select(Subtract(Literal(5), Literal(3)).polars_expr).item()
        2
    """

    KEY = "subtract"
    SYM = "-"
    pl_fn = pl.Expr.sub


class Multiply(ArgsOnlyFn):
    """This non-terminal node represents the multiplication of multiple expressions.

    Example:
        >>> pl.select(Multiply(Literal(2), Literal(3), Literal(4)).polars_expr).item()
        24
    """

    KEY = "multiply"
    SYM = "*"

    @classmethod
    def pl_fn(cls, *args: pl.Expr) -> pl.Expr:
        result = args[0]
        for expr in args[1:]:
            result = result * expr
        return result


class Divide(BinaryOp):
    """This non-terminal node represents the division of two expressions.

    Example:
        >>> pl.select(Divide(Literal(6), Literal(3)).polars_expr).item()
        2.0
    """

    KEY = "divide"
    SYM = "/"
    pl_fn = pl.Expr.truediv


class Mean(ArgsOnlyFn):
    """This non-terminal node represents the mean of multiple expressions.

    Example:
        >>> pl.select(Mean(Literal(1), Literal(2), Literal(3)).polars_expr).item()
        2.0
    """

    KEY = "mean"
    pl_fn = pl.mean_horizontal


class Min(ArgsOnlyFn):
    """This non-terminal node represents the min of multiple expressions.

    Example:
        >>> pl.select(Min(Literal(1), Literal(2), Literal(3)).polars_expr).item()
        1
    """

    KEY = "min"
    pl_fn = pl.min_horizontal


class Max(ArgsOnlyFn):
    """This non-terminal node represents the max of multiple expressions.

    Example:
        >>> pl.select(Max(Literal(1), Literal(2), Literal(3)).polars_expr).item()
        3
    """

    KEY = "max"
    pl_fn = pl.max_horizontal
