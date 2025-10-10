from typing import Any

import polars as pl

from .base import Literal, NestedArgsNode, NodeBase


class RegexExtract(NestedArgsNode):
    """Extract a regex capture group from a string expression."""

    KEY = "regex_extract"

    def __post_init__(self) -> None:
        normalized_kwargs = dict(self.kwargs)

        if self.args:
            if len(self.args) not in (2, 3):
                raise ValueError(
                    "regex_extract requires value, pattern, and optional group arguments"
                )

            value_node, pattern_node, *rest = self.args
            normalized_kwargs.setdefault("from", value_node)
            normalized_kwargs.setdefault("pattern", pattern_node)
            if rest:
                normalized_kwargs.setdefault("group", rest[0])

            self.args = ()

        pattern_node = normalized_kwargs.get("pattern")
        if pattern_node is None:
            raise ValueError("regex_extract requires a 'pattern' argument")
        if isinstance(pattern_node, str):
            pattern_node = Literal(pattern_node)
        normalized_kwargs["pattern"] = pattern_node

        if "group" in normalized_kwargs:
            group_node = normalized_kwargs["group"]
            if isinstance(group_node, int):
                group_node = Literal(group_node)
            normalized_kwargs["group"] = group_node

        self.kwargs = normalized_kwargs

        super().__post_init__()

        try:
            self._value_node = self.kwargs["from"]
        except KeyError as exc:
            raise ValueError("regex_extract requires a 'from' argument") from exc

        pattern_literal = self.kwargs["pattern"]
        if not isinstance(pattern_literal, Literal):
            raise TypeError("regex_extract pattern must be provided as a literal")

        self._pattern_value = pattern_literal.args[0]
        if not isinstance(self._pattern_value, str):
            raise TypeError("regex_extract pattern literal must be a string")

        group_literal = self.kwargs.get("group")
        if group_literal is None:
            self._group_index = 1
        else:
            if not isinstance(group_literal, Literal):
                raise TypeError("regex_extract group must be provided as a literal")
            group_value = group_literal.args[0]
            if not isinstance(group_value, int):
                raise TypeError("regex_extract group literal must be an integer")
            self._group_index = group_value

    @property
    def polars_expr(self) -> pl.Expr:
        value_expr = self._value_node.polars_expr
        return value_expr.str.extract(self._pattern_value, self._group_index)

    @classmethod
    def args_from_value(
        cls, value: Any
    ) -> tuple[tuple[Any, ...], dict[str, Any]]:
        args, kwargs = super().args_from_value(value)

        normalized_kwargs = dict(kwargs)

        if args:
            if len(args) not in (2, 3):
                raise ValueError(
                    "regex_extract requires value, pattern, and optional group arguments"
                )

            normalized_kwargs.setdefault("from", args[0])
            normalized_kwargs.setdefault("pattern", args[1])
            if len(args) == 3:
                normalized_kwargs.setdefault("group", args[2])

        if "pattern" in normalized_kwargs and isinstance(normalized_kwargs["pattern"], str):
            normalized_kwargs["pattern"] = {Literal.KEY: normalized_kwargs["pattern"]}

        if "group" in normalized_kwargs and isinstance(normalized_kwargs["group"], int):
            normalized_kwargs["group"] = {Literal.KEY: normalized_kwargs["group"]}

        return (), normalized_kwargs

    @classmethod
    def from_lark(cls, items: Any) -> dict[str, Any]:
        if isinstance(items, dict):
            normalized = dict(items)
        else:
            values = list(items)
            if len(values) not in (2, 3):
                raise ValueError(
                    "regex_extract requires value, pattern, and optional group arguments"
                )
            normalized = {"from": values[0], "pattern": values[1]}
            if len(values) == 3:
                normalized["group"] = values[2]

        pattern_value = normalized.get("pattern")
        if isinstance(pattern_value, str):
            normalized["pattern"] = {Literal.KEY: pattern_value}

        group_value = normalized.get("group")
        if isinstance(group_value, int):
            normalized["group"] = {Literal.KEY: group_value}

        return {cls.KEY: normalized}
