from __future__ import annotations

from typing import (
    Any,
    Callable,
    ClassVar,
    Iterable,
    List,
    Optional,
    TYPE_CHECKING,
    Type,
    TypeVar,
)

from ..nodes import Expression


if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    from ..parser import Parser
else:  # pragma: no cover - runtime fallback to keep annotations working
    Parser = Any


class ExpressionNode:
    """Base class for expression handlers.

    Subclasses provide hooks for creating :class:`Expression` instances from
    mapping short forms or parse-tree events as well as translating the final
    expression to a backend specific representation.
    """

    type: ClassVar[str]
    aliases: ClassVar[Iterable[str]] = ()

    @classmethod
    def _normalize(cls, name: str) -> str:
        return name.upper()

    # ------------------------------------------------------------------
    @classmethod
    def matches_mapping(
        cls,
        parser: "Parser",  # type: ignore[name-defined]
        expr_type: str,
        args: Any,
    ) -> bool:
        """Return ``True`` if ``expr_type`` should be handled by this class."""

        normalized = cls._normalize(expr_type)
        alias_set = {cls.type, *(cls._normalize(a) for a in cls.aliases)}
        return normalized in alias_set

    # ------------------------------------------------------------------
    @classmethod
    def from_mapping(
        cls,
        parser: "Parser",  # type: ignore[name-defined]
        expr_type: str,
        args: Any,
    ) -> Expression:
        parsed_args = parser._parse_arguments(args)
        return Expression(cls.type, parsed_args)

    # ------------------------------------------------------------------
    @classmethod
    def from_tree(
        cls,
        parser: "Parser",  # type: ignore[name-defined]
        event: str,
        items: List[Any],
        **kwargs: Any,
    ) -> Any:
        """Return an expression (or node) from a grammar event.

        The default implementation does not handle any events and therefore
        returns ``None``.
        """

        return None

    # ------------------------------------------------------------------
    @classmethod
    def to_polars(
        cls,
        expr: Expression,
        to_polars: Callable[[Any], Any],
        *,
        pl: Any,
    ) -> Any:
        raise ValueError(f"Unsupported expression type: {expr.type}")


T = TypeVar("T", bound=Type[ExpressionNode])


class ExpressionRegistry:
    """Registry of all expression handlers."""

    _registry: List[Type[ExpressionNode]] = []

    @classmethod
    def register(cls, node_cls: T) -> T:
        cls._registry.append(node_cls)
        return node_cls

    @classmethod
    def iter(cls) -> List[Type[ExpressionNode]]:
        return list(cls._registry)

    @classmethod
    def create_from_mapping(
        cls,
        parser: "Parser",  # type: ignore[name-defined]
        expr_type: str,
        args: Any,
    ) -> Optional[Expression]:
        for node_cls in cls._registry:
            if node_cls.matches_mapping(parser, expr_type, args):
                return node_cls.from_mapping(parser, expr_type, args)
        return None

    @classmethod
    def create_from_tree(
        cls,
        event: str,
        parser: "Parser",  # type: ignore[name-defined]
        items: List[Any],
        **kwargs: Any,
    ) -> Any:
        for node_cls in cls._registry:
            result = node_cls.from_tree(parser, event, items, **kwargs)
            if result is not None:
                return result
        return None

    @classmethod
    def get(cls, type_name: str) -> Optional[Type[ExpressionNode]]:
        normalized = type_name.upper()
        for node_cls in cls._registry:
            alias_set = {
                node_cls.type,
                *(node_cls._normalize(a) for a in node_cls.aliases),
            }
            if normalized in alias_set:
                return node_cls
        return None

    @classmethod
    def to_polars(
        cls,
        expr: Expression,
        to_polars_func: Callable[[Any], Any],
        *,
        pl: Any,
    ) -> Any:
        node_cls = cls.get(expr.type)
        if node_cls is None:
            raise ValueError(f"Unsupported expression type: {expr.type}")
        return node_cls.to_polars(expr, to_polars_func, pl=pl)


__all__ = ["ExpressionNode", "ExpressionRegistry"]
