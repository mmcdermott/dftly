# Usage Guide

## Basic Usage

dftly expressions map output column names to transformations over input columns.

```python
import polars as pl
from dftly import Parser

df = pl.DataFrame(
    {
        "col1": [1, 2],
        "col2": [3, 4],
        "foo": ["5", "6"],
        "col3": ["2020-01-01", "2021-06-15"],
        "bp": ["120/80", "NULL"],
    }
)
```

### From YAML strings

```python
ops = """
sum: "$col1 + $col2"
diff: "$foo::int - $col1"
compare: "$col1 > ($col2 - 3) * 3"
"""

df.select(**Parser.to_polars(ops))
```

### From Python dicts

```python
ops = {
    "sum": "$col1 + $col2",
    "diff": "$foo::int - $col1",
}
df.select(**Parser.to_polars(ops))
```

### From YAML files

```python
from pathlib import Path

exprs = Parser.to_polars(Path("transforms.yaml"))
df.select(**exprs)
```

### Single expressions

```python
expr = Parser.expr_to_polars("$col1 + $col2")
df.select(result=expr)
```

## Expression Syntax

### Column references

Columns are referenced with the `$` prefix:

```
$col_name
```

### Arithmetic

```
$a + $b          # addition
$a - $b          # subtraction
$a * $b          # multiplication
$a / $b          # division
$a ** $b         # exponentiation (right-associative, binds tighter than * / /)
-$a              # negation
```

Note that `**` binds tighter than `*`/`/` (right-associative like Python), but unary
minus binds tighter than `**` (Excel semantics): `-2 ** 2` parses as `(-2) ** 2 = 4`,
not Python's `-(2**2) = -4`. Use explicit parens `-(2 ** 2)` for the Python
interpretation.

### Comparisons

```
$a > $b          # greater than
$a < $b          # less than
$a >= $b         # greater than or equal
$a <= $b         # less than or equal
$a == $b         # equal
$a != $b         # not equal
```

### Boolean logic

```
$a and $b        # logical AND (also &&)
$a or $b         # logical OR (also ||)
not $a           # logical NOT (also !)
```

### Functions

```
min($a, $b, $c)       # minimum
max($a, $b, $c)       # maximum
mean($a, $b)          # mean
coalesce($a, $b)      # first non-null value
hash($a)              # hash to UInt64
signed_hash($a)       # hash to Int64 (for Int64-typed output schemas)
```

### String operations

```
f"hello {$name}"                       # string interpolation
/\d+/ in $text                         # regex match (boolean)
extract /(\d+)/ from $text             # regex extract
extract group 1 of /(\d+)-(\d+)/ from $text  # extract specific group
```

### Type casting

Two syntaxes with different precedence:

```
$col::int              # local cast (binds tight, higher precedence than arithmetic)
$col as float          # global cast (binds loose, lower precedence)
$col::days             # cast to duration
```

### Datetime parsing

```
$col::"%Y-%m-%d"                  # parse string to date (strict)
$col::?"%Y-%m-%d"                 # parse string to date (non-strict, null on failure)
$date_col @ 11:30 a.m.            # set time on a date
```

### Datetime component extraction

Extract calendar components from a date or datetime via cast syntax. Every component
name follows the `<field>_of_<period>` pattern and works in both the `::` and `as`
forms (which are semantically equivalent):

```
$event::hour_of_day          # 0-23
$event::minute_of_hour       # 0-59
$event::second_of_minute     # 0-59
$event::day_of_week          # 1 (Monday) - 7 (Sunday)
$event::day_of_month         # 1-31
$event::day_of_year          # 1-366
$event::week_of_year         # 1-53 (ISO week)
$event::month_of_year        # 1-12
$event::quarter_of_year      # 1-4
$event::year_of_date         # e.g. 2024
```

`::year` is reserved for the integer-to-date constructor (`2024::year` →
`date(2024, 1, 1)`), so the year-extraction accessor is spelled `::year_of_date`
to keep the direction unambiguous.

Every accessor also has a function-call form (`dt_hour_of_day($event)`,
`dt_year($event)`, etc.) for programmatic construction or when the cast form
doesn't compose cleanly.

### Duration projection

Project a Duration to a numeric total via `total_<unit>` cast names — the dual
to the existing `::days` / `::seconds` construction (numeric to Duration uses
plural unit names; Duration to numeric uses `total_`-prefixed ones):

```
$delta::total_seconds        # Duration -> Int64
$delta::total_milliseconds
$delta::total_microseconds
$delta::total_nanoseconds
$delta::total_minutes
$delta::total_hours
$delta::total_days
```

Combined with datetime subtraction, this covers most time-derived feature
engineering in one line:

```
($event_time - $dob)::total_microseconds / 31557600000000      # age in years
($t2 - $t1) as total_days                                        # elapsed days
```

Use `::` inside larger expressions (binds tight) and `as` when the cast is the
outermost operation — see the `::` vs `as` precedence note under Type casting.

### Conditionals

```
"big" if $col > 100 else "small"       # if-then-else
"found" if /pattern/ in $text          # if-then (null otherwise)
```

### Fallback format parsing

Compose `coalesce()` with non-strict strptime to try multiple date formats:

```
coalesce($date::?"%Y-%m-%d %H:%M:%S", $date::?"%Y-%m-%d")
```

### Bare words as string literals

In YAML configs, bare words (without `$`, quotes, or parentheses) are treated as string literals:

```yaml
code: MEDS_BIRTH        # equivalent to code: '"MEDS_BIRTH"'
```

### Literals

```
42                   # integer
3.14                 # float
true / false         # boolean
"hello"              # string (single or double quotes)
2024-01-01           # date
11:30 a.m.           # time
2024-01-01 11:30     # datetime
```

## Dict/YAML Form

Every string expression has an equivalent dict form. This is useful for complex expressions
or when you need full control:

```yaml
# String form: "$col1 + $col2"
sum:
  add:
    - column: col1
    - column: col2

# String form: '"big" if $col1 > 1 else "small"'
label:
  conditional:
    when:
      greater_than:
        - column: col1
        - literal: 1
    then:
      literal: big
    otherwise:
      literal: small

# String form: '$date::"%Y-%m-%d"'
parsed:
  strptime:
    format:
      literal: '%Y-%m-%d'
    source:
      column: date
```

## Introspection

### Referenced columns

To find which columns an expression depends on, parse it and read
`referenced_columns` from the resulting node. This walks the AST, so it
sees through `f"..."` interpolation, nested function calls, and dict/class
forms — and won't be fooled by `$` appearing inside a string literal.

```python
from dftly import Parser

Parser()("$a + $b * 3").referenced_columns  # {'a', 'b'}
```
