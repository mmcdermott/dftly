# AGENTS.md

Guidance for AI coding agents (Claude Code, Cursor, Copilot, Warp AI, etc.) working on this
repository.

## Overview

dftly (pronounced "deftly") is a DataFrame Transformation Language parser that provides a
YAML-friendly DSL for expressing simple dataframe operations. The library parses expressions into
an AST (abstract syntax tree) of node objects, each of which can produce a Polars expression.

## Core Design Principle: The Form Hierarchy

**This is the most important thing to understand about dftly's architecture.**

Every expression in dftly can be represented in three equivalent forms, each of which is a
different notation for the same underlying tree:

1. **Base form (dict/YAML)** -- The fully explicit tree representation. Every node type, every
    argument, every keyword argument is spelled out. This is the canonical, unambiguous form.

    ```yaml
    add:
      - column: col1
      - multiply:
          - column: col2
          - literal: 3
    ```

2. **Class form** -- Python objects. Isomorphic to the base form. Every dict key maps to a node
    class, every value maps to constructor arguments.

    ```python
    Add(Column("col1"), Multiply(Column("col2"), Literal(3)))
    ```

3. **String form** -- Human-readable syntax parsed by the Lark grammar. Syntactic sugar over the
    base form.

    ```
    $col1 + $col2 * 3
    ```

### The Rule

**All forms must reduce to the same base-form tree.** This means:

- **Start from the base form.** When adding a new feature, first define what the base-form dict
    looks like. What node class does it correspond to? What are its required/optional kwargs or
    positional args? Only then consider whether string-form sugar is warranted.

- **String form is sugar, not structure.** The grammar and `from_lark` methods must produce dicts
    that the Parser can resolve into the same node objects you would get from the dict form.
    `from_lark` must return a dict keyed by its own node's `KEY` -- never a different node type.

- **No magic in the grammar layer.** If `from_lark` for node X returns `{"Y": ...}` (a different
    node type), that is a design violation. The grammar can provide convenient syntax, but the
    output must be a dict that maps to the node the grammar rule is named after.

- **Every string-form feature must have a dict-form equivalent.** If users can write it in a
    string expression, they must also be able to write the equivalent dict/YAML. If you can't
    define a clean base form for a feature, don't add string syntax for it. Composing existing
    primitives is always preferable to grammar-level magic.

### Example of a violation (and the fix)

Bad -- `Strptime.from_lark` returning a `coalesce` node for multi-format syntax:

```python
# WRONG: grammar rule is "strptime" but output is "coalesce"
def from_lark(cls, items):
    if len(items) > 2:
        return {"coalesce": [{"strptime": ...}, {"strptime": ...}]}
```

Good -- users compose existing primitives:

```
coalesce($dod::?"%Y-%m-%d %H:%M:%S", $dod::?"%Y-%m-%d")
```

Each piece (`coalesce`, non-strict `strptime`) has its own base form and the composition is
explicit.

## Architecture

### Project Structure

```
src/dftly/
  __init__.py          -- Public API: Parser, extract_columns
  parser.py            -- Parser class (dict/YAML/string -> Node objects)
  nodes/
    __init__.py         -- Node registration (NODES dict, BINARY_OPS, UNARY_OPS)
    base.py             -- NodeBase, Terminal, Nonterminal, Literal, Column
    arithmetic.py       -- Add, Subtract, Multiply, Divide, Mean, Min, Max, Hash, etc.
    comparison.py       -- GreaterThan, LessThan, Equal, NotEqual, etc.
    conditional.py      -- Conditional (if/then/else)
    str.py              -- StringInterpolate, RegexExtract, RegexMatch, Strptime
    datetime.py         -- SetTime
    types.py            -- Cast
    utils.py            -- Validation helpers
  str_form/
    grammar.lark        -- LALR(1) grammar for string expressions
    parser.py           -- DftlyGrammar (Lark Transformer: tokens -> base-form dicts)
```

### Parsing Pipeline

```
String expression          Dict/YAML input
       |                         |
  [Lark grammar]                 |
       |                         |
  [DftlyGrammar]                 |
  (tokens -> dicts)              |
       |                         |
       +---- base-form dict -----+
                    |
              [Parser.__call__]
              (dict -> Node objects)
                    |
              Node tree (class form)
                    |
              .polars_expr property
                    |
              pl.Expr (Polars expression)
```

### Node Class Hierarchy

- `NodeBase` (abstract) -- base for all nodes
    - `Terminal` -- nodes whose args are raw values, not other nodes
        - `Literal` -- POD values (int, float, str, bool, None, datetime)
        - `Column` -- column references (`$col_name`)
    - `Nonterminal` -- nodes whose args must be other `NodeBase` instances
        - `ArgsOnlyFn` -- variadic positional args (Add, Min, Max, Mean, Coalesce, Hash)
        - `KwargsOnlyFn` -- keyword args only (Conditional, Strptime, RegexExtract, RegexMatch)
        - `BinaryOp` -- exactly 2 positional args (Subtract, Divide, comparisons, SetTime)
        - `UnaryOp` -- exactly 1 positional arg (Not, Negate)

