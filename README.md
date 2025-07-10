# DataFrame Parser-Matcher (DFPM)

> [!WARNING]
> This does not work at all yet. This is just mostly speculative.

A simple library for a safe, expressive, config-file friendly, and readable DSL for encoding simple dataframe
operations. With this library, you can allow your users to write simple, expressive, and safe dataframe
operations in configuration files without needing to write any code and have those operations be executable on
any supported dataframe format.

## Installation
`pip install dfpm`

## Usage

Functionally, this library encodes a simple set of SQL-like operations that can be represneted in a simple
YAML file, to make it easier to communicate common data-pre-processing operations to users. These are largely
_not_ designed to capture dataframe / table level operations -- but rather cell / observation level
manipulations (even though those will then usually be executed over an entire table). This is because this
library is _not_ intended to be a SQL replacement, but rather give a simple, human-readable way to express
only the common operations you might need to express some simple operations you want to apply as a function of
a single row of a dataframe or joined dataframe.

The core library itself _does not_ provide any execution engine, but rather provides the DSL and a simplified
human input form to express the operations. Then, extensions of this library in an engine-specific manner show
how to realize those operations on the given engine. For example, the built-in `polars` extension (which you
can enable simply by installing the `dfpm[polars]` extra argument, or installing polars separately) allows you
to translate any fully resolved expression or input into a `polars` expression that can then be used to
manipulate a `polars` dataframe. In this way, it is possible to extend this library for new dataframe engines
easily without changing its human-readable input format and the DSL it supports.


## Design Concepts

1. Operations can be expressed in a simplified form and a fully-resolved form. The latter is used to
   execute the operations on a dataframe through a variety of engines, and is non-ambiguous. The former is
   used for human readability, and is converted into the latter form before execution via a combination of
   lark parsing rules and a set of prescribed YAML structures.
2. The workflow used by users of this library (and their users) should be (1) express the human-readable
   specification of the desired cell-level operations, (2) resolve those operations into the typed DSL of this
   library, (3) use an execution engine to execute those operations on a dataframe, resulting in a new
   dataframe, which will generally have the same number of rows but with transformed columns reflecting the
   operations specified.
3. The core operations supported in this library are simple arithmetic and string operations, simple table
   joins, simple conditional expressions, column re-mapping, and some basic type manipulation.


### Fully resolved form
The purpose of the fully resolved form is to enable easy mapping of specified operations to dataframe engines
/ operations (e.g., `polars` expressions, SQL queries, etc.), in a manner that is technically unambiguous and
requires minimal technical debt or unnecessary complexity. All fully resolved entities are dictionary like
objects, obeying one of the following simple templates:

#### Literals
Literals are simple string or typed literals (type determined via OmegaConf). They are expressed via a
one-element map with the key `literal` and the value being the literal value itself. For example:

```yaml
literal: $VALUE
```

#### Columns
Columns are simple references to a column in a dataframe. They are expressed via a one-element map with the
key `column` and the value being the column name. For example:
```yaml
column:
  name: $COLUMN_NAME
  type: $COLUMN_TYPE # optional, if not provided, type is inferred from the dataframe

```

#### Tables
Tables are simple references to a table among a collection of dataframes. They are expressed via a one-element
map with the key `table` and the value being a table expression map:

```yaml
table:
  name: $TABLE_NAME
  path: $TABLE_PATH
  columns: ...list of columns to include # optional, if not provided, all columns are included
```

#### Expressions
```yaml
expression:
  type: $EXPR_NAME
  arguments: ...list or map of literals, columns, tables, or expressions

```

Supported expressions include:
##### `ADD`
Adds two or more inputs together. Only supports a list of positional arguments.

##### `SUBTRACT`
Subtracts the second input from the first. Only supports a list of positional arguments.

##### `RESOLVE_TIMESTAMP`
Resovles a lower resolution timestamp to a higher resolution timestamp, e.g. from date to datetime. Only
supports one of several possible set of keyword arguments that clearly indicate the lower and higher
resolution components of the timestamp. Dates and times have resolution controlled via the following
compositional relationships:
```
datetime:
  date:
    year: $YEAR
    month: $MONTH
    day: $DAY
  time:
    hour: $HOUR
    minute: $MINUTE
    second: $SECOND
    microsecond: $MICROSECOND
```

The keyword arguments allowable for this expression must satisfy the property that they are mutually
compatible and not relatively incomplete. E.g., A `date` and a `time` can be passed, as could a `date` and an
`hour`, but a `date` and a `minute` cannot be passed, as, while the latter is compatible with the former, it
is not complete as it is missing the `hour`. Alternatively, a `date` and a `year` cannot be simultaneously
passed as they are not mutually compatible, as the `year` is already contained in the `date`.

##### `REGEX`
Extracts the matches of a regex from a column or checks if a column matches or fails to match a regex.
```yaml
regex: $REGEX # the regex to extract (must be a string and a valid regex)
action: "EXTRACT|MATCH|NOT_MATCH" # the action to perform
input: $EXPR # the input expression to extract from
```

