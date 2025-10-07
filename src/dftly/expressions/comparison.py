from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence

from lark import Token

from ..nodes import Expression
from .base import ExpressionNode, ExpressionRegistry


class _ComparatorExpression(ExpressionNode):
    operator: str

    @classmethod
    def matches_mapping(cls, parser, expr_type: str, args: Any) -> bool:
        normalized = cls._normalize(expr_type)
        alias_set = {cls.type, *(cls._normalize(a) for a in cls.aliases)}
        alias_set.add(cls._normalize(cls.operator))
        return normalized in alias_set

    @classmethod
    def _normalize_arguments(cls, parsed_args: Any) -> Dict[str, Any]:
        if isinstance(parsed_args, Mapping):
            if "left" not in parsed_args or "right" not in parsed_args:
                raise ValueError(f"{cls.type} mapping requires 'left' and 'right'")
            return {"left": parsed_args["left"], "right": parsed_args["right"]}
        if isinstance(parsed_args, Sequence):
            if len(parsed_args) != 2:
                raise ValueError(f"{cls.type} requires exactly two arguments")
            left, right = parsed_args
            return {"left": left, "right": right}
        raise TypeError(f"{cls.type} arguments must be mapping or sequence")

    @classmethod
    def from_mapping(cls, parser, expr_type: str, args: Any) -> Expression:
        parsed_args = parser._parse_arguments(args)
        normalized = cls._normalize_arguments(parsed_args)
        return Expression(cls.type, normalized)

    @classmethod
    def from_tree(cls, parser, event: str, items: List[Any], **kwargs: Any) -> Any:
        if event != "compare_expr" or len(items) != 3:
            return None
        left, op_token, right = items
        if not isinstance(op_token, Token) or str(op_token) != cls.operator:
            return None
        return Expression(
            cls.type,
            {
                "left": parser._as_node(left),
                "right": parser._as_node(right),
            },
        )

    @classmethod
    def to_polars(cls, expr: Expression, to_polars, *, pl: Any) -> Any:
        args = expr.arguments
        left_expr = to_polars(args["left"])
        right_expr = to_polars(args["right"])
        comparator_map = {
            "GREATER_THAN": lambda left, right: left > right,
            "GREATER_OR_EQUAL": lambda left, right: left >= right,
            "LESS_THAN": lambda left, right: left < right,
            "LESS_OR_EQUAL": lambda left, right: left <= right,
        }
        return comparator_map[cls.type](left_expr, right_expr)


@ExpressionRegistry.register
class GreaterThanExpression(_ComparatorExpression):
    type = "GREATER_THAN"
    operator = ">"
    aliases = ("GT", "GREATER_THAN")


@ExpressionRegistry.register
class GreaterOrEqualExpression(_ComparatorExpression):
    type = "GREATER_OR_EQUAL"
    operator = ">="
    aliases = ("GTE", "GE", "GREATER_OR_EQUAL")


@ExpressionRegistry.register
class LessThanExpression(_ComparatorExpression):
    type = "LESS_THAN"
    operator = "<"
    aliases = ("LT", "LESS_THAN")


@ExpressionRegistry.register
class LessOrEqualExpression(_ComparatorExpression):
    type = "LESS_OR_EQUAL"
    operator = "<="
    aliases = ("LTE", "LE", "LESS_OR_EQUAL")
