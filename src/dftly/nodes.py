from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Dict, List, Mapping, Optional, Union


class NodeBase:
    """Base utilities for node dataclasses."""

    KEY: ClassVar[str]

    @staticmethod
    def _validate_keys(
        mapping: Mapping[str, Any],
        allowed: set[str],
        *,
        label: str,
        required: Optional[set[str]] = None,
    ) -> None:
        required = required or set()
        extra = set(mapping) - allowed
        if extra:
            raise ValueError(f"invalid {label} keys: {extra}")
        missing = required - set(mapping)
        if missing:
            raise ValueError(f"{label} missing required keys: {missing}")

    @classmethod
    def _validate_map(cls, value: Any, **kwargs: Any) -> Any:
        """Optional hook to validate the mapping value."""
        return value

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any], **kwargs: Any) -> "NodeBase":
        cls._validate_keys(
            mapping,
            {cls.KEY},
            label=f"{cls.KEY} mapping",
            required={cls.KEY},
        )
        value = cls._validate_map(mapping[cls.KEY], **kwargs)
        if isinstance(value, Mapping):
            return cls(**value)
        return cls(value)


@dataclass
class Literal(NodeBase):
    """A literal value."""

    KEY: ClassVar[str] = "literal"

    value: Any

    def to_dict(self) -> Dict[str, Any]:
        return {"literal": self.value}


@dataclass
class Column(NodeBase):
    """Reference to a dataframe column."""

    KEY: ClassVar[str] = "column"

    name: str
    type: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError("column name must be a string")
        if self.type is not None and not isinstance(self.type, str):
            raise TypeError("column type must be a string")

    def to_dict(self) -> Dict[str, Any]:
        data = {"name": self.name}
        if self.type is not None:
            data["type"] = self.type
        return {"column": data}

    @classmethod
    def _validate_map(
        cls,
        value: Any,
        *,
        input_schema: Optional[Mapping[str, Optional[str]]] = None,
    ) -> Mapping[str, Any]:
        if isinstance(value, str):
            typ = None if input_schema is None else input_schema.get(value)
            return {"name": value, "type": typ}
        if isinstance(value, Mapping):
            cls._validate_keys(value, {"name", "type"}, label="column", required={"name"})
            name = value["name"]
            typ = value.get("type")
            if typ is None and input_schema is not None:
                typ = input_schema.get(name)
            return {"name": name, "type": typ}
        raise TypeError("column value must be a string or mapping")


@dataclass
class Expression(NodeBase):
    """A parsed expression."""

    KEY: ClassVar[str] = "expression"

    type: str
    arguments: Union[List[Any], Dict[str, Any]]

    def __post_init__(self) -> None:
        if not isinstance(self.type, str):
            raise TypeError("expression type must be a string")
        if not isinstance(self.arguments, (list, dict)):
            raise TypeError("expression arguments must be list or dict")

    def to_dict(self) -> Dict[str, Any]:
        return {"expression": {"type": self.type, "arguments": self.arguments}}

    @classmethod
    def _validate_map(
        cls,
        value: Any,
        *,
        parser: "Parser",  # type: ignore[name-defined]
    ) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise TypeError("expression value must be a mapping")
        cls._validate_keys(value, {"type", "arguments"}, label="expression", required={"type"})
        expr_type = value["type"]
        args = value.get("arguments", [])
        parsed_args = parser._parse_arguments(args)
        return {"type": expr_type, "arguments": parsed_args}
