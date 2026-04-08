# DataFrame Transformation Language from YAML (dftly)

[![Python 3.12+](https://img.shields.io/badge/-Python_3.12+-blue?logo=python&logoColor=white)](https://www.python.org/downloads/release/python-3100/)
[![PyPI - Version](https://img.shields.io/pypi/v/dftly)](https://pypi.org/project/dftly/)
[![Documentation Status](https://readthedocs.org/projects/dftly/badge/?version=latest)](https://dftly.readthedocs.io/en/latest/?badge=latest)
[![Tests](https://github.com/mmcdermott/dftly/actions/workflows/tests.yaml/badge.svg)](https://github.com/mmcdermott/dftly/actions/workflows/tests.yaml)
[![Test Coverage](https://codecov.io/github/mmcdermott/dftly/graph/badge.svg?token=BV119L5JQJ)](https://codecov.io/github/mmcdermott/dftly)
[![Code Quality](https://github.com/mmcdermott/dftly/actions/workflows/code-quality-main.yaml/badge.svg)](https://github.com/mmcdermott/dftly/actions/workflows/code-quality-main.yaml)
[![Contributors](https://img.shields.io/github/contributors/mmcdermott/dftly.svg)](https://github.com/mmcdermott/dftly/graphs/contributors)
[![Pull Requests](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/mmcdermott/dftly/pulls)
[![License](https://img.shields.io/badge/License-MIT-green.svg?labelColor=gray)](https://github.com/mmcdermott/dftly#license)

Dftly (pronounced "deftly") is a simple, expressive, human-readable DSL for encoding simple tabular
transformations over dataframes, designed for expression in YAML files. With dftly, you can transform your
data, deftly!

## Installation

```bash
pip install dftly
```

You can also install it locally via [`uv`](https://docs.astral.sh/uv/) via:

```bash
uv sync
```

from the root of the repository.

## Usage

Dftly is designed to make it easy to specify simple dataframe transformations in a YAML file (or a
mapping-like format). In particular, with dftly, you can specify a mapping of output column names to
expressions over input columns, then easily execute that over an input table.

Suppose we have an input dataframe that looks like this:

```python
>>> import polars as pl
>>> from datetime import date
>>> df = pl.DataFrame({
...     "col1": [1, 2],
...     "col2": [3, 4],
...     "foo": ["5", "6"],
...     "col3": ["2020-01-01", "2021-06-15"],
...     "bp": ["120/80", "NULL"],
... })
>>> df
shape: (2, 5)
┌──────┬──────┬─────┬────────────┬────────┐
│ col1 ┆ col2 ┆ foo ┆ col3       ┆ bp     │
│ ---  ┆ ---  ┆ --- ┆ ---        ┆ ---    │
│ i64  ┆ i64  ┆ str ┆ str        ┆ str    │
╞══════╪══════╪═════╪════════════╪════════╡
│ 1    ┆ 3    ┆ 5   ┆ 2020-01-01 ┆ 120/80 │
│ 2    ┆ 4    ┆ 6   ┆ 2021-06-15 ┆ NULL   │
└──────┴──────┴─────┴────────────┴────────┘

```

with dftly, we can write a yaml file like this:

```python
>>> ops = r"""
... sum: "$col1 + $col2"
... diff: "$foo::int - $col1"
... compare: "$col1 > ($col2 - 3) * 3"
... str_interp: 'f"value: {$foo} {$col1}"'
... max: "max($col1, $col2)"
... conditional: '"big" if $col1 > 1 else "small"'
... sys_bp: "extract group 1 of /(\\d+)\\/(\\d+)/ from $bp if /(\\d+)\\/(\\d+)/ in $bp"
... dia_bp: "(extract group 2 of /(\\d+)\\/(\\d+)/ from $bp if /(\\d+)\\/(\\d+)/ in $bp) as float"
... """

```

Then use it to transform the dataframe like so:

```python
>>> from dftly import Parser
>>> df.select(**Parser.to_polars(ops))
shape: (2, 8)
┌─────┬──────┬─────────┬────────────┬─────┬─────────────┬────────┬────────┐
│ sum ┆ diff ┆ compare ┆ str_interp ┆ max ┆ conditional ┆ sys_bp ┆ dia_bp │
│ --- ┆ ---  ┆ ---     ┆ ---        ┆ --- ┆ ---         ┆ ---    ┆ ---    │
│ i64 ┆ i64  ┆ bool    ┆ str        ┆ i64 ┆ str         ┆ str    ┆ f32    │
╞═════╪══════╪═════════╪════════════╪═════╪═════════════╪════════╪════════╡
│ 4   ┆ 4    ┆ true    ┆ value: 5 1 ┆ 3   ┆ small       ┆ 120    ┆ 80.0   │
│ 6   ┆ 4    ┆ false   ┆ value: 6 2 ┆ 4   ┆ big         ┆ null   ┆ null   │
└─────┴──────┴─────────┴────────────┴─────┴─────────────┴────────┴────────┘

```

Other supported operations include string to time parsing, conversion to duration, datetime arithmetic, and
more:

```python
>>> ops = r"""
... as_date: '$col3::"%Y-%m-%d"'
... days_later: '($col3 as "%Y-%m-%d") + $col1::days'
... at_time: '$col3::"%Y-%m-%d" @ 11:30 a.m.'
... """
>>> df.select(**Parser.to_polars(ops))
shape: (2, 3)
┌────────────┬────────────┬─────────────────────┐
│ as_date    ┆ days_later ┆ at_time             │
│ ---        ┆ ---        ┆ ---                 │
│ date       ┆ date       ┆ datetime[μs]        │
╞════════════╪════════════╪═════════════════════╡
│ 2020-01-01 ┆ 2020-01-02 ┆ 2020-01-01 11:30:00 │
│ 2021-06-15 ┆ 2021-06-17 ┆ 2021-06-15 11:30:00 │
└────────────┴────────────┴─────────────────────┘

```

You can also add literal columns:

```python
>>> ops = r"""
... str: '"hello"'
... int: '42'
... float: '3.14'
... bool: 'true'
... time: '11:30 a.m.'
... date: '2024-01-01'
... datetime: '2024-01-01 11:30 a.m.'
... """
>>> df.select(**Parser.to_polars(ops))
shape: (1, 7)
┌───────┬─────┬───────┬──────┬──────────┬────────────┬─────────────────────┐
│ str   ┆ int ┆ float ┆ bool ┆ time     ┆ date       ┆ datetime            │
│ ---   ┆ --- ┆ ---   ┆ ---  ┆ ---      ┆ ---        ┆ ---                 │
│ str   ┆ i32 ┆ f64   ┆ bool ┆ time     ┆ date       ┆ datetime[μs]        │
╞═══════╪═════╪═══════╪══════╪══════════╪════════════╪═════════════════════╡
│ hello ┆ 42  ┆ 3.14  ┆ true ┆ 11:30:00 ┆ 2024-01-01 ┆ 2024-01-01 11:30:00 │
└───────┴─────┴───────┴──────┴──────────┴────────────┴─────────────────────┘

```

### Bare words as string literals

When dftly expressions are embedded in YAML config files, string literals normally require awkward
double-quoting because YAML strips its own quotes before dftly sees the value. To avoid this, dftly
treats **bare words** — identifiers without a `$` prefix, quotes, or parentheses — as string
literals when they appear as a standalone expression:

```python
>>> ops = r"""
... code: MEDS_BIRTH
... label: some_category
... quoted: '"hello"'
... """
>>> pl.select(**Parser.to_polars(ops))
shape: (1, 3)
┌────────────┬───────────────┬────────┐
│ code       ┆ label         ┆ quoted │
│ ---        ┆ ---           ┆ ---    │
│ str        ┆ str           ┆ str    │
╞════════════╪═══════════════╪════════╡
│ MEDS_BIRTH ┆ some_category ┆ hello  │
└────────────┴───────────────┴────────┘

```

This is unambiguous because column references always require the `$` prefix (e.g., `$col_name`),
so a bare word cannot be confused with a column, function call, or any other expression.

**Warning:** If a bare word appears as part of a larger expression (e.g., `$col + TYPO`), dftly
will still interpret it as a string literal but will emit a warning, since this usually indicates a
missing `$` prefix rather than an intentional literal:

```python
>>> import warnings
>>> with warnings.catch_warnings(record=True) as w:
...     warnings.simplefilter("always")
...     expr = Parser.expr_to_polars("$col1 + TYPO")
...     assert len(w) == 1
...     print(w[0].message)
Bare word 'TYPO' interpreted as string literal in a subexpression. Did you mean the column '$TYPO'? Use $TYPO for a column reference or "TYPO" for an explicit string literal.

```

## Detailed Documentation

Internally, this simply parses the yaml file into a mapping, then treats the mapping as a map from desired
output column name to input column expression, parsing each expression via the dftly grammar. In particular,
the below is equivalent to the above:

```python
>>> ops = {
...     "sum": "$col1 + $col2",
...     "diff": "$col2 - $col1",
...     "compare": "$col1 > ($col2 - 3) * 3",
...     "str_interp": 'f"value: {$foo} {$col1}"',
...     "max": "max($col1, $col2)",
...     "conditional": '"big" if $col1 > 1 else "small"',
...     "sys_bp": r"extract group 1 of /(\d+)\/(\d+)/ from $bp if /(\d+)\/(\d+)/ in $bp",
...     "dia_bp": r"extract group 2 of /(\d+)\/(\d+)/ from $bp if /(\d+)\/(\d+)/ in $bp",
... }
>>> from dftly import Parser
>>> parser = Parser()
>>> ops = {k: parser(v).polars_expr for k, v in ops.items()}
>>> df.select(**ops)
shape: (2, 8)
┌─────┬──────┬─────────┬────────────┬─────┬─────────────┬────────┬────────┐
│ sum ┆ diff ┆ compare ┆ str_interp ┆ max ┆ conditional ┆ sys_bp ┆ dia_bp │
│ --- ┆ ---  ┆ ---     ┆ ---        ┆ --- ┆ ---         ┆ ---    ┆ ---    │
│ i64 ┆ i64  ┆ bool    ┆ str        ┆ i64 ┆ str         ┆ str    ┆ str    │
╞═════╪══════╪═════════╪════════════╪═════╪═════════════╪════════╪════════╡
│ 4   ┆ 2    ┆ true    ┆ value: 5 1 ┆ 3   ┆ small       ┆ 120    ┆ 80     │
│ 6   ┆ 2    ┆ false   ┆ value: 6 2 ┆ 4   ┆ big         ┆ null   ┆ null   │
└─────┴──────┴─────────┴────────────┴─────┴─────────────┴────────┴────────┘

```

The way dftly works is that strings are parsed into dictionary forms representing the specified operations,
and an AST over those nodes is built up once they are resolved into dictionary form. This means you can also
specify the operations in a fully explicit manner using these dictionary views for a more expansive, but
precise syntax:

```python
>>> ops = r"""
... sum: # "$col1 + $col2"
...   add:
...     - column: col1
...     - column: col2
... diff: # "$col2 - $col1"
...   subtract:
...     - column: col2
...     - column: col1
... compare: # "$col1 > ($col2 - 3) * 3"
...   greater_than:
...     - column: col1
...     - multiply:
...         - subtract:
...             - column: col2
...             - literal: 3
...         - literal: 3
... str_interp: # 'f"value: {$foo} {$col1}"'
...   string_interpolate:
...     - literal: "value: {} {}"
...     - column: foo
...     - column: col1
... max: # "max($col1, $col2)"
...   max:
...     - column: col1
...     - column: col2
... conditional: # '"big" if $col1 > 1 else "small"'
...   conditional:
...     when:
...       greater_than:
...         - column: col1
...         - literal: 1
...     then:
...       literal: "big"
...     otherwise:
...       literal: "small"
... sys_bp: # "extract group 1 of /(\\d+)\\/(\\d+)/ from $bp if /(\\d+)\\/(\\d+)/ in $bp"
...   conditional:
...     when:
...       regex_match:
...         pattern:
...           literal: (\d+)\/(\d+)
...         source:
...           column: bp
...     then:
...       regex_extract:
...         group_index:
...           literal: 1
...         pattern:
...           literal: (\d+)\/(\d+)
...         source:
...           column: bp
... dia_bp: # "extract group 2 of /(\\d+)\\/(\\d+)/ from $bp if /(\\d+)\\/(\\d+)/ in $bp"
...   conditional:
...     when:
...       regex_match:
...         pattern:
...           literal: (\d+)\/(\d+)
...         source:
...           column: bp
...     then:
...       regex_extract:
...         group_index:
...           literal: 2
...         pattern:
...           literal: (\d+)\/(\d+)
...         source:
...           column: bp
... """
>>> df.select(**Parser.to_polars(ops))
shape: (2, 8)
┌─────┬──────┬─────────┬────────────┬─────┬─────────────┬────────┬────────┐
│ sum ┆ diff ┆ compare ┆ str_interp ┆ max ┆ conditional ┆ sys_bp ┆ dia_bp │
│ --- ┆ ---  ┆ ---     ┆ ---        ┆ --- ┆ ---         ┆ ---    ┆ ---    │
│ i64 ┆ i64  ┆ bool    ┆ str        ┆ i64 ┆ str         ┆ str    ┆ str    │
╞═════╪══════╪═════════╪════════════╪═════╪═════════════╪════════╪════════╡
│ 4   ┆ 2    ┆ true    ┆ value: 5 1 ┆ 3   ┆ small       ┆ 120    ┆ 80     │
│ 6   ┆ 2    ┆ false   ┆ value: 6 2 ┆ 4   ┆ big         ┆ null   ┆ null   │
└─────┴──────┴─────────┴────────────┴─────┴─────────────┴────────┴────────┘

```

Note that literals are parsed by the string parser into either (a) a literal of the appropriate type (int,
float, bool) or into literal nodes which have the syntax `literal: [value]`. In some cases, what looks like a
string in the string syntax is actually parsed directly to a literal; for example, the syntax
`$col3::"%Y-%m-%d" @ 11:30 a.m.` features a string literal for the format, but a _time_ literal for the time.
In this way, using the string syntax is often more concise, as you would need to explicitly construct or cast
a string to a time were you to use the dictionary syntax. Note that these circumstances can be identified by
the lack of quotes around the time literal in the string syntax; string literals will always be quoted, things
without quotes will be interpreted as non-string literals.
