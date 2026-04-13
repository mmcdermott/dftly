"""This module defines arithmetic non-terminal nodes.

As non-terminals, all args and kwargs to these nodes must be other nodes.
"""

from .base import ArgsOnlyFn, BinaryOp, UnaryOp
import polars as pl


class Hash(ArgsOnlyFn):
    """This non-terminal node computes a hash of the input expression.

    The result is a UInt64 value (Polars' native hash type). For schemas requiring Int64 (e.g.
    MEDS ``subject_id``), use :class:`SignedHash` instead — a plain ``::int64`` cast silently
    nulls values above ``i64.max``.

    Example:
        >>> from dftly.nodes import Literal
        >>> result = pl.select(Hash(Literal("hello")).polars_expr).item()
        >>> isinstance(result, int) and result >= 0
        True
        >>> pl.select(Hash(Literal("hello")).polars_expr).dtypes
        [UInt64]
        >>> pl.select(Hash(Literal("hello")).polars_expr).item() == pl.select(Hash(Literal("hello")).polars_expr).item()
        True
        >>> pl.select(Hash(Literal("hello")).polars_expr).item() != pl.select(Hash(Literal("world")).polars_expr).item()
        True

    Only one argument is accepted:

        >>> Hash(Literal("a"), Literal("b"))
        Traceback (most recent call last):
            ...
        ValueError: hash requires exactly one argument; got 2
    """

    KEY = "hash"

    def __post_init__(self):
        super().__post_init__()
        if len(self.args) != 1:
            raise ValueError(
                f"{self.KEY} requires exactly one argument; got {len(self.args)}"
            )

    @classmethod
    def from_lark(cls, items):
        """Wrap single-argument lark results in a list for consistent handling.

        Examples:
            >>> Hash.from_lark([{"literal": 42}])
            {'hash': [{'literal': 42}]}
            >>> Hash.from_lark({"literal": 42})
            {'hash': [{'literal': 42}]}
        """
        if not isinstance(items, list):
            items = [items]
        return {cls.KEY: items}

    @property
    def polars_expr(self) -> pl.Expr:
        return self.args[0].polars_expr.hash()


class SignedHash(Hash):
    """This non-terminal node computes a signed (Int64) hash of the input expression.

    The result is an Int64 value produced by reinterpreting Polars' native UInt64 hash as a
    two's-complement signed integer. This preserves the full bit pattern — unlike a
    ``::int64`` cast, which silently nulls values above ``i64.max`` — at the cost of changing
    the numeric value for roughly half of inputs. Downstream consumers that compute hashes
    outside dftly will only get bit-compatible values if they also reinterpret.

    Use this when landing into an Int64-typed column (e.g. MEDS ``subject_id``).

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(SignedHash(Literal("hello")).polars_expr).dtypes
        [Int64]
        >>> unsigned = pl.select(Hash(Literal("hello")).polars_expr).item()
        >>> signed = pl.select(SignedHash(Literal("hello")).polars_expr).item()
        >>> signed == (unsigned - (1 << 64) if unsigned >= (1 << 63) else unsigned)
        True

    It also parses from string form via the function-call grammar:

        >>> from dftly import Parser
        >>> df = pl.DataFrame({"mrn": ["abc", "def"]})
        >>> df.select(**Parser.to_polars({"subject_id": "signed_hash($mrn)"})).dtypes
        [Int64]

    Only one argument is accepted:

        >>> SignedHash(Literal("a"), Literal("b"))
        Traceback (most recent call last):
            ...
        ValueError: signed_hash requires exactly one argument; got 2
    """

    KEY = "signed_hash"

    @property
    def polars_expr(self) -> pl.Expr:
        return self.args[0].polars_expr.hash().reinterpret(signed=True)


class Not(UnaryOp):
    """This non-terminal node represents the logical NOT of an expression.

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(Not(Literal(True)).polars_expr).item()
        False
        >>> pl.select(Not(Literal(False)).polars_expr).item()
        True
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
        >>> pl.select(Negate(Literal(-3)).polars_expr).item()
        3
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
        >>> pl.select(Add(Literal("hello "), Literal("world")).polars_expr).item()
        'hello world'
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


class Coalesce(ArgsOnlyFn):
    """This non-terminal node returns the first non-null value among its arguments.

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(Coalesce(Literal(None), Literal(1), Literal(2)).polars_expr).item()
        1
        >>> pl.select(Coalesce(Literal(3), Literal(None)).polars_expr).item()
        3
    """

    KEY = "coalesce"
    pl_fn = pl.coalesce
