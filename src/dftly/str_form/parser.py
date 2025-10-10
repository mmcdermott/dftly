from __future__ import annotations

from typing import Any

from importlib.resources import files
from lark import Lark, Transformer
from lark.visitors import Discard

from ..nodes import BINARY_OPS, NODES, Column, StringInterpolate, Conditional, Literal


GRAMMAR_TEXT = files(__package__).joinpath("grammar.lark").read_text()
GRAMMAR = Lark(GRAMMAR_TEXT, parser="lalr")


class DftlyGrammar(Transformer):
    """Transform parsed tokens into object form via a lark grammar.

    This class allows for parsing string forms into object nodes. It should primarily be used not through a
    constructed instance, but through the `parse_str` class method, as shown below.

    Examples:
        >>> DftlyGrammar.parse_str("1 + 2 * 3")
        {'add': [1, {'multiply': [2, 3]}]}
        >>> DftlyGrammar.parse_str("1 / (2 + 3) > 0.1")
        {'greater_than': [{'divide': [1, {'add': [2, 3]}]}, 0.1]}
        >>> DftlyGrammar.parse_str("5 == 2 + 3")
        {'equal': [5, {'add': [2, 3]}]}
        >>> DftlyGrammar.parse_str("equal(add(1, multiply(2, 3)), 7)")
        {'equal': [{'add': [1, {'multiply': [2, 3]}]}, 7]}

    You can also express columns using the `"@column_name"` syntax:

        >>> DftlyGrammar.parse_str("@a + @b * 3")
        {'add': [{'column': 'a'}, {'multiply': [{'column': 'b'}, 3]}]}

    Strings will be parsed into string nodes:

        >>> DftlyGrammar.parse_str("'hello' + ' ' + 'world'")
        {'add': [{'add': [{'literal': 'hello'}, {'literal': ' '}]}, {'literal': 'world'}]}

    String interpolation is supported via f-strings:

        >>> DftlyGrammar.parse_str("f'hello {@name}'")
        {'string_interpolate': [{'literal': 'hello {}'}, '@name']}

    Conditional expressions can be expressed using the `... if ... else ...` syntax; `else ...` is optional:

        >>> DftlyGrammar.parse_str("'big' if @a > 5")
        {'conditional': {'when': {'greater_than': [{'column': 'a'}, 5]}, 'then': {'literal': 'big'}}}
        >>> DftlyGrammar.parse_str("'big' if @a > 5 else 'small'")
        {'conditional': {'when': {'greater_than': [{'column': 'a'}, 5]},
                         'then': {'literal': 'big'},
                         'otherwise': {'literal': 'small'}}}
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

    def STRING(self, token: str) -> str:
        """Remove the surrounding quotes from a string token."""
        return Literal.from_lark(str(token[1:-1]))

    def NAME(self, token: str) -> str:
        """Return the name token as a string."""
        return str(token)

    def column(self, items: list[str]) -> dict:
        """Resolve the "@column_name" syntax into a column node."""
        at_sign, column_name = items
        return Column.from_lark(column_name)

    def binary_expr(self, items: list[dict | str]) -> dict:
        left, op, right = items

        if op not in BINARY_OPS:
            raise ValueError(
                f"Unsupported binary operator: {op}; allowed: {list(BINARY_OPS)}"
            )

        return BINARY_OPS[op].from_lark([left, right])

    def args(self, items: list[Any]) -> list[Any]:
        return items

    def func(self, items: list[Any]) -> dict:
        func_name = items[0]
        args = items[1]

        if func_name not in NODES:
            raise ValueError(
                f"Unsupported function: {func_name}; allowed: {list(NODES)}"
            )

        return NODES[func_name].from_lark(args)

    def format_string(self, items: list[Any]) -> dict:
        f, pattern = items

        return StringInterpolate.from_lark(pattern)

    def IF(self, token: str) -> str:
        return Discard

    def ELSE(self, token: str) -> str:
        return Discard

    def conditional_expr(self, items: list[Any]) -> dict:
        return Conditional.from_lark(items)
