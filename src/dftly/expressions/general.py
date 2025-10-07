from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, MutableMapping, Optional

from dateutil import parser as dtparser
from lark import Token

from ..nodes import Column, Expression, Literal
from .base import ExpressionNode, ExpressionRegistry


_CLOCK_TIME = object()


def _ensure_naive_datetime(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


@ExpressionRegistry.register
class CoalesceExpression(ExpressionNode):
    type = "COALESCE"

    @classmethod
    def from_mapping(cls, parser, expr_type: str, args: Any) -> Expression:
        parsed_args = parser._parse_arguments(args)
        if isinstance(parsed_args, Mapping):
            values = list(parsed_args.values())
        elif isinstance(parsed_args, list):
            values = parsed_args
        else:
            values = [parsed_args]
        return Expression(cls.type, values)

    @classmethod
    def from_tree(cls, parser, event: str, items: List[Any], **kwargs: Any) -> Any:
        if event != "func":
            return None
        name = kwargs.get("name")
        if str(name).upper() != cls.type:
            return None
        args = kwargs.get("args", [])
        parsed_args = [parser._as_node(a) for a in args]
        return Expression(cls.type, parsed_args)

    @classmethod
    def to_polars(cls, expr: Expression, to_polars, *, pl: Any) -> Any:
        return pl.coalesce([to_polars(arg) for arg in expr.arguments])


@ExpressionRegistry.register
class TypeCastExpression(ExpressionNode):
    type = "TYPE_CAST"

    @classmethod
    def from_tree(cls, parser, event: str, items: List[Any], **kwargs: Any) -> Any:
        if event != "cast":
            return None
        value = items[0]
        out_type = items[-1]
        return Expression(
            cls.type,
            {
                "input": parser._as_node(value),
                "output_type": Literal(out_type),
            },
        )

    @classmethod
    def to_polars(cls, expr: Expression, to_polars, *, pl: Any) -> Any:
        args = expr.arguments
        dtype_map = {
            "int": int,
            "integer": int,
            "float": float,
            "double": float,
            "bool": bool,
            "boolean": bool,
            "str": str,
            "string": str,
            "date": pl.Date,
            "datetime": pl.Datetime,
            "duration": pl.Duration,
            "time": _CLOCK_TIME,
            "clock_time": _CLOCK_TIME,
            "clock-time": _CLOCK_TIME,
        }
        inp = to_polars(args["input"])
        out_type = args["output_type"].value
        dtype = dtype_map.get(str(out_type).lower(), out_type)
        if dtype is _CLOCK_TIME:
            raise ValueError("TYPE_CAST does not support the 'clock_time' output type")
        return inp.cast(dtype)


@ExpressionRegistry.register
class ConditionalExpression(ExpressionNode):
    type = "CONDITIONAL"

    @classmethod
    def from_tree(cls, parser, event: str, items: List[Any], **kwargs: Any) -> Any:
        if event != "ifexpr":
            return None
        then = items[0]
        pred = items[2]
        els = items[4]
        return Expression(
            cls.type,
            {
                "if": parser._as_node(pred),
                "then": parser._as_node(then),
                "else": parser._as_node(els),
            },
        )

    @classmethod
    def to_polars(cls, expr: Expression, to_polars, *, pl: Any) -> Any:
        args = expr.arguments
        return (
            pl.when(to_polars(args["if"]))
            .then(to_polars(args["then"]))
            .otherwise(to_polars(args["else"]))
        )


@ExpressionRegistry.register
class ResolveTimestampExpression(ExpressionNode):
    type = "RESOLVE_TIMESTAMP"

    @classmethod
    def _parse_time_string(cls, parser, text: str) -> Optional[Dict[str, Any]]:
        return parser._parse_time_string(text)

    @classmethod
    def _parse_datetime_string(cls, parser, text: str) -> Optional[Dict[str, Any]]:
        return parser._parse_datetime_string(text)

    @classmethod
    def from_tree(cls, parser, event: str, items: List[Any], **kwargs: Any) -> Any:
        if event != "resolve_ts" or len(items) != 3:
            return None
        left, _, right = items
        left_node = parser._as_node(left)
        text: Optional[str] = None
        if isinstance(right, Literal) and isinstance(right.value, str):
            text = right.value
        elif isinstance(right, str):
            text = right
        if text is not None:
            parsed = cls._parse_datetime_string(parser, text) or cls._parse_time_string(
                parser, text
            )
            if parsed is not None:
                args: Dict[str, Any] = {}
                if "date" in parsed and "year" not in parsed["date"]:
                    parsed["date"]["year"] = left_node
                    args.update(parsed)
                elif "time" in parsed and "date" not in parsed:
                    args["date"] = left_node
                    args["time"] = parsed["time"]
                else:
                    args.update(parsed)
                    args["date"] = left_node
                return Expression(cls.type, args)
        return Expression(
            cls.type,
            {"date": left_node, "time": parser._as_node(right)},
        )

    @classmethod
    def to_polars(cls, expr: Expression, to_polars, *, pl: Any) -> Any:
        args = expr.arguments
        date = args["date"]
        time = args["time"]
        if isinstance(date, Mapping):
            year = to_polars(date["year"])
            month = to_polars(date["month"])
            day = to_polars(date["day"])
        else:
            date_expr = to_polars(date)
            year = date_expr.dt.year()
            month = date_expr.dt.month()
            day = date_expr.dt.day()
        base_datetime = pl.datetime(year, month, day, 0, 0, 0)
        if isinstance(time, Mapping):

            def _component(name: str) -> Any:
                node = time.get(name)
                return to_polars(node) if node is not None else pl.lit(0)

            hour = _component("hour")
            minute = _component("minute")
            second = _component("second")
            return pl.datetime(year, month, day, hour, minute, second)
        return base_datetime + to_polars(time)


@ExpressionRegistry.register
class ValueInLiteralSetExpression(ExpressionNode):
    type = "VALUE_IN_LITERAL_SET"

    @classmethod
    def from_tree(cls, parser, event: str, items: List[Any], **kwargs: Any) -> Any:
        if event != "value_in_set":
            return None
        value = items[0]
        set_vals = items[-1]
        parsed_set = [parser._as_node(v) for v in set_vals]
        return Expression(
            cls.type,
            {"value": parser._as_node(value), "set": parsed_set},
        )

    @classmethod
    def to_polars(cls, expr: Expression, to_polars, *, pl: Any) -> Any:
        value = to_polars(expr.arguments["value"])
        set_arg = expr.arguments["set"]
        if isinstance(set_arg, Expression) and set_arg.type == "COALESCE":
            items = set_arg.arguments
        else:
            items = set_arg
        set_vals = [v.value if isinstance(v, Literal) else None for v in items]
        return value.is_in(set_vals)


@ExpressionRegistry.register
class ValueInRangeExpression(ExpressionNode):
    type = "VALUE_IN_RANGE"

    @classmethod
    def from_tree(cls, parser, event: str, items: List[Any], **kwargs: Any) -> Any:
        if event != "value_in_range":
            return None
        value = items[0]
        range_args = items[-1]
        args = dict(range_args)
        args["value"] = parser._as_node(value)
        return Expression(cls.type, args)

    @classmethod
    def to_polars(cls, expr: Expression, to_polars, *, pl: Any) -> Any:
        args = expr.arguments
        value = to_polars(args["value"])
        expr_out = pl.lit(True)
        if "min" in args:
            min_expr = to_polars(args["min"])
            incl = args.get("min_inclusive", Literal(True)).value
            expr_out = expr_out & (value >= min_expr if incl else value > min_expr)
        if "max" in args:
            max_expr = to_polars(args["max"])
            incl = args.get("max_inclusive", Literal(True)).value
            expr_out = expr_out & (value <= max_expr if incl else value < max_expr)
        return expr_out


@ExpressionRegistry.register
class StringInterpolateExpression(ExpressionNode):
    type = "STRING_INTERPOLATE"

    @classmethod
    def from_mapping(cls, parser, expr_type: str, args: Any) -> Expression:
        if isinstance(args, Mapping):
            pattern = args.get("pattern")
            if pattern is None:
                raise ValueError("STRING_INTERPOLATE requires a 'pattern'")
            if not isinstance(pattern, Literal):
                pattern = Literal(pattern)
            inputs = args.get("inputs", {})
            if isinstance(inputs, Mapping):
                parsed_inputs = {k: parser._parse_value(v) for k, v in inputs.items()}
            else:
                parsed_inputs = inputs
            return Expression(
                cls.type,
                {"pattern": pattern, "inputs": parsed_inputs},
            )
        raise TypeError("STRING_INTERPOLATE arguments must be a mapping")

    @classmethod
    def to_polars(cls, expr: Expression, to_polars, *, pl: Any) -> Any:
        pattern = expr.arguments["pattern"]
        if isinstance(pattern, Literal):
            pattern = pattern.value
        inputs = expr.arguments.get("inputs", {})
        if isinstance(inputs, Mapping):
            order = []
            fmt_parts: List[str] = []
            import string

            for literal, field, _, _ in string.Formatter().parse(pattern):
                fmt_parts.append(literal)
                if field is not None:
                    fmt_parts.append("{}")
                    order.append(field)
            pattern = "".join(fmt_parts)
            exprs = [to_polars(inputs[field]) for field in order]
        else:
            exprs = []
        return pl.format(pattern, *exprs)


@ExpressionRegistry.register
class ParseWithFormatStringExpression(ExpressionNode):
    type = "PARSE_WITH_FORMAT_STRING"
    aliases = ("PARSE",)

    @classmethod
    def matches_mapping(cls, parser, expr_type: str, args: Any) -> bool:
        normalized = cls._normalize(expr_type)
        if normalized in {cls.type, *(cls._normalize(a) for a in cls.aliases)}:
            return True
        if isinstance(args, Mapping) and any(
            key in args
            for key in {"format", "datetime_format", "duration_format", "numeric_format", "output_type"}
        ):
            return True
        return False

    @classmethod
    def _post_process_arguments(cls, parsed_args: MutableMapping[str, Any]) -> None:
        if "datetime_format" in parsed_args:
            parsed_args.setdefault("format", parsed_args.pop("datetime_format"))
        if "duration_format" in parsed_args:
            parsed_args.setdefault("format", parsed_args.pop("duration_format"))
            parsed_args.setdefault("output_type", Literal("duration"))
        if "numeric_format" in parsed_args:
            parsed_args.setdefault("format", parsed_args.pop("numeric_format"))
            parsed_args.setdefault("output_type", Literal("float"))

    @classmethod
    def from_mapping(cls, parser, expr_type: str, args: Any) -> Expression:
        parsed_args = parser._parse_arguments(args)
        if isinstance(parsed_args, Mapping):
            parsed_args = dict(parsed_args)
        else:
            raise TypeError("PARSE_WITH_FORMAT_STRING arguments must be a mapping")
        normalized = cls._normalize(expr_type)
        if normalized not in {cls.type, *(cls._normalize(a) for a in cls.aliases)}:
            parsed_args.setdefault(
                "input",
                Column(expr_type, parser.input_schema.get(expr_type)),
            )
        cls._post_process_arguments(parsed_args)
        return Expression(cls.type, parsed_args)

    @classmethod
    def from_tree(cls, parser, event: str, items: List[Any], **kwargs: Any) -> Any:
        if event != "parse_as_format":
            return None
        expr, _, fmt = items
        if isinstance(fmt, str):
            import ast

            fmt = ast.literal_eval(fmt)
        out_type = parser._infer_output_type(fmt)
        return Expression(
            cls.type,
            {
                "input": parser._as_node(expr),
                "format": Literal(fmt),
                "output_type": Literal(out_type),
            },
        )

    @classmethod
    def to_polars(cls, expr: Expression, to_polars, *, pl: Any) -> Any:
        dtype_map = {
            "int": int,
            "integer": int,
            "float": float,
            "double": float,
            "bool": bool,
            "boolean": bool,
            "str": str,
            "string": str,
            "date": pl.Date,
            "datetime": pl.Datetime,
            "duration": pl.Duration,
            "time": _CLOCK_TIME,
            "clock_time": _CLOCK_TIME,
            "clock-time": _CLOCK_TIME,
        }
        args = expr.arguments
        inp = to_polars(args["input"])
        fmt_node = args.get("format")
        fmt = fmt_node.value if isinstance(fmt_node, Literal) else fmt_node
        out_type = args.get("output_type")
        if isinstance(out_type, Literal):
            out_type = out_type.value
        dtype = dtype_map.get(str(out_type).lower(), out_type)
        if dtype is _CLOCK_TIME:
            dtype = pl.Duration
        fmt_auto = isinstance(fmt, str) and fmt.upper() == "AUTO"
        fmt_value = None if fmt_auto else fmt

        if dtype == pl.Duration:
            base = datetime(1900, 1, 1)

            if fmt_auto:

                def parse_func(val: str | None) -> object:
                    if val is None:
                        return None
                    try:
                        dt = dtparser.parse(val, default=base)
                    except (ValueError, OverflowError, TypeError):
                        return None
                    dt_local = _ensure_naive_datetime(dt)
                    return dt_local - base

                return inp.map_elements(parse_func, return_dtype=pl.Duration)

            if fmt_value:

                def parse_func(val: str | None) -> object:
                    if val is None:
                        return None
                    try:
                        dt = datetime.strptime(val, fmt_value)
                    except Exception:
                        return None
                    dt_local = _ensure_naive_datetime(dt)
                    return dt_local - base

                return inp.map_elements(parse_func, return_dtype=pl.Duration)

            return inp.str.strptime(pl.Time).cast(pl.Duration)

        if dtype in {pl.Date, pl.Datetime} and fmt_auto:

            def parse_func(val: str | None) -> object:
                if val is None:
                    return None
                try:
                    dt = dtparser.parse(val)
                except (ValueError, OverflowError, TypeError):
                    return None
                dt_local = _ensure_naive_datetime(dt)
                if dtype == pl.Date:
                    return dt_local.date()
                return dt_local

            return inp.map_elements(parse_func, return_dtype=dtype)

        if dtype in {int, float}:
            cleaned = inp.str.replace_all(r"[^0-9.+-]", "")
            if dtype is int:
                return cleaned.str.to_integer()
            return cleaned.str.to_decimal(scale=2).cast(float)

        return inp.str.strptime(dtype, fmt_value)


@ExpressionRegistry.register
class HashToIntExpression(ExpressionNode):
    type = "HASH_TO_INT"
    aliases = ("HASH",)

    @classmethod
    def from_mapping(cls, parser, expr_type: str, args: Any) -> Expression:
        parsed_args = parser._parse_arguments(args)
        if isinstance(parsed_args, Mapping):
            inp = parsed_args.get("input")
            if inp is None:
                raise ValueError("HASH_TO_INT mapping requires 'input'")
            return Expression(cls.type, parsed_args)
        if isinstance(parsed_args, list):
            if not parsed_args:
                raise ValueError("HASH_TO_INT requires at least one argument")
            return Expression(cls.type, parsed_args)
        return Expression(cls.type, [parsed_args])

    @classmethod
    def from_tree(cls, parser, event: str, items: List[Any], **kwargs: Any) -> Any:
        if event != "func":
            return None
        name = kwargs.get("name")
        if str(name).lower() not in {"hash", "hash_to_int"}:
            return None
        args = kwargs.get("args", [])
        parsed_args = [parser._as_node(a) for a in args]
        return Expression(cls.type, parsed_args)

    @classmethod
    def to_polars(cls, expr: Expression, to_polars, *, pl: Any) -> Any:
        args = expr.arguments
        if isinstance(args, Mapping):
            inp = args.get("input")
            alg = args.get("algorithm")
        else:
            inp = args[0]
            alg = args[1] if len(args) > 1 else None
        expr_inp = to_polars(inp)
        if isinstance(alg, Literal):
            alg_val = alg.value
        elif alg is None:
            alg_val = None
        else:
            alg_val = alg
        if alg_val is None:
            return expr_inp.hash()
        import hashlib

        def _hash_func(val: Any, algorithm: str = str(alg_val)) -> int | None:
            if val is None:
                return None
            h = hashlib.new(algorithm)
            h.update(str(val).encode())
            return int.from_bytes(h.digest()[:8], "big", signed=False)

        return expr_inp.map_elements(_hash_func, return_dtype=pl.UInt64)


@ExpressionRegistry.register
class RegexExpression(ExpressionNode):
    type = "REGEX"

    @classmethod
    def matches_mapping(cls, parser, expr_type: str, args: Any) -> bool:
        normalized = cls._normalize(expr_type)
        return normalized in {
            cls.type,
            "REGEX_EXTRACT",
            "REGEX_MATCH",
            "REGEX_NOT_MATCH",
        }

    @classmethod
    def from_mapping(cls, parser, expr_type: str, args: Any) -> Expression:
        parsed_args = parser._parse_arguments(args)
        normalized = cls._normalize(expr_type)
        if isinstance(parsed_args, Mapping):
            args_map = dict(parsed_args)
        else:
            raise TypeError("REGEX short form must be a mapping")
        action_map = {
            "REGEX_EXTRACT": "EXTRACT",
            "REGEX_MATCH": "MATCH",
            "REGEX_NOT_MATCH": "NOT_MATCH",
        }
        if normalized in action_map and "action" not in args_map:
            args_map["action"] = Literal(action_map[normalized])
        return Expression(cls.type, args_map)

    @classmethod
    def from_tree(cls, parser, event: str, items: List[Any], **kwargs: Any) -> Any:
        if event == "regex_extract":
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
                "input": parser._as_node(expr),
            }
            if group is not None:
                args["group"] = Literal(group)
            return Expression(cls.type, args)
        if event == "regex_match":
            tokens = [i for i in items if not isinstance(i, Token)]
            regex_text, expr = tokens
            action = (
                "NOT_MATCH"
                if any(isinstance(t, Token) and t.type == "NOT_MATCH" for t in items)
                else "MATCH"
            )
            return Expression(
                cls.type,
                {
                    "regex": Literal(str(regex_text)),
                    "action": Literal(action),
                    "input": parser._as_node(expr),
                },
            )
        if event == "func":
            name = kwargs.get("name")
            if str(name).upper() != cls.type:
                return None
            args = kwargs.get("args", [])
            parsed_args = parser._parse_arguments(args)
            if isinstance(parsed_args, Mapping):
                return Expression(cls.type, parsed_args)
        return None

    @classmethod
    def to_polars(cls, expr: Expression, to_polars, *, pl: Any) -> Any:
        args = expr.arguments
        pattern_node = args["regex"]
        pattern = pattern_node.value if isinstance(pattern_node, Literal) else pattern_node
        inp = to_polars(args["input"])
        action = args.get("action")
        if isinstance(action, Literal):
            action = action.value
        if action == "EXTRACT":
            group = args.get("group", Literal(1))
            group_idx = group.value if isinstance(group, Literal) else group
            return inp.str.extract(pattern, group_idx)
        if action == "MATCH":
            return inp.str.contains(pattern)
        if action == "NOT_MATCH":
            return ~inp.str.contains(pattern)
        raise ValueError("Invalid REGEX action")
