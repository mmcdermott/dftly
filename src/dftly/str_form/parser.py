from __future__ import annotations

from typing import Any, Dict, Mapping, Optional
import re
from datetime import datetime
from dateutil import parser as dtparser
import string

from importlib.resources import files
from lark import Lark, Transformer
from lark.exceptions import LarkError, VisitError
from .expressions import ExpressionRegistry
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
            registry_expr = ExpressionRegistry.create_from_mapping(
                self, expr_type, args
            )
            if registry_expr is not None:
                return registry_expr

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
        try:
            tree = self._lark.parse(value)
            return self._transformer.transform(tree)
        except (LarkError, VisitError):
            pass

        interp = self._parse_string_interpolate(value)
        if interp is not None:
            return interp

        if re.search(
            r"(?:\s[+\-@]\s)|(?:>=|<=|>|<)|(?:&&|\|\||!)|\b(?:as|if|else|and|or|in|not)\b",
            value,
            re.IGNORECASE,
        ):
            raise ValueError(f"invalid expression syntax: {value!r}")

        return self._as_node(value)

    # ------------------------------------------------------------------
    def _infer_output_type(self, fmt: str) -> str:
        time_tokens = ["%H", "%I", "%M", "%S", "%p", "%X", "%T"]
        date_tokens = ["%Y", "%y", "%m", "%d", "%b", "%B", "%j", "%U", "%W", "%F"]
        num_tokens = {"%d", "%f", "%i", "%u", "%e", "%g"}
        # TODO(mmd): %d is duplicated in num and date tokens
        tokens = [f"%{t}" for t in re.findall(r"%[^A-Za-z]*([A-Za-z])", fmt)]
        has_time = any(t in tokens for t in time_tokens)
        has_date = any(t in tokens for t in date_tokens)
        if tokens and all(t in num_tokens for t in tokens):
            return "float" if any(t in {"%f", "%e", "%g"} for t in tokens) else "int"
        if has_time and not has_date:
            return "duration"
        return "datetime" if has_time else "date"

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

    def NUMBER(self, token: Any) -> str:  # type: ignore[override]
        return str(token)

    def STRING(self, token: Any) -> str:  # type: ignore[override]
        return str(token)

    def number(self, items: list[str]) -> Literal:  # type: ignore[override]
        (text,) = items
        if "." in text:
            val: Any = float(text)
        else:
            val = int(text)
        return Literal(val)

    def name(self, items: list[str]) -> Any:  # type: ignore[override]
        (val,) = items
        return self.parser._as_node(val)

    def regex(self, items: list[Any]) -> str:  # type: ignore[override]
        (val,) = items
        return str(val)

    def string(self, items: list[str]) -> Literal:  # type: ignore[override]
        import ast

        (text,) = items
        return Literal(ast.literal_eval(text))

    def paren_expr(self, items: list[Any]) -> Any:  # type: ignore[override]
        (item,) = items
        return item

    def expr(self, items: list[Any]) -> Any:  # type: ignore[override]
        (item,) = items
        return item

    def conditional(self, items: list[Any]) -> Any:  # type: ignore[override]
        (item,) = items
        return item

    def cast(self, items: list[Any]) -> Expression:  # type: ignore[override]
        result = ExpressionRegistry.create_from_tree("cast", self.parser, items)
        if result is None:
            raise ValueError("Unable to parse cast expression")
        return result

    def primary(self, items: list[Any]) -> Any:  # type: ignore[override]
        (item,) = items
        return item

    def arg_list(self, items: list[Any]) -> list[Any]:  # type: ignore[override]
        return items

    def func(self, items: list[Any]) -> Expression:  # type: ignore[override]
        name = items[0]
        args = items[1] if len(items) > 1 else []
        result = ExpressionRegistry.create_from_tree(
            "func", self.parser, [], name=name, args=args
        )
        if result is not None:
            return result
        parsed_args = [self.parser._as_node(a) for a in args]
        return Expression(str(name).upper(), parsed_args)

    def literal_set(self, items: list[Any]) -> list[Any]:  # type: ignore[override]
        if not items:
            return []
        (vals,) = items
        return [self.parser._as_node(v) for v in vals]

    def range_inc(self, items: list[Any]) -> Dict[str, Any]:  # type: ignore[override]
        low, high = items
        return {
            "min": self.parser._as_node(low),
            "max": self.parser._as_node(high),
            "min_inclusive": Literal(True),
            "max_inclusive": Literal(True),
        }

    def range_ie(self, items: list[Any]) -> Dict[str, Any]:  # type: ignore[override]
        low, high = items
        return {
            "min": self.parser._as_node(low),
            "max": self.parser._as_node(high),
            "min_inclusive": Literal(True),
            "max_inclusive": Literal(False),
        }

    def range_ei(self, items: list[Any]) -> Dict[str, Any]:  # type: ignore[override]
        low, high = items
        return {
            "min": self.parser._as_node(low),
            "max": self.parser._as_node(high),
            "min_inclusive": Literal(False),
            "max_inclusive": Literal(True),
        }

    def range_exc(self, items: list[Any]) -> Dict[str, Any]:  # type: ignore[override]
        low, high = items
        return {
            "min": self.parser._as_node(low),
            "max": self.parser._as_node(high),
            "min_inclusive": Literal(False),
            "max_inclusive": Literal(False),
        }

    def regex_extract(self, items: list[Any]) -> Expression:  # type: ignore[override]
        result = ExpressionRegistry.create_from_tree(
            "regex_extract", self.parser, items
        )
        if result is None:
            raise ValueError("Unable to parse regex extract expression")
        return result

    def regex_match(self, items: list[Any]) -> Expression:  # type: ignore[override]
        result = ExpressionRegistry.create_from_tree("regex_match", self.parser, items)
        if result is None:
            raise ValueError("Unable to parse regex match expression")
        return result

    def value_in_set(self, items: list[Any]) -> Expression:  # type: ignore[override]
        result = ExpressionRegistry.create_from_tree("value_in_set", self.parser, items)
        if result is None:
            raise ValueError("Unable to parse value-in-set expression")
        return result

    def value_in_range(self, items: list[Any]) -> Expression:  # type: ignore[override]
        result = ExpressionRegistry.create_from_tree(
            "value_in_range", self.parser, items
        )
        if result is None:
            raise ValueError("Unable to parse value-in-range expression")
        return result

    def parse_as_format(self, items: list[Any]) -> Expression:  # type: ignore[override]
        result = ExpressionRegistry.create_from_tree(
            "parse_as_format", self.parser, items
        )
        if result is None:
            raise ValueError("Unable to parse formatted parse expression")
        return result

    def additive(self, items: list[Any]) -> Any:  # type: ignore[override]
        result = ExpressionRegistry.create_from_tree("additive", self.parser, items)
        if result is None:
            if len(items) == 1:
                return self.parser._as_node(items[0])
            raise ValueError("Unsupported additive expression")
        return result

    def and_expr(self, items: list[Any]) -> Any:  # type: ignore[override]
        result = ExpressionRegistry.create_from_tree("and_expr", self.parser, items)
        if result is None:
            raise ValueError("Unable to parse AND expression")
        return result

    def or_expr(self, items: list[Any]) -> Any:  # type: ignore[override]
        result = ExpressionRegistry.create_from_tree("or_expr", self.parser, items)
        if result is None:
            raise ValueError("Unable to parse OR expression")
        return result

    def not_expr(self, items: list[Any]) -> Expression:  # type: ignore[override]
        result = ExpressionRegistry.create_from_tree("not_expr", self.parser, items)
        if result is None:
            raise ValueError("Unable to parse NOT expression")
        return result

    def ifexpr(self, items: list[Any]) -> Expression:  # type: ignore[override]
        result = ExpressionRegistry.create_from_tree("ifexpr", self.parser, items)
        if result is None:
            raise ValueError("Unable to parse conditional expression")
        return result

    def resolve_ts(self, items: list[Any]) -> Expression:  # type: ignore[override]
        result = ExpressionRegistry.create_from_tree("resolve_ts", self.parser, items)
        if result is None:
            raise ValueError("Unable to parse RESOLVE_TIMESTAMP expression")
        return result

    def compare_expr(self, items: list[Any]) -> Expression:  # type: ignore[override]
        result = ExpressionRegistry.create_from_tree("compare_expr", self.parser, items)
        if result is None:
            raise ValueError("Unable to parse comparison expression")
        return result

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
