"""This file defines the base class for Nodes in our minimal AST for dataframe operations.

Each node can be expressed in four forms:
    1. Class-form: A class object of the appropriate type.
    2. Resolved-form: An explicit dictionary indicating the type and arguments for the node.
    3. Short-form: A dictionary with a single key indicating the type and a value that is the arguments for
       the node.
    4. Human-readable-form: A string representation of the node, if applicable.
"""

from typing import Any, Callable, ClassVar, Sequence
from datetime import datetime

from abc import ABC, abstractmethod
import polars as pl


EXPRESSION_KEY = "expression"
EXPRESSION_TYPE_KEY = "type"


class NodeBase(ABC):
    """An abstract base class for node dataclasses.

    Nodes are the base class of our minimal abstract syntax tree (AST) for representing the set of data
    transformation operations we support.
    """

    KEY: ClassVar[str]
    is_terminal: ClassVar[bool] = False

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

        self.__post_init__()

    @abstractmethod
    def __post_init__(self):
        """Post-initialization hook for subclasses to validate arguments."""

        if not isinstance(self.KEY, str):
            raise TypeError(f"KEY must be a string; got {type(self.KEY).__name__}")

        if not self.KEY:
            raise ValueError("KEY must be a non-empty string")

        if not isinstance(self.args, Sequence):
            raise TypeError(f"args must be a sequence; got {type(self.args).__name__}")

        if not isinstance(self.kwargs, dict):
            raise TypeError(
                f"kwargs must be a dictionary; got {type(self.kwargs).__name__}"
            )

        if self.KEY != self.KEY.lower():
            raise ValueError(f"KEY must be lowercase; got {self.KEY}")

        if not all(isinstance(k, str) for k in self.kwargs.keys()):
            raise TypeError(f"KEY must be a string; got {type(self.KEY).__name__}")

    @classmethod
    def args_from_value(cls, value: Any) -> tuple[tuple[Any], dict[str, Any]]:
        """Extracts positional and keyword arguments from the given value.

        Args:
            value: The value to extract arguments from. Must match the node type, but not be in class form.

        Returns:
            A tuple of (positional arguments, keyword arguments) to be used in constructing the node.

        Raises:
            ValueError: If the input doesn't match the node type or is in class form.

        Examples:
            >>> class MyNode(NodeBase):
            ...    KEY = "mynode"
            ...    def __post_init__(self): pass
            ...    def polars_expr(self): pass
            >>> MyNode.args_from_value({"mynode": {}})
            ((), {})
            >>> MyNode.args_from_value({"expression": {"type": "mynode"}})
            ((), {})
            >>> MyNode.args_from_value({"mynode": {"arg1": 42, "arg2": "foo"}})
            ((), {'arg1': 42, 'arg2': 'foo'})
            >>> MyNode.args_from_value({"expression": {"type": "mynode", "arguments": ["bar", 3.14]}})
            (('bar', 3.14), {})

        Note that non-list arguments are treated as a single positional argument:

            >>> MyNode.args_from_value({"expression": {"type": "mynode", "arguments": "bar"}})
            (('bar',), {})

        An error is raised if the input doesn't match the node type or is in class form:

            >>> MyNode.args_from_value({"othernode": {}})
            Traceback (most recent call last):
                ...
            ValueError: Input must match node type mynode but be unresolved; got {'othernode': {}}
            >>> MyNode.args_from_value(MyNode())
            Traceback (most recent call last):
                ...
            ValueError: Input must match node type mynode but be unresolved; got ...
        """

        if cls._is_resolved_form(value):
            raw_args = value[EXPRESSION_KEY].get("arguments", None)
        elif cls._is_short_form(value):
            raw_args = value[cls.KEY]
        else:
            raise ValueError(
                f"Input must match node type {cls.KEY} but be unresolved; got {value}"
            )

        if raw_args is None:
            return (), {}
        elif isinstance(raw_args, dict):
            return (), raw_args
        elif isinstance(raw_args, (list, tuple)):
            return tuple(raw_args), {}
        else:
            return (raw_args,), {}

    @classmethod
    def _is_class_form(cls, value: Any) -> bool:
        """Returns True if the passed value is a class-form representation of this node.

        Examples:
            >>> class MyNode(NodeBase):
            ...    KEY = "mynode"
            ...    def __post_init__(self): pass
            ...    def polars_expr(self): pass
            >>> class OtherNode(NodeBase):
            ...    KEY = "othernode"
            ...    def __post_init__(self): pass
            ...    def polars_expr(self): pass
            >>> MyNode._is_class_form(MyNode())
            True
            >>> MyNode._is_class_form(OtherNode())
            False
            >>> MyNode._is_class_form({"expression": {"type": "mynode"}})
            False
            >>> MyNode._is_class_form({"mynode": {}})
            False
            >>> MyNode._is_class_form(42)
            False
        """

        return isinstance(value, cls)

    @classmethod
    def _is_resolved_form(cls, value: dict) -> bool:
        """Returns True if the passed map (value) is a fully resolved-form representation of this node.

        A resolved-form representation is a dictionary with a single key "expression" whose value is
        another dictionary with a "type" key equal to this node's KEY. Note that this may not be a valid
        representation of the node (e.g., if the arguments are in the wrong type), just that it is in the
        correct resolved-form structure.

        Examples:
            >>> class MyNode(NodeBase):
            ...    KEY = "mynode"
            ...    def __post_init__(self): pass
            ...    def polars_expr(self): pass
            >>> MyNode._is_resolved_form({"expression": {"type": "mynode"}})
            True
            >>> MyNode._is_resolved_form({"expression": {"type": "mynode"}, "extra": 1})
            False
            >>> MyNode._is_resolved_form({"expression": {"type": "othernode"}})
            False
            >>> MyNode._is_resolved_form({"expression": "mynode"})
            False
            >>> MyNode._is_resolved_form(MyNode())
            False
            >>> MyNode._is_resolved_form({"mynode": {}})
            False
            >>> MyNode._is_resolved_form(42)
            False
        """

        return (
            isinstance(value, dict)
            and len(value) == 1
            and EXPRESSION_KEY in value
            and isinstance(value[EXPRESSION_KEY], dict)
            and value[EXPRESSION_KEY].get(EXPRESSION_TYPE_KEY, None) == cls.KEY
        )

    @classmethod
    def _is_short_form(cls, value: dict) -> bool:
        """Returns True if the passed map (value) is a short-form representation of this node.

        A short-form representation is a dictionary with a single key equal to this node's KEY, which points
        to the arguments for this node type (which may be of variable type).

        Examples:
            >>> class MyNode(NodeBase):
            ...    KEY = "mynode"
            ...    def __post_init__(self): pass
            ...    def polars_expr(self): pass
            >>> MyNode._is_short_form({"mynode": {}})
            True
            >>> MyNode._is_short_form({"mynode": "foobar"})
            True
            >>> MyNode._is_short_form({"mynode": {}, "extra": 1})
            False
            >>> MyNode._is_short_form({"expression": {"type": "mynode"}})
            False
            >>> MyNode._is_short_form(MyNode())
            False
            >>> MyNode._is_short_form(42)
            False
        """
        return isinstance(value, dict) and len(value) == 1 and cls.KEY in value

    @classmethod
    def matches(cls, value: Any) -> bool:
        """Returns True if the passed value matches any of the accepted forms for this node.

        Examples:
            >>> class MyNode(NodeBase):
            ...    KEY = "mynode"
            ...    def __post_init__(self): pass
            ...    def polars_expr(self): pass
            >>> MyNode.matches({"mynode": {}})
            True
            >>> MyNode.matches({"expression": {"type": "mynode"}})
            True
            >>> MyNode.matches(MyNode())
            True

        False is returned if the form doesn't match any of the accepted forms:

            >>> MyNode.matches({"mynode": {}, "extra": 1})
            False
            >>> MyNode.matches({"expression": {"type": "othernode"}})
            False
            >>> MyNode.matches(42)
            False
        """
        if cls._is_class_form(value):
            return True
        if isinstance(value, dict):
            return cls._is_resolved_form(value) or cls._is_short_form(value)
        return False

    @property
    @abstractmethod
    def polars_expr(self) -> pl.Expr:
        raise NotImplementedError("Subclasses must implement polars_expr")

    def __repr__(self) -> str:
        """Returns a string representation of the node."""
        args_str = ", ".join(repr(arg) for arg in self.args)
        kwargs_str = ", ".join(f"{k}={v!r}" for k, v in self.kwargs.items())
        all_args = ", ".join(filter(None, [args_str, kwargs_str]))
        return f"{self.__class__.__name__}({all_args})"


