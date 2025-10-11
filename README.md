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
... sum: "@col1 + @col2"
... diff: "@foo::int - @col1"
... compare: "@col1 > (@col2 - 3) * 3"
... str_interp: 'f"value: {@foo} {@col1}"'
... max: "max(@col1, @col2)"
... conditional: '"big" if @col1 > 1 else "small"'
... sys_bp: "extract group 1 of /(\\d+)\\/(\\d+)/ from @bp if /(\\d+)\\/(\\d+)/ in @bp"
... dia_bp: "(extract group 2 of /(\\d+)\\/(\\d+)/ from @bp if /(\\d+)\\/(\\d+)/ in @bp) as float"
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
... as_date: '@col3 as "%Y-%m-%d"'
... days_later: '(@col3 as "%Y-%m-%d") + @col1::days'
... """
>>> df.select(**Parser.to_polars(ops))
shape: (2, 2)
┌────────────┬────────────┐
│ as_date    ┆ days_later │
│ ---        ┆ ---        │
│ date       ┆ date       │
╞════════════╪════════════╡
│ 2020-01-01 ┆ 2020-01-02 │
│ 2021-06-15 ┆ 2021-06-17 │
└────────────┴────────────┘

```

## Detailed Documentation

Internally, this simply parses the yaml file into a mapping, then treats the mapping as a map from desired
output column name to input column expression, parsing each expression via the dftly grammar. In particular,
the below is equivalent to the above:

```python
>>> ops = {
...     "sum": "@col1 + @col2",
...     "diff": "@col2 - @col1",
...     "compare": "@col1 > (@col2 - 3) * 3",
...     "str_interp": 'f"value: {@foo} {@col1}"',
...     "max": "max(@col1, @col2)",
...     "conditional": '"big" if @col1 > 1 else "small"',
...     "sys_bp": r"extract group 1 of /(\d+)\/(\d+)/ from @bp if /(\d+)\/(\d+)/ in @bp",
...     "dia_bp": r"extract group 2 of /(\d+)\/(\d+)/ from @bp if /(\d+)\/(\d+)/ in @bp",
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
... sum: # "@col1 + @col2"
...   add:
...     - column: col1
...     - column: col2
... diff: # "@col2 - @col1"
...   subtract:
...     - column: col2
...     - column: col1
... compare: # "@col1 > (@col2 - 3) * 3"
...   greater_than:
...     - column: col1
...     - multiply:
...         - subtract:
...             - column: col2
...             - literal: 3
...         - literal: 3
... str_interp: # 'f"value: {@foo} {@col1}"'
...   string_interpolate:
...     - literal: "value: {} {}"
...     - column: foo
...     - column: col1
... max: # "max(@col1, @col2)"
...   max:
...     - column: col1
...     - column: col2
... conditional: # '"big" if @col1 > 1 else "small"'
...   conditional:
...     when:
...       greater_than:
...         - column: col1
...         - literal: 1
...     then:
...       literal: "big"
...     otherwise:
...       literal: "small"
... sys_bp: # "extract group 1 of /(\\d+)\\/(\\d+)/ from @bp if /(\\d+)\\/(\\d+)/ in @bp"
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
... dia_bp: # "extract group 2 of /(\\d+)\\/(\\d+)/ from @bp if /(\\d+)\\/(\\d+)/ in @bp"
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
