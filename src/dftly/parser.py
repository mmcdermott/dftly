from .nodes.base import NodeBase
from pathlib import Path
import re
import warnings
import polars as pl
from .nodes import NODES
import inspect
from typing import Any
from collections import defaultdict
from .str_form.parser import DftlyGrammar
import yaml

try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:  # pragma: no cover
    from yaml import SafeLoader

_COLUMN_RE = re.compile(r"\$([A-Za-z_]\w*)")


def extract_columns(expr: str) -> set[str]:
    """Extract column names referenced in a dftly expression string.

    This uses a lightweight regex scan for ``$identifier`` patterns, so it works without parsing the
    expression. Useful when you need to know which columns an expression depends on before building a schema.

    Args:
        expr: A dftly expression string.

    Returns:
        A set of column names.

    Examples:
        >>> sorted(extract_columns("$a + $b * 3"))
        ['a', 'b']
        >>> extract_columns("f'hello {$name}'")
        {'name'}
        >>> extract_columns("1 + 2")
        set()
        >>> sorted(extract_columns("$col1 > 0 and $col2 != $col1"))
        ['col1', 'col2']
    """
    return set(_COLUMN_RE.findall(expr))


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
        >>> from dftly.nodes import Add, Multiply, Subtract, Literal
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

    Bare words (identifiers without ``$``, quotes, or parentheses) are treated as string literals
    when they appear as the entire expression. This is especially useful in YAML configs where
    writing ``code: MEDS_BIRTH`` is much cleaner than ``code: '"MEDS_BIRTH"'``:

        >>> full_parser = Parser()
        >>> node = full_parser("MEDS_BIRTH")
        >>> node
        Literal('MEDS_BIRTH')
        >>> pl.select(node.polars_expr).item()
        'MEDS_BIRTH'

    However, when a bare word appears inside a larger expression, a warning is issued because it
    likely indicates a missing ``$`` prefix for a column reference:

        >>> import warnings
        >>> with warnings.catch_warnings(record=True) as w:
        ...     warnings.simplefilter("always")
        ...     node = full_parser("$col + TYPO")
        ...     assert len(w) == 1
        ...     assert "Bare word 'TYPO'" in str(w[0].message)
        >>> node
        Add(Column('col'), Literal('TYPO'))

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

    def __call__(self, value: Any, _nested: bool = False):
        outputs = {}
        errors = {}

        if isinstance(value, str):
            value = DftlyGrammar.parse_str(value)

        if isinstance(value, dict) and list(value.keys()) == ["bare_word"]:
            word = value["bare_word"]
            if _nested:
                warnings.warn(
                    f"Bare word {word!r} interpreted as string literal in a subexpression. "
                    f"Did you mean the column '${word}'? "
                    f'Use ${word} for a column reference or "{word}" for an explicit string literal.',
                    stacklevel=2,
                )
            value = {"literal": word}

        for node in self._matching_nodes(value):
            try:
                node_cls = self.registered_nodes[node]

                if isinstance(value, node_cls):
                    outputs[node] = value
                else:
                    args, kwargs = node_cls.args_from_value(value)

                    if not node_cls.is_terminal:
                        args = [self(arg, _nested=True) for arg in args]
                        kwargs = {k: self(v, _nested=True) for k, v in kwargs.items()}

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
        if len(outputs) > 1:  # pragma: no cover
            raise ValueError(f"multiple matching nodes for {node}: {list(outputs)}")
        return next(iter(outputs.values()))

    @classmethod
    def to_polars(cls, data: str | Path | dict[str, Any]) -> dict[str, pl.Expr]:
        """Parse expressions into a dictionary of Polars expressions.

        Accepts a YAML string, a file path, or a dict mapping column names to expression strings/dicts.

        Args:
            data: A YAML string, a path to a YAML file, or a dict of ``{name: expression}``.

        Returns:
            A dictionary mapping output column names to Polars expressions.

        Raises:
            ValueError: If the YAML content is not a dictionary at the top level.
            FileNotFoundError: If a Path object is passed that does not exist.
            TypeError: If the input is not a string, Path, or dict.

        Examples:
            >>> exprs = Parser.to_polars("sum: '$col1 + $col2'")
            >>> df = pl.DataFrame({"col1": [1, 2], "col2": [3, 4]})
            >>> df.select(**exprs)
            shape: (2, 1)
            ┌─────┐
            │ sum │
            │ --- │
            │ i64 │
            ╞═════╡
            │ 4   │
            │ 6   │
            └─────┘

        A dict can be passed directly (no YAML parsing needed):

            >>> exprs = Parser.to_polars({"diff": "$col1 - $col2"})
            >>> df.select(**exprs)
            shape: (2, 1)
            ┌──────┐
            │ diff │
            │ ---  │
            │ i64  │
            ╞══════╡
            │ -2   │
            │ -2   │
            └──────┘

        It also works with file paths:

            >>> import tempfile, os
            >>> with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            ...     _ = f.write("double: '$x * 2'")
            ...     path = f.name
            >>> exprs = Parser.to_polars(path)
            >>> pl.DataFrame({"x": [5]}).select(**exprs)
            shape: (1, 1)
            ┌────────┐
            │ double │
            │ ---    │
            │ i64    │
            ╞════════╡
            │ 10     │
            └────────┘
            >>> os.unlink(path)

        It also works with Path objects:

            >>> with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            ...     _ = f.write("triple: '$x * 3'")
            ...     path = f.name
            >>> exprs = Parser.to_polars(Path(path))
            >>> pl.DataFrame({"x": [2]}).select(**exprs)
            shape: (1, 1)
            ┌────────┐
            │ triple │
            │ ---    │
            │ i64    │
            ╞════════╡
            │ 6      │
            └────────┘
            >>> os.unlink(path)

        Non-dictionary YAML raises an error:

            >>> Parser.to_polars("- item1")
            Traceback (most recent call last):
                ...
            ValueError: YAML content must be a dictionary at the top level; got <class 'list'>

        A missing file path raises an error:

            >>> Parser.to_polars(Path("/nonexistent/file.yaml"))
            Traceback (most recent call last):
                ...
            FileNotFoundError: YAML file not found: /nonexistent/file.yaml

        Invalid input types raise an error:

            >>> Parser.to_polars(42)
            Traceback (most recent call last):
                ...
            TypeError: data must be a str, Path, or dict; got <class 'int'> instead
        """
        parser = cls()

        if isinstance(data, dict):
            mapping = data
        elif isinstance(data, str):
            try:
                if Path(data).is_file():
                    data = Path(data).read_text()
            except (OSError, ValueError):
                pass  # Not a valid path; treat as raw YAML string
            mapping = yaml.load(data, Loader=SafeLoader)
        elif isinstance(data, Path):
            if data.is_file():
                data = data.read_text()
            else:
                raise FileNotFoundError(f"YAML file not found: {data}")
            mapping = yaml.load(data, Loader=SafeLoader)
        else:
            raise TypeError(
                f"data must be a str, Path, or dict; got {type(data)} instead"
            )

        if not isinstance(mapping, dict):
            raise ValueError(
                f"YAML content must be a dictionary at the top level; got {type(mapping)}"
            )

        exprs = {}
        for name, value in mapping.items():
            exprs[name] = parser(value).polars_expr.alias(name)

        return exprs

    @classmethod
    def expr_to_polars(cls, expr: str) -> pl.Expr:
        """Parse a single expression string into a Polars expression.

        This is a convenience method for compiling one expression without wrapping it in a dict.

        Args:
            expr: A dftly expression string.

        Returns:
            A Polars expression.

        Examples:
            >>> df = pl.DataFrame({"a": [1, 2], "b": [3, 4]})
            >>> df.select(Parser.expr_to_polars("$a + $b"))
            shape: (2, 1)
            ┌─────┐
            │ a   │
            │ --- │
            │ i64 │
            ╞═════╡
            │ 4   │
            │ 6   │
            └─────┘
            >>> pl.select(Parser.expr_to_polars("1 + 2 * 3")).item()
            7
        """
        return cls()(expr).polars_expr
