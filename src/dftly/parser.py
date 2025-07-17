from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Tuple

from importlib.resources import files

from lark import Lark, Transformer

from .nodes import Column, Expression, Literal


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
            return Literal(value["literal"])
        if "column" in value:
            col_val = value["column"]
            if isinstance(col_val, str):
                return Column(col_val, self.input_schema.get(col_val))
            if isinstance(col_val, Mapping):
                name = col_val.get("name")
                typ = col_val.get("type", self.input_schema.get(name))
                return Column(name, typ)
        if "expression" in value:
            expr = value["expression"]
            expr_type = expr.get("type")
            args = expr.get("arguments", [])
            parsed_args = self._parse_arguments(args)
            return Expression(expr_type, parsed_args)
        # dictionary short form for expressions
        if len(value) == 1:
            expr_type, args = next(iter(value.items()))
            parsed_args = self._parse_arguments(args)
            return Expression(expr_type.upper(), parsed_args)
        raise ValueError("invalid mapping input")

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