### Node Registration

Nodes are registered in `nodes/__init__.py`:

1. Add the class to the imports
2. Add it to the `__nodes` list
3. `NODES = NodeBase.unique_dict_by_prop(__nodes)` creates the `{KEY: class}` mapping

Once registered, the node automatically gets:

- Dict-form parsing via `Parser.__call__` (matches on KEY)
- Function-call syntax in the grammar via `DftlyGrammar.func()` (e.g., `min($a, $b)`)

Infix operators additionally need:

- A `SYM` class variable on the node
- Addition to `BINARY_OPS` or `UNARY_OPS` in `__init__.py`
- A grammar rule in `grammar.lark` at the appropriate precedence level

## Adding a New Node Type

Follow this checklist:

1. **Define the base form.** What does the dict look like? Example:

    ```yaml
    my_node:
      - column: a
      - literal: 42
    ```

2. **Create the class** in the appropriate `nodes/*.py` file:

    - Set `KEY = "my_node"`
    - Choose the right base class (`ArgsOnlyFn`, `KwargsOnlyFn`, `BinaryOp`, `UnaryOp`)
    - Implement `polars_expr` property
    - Implement `from_lark` class method (must return `{cls.KEY: ...}`)
    - Add doctests

3. **Register** in `nodes/__init__.py` (import + add to `__nodes`)

4. **String syntax** (optional):

    - If function-call syntax suffices (`my_node($a, $b)`), nothing else needed
    - If infix syntax is desired, add `SYM`, update `BINARY_OPS`/`UNARY_OPS`, add grammar rule

5. **Run tests**: `uv run pytest --tb=short`

## Development Commands

```bash
# Install with dev dependencies
uv sync

# Run all tests (doctests in source + README)
uv run pytest

# Run tests with coverage
uv run pytest --cov=dftly

# Run pre-commit hooks
pre-commit run --all-files
```

## Testing Strategy

- **Doctests are the primary test mechanism.** Every node class and public function should have
    doctests demonstrating usage and edge cases.
- **README.md is tested** via `--doctest-glob=README.md` -- examples must be runnable.
- **conftest.py** provides the doctest namespace (`pl`, `datetime`, `Path`, etc.).
- Prefer doctests over separate test files unless the test is too complex for a docstring.

## Key Conventions

- All node `KEY` values are lowercase strings.
- Column references use `$` prefix in string form (`$col_name`).
- `from_lark` must return `{cls.KEY: args_or_kwargs}` -- never a different node's key.
- `polars_expr` is a property, not a method.
- `pl_fn` is a `ClassVar` on `ArgsOnlyFn` subclasses -- don't use `@classmethod` for it.
- Keyword-only nodes validate via `REQUIRED_KWARGS` and `OPTIONAL_KWARGS` sets.
- Custom transformer methods in `DftlyGrammar` (like `cast_expr`, `strptime_nonstrict`) are
    acceptable when the grammar needs to wrap tokens into the base form, but they must still
    produce dicts keyed by the correct node KEY.

## Common Pitfalls

- **Don't add string syntax without a base form.** If there's no clean dict representation,
    the feature shouldn't exist as syntax sugar.
- **Don't have `from_lark` return a different node type.** This breaks the form hierarchy.
- **Don't evaluate polars expressions in string-form parsing.** The grammar transformer
    (`DftlyGrammar`) should only produce dicts. Polars evaluation happens later via
    `polars_expr`.
- **Don't modify the grammar without considering precedence.** The LALR(1) grammar has
    carefully ordered precedence levels. Adding rules at the wrong level causes ambiguities.

## Important Files

| File                              | Purpose                                                |
| --------------------------------- | ------------------------------------------------------ |
| `src/dftly/__init__.py`           | Public API exports                                     |
| `src/dftly/parser.py`             | Parser class, `extract_columns`, `is_expression`       |
| `src/dftly/nodes/base.py`         | NodeBase hierarchy and terminal nodes                  |
| `src/dftly/nodes/__init__.py`     | Node registration (`NODES`, `BINARY_OPS`, `UNARY_OPS`) |
| `src/dftly/str_form/grammar.lark` | LALR(1) expression grammar                             |
| `src/dftly/str_form/parser.py`    | `DftlyGrammar` Lark transformer                        |
| `conftest.py`                     | Doctest namespace fixtures                             |
| `pyproject.toml`                  | Project config, test settings, dependencies            |
