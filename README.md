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
...     "col3": [date(2020, 1, 1), date(2021, 6, 15)],
...     "bp": ["120/80", "NULL"],
... })
>>> df
shape: (2, 5)
┌──────┬──────┬─────┬────────────┬────────┐
│ col1 ┆ col2 ┆ foo ┆ col3       ┆ bp     │
│ ---  ┆ ---  ┆ --- ┆ ---        ┆ ---    │
│ i64  ┆ i64  ┆ str ┆ date       ┆ str    │
╞══════╪══════╪═════╪════════════╪════════╡
│ 1    ┆ 3    ┆ 5   ┆ 2020-01-01 ┆ 120/80 │
│ 2    ┆ 4    ┆ 6   ┆ 2021-06-15 ┆ NULL   │
└──────┴──────┴─────┴────────────┴────────┘

```

with dftly, we can do this:

```python
>>> ops = {
...     "sum": "@col1 + @col2",
...     "diff": "@col2 - @col1",
...     "compare": "@col1 > (@col2 - 3) * 3",
...     "str_interp": 'f"value: {@foo} {@col1}"',
... }
>>> from dftly import Parser
>>> parser = Parser()
>>> ops = {k: parser(v).polars_expr for k, v in ops.items()}
>>> df.select(**ops)
shape: (2, 4)
┌─────┬──────┬─────────┬────────────┐
│ sum ┆ diff ┆ compare ┆ str_interp │
│ --- ┆ ---  ┆ ---     ┆ ---        │
│ i64 ┆ i64  ┆ bool    ┆ str        │
╞═════╪══════╪═════════╪════════════╡
│ 4   ┆ 2    ┆ true    ┆ value: 5 1 │
│ 6   ┆ 2    ┆ false   ┆ value: 6 2 │
└─────┴──────┴─────────┴────────────┘

```