# Intermediate base shared validators
class _ArgsFn(NodeBase):
    """Base class for nodes that accept only positoinal arguments and apply a simple polars function to them.

    Examples:
        >>> class MyArgsFn(_ArgsFn):
        ...    KEY = "myargsfn"
        ...    pl_fn = lambda *x: sum(x)
        >>> MyArgsFn(1, 2, 3)
        MyArgsFn(1, 2, 3)
        >>> MyArgsFn()
        MyArgsFn()
        >>> MyArgsFn(1, a=1)
        Traceback (most recent call last):
            ...
        ValueError: myargsfn does not accept keyword arguments
        >>> MyArgsFn(1, 2, 3).polars_expr
        6
    """

    pl_fn: ClassVar[Callable[..., pl.Expr]]

    def __post_init__(self):
        super().__post_init__()

        if self.kwargs:
            raise ValueError(f"{self.KEY} does not accept keyword arguments")

    @property
    def polars_expr(self) -> pl.Expr:
        args = [a.polars_expr if isinstance(a, NodeBase) else a for a in self.args]
        return self.__class__.pl_fn(*args)


class _UnaryOp(_ArgsFn):
    """Base class for nodes that map a polars function on exactly one positional argument.

    Examples:
        >>> class MyUnaryOp(_UnaryOp):
        ...    KEY = "myunaryop"
        >>> MyUnaryOp(42)
        MyUnaryOp(42)
        >>> MyUnaryOp(a=42)
        Traceback (most recent call last):
            ...
        ValueError: myunaryop does not accept keyword arguments
        >>> MyUnaryOp(1, 2)
        Traceback (most recent call last):
            ...
        ValueError: myunaryop requires exactly one positional arguments; got 2
    """

    def __post_init__(self):
        super().__post_init__()

        if len(self.args) != 1:
            raise ValueError(
                f"{self.KEY} requires exactly one positional arguments; got {len(self.args)}"
            )


