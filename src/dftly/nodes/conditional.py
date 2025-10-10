from .base import KwargsOnlyFn
import polars as pl
from typing import Any


class Conditional(KwargsOnlyFn):
    """Executes if-then-else statements, with args "when", "then", and optional "otherwise".

    This node only accepts keyword arguments, and requires "when" and "then" keys, with an optional
    "otherwise" key. These are used instead of `if`, `then`, and `else` to avoid conflicts with Python
    keywords.

    Example:
        >>> from dftly.nodes import Literal
        >>> node = Conditional(when=Literal(True), then=Literal(1), otherwise=Literal(0))
        >>> pl.select(node.polars_expr).item()
        1
        >>> node = Conditional(when=Literal(False), then=Literal(1), otherwise=Literal(0))
        >>> pl.select(node.polars_expr).item()
        0
        >>> node = Conditional(when=Literal(True), then=Literal(2))
        >>> pl.select(node.polars_expr).item()
        2
        >>> node = Conditional(when=Literal(False), then=Literal(2))
        >>> print(pl.select(node.polars_expr).item())
        None
    """

    KEY = "conditional"
    REQUIRED_KWARGS = {"when", "then"}
    OPTIONAL_KWARGS = {"otherwise"}

    @property
    def polars_expr(self) -> pl.Expr:
        when_expr = self.kwargs["when"].polars_expr
        then_expr = self.kwargs["then"].polars_expr
        if "otherwise" in self.kwargs:
            otherwise_expr = self.kwargs["otherwise"].polars_expr
            return pl.when(when_expr).then(then_expr).otherwise(otherwise_expr)
        else:
            return pl.when(when_expr).then(then_expr)

    @classmethod
    def from_lark(cls, items: list[Any]) -> dict[str, Any]:
        kwargs = {"when": items[1], "then": items[0]}
        if len(items) == 3:
            kwargs["otherwise"] = items[2]

        return {cls.KEY: kwargs}
