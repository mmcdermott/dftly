from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Tuple
import re
from datetime import datetime
from dateutil import parser as dtparser
import string

from importlib.resources import files
from lark import Lark, Transformer, Token
from .nodes import Column, Expression, Literal

# ---------------------------------------------------------------------------
# Constants and regex patterns for timestamp parsing

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

DATE_TIME_RE = re.compile(
    r"^(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2}),\s*(?P<time>.+)$",
    re.IGNORECASE,
)

# supported expression names for dictionary short-form
_EXPR_TYPES = {
    "ADD",
    "SUBTRACT",
    "COALESCE",
    "AND",
    "OR",
    "NOT",
    "TYPE_CAST",
    "CONDITIONAL",
    "RESOLVE_TIMESTAMP",
    "VALUE_IN_LITERAL_SET",
    "VALUE_IN_RANGE",
    "STRING_INTERPOLATE",
    "PARSE_WITH_FORMAT_STRING",
    "HASH_TO_INT",
}


class Parser:
    """Parse simplified YAML-like structures into dftly nodes."""

    def __init__(
        self, input_schema: Optional[Mapping[str, Optional[str]]] = None
    ) -> None:
        self.input_schema = dict(input_schema or {})
        grammar_text = files(__package__).joinpath("grammar.lark").read_text()
        self._lark = Lark(grammar_text, parser="lalr")
        self._transformer = DftlyTransformer(self)

    def parse(self, data: Mapping[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, Mapping):
            raise TypeError("top level data must be a mapping")
        return {key: self._parse_value(value) for key, value in data.items()}

    # ------------------------------------------------------------------
    def _parse_value(self, value: Any) -> Any:
        if isinstance(value, Mapping):
            return self._parse_mapping(value)
        if isinstance(value, list):
            # default behaviour: COALESCE
            return Expression("COALESCE", [self._parse_value(v) for v in value])
        if isinstance(value, (int, float, bool)):
            return Literal(value)
        if isinstance(value, str):
            return self._parse_string(value)
        raise TypeError(f"unsupported type: {type(value).__name__}")

    # ------------------------------------------------------------------
    def _parse_mapping(self, value: Mapping[str, Any]) -> Any:
        if "literal" in value:
            return Literal.from_mapping(value)

        if "column" in value:
            return Column.from_mapping(value, input_schema=self.input_schema)

        if "expression" in value:
            return Expression.from_mapping(value, parser=self)
        # dictionary short form for expressions
        if len(value) == 1:
            expr_type, args = next(iter(value.items()))
            expr_upper = expr_type.upper()
            if expr_upper in _EXPR_TYPES:
                if expr_upper == "STRING_INTERPOLATE" and isinstance(args, Mapping):
                    pattern = args.get("pattern")
                    inputs = args.get("inputs", {})
                    pattern_node = (
                        pattern if isinstance(pattern, Literal) else Literal(pattern)
                    )
                    parsed_inputs = {k: self._parse_value(v) for k, v in inputs.items()}
                    parsed_args = {"pattern": pattern_node, "inputs": parsed_inputs}
                else:
                    parsed_args = self._parse_arguments(args)
                return Expression(expr_upper, parsed_args)

        # generic mapping value
        return {k: self._parse_value(v) for k, v in value.items()}

    # ------------------------------------------------------------------
    def _parse_arguments(self, args: Any) -> Any:
        if isinstance(args, Mapping):
            return {k: self._parse_value(v) for k, v in args.items()}
        if isinstance(args, list):
            return [self._parse_value(a) for a in args]
        return self._parse_value(args)

    # ------------------------------------------------------------------

    def _parse_string(self, value: str) -> Any:
        # handle resolve timestamp syntax using '@'
        if "@" in value and value.count("@") == 1:
            resolved = self._parse_resolve_timestamp(value)
            if resolved is not None:
                return resolved

        interp = self._parse_string_interpolate(value)
        if interp is not None:
            return interp

        try:
            tree = self._lark.parse(value)
            result = self._transformer.transform(tree)
            return result
        except Exception:
            return self._as_node(value)

    # ------------------------------------------------------------------
    def _as_node(self, value: Any) -> Any:
        if isinstance(value, (Expression, Column, Literal)):
            return value
        if isinstance(value, str):
            if value in self.input_schema:
                return Column(value, self.input_schema.get(value))
            return Literal(value)
        raise TypeError(f"cannot convert {type(value).__name__} to node")

    # ------------------------------------------------------------------
    def _parse_time_string(self, text: str) -> Optional[Dict[str, Any]]:
        text = text.strip()
        if any(month in text.lower() for month in MONTHS):
            return None
        try:
            dt = dtparser.parse(text, default=datetime(1900, 1, 1))
        except (ValueError, OverflowError):
            return None

        return {
            "time": {
                "hour": Literal(dt.hour),
                "minute": Literal(dt.minute),
                "second": Literal(dt.second),
            }
        }

    def _parse_datetime_string(self, text: str) -> Optional[Dict[str, Any]]:
        match = DATE_TIME_RE.match(text.strip())
        if not match:
            return None
        month_name = match.group("month").lower()
        month = MONTHS.get(month_name)
        if month is None:
            return None
        day = int(match.group("day"))
        time_part = match.group("time")
        try:
            dt = dtparser.parse(time_part, default=datetime(1900, 1, 1))
        except (ValueError, OverflowError):
            return None
        return {
            "date": {
                "month": Literal(month),
                "day": Literal(day),
            },
            "time": {
                "hour": Literal(dt.hour),
                "minute": Literal(dt.minute),
                "second": Literal(dt.second),
            },
        }

    def _parse_resolve_timestamp(self, value: str) -> Optional[Expression]:
        try:
            left_text, right_text = [part.strip() for part in value.split("@", 1)]
        except ValueError:
            return None

        # parse right side first to determine missing pieces
        right_parsed = self._parse_datetime_string(
            right_text
        ) or self._parse_time_string(right_text)
        if right_parsed is None:
            return None

        left_node = self._parse_string(left_text)

        args: Dict[str, Any] = {}
        if "date" in right_parsed and "year" not in right_parsed["date"]:
            right_parsed["date"]["year"] = self._as_node(left_node)
            args.update(right_parsed)
        elif "time" in right_parsed and "date" not in right_parsed:
            args["date"] = self._as_node(left_node)
            args["time"] = right_parsed["time"]
        else:
            args.update(right_parsed)
            args["date"] = self._as_node(left_node)

        return Expression("RESOLVE_TIMESTAMP", args)

    def _parse_string_interpolate(self, text: str) -> Optional[Expression]:
        """Parse python string interpolation syntax."""
        if "{" not in text or "}" not in text:
            return None

        pieces = list(string.Formatter().parse(text))
        if not any(field for _, field, _, _ in pieces if field is not None):
            return None

        inputs: Dict[str, Any] = {}
        for _, field_name, _, _ in pieces:
            if field_name is None:
                continue
            inputs[field_name] = self._parse_string(field_name)

        return Expression(
            "STRING_INTERPOLATE",
            {
                "pattern": Literal(text),
                "inputs": inputs,
            },
        )


class DftlyTransformer(Transformer):
    """Transform parsed tokens into dftly nodes."""

    def __init__(self, parser: Parser) -> None:
        super().__init__()
        self.parser = parser

    def NAME(self, token: Any) -> str:  # type: ignore[override]
        return str(token)

    def name(self, items: list[str]) -> str:  # type: ignore[override]
        (val,) = items
        return val

    def expr(self, items: list[Any]) -> Any:  # type: ignore[override]
        (item,) = items
        return item

    def conditional(self, items: list[Any]) -> Any:  # type: ignore[override]
        (item,) = items
        return item

    def cast(self, items: list[Any]) -> Expression:  # type: ignore[override]
        value = items[0]
        out_type = items[-1]
        return Expression(
            "TYPE_CAST",
            {
                "input": self.parser._as_node(value),
                "output_type": Literal(out_type),
            },
        )

    def cast_expr(self, items: list[Any]) -> Any:  # type: ignore[override]
        (item,) = items
        return item

    def arg_list(self, items: list[Any]) -> list[Any]:  # type: ignore[override]
        return items

    def func(self, items: list[Any]) -> Expression:  # type: ignore[override]
        name = items[0]
        args = items[1] if len(items) > 1 else []
        parsed_args = [self.parser._as_node(a) for a in args]
        return Expression(name.upper(), parsed_args)

    def plus(self, items: list[Any]) -> Tuple[str, Any]:  # type: ignore[override]
        _, val = items
        return "+", val

    def minus(self, items: list[Any]) -> Tuple[str, Any]:  # type: ignore[override]
        _, val = items
        return "-", val

    def additive(self, items: list[Any]) -> Any:  # type: ignore[override]
        base = self.parser._as_node(items[0])
        if len(items) == 1:
            return base
        ops = items[1:]
        symbols = [s for s, _ in ops]
        operands = [self.parser._as_node(v) for _, v in ops]
        if all(sym == "+" for sym in symbols):
            return Expression("ADD", [base] + operands)
        if all(sym == "-" for sym in symbols) and len(symbols) == 1:
            return Expression("SUBTRACT", [base, operands[0]])
        raise ValueError("invalid arithmetic expression")

    def and_expr(self, items: list[Any]) -> Any:  # type: ignore[override]
        args = [self.parser._as_node(i) for i in items if not isinstance(i, Token)]
        if len(args) == 1:
            return args[0]
        return Expression("AND", args)

    def or_expr(self, items: list[Any]) -> Any:  # type: ignore[override]
        args = [self.parser._as_node(i) for i in items if not isinstance(i, Token)]
        if len(args) == 1:
            return args[0]
        return Expression("OR", args)

    def not_expr(self, items: list[Any]) -> Expression:  # type: ignore[override]
        item = items[-1]
        return Expression("NOT", [self.parser._as_node(item)])

    def ifexpr(self, items: list[Any]) -> Expression:  # type: ignore[override]
        then = items[0]
        pred = items[2]
        els = items[4]
        return Expression(
            "CONDITIONAL",
            {
                "if": self.parser._as_node(pred),
                "then": self.parser._as_node(then),
                "else": self.parser._as_node(els),
            },
        )

    def resolve_ts(self, items: list[Any]) -> Expression:  # type: ignore[override]
        left, right = items
        return Expression(
            "RESOLVE_TIMESTAMP",
            {
                "date": self.parser._as_node(left),
                "time": self.parser._as_node(right),
            },
        )

    def start(self, items: list[Any]) -> Any:  # type: ignore[override]
        (item,) = items
        return item


def parse(
    data: Mapping[str, Any], input_schema: Optional[Mapping[str, Optional[str]]] = None
) -> Dict[str, Any]:
    """Parse simplified data into fully resolved form."""

    parser = Parser(input_schema)
    return parser.parse(data)


def from_yaml(
    yaml_text: str, input_schema: Optional[Mapping[str, Optional[str]]] = None
) -> Dict[str, Any]:
    """Parse from a YAML string."""

    import yaml

    data = yaml.safe_load(yaml_text) or {}
    if not isinstance(data, Mapping):
        raise TypeError("YAML input must produce a mapping")
    return parse(data, input_schema)
