# DataFrame Transformation Language from YAML (dftly)

Dftly (pronounced "deftly") is a simple, expressive, human-readable DSL for encoding simple tabular
transformations over dataframes, designed for expression in YAML files. With dftly, you can transform your
data, deftly!

> [!WARNING]
> This does not work at all yet. This is just mostly speculative.

## Installation

`pip install dftly`

## Usage

**TODO**

## Design Documentation

### Key Principles

Dftly is designed to enable users to easily express a (1) class of simple dataframe operations (2) in a
human-readable way, that (3) can then be used across different execution engines through a middle-layer DSL
that is fully resolved and unambiguous. Note that dftly will most often be used through downstream packages
that make use of the common human-readable input format but may do intermediate processing of the YAML files
their users specify before calling dftly's internal parsing and resolution functions.

#### (1) Class of Simple Dataframe Operations

Dftly is _not_ designed to be a full SQL or dataframe manipulation DSL. Rather, it is only intended to capture
operations that we call "tabular transformations", meaning those that can be expressed as a simple function of
a (subset of) a single row of a dataframe, returning a single value (cell) in an output dataframe at an
analogous row. This excludes operations that are at a table-level, such as pivoting or grouping, as well as
operations that yield outputs over multiple rows, such as `explode` or `unpack` operations.

It also includes some operations that are very common in data pre-processing workflows but are less common in
typical SQL workflows, such as simple arithmetic operations, temporal resolution operations, and string
manipulation.

#### (2) Huamn-readable way

The entire point of dftly is to make it easy to express data pre-processing operations in a communicable but
unambiguous way. This is done by providing both a simplified language and a fully-resolved specification of
dftly supported operations -- with the simplified language designed for use with YAML files. Internally, dftly
will parse the simplified language into a fully-resolved form that can then be executed on a dataframe.

#### (3) Middle-layer DSL and execution engines

When the simplified form is parsed into a fully resolved form, the resulting structure is fully unambiguous
and readily translatable to a dataframe execution context. Notably, the core library itself _does not_ provide
any execution engine, but rather provides only the DSL for the fully resolved form, the parsing library for
the simplified form. Then, extensions of this library in an engine-specific manner enable translation of the
fully resolved form into operations on the given engine. For example, the built-in `polars` extension (which
you can enable simply by installing the `dftly[polars]` extra argument, or installing polars separately)
allows you to translate any fully resolved expression or input into a `polars` expression that can then be
used to manipulate a `polars` dataframe. In this way, it is possible to extend this library for new dataframe
engines easily without changing its human-readable input format and the DSL it supports.

### Typical Workflow

A typical workflow for using dftly (including both internal and external steps) would look like this:

1. A user specifies a YAML file which contains a map (or collection of maps) from output column names to
    dftly specifications for transformations to realize that output column.
2. The library in use (not dftly itself, but the library the user is using that depends on dftly) reads
    the YAML file and may perform some pre-processing (e.g., to extract sections for parsing with dftly from
    those used for other purposes).
3. As needed, the library calls `dftly.parse` on the (loaded) YAML file contents (in python data form --
    e.g., not as strings, but dictionaries, lists, etc.). This will return a map of output column names to
    fully resolved operations. If an extension is enabled, those resolved operations can be naively converted
    to source execution code.
4. The library then uses this output to execute those transformations (either in bulk across all columns or
    on a per-column basis in the output map from dftly) on the input dataframes in use and uses the outputs
    as needed.

### Fully resolved dftly DSL:

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
  type: $COLUMN_TYPE # optional, if missing, type is assumed to be unknown & valid for subsequent operations.

```

#### Expressions

```yaml
expression:
  type: $EXPR_NAME
  arguments: '...list or map of literals, columns, or expressions'

```

Supported expressions include:

##### `ADD`

Adds two or more inputs together. Only supports a list of positional arguments.

##### `SUBTRACT`

Subtracts the second input from the first. Only supports a list of positional arguments.

##### `RESOLVE_TIMESTAMP`

Resolves a lower resolution timestamp to a higher resolution timestamp, e.g. from date to datetime. Only
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
action: EXTRACT|MATCH|NOT_MATCH   # the action to perform
input: $EXPR # the input expression to extract from
```

##### `COALESCE`

Identify the first non-null value in a list of expressions.

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
  - '...'
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
during resolution, and can use that information to more intelligently differentiate columns and literals.

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
time: ${date_col} @ 11:59:59 p.m. # Identical to above, but a more explicit column identifier?
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