class _BinaryOp(_ArgsFn):
    """Base class for nodes that map a polars function on exactly two positional arguments.

    Examples:
        >>> class MyBinaryOp(_BinaryOp):
        ...    KEY = "mybinaryop"

    MyBinaryOp will error if instantiated with the wrong number of arguments:

        >>> MyBinaryOp(1)
        Traceback (most recent call last):
            ...
        ValueError: mybinaryop requires exactly two positional arguments; got 1
        >>> MyBinaryOp(1, 2, 3)
        Traceback (most recent call last):
            ...
        ValueError: mybinaryop requires exactly two positional arguments; got 3
        >>> MyBinaryOp(a=1, b=2)
        Traceback (most recent call last):
            ...
        ValueError: mybinaryop does not accept keyword arguments
        >>> MyBinaryOp(1, 2)
        MyBinaryOp(1, 2)
    """

    def __post_init__(self):
        super().__post_init__()

        if len(self.args) != 2:
            raise ValueError(
                f"{self.KEY} requires exactly two positional arguments; got {len(self.args)}"
            )


# Terminal Nodes
class Literal(_UnaryOp):
    """This node represents a literal value.

    The literal value has a special syntax for matching, as generic base-types can be matched to the literal
    value.
    """

    KEY = "literal"
    is_terminal = True
    pl_fn = pl.lit

    @classmethod
    def _is_pod_type(cls, value: Any) -> bool:
        """Returns True if the passed value is a "plain-old-data" (POD) type that can map to a literal.

        "Plain-old-data" types include int, float, str, bool, datetime, and None.

        Examples:
            >>> Literal._is_pod_type(42)
            True
            >>> Literal._is_pod_type(3.14)
            True
            >>> Literal._is_pod_type("foo")
            True
            >>> Literal._is_pod_type(True)
            True
            >>> Literal._is_pod_type(False)
            True
            >>> Literal._is_pod_type(None)
            True
            >>> Literal._is_pod_type(datetime(2023, 1, 1))
            True
            >>> Literal._is_pod_type({"literal": 42})
            False
            >>> Literal._is_pod_type([1, 2, 3])
            False
        """
        return isinstance(value, (int, float, str, bool, type(None), datetime))

    @classmethod
    def matches(cls, value: Any) -> bool:
        """Returns True if the passed value matches any of the accepted forms for this node, including POD.

        Examples:
            >>> Literal.matches(42)
            True
            >>> Literal.matches("foo")
            True
            >>> Literal.matches({"literal": [1, 2, 3]})
            True
            >>> Literal.matches({"expression": {"type": "column"}})
            False
        """

        return cls._is_pod_type(value) or super().matches(value)

    @classmethod
    def args_from_value(cls, value: Any) -> tuple[tuple[Any], dict[str, Any]]:
        """Extracts positional arguments from the given value.

        This method is overridden to handle POD values as a special case, mapping them to a single
        positional argument, and to ensure that even if a dictionary is passed as the argument to a different
        form, it is parsed as a positional argument, not a keyword argument, unlike other nodes.

        Args:
            value: The value to extract arguments from. Must match the node type, but not be in class form.

        Returns:
            A tuple of (positional arguments, keyword arguments) to be used in constructing the node. For this
            node type, only positional arguments will be returned.

        Raises:
            ValueError: If the input doesn't match the node type or is in class form.

        Examples:
            >>> Literal.args_from_value(42)
            ((42,), {})
            >>> Literal.args_from_value("foo")
            (('foo',), {})
            >>> Literal.args_from_value({"literal": [1, 2, 3]})
            (([1, 2, 3],), {})
            >>> Literal.args_from_value({"literal": {"arg1": 42}})
            (({'arg1': 42},), {})
            >>> Literal.args_from_value({"other": {"arg1": 42}})
            Traceback (most recent call last):
                ...
            ValueError: Input must match node type literal but be unresolved; got {'other': {'arg1': 42}}
        """

        if cls._is_pod_type(value):
            return ((value,), {})
        elif cls._is_resolved_form(value):
            return ((value[EXPRESSION_KEY].get("arguments", None),), {})
        elif cls._is_short_form(value):
            return ((value[cls.KEY],), {})
        else:
            raise ValueError(
                f"Input must match node type {cls.KEY} but be unresolved; got {value}"
            )


