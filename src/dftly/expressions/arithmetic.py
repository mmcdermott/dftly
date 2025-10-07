from __future__ import annotations

from typing import Any, List, Mapping, Sequence

from lark import Token

from ..nodes import Expression
from .base import ExpressionNode, ExpressionRegistry


@ExpressionRegistry.register
class AddExpression(ExpressionNode):
    type = "ADD"
    aliases = ("+",)

    @classmethod
    def from_mapping(cls, parser, expr_type: str, args: Any) -> Expression:
        parsed_args = parser._parse_arguments(args)
        if isinstance(parsed_args, Mapping):
            values = list(parsed_args.values())
        elif isinstance(parsed_args, Sequence):
            values = list(parsed_args)
        else:
            values = [parsed_args]
        return Expression(cls.type, values)

    @classmethod
    def from_tree(cls, parser, event: str, items: List[Any], **kwargs: Any) -> Any:
        if event != "additive":
            return None
        if len(items) == 1:
            return parser._as_node(items[0])
        left, op_token, right = items
        if isinstance(op_token, Token) and str(op_token) != "+":
            return None
        left_node = parser._as_node(left)
        right_node = parser._as_node(right)
        if isinstance(left_node, Expression) and left_node.type == cls.type:
            return Expression(cls.type, list(left_node.arguments) + [right_node])
        return Expression(cls.type, [left_node, right_node])

    @classmethod
    def to_polars(cls, expr: Expression, to_polars, *, pl: Any) -> Any:
        args = expr.arguments
        first = to_polars(args[0])
        for arg in args[1:]:
            first = first + to_polars(arg)
        return first


@ExpressionRegistry.register
class SubtractExpression(ExpressionNode):
    type = "SUBTRACT"
    aliases = ("-",)

    @classmethod
    def from_mapping(cls, parser, expr_type: str, args: Any) -> Expression:
        parsed_args = parser._parse_arguments(args)
        if isinstance(parsed_args, Mapping):
            left = parsed_args.get("left")
            right = parsed_args.get("right")
            if left is None or right is None:
                raise ValueError("SUBTRACT mapping requires 'left' and 'right'")
            values = [left, right]
        elif isinstance(parsed_args, Sequence):
            if len(parsed_args) != 2:
                raise ValueError("SUBTRACT requires exactly two arguments")
            values = list(parsed_args)
        else:
            raise TypeError("SUBTRACT arguments must be list or mapping")
        return Expression(cls.type, values)

    @classmethod
    def from_tree(cls, parser, event: str, items: List[Any], **kwargs: Any) -> Any:
        if event != "additive" or len(items) != 3:
            return None
        left, op_token, right = items
        if not isinstance(op_token, Token) or str(op_token) != "-":
            return None
        left_node = parser._as_node(left)
        right_node = parser._as_node(right)
        return Expression(cls.type, [left_node, right_node])

    @classmethod
    def to_polars(cls, expr: Expression, to_polars, *, pl: Any) -> Any:
        left, right = expr.arguments
        return to_polars(left) - to_polars(right)
