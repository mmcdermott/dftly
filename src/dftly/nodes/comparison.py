"""This module defines comparison non-terminal nodes.

As non-terminals, all args and kwargs to these nodes must be other nodes.
"""

from .base import BinaryOp
from .base import Literal  # noqa: F401
import polars as pl


class GreaterThan(BinaryOp):
    """This non-terminal node represents the 'greater than' comparison of two expressions.

    Example:
        >>> pl.select(GreaterThan(Literal(5), Literal(3)).polars_expr).item()
        True
        >>> pl.select(GreaterThan(Literal(2), Literal(3)).polars_expr).item()
        False
    """

    KEY = "greater_than"
    pl_fn = pl.Expr.gt


class LessThan(BinaryOp):
    """This non-terminal node represents the 'less than' comparison of two expressions.

    Example:
        >>> pl.select(LessThan(Literal(2), Literal(3)).polars_expr).item()
        True
        >>> pl.select(LessThan(Literal(5), Literal(3)).polars_expr).item()
        False
    """

    KEY = "less_than"
    pl_fn = pl.Expr.lt


class Equal(BinaryOp):
    """This non-terminal node represents the 'equal to' comparison of two expressions.

    Example:
        >>> pl.select(Equal(Literal(3), Literal(3)).polars_expr).item()
        True
        >>> pl.select(Equal(Literal(2), Literal(3)).polars_expr).item()
        False
    """

    KEY = "equal"
    pl_fn = pl.Expr.eq


class NotEqual(BinaryOp):
    """This non-terminal node represents the 'not equal to' comparison of two expressions.

    Example:
        >>> pl.select(NotEqual(Literal(2), Literal(3)).polars_expr).item()
        True
        >>> pl.select(NotEqual(Literal(3), Literal(3)).polars_expr).item()
        False
    """

    KEY = "not_equal"
    pl_fn = pl.Expr.ne


class GreaterThanOrEqual(BinaryOp):
    """This non-terminal node represents the 'greater than or equal to' comparison of two expressions.

    Example:
        >>> pl.select(GreaterThanOrEqual(Literal(5), Literal(3)).polars_expr).item()
        True
        >>> pl.select(GreaterThanOrEqual(Literal(3), Literal(3)).polars_expr).item()
        True
        >>> pl.select(GreaterThanOrEqual(Literal(2), Literal(3)).polars_expr).item()
        False
    """

    KEY = "greater_than_or_equal"
    pl_fn = pl.Expr.ge


class LessThanOrEqual(BinaryOp):
    """This non-terminal node represents the 'less than or equal to' comparison of two expressions.

    Example:
        >>> pl.select(LessThanOrEqual(Literal(2), Literal(3)).polars_expr).item()
        True
        >>> pl.select(LessThanOrEqual(Literal(3), Literal(3)).polars_expr).item()
        True
        >>> pl.select(LessThanOrEqual(Literal(5), Literal(3)).polars_expr).item()
        False
    """

    KEY = "less_than_or_equal"
    pl_fn = pl.Expr.le
