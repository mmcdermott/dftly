from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union


@dataclass
class Literal:
    """A literal value."""

    value: Any

    def to_dict(self) -> Dict[str, Any]:
        return {"literal": self.value}


@dataclass
class Column:
    """Reference to a dataframe column."""

    name: str
    type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {"name": self.name}
        if self.type is not None:
            data["type"] = self.type
        return {"column": data}


@dataclass
class Expression:
    """A parsed expression."""

    type: str
    arguments: Union[List[Any], Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {"expression": {"type": self.type, "arguments": self.arguments}}
