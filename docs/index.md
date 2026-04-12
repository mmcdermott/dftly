# dftly

**dftly** (pronounced "deftly") is a simple, expressive, human-readable DSL for encoding tabular
transformations over dataframes, designed for expression in YAML files.

## Quick Start

```bash
pip install dftly
```

```python
import polars as pl
from dftly import Parser

df = pl.DataFrame({"col1": [1, 2], "col2": [3, 4], "name": ["Alice", "Bob"]})

ops = """
sum: "$col1 + $col2"
greeting: 'f"hello {$name}"'
big: '"yes" if $col1 > 1 else "no"'
"""

df.select(**Parser.to_polars(ops))
```

## Features

- **YAML-friendly syntax** -- expressions are strings that work naturally in config files
- **Human-readable** -- `$col1 + $col2` instead of `pl.col("col1") + pl.col("col2")`
- **Arithmetic, boolean, string, datetime, and regex operations** -- covers common data transforms
- **Three equivalent forms** -- string, dict/YAML, and Python class forms all produce the same AST
- **Polars backend** -- compiles to native Polars expressions for performance

## Next Steps

- [Design Philosophy](design.md) -- understand the form hierarchy
- [Usage Guide](usage.md) -- detailed examples and syntax reference
- [API Reference](api.md) -- public classes and functions
