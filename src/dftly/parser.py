from __future__ import annotations

from typing import Any, Dict, Mapping, Optional
import re
from datetime import datetime
from dateutil import parser as dtparser
import string

from importlib.resources import files
from lark import Lark, Transformer, Token
from lark.exceptions import LarkError, VisitError
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
    "HASH",
    "REGEX",
    "GREATER_THAN",
    "GREATER_OR_EQUAL",
    "LESS_THAN",
    "LESS_OR_EQUAL",
}

_EXPR_ALIASES = {
    "GT": "GREATER_THAN",
    "GREATER_THAN": "GREATER_THAN",
    "GTE": "GREATER_OR_EQUAL",
    "GE": "GREATER_OR_EQUAL",
    "GREATER_OR_EQUAL": "GREATER_OR_EQUAL",
    "LT": "LESS_THAN",
    "LESS_THAN": "LESS_THAN",
    "LTE": "LESS_OR_EQUAL",
    "LE": "LESS_OR_EQUAL",
    "LESS_OR_EQUAL": "LESS_OR_EQUAL",
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
            if expr_type in {"parse_with_format_string", "parse"}:
                parsed_args = self._parse_arguments(args)
                if isinstance(parsed_args, Mapping):
                    if "datetime_format" in parsed_args:
                        parsed_args.setdefault(
                            "format", parsed_args.pop("datetime_format")
                        )
                    if "duration_format" in parsed_args:
                        parsed_args.setdefault(
                            "format", parsed_args.pop("duration_format")
                        )
                        parsed_args.setdefault("output_type", Literal("duration"))
                    if "numeric_format" in parsed_args:
                        parsed_args.setdefault(
                            "format", parsed_args.pop("numeric_format")
                        )
                        parsed_args.setdefault("output_type", Literal("float"))
                return Expression("PARSE_WITH_FORMAT_STRING", parsed_args)
            if expr_type in {
                "regex_extract",
                "regex_match",
                "regex_not_match",
            } and isinstance(args, Mapping):
                action_map = {
                    "regex_extract": "EXTRACT",
                    "regex_match": "MATCH",
                    "regex_not_match": "NOT_MATCH",
                }
                parsed_args = self._parse_arguments(args)
                parsed_args.setdefault("action", Literal(action_map[expr_type]))
                return Expression("REGEX", parsed_args)
            expr_upper = _EXPR_ALIASES.get(expr_upper, expr_upper)
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
                if expr_upper in {
                    "GREATER_THAN",
                    "GREATER_OR_EQUAL",
                    "LESS_THAN",
                    "LESS_OR_EQUAL",
                }:
                    if isinstance(parsed_args, list):
                        if len(parsed_args) != 2:
                            raise ValueError(
                                f"{expr_type} requires exactly two arguments"
                            )
                        parsed_args = {
                            "left": parsed_args[0],
                            "right": parsed_args[1],
                        }
                    elif isinstance(parsed_args, Mapping):
                        if "left" not in parsed_args or "right" not in parsed_args:
                            raise ValueError(
                                f"{expr_type} mapping requires 'left' and 'right'"
                            )
                    else:
                        raise TypeError(
                            f"{expr_type} arguments must be mapping or list"
                        )
                if expr_upper == "HASH":
                    expr_upper = "HASH_TO_INT"
                return Expression(expr_upper, parsed_args)
            if isinstance(args, Mapping) and any(
                k in args
                for k in {
                    "format",
                    "datetime_format",
                    "duration_format",
                    "numeric_format",
                    "output_type",
                }
            ):
                parsed_args = self._parse_arguments(args)
                parsed_args.setdefault(
                    "input",
                    Column(expr_type, self.input_schema.get(expr_type)),
                )
                if "datetime_format" in parsed_args:
                    parsed_args.setdefault("format", parsed_args.pop("datetime_format"))
                if "duration_format" in parsed_args:
                    parsed_args.setdefault("format", parsed_args.pop("duration_format"))
                    parsed_args.setdefault("output_type", Literal("duration"))
                if "numeric_format" in parsed_args:
                    parsed_args.setdefault("format", parsed_args.pop("numeric_format"))
                    parsed_args.setdefault("output_type", Literal("float"))
                return Expression("PARSE_WITH_FORMAT_STRING", parsed_args)

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
        value = items[0]
        out_type = items[-1]
        return Expression(
            "TYPE_CAST",
            {
                "input": self.parser._as_node(value),
                "output_type": Literal(out_type),
            },
        )

    def primary(self, items: list[Any]) -> Any:  # type: ignore[override]
        (item,) = items
        return item

    def arg_list(self, items: list[Any]) -> list[Any]:  # type: ignore[override]
        return items

    def func(self, items: list[Any]) -> Expression:  # type: ignore[override]
        name = items[0]
        if isinstance(name, str) and name.lower() == "hash":
            name = "hash_to_int"
        args = items[1] if len(items) > 1 else []
        parsed_args = [self.parser._as_node(a) for a in args]
        return Expression(name.upper(), parsed_args)

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
        tokens = [i for i in items if not isinstance(i, Token)]
        if len(tokens) == 3:
            group_token, regex_text, expr = tokens
            group = int(group_token)
        else:
            regex_text, expr = tokens
            group = None
        args: Dict[str, Any] = {
            "regex": Literal(str(regex_text)),
            "action": Literal("EXTRACT"),
            "input": self.parser._as_node(expr),
        }
        if group is not None:
            args["group"] = Literal(group)
        return Expression("REGEX", args)

    def regex_match(self, items: list[Any]) -> Expression:  # type: ignore[override]
        tokens = [i for i in items if not isinstance(i, Token)]
        regex_text, expr = tokens
        action = (
            "NOT_MATCH"
            if any(isinstance(t, Token) and t.type == "NOT_MATCH" for t in items)
            else "MATCH"
        )
        return Expression(
            "REGEX",
            {
                "regex": Literal(str(regex_text)),
                "action": Literal(action),
                "input": self.parser._as_node(expr),
            },
        )

    def value_in_set(self, items: list[Any]) -> Expression:  # type: ignore[override]
        value = items[0]
        set_vals = items[-1]
        return Expression(
            "VALUE_IN_LITERAL_SET",
            {"value": self.parser._as_node(value), "set": set_vals},
        )

    def value_in_range(self, items: list[Any]) -> Expression:  # type: ignore[override]
        value = items[0]
        range_args = items[-1]
        args = dict(range_args)
        args["value"] = self.parser._as_node(value)
        return Expression("VALUE_IN_RANGE", args)

    def parse_as_format(self, items: list[Any]) -> Expression:  # type: ignore[override]
        expr, _, fmt = items
        fmt_text = fmt
        if isinstance(fmt_text, str):
            import ast

            fmt_text = ast.literal_eval(fmt_text)
        out_type = self.parser._infer_output_type(fmt_text)
        args = {
            "input": self.parser._as_node(expr),
            "format": Literal(fmt_text),
            "output_type": Literal(out_type),
        }
        return Expression("PARSE_WITH_FORMAT_STRING", args)

    def additive(self, items: list[Any]) -> Any:  # type: ignore[override]
        if len(items) == 1:
            return self.parser._as_node(items[0])
        left, op_token, right = items
        left_node = self.parser._as_node(left)
        right_node = self.parser._as_node(right)
        op = str(op_token)
        if op == "+":
            if isinstance(left_node, Expression) and left_node.type == "ADD":
                return Expression("ADD", left_node.arguments + [right_node])
            return Expression("ADD", [left_node, right_node])
        return Expression("SUBTRACT", [left_node, right_node])

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
        left, _, right = items
        parser = self.parser

        left_node = parser._as_node(left)

        text: Optional[str] = None
        if isinstance(right, Literal) and isinstance(right.value, str):
            text = right.value
        elif isinstance(right, str):
            text = right

        if text is not None:
            right_parsed = parser._parse_datetime_string(
                text
            ) or parser._parse_time_string(text)
            if right_parsed is not None:
                args: Dict[str, Any] = {}
                if "date" in right_parsed and "year" not in right_parsed["date"]:
                    right_parsed["date"]["year"] = left_node
                    args.update(right_parsed)
                elif "time" in right_parsed and "date" not in right_parsed:
                    args["date"] = left_node
                    args["time"] = right_parsed["time"]
                else:
                    args.update(right_parsed)
                    args["date"] = left_node
                return Expression("RESOLVE_TIMESTAMP", args)

        return Expression(
            "RESOLVE_TIMESTAMP",
            {"date": left_node, "time": parser._as_node(right)},
        )

    def compare_expr(self, items: list[Any]) -> Expression:  # type: ignore[override]
        left, op_token, right = items
        left_node = self.parser._as_node(left)
        right_node = self.parser._as_node(right)
        op_map = {
            ">": "GREATER_THAN",
            ">=": "GREATER_OR_EQUAL",
            "<": "LESS_THAN",
            "<=": "LESS_OR_EQUAL",
        }
        op = str(op_token)
        expr_type = op_map[op]
        return Expression(expr_type, {"left": left_node, "right": right_node})

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