##### `COALESCE`
Identify the first non-null value in a list of expressions.

##### `JOIN`
Joins two or more tables together on one or more keys. Argument spec:

```yaml
tables: # list of tables (as resolved tables)
  - $TABLE_1
  - $TABLE_2
on: # list of join keys
  - $KEY_1
  - $KEY_2
type: "INNER|LEFT|RIGHT|FULL" # the type of join to perform
```

##### `CONDITIONAL`
A conditional expression that takes a boolean predicate, a true value, and a false value, and returns the
appropriate value based on the predicate.
```yaml
predicate: $PREDICATE # the boolean predicate to evaluate
if_true: $TRUE_VALUE # the value to return if the predicate is true
if_false: $FALSE_VALUE # the value to return if the predicate is false
```

##### `STRING_INTERPOLATE`
Interpolates a string with one or more input expressions. Argument spec:

```yaml
pattern: $PATTERN # the string pattern to interpolate, in python syntax, e.g., "${key_1}!"
inputs:
  key_1: $VALUE_1_EXPR
  key_2: $VALUE_2_EXPR
  ...
```

##### `TYPE_CAST`
Casts a value to a specific type. Argument spec:

```yaml
input: $INPUT_EXPR # the input expression to cast
output_type: $OUTPUT_TYPE # the type to cast to, e.g., "int", "float", "str", "bool", etc.
```

##### `VALUE_IN_SET`
Checks if a value is in a set of values. Argument spec:

```yaml
value: $VALUE_EXPR # the value to check
set: # the set of values to check against (as a list)
  - $VALUE_1
  - $VALUE_2
  - ...
```

##### `VALUE_IN_RANGE`
Checks if a (numeric) value is in a range. Argument spec:

```yaml
value: $VALUE_EXPR # the value to check
min: $MIN_EXPR # the minimum value of the range
min_inclusive: $MIN_INCLUSIVE # whether the minimum value is inclusive (default: true)
max: $MAX_EXPR # the maximum value of the range
max_inclusive: $MAX_INCLUSIVE # whether the maximum value is inclusive (default: true)
```

Either or both of `min` or `max` can be omitted, in which case the range is unbounded in that direction.

##### `NOT`/`AND`/`OR`
Logical operations that take one or more boolean expressions and return a boolean value. Arguments are
positional only.

##### `PARSE_WITH_FORMAT_STRING`
Parses a string into a specific type. Argument spec:

```yaml
input: $INPUT_EXPR # the input expression to parse
output_type: $OUTPUT_TYPE # the type to parse to, e.g., "datetime", "float", "int"..
format: $FORMAT # the format to parse the input. Meaning differs based on the output type.
```

##### `HASH_TO_INT`
Generates a hash in int64 format of an input expression. Argument can either be a single positional argument
or follow the argument spec:

```yaml
input: $INPUT_EXPR # the input expression to hash
algorithm: $ALGORITHM # the hash algorithm to use, e.g., "md5", "sha256", etc. Defaults to "sha256"
```


### Simplified Form:
The purpose of the simplified form is to take a concise, human-readable, unambiguous `YAML` file and return a
mapping / structure of the associated referenced fully resolved form. Resolution from the simplified form to
the fully-resolved form always happens in the context of a single table or table expression (which at this
point is only a join of two or more tables) -- this means we always know the columns and input types available
during resoltuion, and can use that information to more intelligently differentiate columns and literals.

> [!NOTE]
> This also implies that there must be some table resolution process for resolving a simplified form of a
> table expression to a fully resolved table or join expression, but this should be much simpler given its
> limited scope.

For example, the following YAML file:

```yaml
code: foobar
value: 221

```

might map to the following fully resolved form:

```yaml
code: {column: {name: foobar, type: null}}
time: {literal: 221}

```

It should always be the case that one can specify a fully resolved form in the simplified specification and it
will be correctly interpreted as itself. This allows one to always provide an unambiguous input when desired.

Here are some specifications we want to support in the simplified form:

```yaml
code: "GENDER//${gender}" # String interpolate with a literal and a column
time: date_col @ 11:59:59 p.m. # Resolve a date column to a datetime with a specific time
time: ${date_col} @ 11:59:59 p.m. # Identical to above, but a more explicit colum identifier?
time: admission_date + offset_to_icu_start minutes + offset_from_icu_start # Complex arithmetic with units.
text_value: "REGEX_EXTRACT(${code}, r'^[A-Z]{3}$')" # Extract a regex from a column
code: [option_1, option_2] # coalesce a list of options
code:
  when: condition # Conditional expression with a predicate
  then: true_value
  else: false_value

```

Much of this resolution process will happen leveraging specific lark grammars over string inputs, along with
specialized processing of YAML structured inputs as well.