def _col(x: str) -> pl.Expr:
    """This is necessary because for some reason using pl.col directly fails."""
    return pl.col(x)


class Column(_UnaryOp):
    """This node represents a column in a dataframe."""

    KEY = "column"
    is_terminal = True
    pl_fn = _col


# Base classes for more complex non-terminal nodes
class NestedArgsNode(NodeBase):
    """Base class for nodes whose positional or keyword arguments must be nested node types.

    Examples:
        >>> class MyNestedArgsNode(NestedArgsNode):
        ...    KEY = "mynestedargsnode"
        ...    @property
        ...    def polars_expr(self): return pl.lit(42)
        >>> MyNestedArgsNode(Column("foo"), Literal(42), extra=Column("bar"))
        MyNestedArgsNode(Column('foo'), Literal(42), extra=Column('bar'))
        >>> MyNestedArgsNode(1, 2)
        Traceback (most recent call last):
            ...
        TypeError: all arguments to mynestedargsnode must be NodeBase instances
        >>> MyNestedArgsNode(Column("foo"), extra=42)
        Traceback (most recent call last):
            ...
        TypeError: all keyword arguments to mynestedargsnode must be str:NodeBase pairs
    """

    def __post_init__(self):
        super().__post_init__()

        if not all(isinstance(arg, NodeBase) for arg in self.args):
            raise TypeError(f"all arguments to {self.KEY} must be NodeBase instances")
        if not (
            all(isinstance(k, str) for k in self.kwargs.keys())
            and all(isinstance(v, NodeBase) for v in self.kwargs.values())
        ):
            raise TypeError(
                f"all keyword arguments to {self.KEY} must be str:NodeBase pairs"
            )


class BinaryOp(NestedArgsNode, _BinaryOp):
    """Base class for non-terminal binary operation nodes."""


class UnaryOp(NestedArgsNode, _UnaryOp):
    """Base class for non-terminal unary operation nodes."""


class ArgsOnlyFn(NestedArgsNode, _ArgsFn):
    """Base class for non-terminal nodes that accept only positional arguments."""
