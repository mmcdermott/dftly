"""This module defines arithmetic non-terminal nodes.

As non-terminals, all args and kwargs to these nodes must be other nodes.
"""

from .base import ArgsOnlyFn, BinaryOp, UnaryOp
import polars as pl


class Not(UnaryOp):
    """This non-terminal node represents the logical NOT of an expression.

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(Not(Literal(True)).polars_expr).item()
        False
    """

    KEY = "not"
    SYM = ("!", "not")
    pl_fn = pl.Expr.not_


class Negate(UnaryOp):
    """This non-terminal node represents the negation of an expression.

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(Negate(Literal(5)).polars_expr).item()
        -5
    """

    KEY = "negate"
    SYM = "-"

    @classmethod
    def pl_fn(cls, arg: pl.Expr) -> pl.Expr:
        return -arg


class And(ArgsOnlyFn):
    """This non-terminal node represents the logical AND of multiple expressions.

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(And(Literal(True), Literal(False), Literal(True)).polars_expr).item()
        False
    """

    KEY = "and"
    SYM = ("&&", "and")
    pl_fn = pl.all_horizontal


class Or(ArgsOnlyFn):
    """This non-terminal node represents the logical OR of multiple expressions.

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(Or(Literal(True), Literal(False), Literal(True)).polars_expr).item()
        True
    """

    KEY = "or"
    SYM = ("||", "or")
    pl_fn = pl.any_horizontal


class Add(ArgsOnlyFn):
    """This non-terminal node represents the addition of multiple expressions.

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(Add(Literal(1), Literal(2), Literal(3)).polars_expr).item()
        6
    """

    KEY = "add"
    SYM = "+"
    pl_fn = pl.sum_horizontal


class Subtract(BinaryOp):
    """This non-terminal node represents the difference between the two inputs x, y -> x - y.

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(Subtract(Literal(5), Literal(3)).polars_expr).item()
        2
    """

    KEY = "subtract"
    SYM = "-"
    pl_fn = pl.Expr.sub


class Multiply(ArgsOnlyFn):
    """This non-terminal node represents the multiplication of multiple expressions.

    Example:
        >>> from dftly.nodes import Literal
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
        >>> from dftly.nodes import Literal
        >>> pl.select(Divide(Literal(6), Literal(3)).polars_expr).item()
        2.0
    """

    KEY = "divide"
    SYM = "/"
    pl_fn = pl.Expr.truediv


class Mean(ArgsOnlyFn):
    """This non-terminal node represents the mean of multiple expressions.

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(Mean(Literal(1), Literal(2), Literal(3)).polars_expr).item()
        2.0
    """

    KEY = "mean"
    pl_fn = pl.mean_horizontal


class Min(ArgsOnlyFn):
    """This non-terminal node represents the min of multiple expressions.

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(Min(Literal(1), Literal(2), Literal(3)).polars_expr).item()
        1
    """

    KEY = "min"
    pl_fn = pl.min_horizontal


class Max(ArgsOnlyFn):
    """This non-terminal node represents the max of multiple expressions.

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(Max(Literal(1), Literal(2), Literal(3)).polars_expr).item()
        3
    """

    KEY = "max"
    pl_fn = pl.max_horizontal
