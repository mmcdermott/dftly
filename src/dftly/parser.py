from .nodes.base import NodeBase
from pathlib import Path
import polars as pl
from .nodes import NODES
import inspect
from typing import Any
from collections import defaultdict
from .str_form.parser import DftlyGrammar
import yaml

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader


class Parser:
    """A parser parses a yaml value into a Node object within a set of registered nodes.

    This is intended to be used within a single YAML value; however, node arguments will often be recursive
    given they will be other nodes, that will be parsed in turn by this object. Some limited validation of the
    registered nodes is performed at initialization, including validation that the node keys (used to match
    nodes to yaml values) are unique and that all registered nodes are subclasses of NodeBase. The parser is
    used like a function through its `__call__` method, which takes a single value and returns a single node.

    Args:
        registered_nodes: A dictionary mapping node names to NodeBase subclasses. These nodes will be
          considered when parsing a value.

    Raises:
        TypeError: If any registered node is not a subclass of NodeBase.
        ValueError: If multiple registered nodes share the same KEY.
        ValueError: If no registered nodes match the input value, multiple registered nodes match the input
          value, or if a matching node raises an error during parsing.

    Returns:
        A NodeBase subclass instance parsed from the input value.

    Examples:
        >>> from dftly.nodes.arithmetic import Add, Multiply, Subtract, Literal
        >>> parser = Parser({'add': Add, 'multiply': Multiply, 'subtract': Subtract, 'literal': Literal})
        >>> node = parser({'add': [1, {'multiply': [2, 3]}]})
        >>> node
        Add(Literal(1), Multiply(Literal(2), Literal(3)))
        >>> pl.select(node.polars_expr).item()
        7
        >>> node = parser({'subtract': [10, {'add': [2, 3, 4]}]})
        >>> node
        Subtract(Literal(10), Add(Literal(2), Literal(3), Literal(4)))
        >>> pl.select(node.polars_expr).item()
        1

    The parser can also handle node class objects in the value directly:

        >>> node = parser({'add': [1, Literal(2)]})
        >>> node
        Add(Literal(1), Literal(2))
        >>> pl.select(node.polars_expr).item()
        3

    Strings route to the string parser via the `DftlyGrammar` class, though this class does resolve quoted
    strings into string literals:

        >>> node = parser("1 + 2 * 3")
        >>> node
        Add(Literal(1), Multiply(Literal(2), Literal(3)))
        >>> pl.select(node.polars_expr).item()
        7
        >>> node = parser("'foo'")
        >>> node
        Literal('foo')
        >>> pl.select(node.polars_expr).item()
        'foo'

    The parser parses nodes recursively:

        >>> node = parser({'add': ['"foo"', '"bar"']})
        >>> node
        Add(Literal('foo'), Literal('bar'))
        >>> pl.select(node.polars_expr).item()
        'foobar'
        >>> node = parser({'add': ["1 * 2", "2 - 3"]})
        >>> node
        Add(Multiply(Literal(1), Literal(2)), Subtract(Literal(2), Literal(3)))
        >>> pl.select(node.polars_expr).item()
        1

    If we try to parse a node that depends on something we don't know about, we get an error:

        >>> node = parser({'fake': [2, 3]})
        Traceback (most recent call last):
            ...
        ValueError: No matching node found for value: {'fake': [2, 3]}.

    This also happens within nested nodes, reporting the node that failed:

        >>> node = parser({'add': [1, {'fake': [2, 3]}]})
        Traceback (most recent call last):
            ...
        ValueError: No matching node found for value: {'add': [1, {'fake': [2, 3]}]}.
        Errors from attempted matches:
        - add: No matching node found for value: {'fake': [2, 3]}.

    If we pass invalid nodes or duplicate keys, we get errors:

        >>> parser = Parser({'add': Add, 'sum': "hi there"})
        Traceback (most recent call last):
            ...
        TypeError: registered node sum is not a subclass of NodeBase; got hi there
        >>> parser = Parser({'add': Add, 'sum': Add})
        Traceback (most recent call last):
            ...
        ValueError: multiple nodes registered with key 'add': ['add', 'sum']
    """

    def __init__(self, registered_nodes: dict[str, NodeBase] = NODES):
        self.registered_nodes = registered_nodes

        by_key = defaultdict(list)

        for name, node_cls in registered_nodes.items():
            if not (inspect.isclass(node_cls) and issubclass(node_cls, NodeBase)):
                raise TypeError(
                    f"registered node {name} is not a subclass of NodeBase; got {node_cls}"
                )

            by_key[node_cls.KEY].append(name)

        for key, names in by_key.items():
            if len(names) > 1:
                raise ValueError(f"multiple nodes registered with key '{key}': {names}")

    def _matching_nodes(self, value: Any) -> set[str]:
        matches = set()
        for name, node_obj in self.registered_nodes.items():
            if node_obj.matches(value):
                matches.add(name)
        return matches

    def __call__(self, value: Any):
        outputs = {}
        errors = {}

        if isinstance(value, str):
            value = DftlyGrammar.parse_str(value)

        for node in self._matching_nodes(value):
            try:
                node_cls = self.registered_nodes[node]

                if isinstance(value, node_cls):
                    outputs[node] = value
                else:
                    args, kwargs = node_cls.args_from_value(value)

                    if not node_cls.is_terminal:
                        args = [self(arg) for arg in args]
                        kwargs = {k: self(v) for k, v in kwargs.items()}

                    outputs[node] = node_cls(*args, **kwargs)
            except Exception as e:
                errors[node] = e

        if not outputs:
            err_lines = [f"No matching node found for value: {value}."]
            if errors:
                err_lines.append("Errors from attempted matches:")
                for name, err in errors.items():
                    err_lines.append(f"- {name}: {err}")
            raise ValueError("\n".join(err_lines))
        if len(outputs) > 1:
            raise ValueError(f"multiple matching nodes for {node}: {list(outputs)}")
        return next(iter(outputs.values()))

    @classmethod
    def to_polars(cls, yaml_file: str | Path) -> dict[str, pl.Expr]:
        """Parse a YAML file into a dictionary of Polars expressions."""
        parser = cls()

        if isinstance(yaml_file, str):
            try:
                if Path(yaml_file).is_file:
                    yaml_file = Path(yaml_file).read_text()
            except Exception:
                pass
        elif isinstance(yaml_file, Path):
            if yaml_file.is_file():
                yaml_file = yaml_file.read_text()
            else:
                raise FileNotFoundError(f"YAML file not found: {yaml_file}")
        else:
            raise TypeError(
                f"yaml_file must be a str or Path; got {type(yaml_file)} instead"
            )

        if not isinstance(yaml_file, str):
            raise TypeError(
                f"yaml_file must be a str or Path; got {type(yaml_file)} instead"
            )

        yaml_content = yaml.load(yaml_file, Loader=Loader)

        if not isinstance(yaml_content, dict):
            raise ValueError(
                f"YAML content must be a dictionary at the top level; got {type(yaml_content)}"
            )

        exprs = {}
        for name, value in yaml_content.items():
            exprs[name] = parser(value).polars_expr.alias(name)

        return exprs
