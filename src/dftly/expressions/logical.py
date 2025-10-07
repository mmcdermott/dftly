from __future__ import annotations

from typing import Any, List

from lark import Token

from ..nodes import Expression
from .base import ExpressionNode, ExpressionRegistry


def _filter_tokens(parser, items: List[Any]) -> List[Any]:
    return [parser._as_node(i) for i in items if not isinstance(i, Token)]


@ExpressionRegistry.register
class AndExpression(ExpressionNode):
    type = "AND"

    @classmethod
    def from_tree(cls, parser, event: str, items: List[Any], **kwargs: Any) -> Any:
        if event != "and_expr":
            return None
        args = _filter_tokens(parser, items)
        if len(args) == 1:
            return args[0]
        return Expression(cls.type, args)

    @classmethod
    def to_polars(cls, expr: Expression, to_polars, *, pl: Any) -> Any:
        args = expr.arguments
        result = to_polars(args[0])
        for arg in args[1:]:
            result = result & to_polars(arg)
        return result


@ExpressionRegistry.register
class OrExpression(ExpressionNode):
    type = "OR"

    @classmethod
    def from_tree(cls, parser, event: str, items: List[Any], **kwargs: Any) -> Any:
        if event != "or_expr":
            return None
        args = _filter_tokens(parser, items)
        if len(args) == 1:
            return args[0]
        return Expression(cls.type, args)

    @classmethod
    def to_polars(cls, expr: Expression, to_polars, *, pl: Any) -> Any:
        args = expr.arguments
        result = to_polars(args[0])
        for arg in args[1:]:
            result = result | to_polars(arg)
        return result


@ExpressionRegistry.register
class NotExpression(ExpressionNode):
    type = "NOT"

    @classmethod
    def from_mapping(cls, parser, expr_type: str, args: Any) -> Expression:
        parsed_args = parser._parse_arguments(args)
        if isinstance(parsed_args, list):
            if len(parsed_args) != 1:
                raise ValueError("NOT requires exactly one argument")
            argument = parsed_args[0]
        else:
            argument = parsed_args
        return Expression(cls.type, [argument])

    @classmethod
    def from_tree(cls, parser, event: str, items: List[Any], **kwargs: Any) -> Any:
        if event != "not_expr":
            return None
        item = items[-1]
        return Expression(cls.type, [parser._as_node(item)])

    @classmethod
    def to_polars(cls, expr: Expression, to_polars, *, pl: Any) -> Any:
        (arg,) = expr.arguments
        return ~to_polars(arg)
