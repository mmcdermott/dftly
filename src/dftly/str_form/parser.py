from __future__ import annotations

from typing import Any

from importlib.resources import files
from lark import Lark, Transformer

from ..nodes import BINARY_OPS


GRAMMAR_TEXT = files(__package__).joinpath("grammar.lark").read_text()
GRAMMAR = Lark(GRAMMAR_TEXT, parser="lalr")


class DftlyGrammar(Transformer):
    """Transform parsed tokens into object form via a lark grammar.

    This class allows for parsing string forms into object nodes.

    Examples:
        >>> node = DftlyGrammar.parse_str("1 + 2 * 3")
        >>> node
        {'add': [1, {'multiply': [2, 3]}]}
    """

    @classmethod
    def parse_str(cls, s: str) -> Any:
        """Parse a string into an expression tree."""
        tree = GRAMMAR.parse(s)

        return cls().transform(tree)

    def NUMBER(self, token: str) -> dict:
        if "." in token or "e" in token or "E" in token:
            return float(token)
        else:
            return int(token)

    def binary_expr(self, items: list[dict | str]) -> dict:
        left, op, right = items

        if op not in BINARY_OPS:
            raise ValueError(
                f"Unsupported binary operator: {op}; allowed: {list(BINARY_OPS)}"
            )

        return BINARY_OPS[op].from_lark([left, right])
