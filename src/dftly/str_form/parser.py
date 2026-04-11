from __future__ import annotations

from typing import Any, Callable
from functools import partial
from dateutil import parser as dt_parser


from importlib.resources import files
from lark import Lark, Token, Transformer
from lark.visitors import Discard

from ..nodes import (
    BINARY_OPS,
    UNARY_OPS,
    NODES,
    Cast,
    Literal,
)


GRAMMAR_TEXT = files(__package__).joinpath("grammar.lark").read_text()
GRAMMAR = Lark(GRAMMAR_TEXT, parser="lalr")


class DftlyGrammar(Transformer):
    """Transform parsed tokens into object form via a lark grammar.

    This class allows for parsing string forms into object nodes. It should primarily be used not through a
    constructed instance, but through the `parse_str` class method, as shown below.

    Examples:
        >>> DftlyGrammar.parse_str("1 + 2 * 3")
        {'add': [{'literal': 1}, {'multiply': [{'literal': 2}, {'literal': 3}]}]}
        >>> DftlyGrammar.parse_str("2023 - 01 - 01")
        {'subtract': [{'subtract': [{'literal': 2023}, {'literal': 1}]}, {'literal': 1}]}
        >>> DftlyGrammar.parse_str("1 / (2 + 3) > 0.1")
        {'greater_than': [{'divide': [{'literal': 1},
                                      {'add': [{'literal': 2}, {'literal': 3}]}]}, {'literal': 0.1}]}
        >>> DftlyGrammar.parse_str("5 == 2 + 3 and 4 < 10")
        {'and': [{'equal': [{'literal': 5}, {'add': [{'literal': 2}, {'literal': 3}]}]},
                 {'less_than': [{'literal': 4}, {'literal': 10}]}]}
        >>> DftlyGrammar.parse_str("equal(add(1, multiply(2, 3)), 7)")
        {'equal': [{'add': [{'literal': 1}, {'multiply': [{'literal': 2}, {'literal': 3}]}]}, {'literal': 7}]}

    AND binds tighter than OR (standard precedence), so ``a or b and c`` parses as ``a or (b and c)``:

        >>> DftlyGrammar.parse_str("true or false and false")
        {'or': [{'literal': True}, {'and': [{'literal': False}, {'literal': False}]}]}

    Various literal types are supported:

        >>> DftlyGrammar.parse_str("1")
        {'literal': 1}
        >>> DftlyGrammar.parse_str("3.14")
        {'literal': 3.14}
        >>> DftlyGrammar.parse_str("true")
        {'literal': True}
        >>> DftlyGrammar.parse_str("'hello'")
        {'literal': 'hello'}
        >>> DftlyGrammar.parse_str("11:32 a.m.")
        {'literal': datetime.time(11, 32)}
        >>> DftlyGrammar.parse_str("2023-01-01")
        {'literal': datetime.date(2023, 1, 1)}
        >>> DftlyGrammar.parse_str("2023-01-01 12:34:56")
        {'literal': datetime.datetime(2023, 1, 1, 12, 34, 56)}

    You can also express columns using the `"$column_name"` syntax:

        >>> DftlyGrammar.parse_str("$a + $b * 3")
        {'add': [{'column': 'a'}, {'multiply': [{'column': 'b'}, {'literal': 3}]}]}

    Strings will be parsed into string nodes:

        >>> DftlyGrammar.parse_str("'hello' + ' ' + 'world'")
        {'add': [{'add': [{'literal': 'hello'}, {'literal': ' '}]}, {'literal': 'world'}]}

    String interpolation is supported via f-strings:

        >>> DftlyGrammar.parse_str("f'hello {$name}'")
        {'string_interpolate': [{'literal': 'hello {}'}, '$name']}

    Conditional expressions can be expressed using the `... if ... else ...` syntax; `else ...` is optional:

        >>> DftlyGrammar.parse_str("'big' if $a > 5")
        {'conditional': {'when': {'greater_than': [{'column': 'a'}, {'literal': 5}]},
                         'then': {'literal': 'big'}}}
        >>> DftlyGrammar.parse_str("'big' if $a > 5 else 'small'")
        {'conditional': {'when': {'greater_than': [{'column': 'a'}, {'literal': 5}]},
                         'then': {'literal': 'big'},
                         'otherwise': {'literal': 'small'}}}

    Regex operations are supported via the following syntax:

        >>> DftlyGrammar.parse_str(r"extract /\\d+/ from $text")
        {'regex_extract': {'pattern': {'literal': '\\\\d+'}, 'source': {'column': 'text'}}}
        >>> DftlyGrammar.parse_str(r"/\\d+/ in $text")
        {'regex_match': {'pattern': {'literal': '\\\\d+'}, 'source': {'column': 'text'}}}

    Casting is supported via the `::` or `... as ...` syntax. Note the two have different precedence, with
    `::` having higher precedence than arithmetic operations, and `as` having lower precedence.

        >>> DftlyGrammar.parse_str("4 + '3'::int")
        {'add': [{'literal': 4}, {'cast': [{'literal': '3'}, {'literal': 'int'}]}]}
        >>> DftlyGrammar.parse_str("'2023-' + '01-' + '01' as date")
        {'cast': [{'add': [{'add': [{'literal': '2023-'},
                                    {'literal': '01-'}]},
                           {'literal': '01'}]},
                  {'literal': 'date'}]}

    Unary operations are supported:

        >>> DftlyGrammar.parse_str("not true")
        {'not': [{'literal': True}]}
        >>> DftlyGrammar.parse_str("-5")
        {'negate': [{'literal': 5}]}

    Bare words (identifiers without a ``$`` prefix, quotes, or parentheses) are parsed as bare_word
    nodes, distinct from regular literals. This enables YAML-friendly configs where string values
    like ``MEDS_BIRTH`` don't need awkward double-quoting (``'"MEDS_BIRTH"'``). The ``bare_word``
    dict key is converted to a ``literal`` by the :class:`Parser`, which also warns if a bare word
    appears inside a larger expression (where it likely indicates a missing ``$`` prefix):

        >>> DftlyGrammar.parse_str("MEDS_BIRTH")
        {'bare_word': 'MEDS_BIRTH'}
        >>> DftlyGrammar.parse_str("hello_world")
        {'bare_word': 'hello_world'}
        >>> DftlyGrammar.parse_str("$col + TYPO")
        {'add': [{'column': 'col'}, {'bare_word': 'TYPO'}]}

    Function calls with multiple arguments work:

        >>> DftlyGrammar.parse_str("min($a, $b, $c)")
        {'min': [{'column': 'a'}, {'column': 'b'}, {'column': 'c'}]}
        >>> DftlyGrammar.parse_str("max(1, 2)")
        {'max': [{'literal': 1}, {'literal': 2}]}

    The `::` or `... as ...` syntax can also be used to indicate string parsing, which currently only supports
    datetime parsing via strptime:

        >>> DftlyGrammar.parse_str("'2023-01-01 12:34:56' as '%Y-%m-%d %H:%M:%S'")
        {'strptime': {'format': {'literal': '%Y-%m-%d %H:%M:%S'},
                      'source': {'literal': '2023-01-01 12:34:56'}}}
        >>> DftlyGrammar.parse_str("'2023 01 01'::'%Y %m %d'")
        {'strptime': {'format': {'literal': '%Y %m %d'},
                      'source': {'literal': '2023 01 01'}}}

    Non-strict strptime uses the ``?`` prefix on the format string:

        >>> DftlyGrammar.parse_str('$dod::?"%Y-%m-%d %H:%M:%S"')
        {'strptime': {'format': {'literal': '%Y-%m-%d %H:%M:%S'},
                      'source': {'column': 'dod'},
                      'strict': {'literal': False}}}
        >>> DftlyGrammar.parse_str('$dod as ?"%Y-%m-%d %H:%M:%S"')
        {'strptime': {'format': {'literal': '%Y-%m-%d %H:%M:%S'},
                      'source': {'column': 'dod'},
                      'strict': {'literal': False}}}
    """

    @classmethod
    def parse_str(cls, s: str) -> Any:
        """Parse a string into an expression tree.

        Raises:
            ValueError: If the string cannot be parsed.

        Examples:
            >>> DftlyGrammar.parse_str("???")
            Traceback (most recent call last):
                ...
            ValueError: Failed to parse expression '???': ...
        """
        try:
            tree = GRAMMAR.parse(s)
        except Exception as e:
            raise ValueError(f"Failed to parse expression {s!r}: {e}") from e

        return cls().transform(tree)

    LITERAL_PARSERS = {
        "INT": int,
        "NUMBER": lambda x: float(x) if "." in x or "e" in x.lower() else int(x),
        "BOOL": lambda x: x.lower() == "true",
        "TIME": lambda x: dt_parser.parse(x).time(),
        "DATE": lambda x: dt_parser.parse(x).date(),
        "DATETIME": dt_parser.parse,
        "STRING": lambda x: x[1:-1],  # Remove surrounding quotes
        "REGEX_LITERAL": lambda x: x[1:-1],  # Remove surrounding
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for node in NODES.values():
            if not hasattr(self, node.KEY):
                self.__setattr__(node.KEY, partial(self._send_items, node_cls=node))

        for lit, fn in self.LITERAL_PARSERS.items():
            self.__setattr__(lit, partial(self._parse_literal, fn=fn))

    def _parse_literal(self, token: Token, fn: Callable[[str], Any]) -> dict[str, Any]:
        try:
            return Literal.from_lark(fn(token))
        except Exception as e:
            raise ValueError(f"Failed to parse literal {token}") from e

    def _send_items(self, val: list[Any] | Token, node_cls) -> dict[str, Any]:
        if node_cls.is_terminal and isinstance(val, list):
            if len(val) != 1:
                raise ValueError(
                    f"terminal node {node_cls} received multiple values: {val}"
                )
            val = val[0]
        return node_cls.from_lark(val)

    def _discard_token(self, _: Token) -> Discard:
        return Discard

    IF = ELSE = EXTRACT = GROUP = OF = FROM = IN = CAST = AS = _discard_token
    FORMAT_PFX = DOLLAR = QUESTION = _discard_token

    def NAME(self, val: Token) -> str:
        return str(val)

    def args(self, items: list[Any]) -> list[Any]:
        return items

    def binary_expr(self, items: list[dict | str]) -> dict:
        left, op, right = items

        if op not in BINARY_OPS:
            raise ValueError(
                f"Unsupported binary operator: {op}; allowed: {list(BINARY_OPS)}"
            )

        return BINARY_OPS[op].from_lark([left, right])

    def unary_expr(self, items: list[dict | str]) -> dict:
        op, operand = items

        if op not in UNARY_OPS:
            raise ValueError(
                f"Unsupported unary operator: {op}; allowed: {list(UNARY_OPS)}"
            )

        return UNARY_OPS[op].from_lark([operand])

    def func(self, items: list[Any]) -> dict:
        func_name = items[0]
        args = items[1]

        if func_name not in NODES:
            raise ValueError(
                f"Unsupported function: {func_name}; allowed: {list(NODES)}"
            )

        return NODES[func_name].from_lark(args)

    def bare_word(self, items: list[Any]) -> dict:
        return {"bare_word": items[0]}

    def strptime_nonstrict(self, items: list[Any]) -> dict:
        source, format_str = items
        return {
            "strptime": {
                "format": format_str,
                "source": source,
                "strict": {"literal": False},
            }
        }

    def cast_expr(self, items: list[Any]) -> dict:
        input, output_type = items
        return Cast.from_lark([input, Literal.from_lark(output_type)])
