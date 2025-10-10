from __future__ import annotations

from typing import Any

from importlib.resources import files
from lark import Lark, Transformer
from lark.visitors import Discard

from ..nodes import (
    BINARY_OPS,
    NODES,
    Cast,
    Column,
    StringInterpolate,
    Conditional,
    Literal,
    RegexExtract,
    RegexMatch,
)


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

    Regex operations are supported via the following syntax:

        >>> DftlyGrammar.parse_str("extract /\\d+/ from @text")
        {'regex_extract': {'pattern': {'literal': '\\\\d+'}, 'source': {'column': 'text'}}}
        >>> DftlyGrammar.parse_str("/\\d+/ in @text")
        {'regex_match': {'pattern': {'literal': '\\\\d+'}, 'source': {'column': 'text'}}}

    Casting is supported via the `::` or `... as ...` syntax. Note the two have different precedence, with
    `::` having higher precedence than arithmetic operations, and `as` having lower precedence.

        >>> DftlyGrammar.parse_str("4 + '3'::int")
        {'add': [4, {'cast': [{'literal': '3'}, {'literal': 'int'}]}]}
        >>> DftlyGrammar.parse_str("'2023-' + '01-' + '01' as date")
        {'cast': [{'add': [{'add': [{'literal': '2023-'},
                                    {'literal': '01-'}]},
                           {'literal': '01'}]},
                  {'literal': 'date'}]}
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

    def INT(self, token: str) -> int:
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

    def IF(self, token: str):
        return Discard

    def ELSE(self, token: str):
        return Discard

    def conditional_expr(self, items: list[Any]) -> dict:
        return Conditional.from_lark(items)

    def EXTRACT(self, token: str):
        return Discard

    def GROUP(self, token: str):
        return Discard

    def OF(self, token: str):
        return Discard

    def FROM(self, token: str):
        return Discard

    def IN(self, token: str):
        return Discard

    def REGEX_LITERAL(self, token: str) -> str:
        return Literal.from_lark(str(token[1:-1]))

    def CAST(self, token: str):
        return Discard

    def AS(self, token: str):
        return Discard

    def regex_extract(self, items: list[Any]) -> dict:
        return RegexExtract.from_lark(items)

    def regex_match(self, items: list[Any]) -> dict:
        return RegexMatch.from_lark(items)

    def cast_expr(self, items: list[Any]) -> dict:
        input, output_type = items
        return Cast.from_lark([input, Literal.from_lark(output_type)])
