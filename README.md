# DataFrame Parser-Matcher (DFPM)
A simple library for a safe, expressive, config-file friendly, and readable DSL for encoding simple dataframe
operations. With this library, you can allow your users to write simple, expressive, and safe dataframe
operations in configuration files without needing to write any code and have those operations be executable on
any supported dataframe format.

## Installation
`pip install dfpm`

## Usage

## Supported DataFrame Formats
Currently, the library only supports Polars. Open an issue to request additional formats.

## Supported Operations
### Simple Column Expressions:
These are used to express simple operations over column. They can take the following forms:
  - `ColExprType.COLUMN` expressions just select a column.
  - `ColExprType.LITERAL` expressions just yield a literal value.
  - `ColExprType.STR` expressions enable string interpolation between columns and string literals using python's f-string
    format (without format type specifiers).
  - `ColExprType.REGEX_EXTRACT` expressions extract a regex from a column's values.

These are expressed in structured forms as follows:

### Simple Matcher Expressions:
These are used to return a boolean mask over a column. They can take the following forms:
  - `MatcherType.EQ` expressions check for equality.
  - `MatcherType.NEQ` expressions check for inequality.
  - `MatcherType.GT` expressions check for greater than.
  - `MatcherType.GTE` expressions check for greater than or equal to.
  - `MatcherType.LT` expressions check for less than.
  - `MatcherType.LTE` expressions check for less than or equal to.
  - `MatcherType.REGEX_MATCH` expressions check for regex matches.
  - `MatcherType.REGEX_NOT_MATCH` expressions check for regex non-matches.

These are expressed in structured forms as follows:

### Compound Expressions:
Column Expressions can be modified via the following compound expressions:
  - `CompoundExprType.COALESCE` coalesces a list of column expressions (either simple or Compound).
  - `CompoundExprType.WHEN_THEN` is a conditional expression that takes a list of matchers and expressions to
    evaluate and return the first expression that matches.

Matchers can be combined via the following compound expressions:
  - `CompoundMatcherType.AND` combines a list of matchers with an AND operation.
  - `CompoundMatcherType.OR` combines a list of matchers with an OR operation.
  - `CompoundMatcherType.NOT` negates a matcher.
