"""Nodes for frame-level (row-multiplying) operations.

These live in their own module because they break the invariant every other node in dftly
holds to: that a node compiles to a length-preserving ``pl.Expr``. See :class:`Explode`.
"""

from typing import Any

import polars as pl

from .base import ArgsOnlyFn, NodeBase


class Explode(ArgsOnlyFn):
    """Marks a list-valued expression for expansion into one row per element.

    **This node has no expression form.** Every other dftly node compiles to a ``pl.Expr`` that
    ``df.select`` can evaluate, which requires it to preserve the frame's height. Explode does
    not -- it multiplies rows -- so it cannot be handled by ``select`` at all as soon as any
    other output column exists:

        >>> import polars as pl
        >>> df = pl.DataFrame({"id": [1, 2], "csv": ["a,b,c", "d"]})
        >>> df.select(pl.col("csv").str.split(",").explode(), pl.col("id"))
        Traceback (most recent call last):
            ...
        polars.exceptions.ShapeError: ...

    Rather than let that surface as a polars shape error far from its cause, ``polars_expr``
    refuses outright and points at the frame-level entry point:

        >>> from dftly.nodes import Column
        >>> Explode(Column("parts")).polars_expr
        Traceback (most recent call last):
            ...
        ValueError: `explode` is a row-multiplying operation with no expression form. ...

    Use :meth:`dftly.Parser.to_frame`, which hoists the marker out of the expression and applies
    it as ``DataFrame.explode`` after the select -- the only form that repeats the non-exploded
    columns correctly:

        >>> from dftly import Parser
        >>> ops = {"id": "$id", "part": 'explode(split($csv, ","))'}
        >>> Parser.to_frame(df, ops)
        shape: (4, 2)
        ┌─────┬──────┐
        │ id  ┆ part │
        │ --- ┆ ---  │
        │ i64 ┆ str  │
        ╞═════╪══════╡
        │ 1   ┆ a    │
        │ 1   ┆ b    │
        │ 1   ┆ c    │
        │ 2   ┆ d    │
        └─────┴──────┘

    Exactly one argument is required:

        >>> Explode(Column("a"), Column("b"))
        Traceback (most recent call last):
            ...
        ValueError: explode requires exactly one argument; got 2
    """

    KEY = "explode"

    def __post_init__(self):
        super().__post_init__()
        if len(self.args) != 1:
            raise ValueError(
                f"{self.KEY} requires exactly one argument; got {len(self.args)}"
            )

    @property
    def source(self) -> NodeBase:
        """The list-valued expression to be expanded."""
        return self.args[0]

    @property
    def polars_expr(self) -> pl.Expr:
        raise ValueError(
            "`explode` is a row-multiplying operation with no expression form. It must appear as "
            "the outermost node of a top-level output and be compiled with `Parser.to_frame(df, "
            "ops)`, which applies it as a frame operation after the select."
        )

    @classmethod
    def from_lark(cls, items: list[Any]) -> dict[str, Any]:
        if not isinstance(items, list):
            items = [items]
        return {cls.KEY: items}
