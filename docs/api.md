# API Reference

## Public API

::: dftly.Parser
    options:
      show_source: false
      members:
        - __init__
        - __call__
        - to_polars
        - expr_to_polars

## Node Types

### Terminal Nodes

::: dftly.nodes.base.Literal
    options:
      show_source: false

::: dftly.nodes.base.Column
    options:
      show_source: false

### Arithmetic

::: dftly.nodes.arithmetic.Add
    options:
      show_source: false

::: dftly.nodes.arithmetic.Subtract
    options:
      show_source: false

::: dftly.nodes.arithmetic.Multiply
    options:
      show_source: false

::: dftly.nodes.arithmetic.Divide
    options:
      show_source: false

::: dftly.nodes.arithmetic.Power
    options:
      show_source: false

::: dftly.nodes.arithmetic.Mean
    options:
      show_source: false

::: dftly.nodes.arithmetic.Min
    options:
      show_source: false

::: dftly.nodes.arithmetic.Max
    options:
      show_source: false

::: dftly.nodes.arithmetic.Coalesce
    options:
      show_source: false

::: dftly.nodes.arithmetic.Hash
    options:
      show_source: false

::: dftly.nodes.arithmetic.SignedHash
    options:
      show_source: false

::: dftly.nodes.arithmetic.Negate
    options:
      show_source: false

::: dftly.nodes.arithmetic.Not
    options:
      show_source: false

::: dftly.nodes.arithmetic.And
    options:
      show_source: false

::: dftly.nodes.arithmetic.Or
    options:
      show_source: false

### Comparison

::: dftly.nodes.comparison.GreaterThan
    options:
      show_source: false

::: dftly.nodes.comparison.LessThan
    options:
      show_source: false

::: dftly.nodes.comparison.Equal
    options:
      show_source: false

::: dftly.nodes.comparison.NotEqual
    options:
      show_source: false

::: dftly.nodes.comparison.GreaterThanOrEqual
    options:
      show_source: false

::: dftly.nodes.comparison.LessThanOrEqual
    options:
      show_source: false

### String Operations

::: dftly.nodes.str.StringInterpolate
    options:
      show_source: false

::: dftly.nodes.str.RegexExtract
    options:
      show_source: false

::: dftly.nodes.str.RegexMatch
    options:
      show_source: false

::: dftly.nodes.str.Strptime
    options:
      show_source: false

### Conditional

::: dftly.nodes.conditional.Conditional
    options:
      show_source: false

### Type Casting

::: dftly.nodes.types.Cast
    options:
      show_source: false

### DateTime

::: dftly.nodes.datetime.SetTime
    options:
      show_source: false

#### Datetime Component Accessors

::: dftly.nodes.datetime.DtYear
    options:
      show_source: false

::: dftly.nodes.datetime.DtMonthOfYear
    options:
      show_source: false

::: dftly.nodes.datetime.DtDayOfMonth
    options:
      show_source: false

::: dftly.nodes.datetime.DtDayOfWeek
    options:
      show_source: false

::: dftly.nodes.datetime.DtDayOfYear
    options:
      show_source: false

::: dftly.nodes.datetime.DtHourOfDay
    options:
      show_source: false

::: dftly.nodes.datetime.DtMinuteOfHour
    options:
      show_source: false

::: dftly.nodes.datetime.DtSecondOfMinute
    options:
      show_source: false

::: dftly.nodes.datetime.DtWeekOfYear
    options:
      show_source: false

::: dftly.nodes.datetime.DtQuarterOfYear
    options:
      show_source: false

#### Duration Total Accessors

::: dftly.nodes.datetime.DtTotalSeconds
    options:
      show_source: false

::: dftly.nodes.datetime.DtTotalMilliseconds
    options:
      show_source: false

::: dftly.nodes.datetime.DtTotalMicroseconds
    options:
      show_source: false

::: dftly.nodes.datetime.DtTotalNanoseconds
    options:
      show_source: false

::: dftly.nodes.datetime.DtTotalMinutes
    options:
      show_source: false

::: dftly.nodes.datetime.DtTotalHours
    options:
      show_source: false

::: dftly.nodes.datetime.DtTotalDays
    options:
      show_source: false

## Base Classes

::: dftly.nodes.base.NodeBase
    options:
      show_source: false
      members:
        - polars_expr
        - referenced_columns
        - matches
        - args_from_value
        - from_lark
