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
that is fully resolved and unambiguous.

> [!NOTE]
> that dftly will most often be used through downstream packages that make use of the common
> human-readable input format but may do intermediate processing of the YAML files their users specify before
> calling dftly's internal parsing and resolution functions.

> [!WARNING]
> dftly is _not_ designed to perform complex, interdependent operations across multiple dftly
> blocks -- it will neither type check such operations nor provide a meaningful dependency graph for a parsed
> dftly specification, and instead is designed to parse all specified blocks independently.

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

Adds two or more inputs together. Only supports a list of positional arguments, which must obey the following
type restrictions:

1. All inputs are numeric or duration types (in which case the output will be the same type as the inputs).
2. One input is a datetime and the rest are duration values (in which case the output will be a
    datetime type).

> [!NOTE]
> For strings, use the `STRING_INTERPOLATE` expression instead; addition of strings is not supported.

##### `SUBTRACT`

Subtracts the second input from the first. Only supports a list of two positional arguments, which must obey
the following type restrictions:

1. Both inputs are numeric or duration types (in which case the output will be the same type as the inputs).
2. The first input is a datetime and the second is a duration value (in which case the output will be a
    datetime type).

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
if: $PREDICATE # the boolean predicate to evaluate
then: $TRUE_VALUE # the value to return if the predicate is true
else: $FALSE_VALUE # the value to return if the predicate is false. If omitted, `null` is returned when false.
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

##### `VALUE_IN_LITERAL_SET`

Checks if a value is in a set of values. Argument spec:

```yaml
value: $VALUE_EXPR # the value to check
set: # the set of values to check against (as a list -of only literals-
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

The purpose of the simplified form is to take a concise, human-readable representation (designed for use with
`YAML` files, though it will ultimately be parsed from direct python structures) and return the fully resolved
form.

#### Parsing Design Principles

1. All parsing happens in a specific "context", which is simply a map of options that change certain aspects
    of parsing behavior. Typically, parsing is in a `null` context, which means that default behavior is
    used.
2. Parsing a YAML map (or a python dictionary parsed from a YAML file) is done independently for each
    key-value pair in the dictionary, with the key being the output column name and the value being the
    expression to be parsed. If a top-level parse operation is attempted on a non-map value (e.g., a list),
    it will fail.
3. A key constraint of the simplified form is that if a fully-resolved form is specified in the simplified
    form, it _must_ resolve to itself.
4. Value-parsing (meaning not the top-level `parse` call but the internal call used on each of the values in
    the input map) will go through different program flows depending on the type of the value passed. In
    particular, value-parsing (hereafter just referred to as "parsing" despite the ambiguity with the
    top-level operation) will go through a different flow depending on whether the input value is: (a) a
    boolean or numeric literal, (b) a list, (c) a map, or (d) a string. The parsing rules for each of these
    will be described below.

#### Context flags

##### `recursive_list`

Lists are parsed recursively and returned as lists, rather than being parsed into expression form (see below).

##### `literal`

All inputs are parsed as literals, and no further resolution happens.

##### `recurse_to_literal`

Subsequent recursive resolution calls will enable the `literal` context flag.

#### A numeric or boolean literal

These are parsed as typed literals in the fully resolved form, with the value being the literal specified:

```yaml
foo: 1234 # int literal
bar: 12.34 # float literal
baz: true # boolean literal
```

will go to

```yaml
foo: {literal: 1234}
bar: {literal: 12.34}
baz: {literal: true}
```

Note that this implies that if you wish to specify a literal that is a different type than numeric or boolean,
you may need to use the fully-resolved form (especially for lists and maps, which are parsed differently).

#### A list

Lists are resolved (recursively) in one of three ways. First, if the context contains the key
`recursive_list`, then the list will be resolved to a list of fully resolved expressions and returned
as a list. This context is _only_ used for a subset of simplified expression input forms, where the expression
input is expecting a list as one of the arguments.

If that context variable is not enabled (the more common case), then the list is parsed into one of two
expression inputs (though the two are actually mutually consistent, but warrant a separation for clarity):

##### As coalesce operations:

If the list (after recursive parsing) contains only elements that are either literals, columns, or
expressions, then it is parsed as a `COALESCE` operation, which returns the first non-null value in the list.

##### As a conditional expression:

If each element but the last in the list is a map with two elements, one with key `if` -or- `when` and a value
that evaluates to a scalar and one `then` with a value that evaluates to a scalar (the last element in the
list may either be a scalar or another if/then block), then the list is parsed as a `CONDITIONAL` expression
that follows the specified program flow.

> [!NOTE]
> This is actually consistent with the coalesce operation interpretation of this same list, as
> conditional expressions without a `if_false` value yield `null` and thus would not trigger the coalesce.

#### A map

An associative array is parsed in one of two ways:
First, if the map is a valid fully-resolved dftly specification, then it will be returned as is.

Otherwise, it will be parsed into an `expression` input based on a collection of rules matching map structure
(in terms of both number, type, and identity of keys and values) into different expression types and argument
specifications. Typically, these inputs will be structured as a small number of key-value pairs (often only
one) where the key is the type of the expression and the value is the arguments to that expression (though
they will be parsed as well). Note that the context of the expression being parsed into will _change_ how
downstream elements are parsed (e.g., a list of values may be parsed not as a coalesce operation but as a
recursive list, and arguments may be mapped more directly to literals if the expression type mandates literal
inputs). For example:

```yaml
foo:
  value_in_literal_set:
    value: ${bar}
    set:
      - 1
      - foo
      - ${baz}
```

goes to

```yaml
foo:
  expression:
    type: VALUE_IN_LITERAL_SET
    arguments:
      value: {column: {name: bar, type: null}}
      set:
        - {literal: 1}
        - {literal: foo}
        - {literal: '${baz}'} # Note that this is still resolved as a literal given the expr type constraints
```

Note that for expressions that take positional arguments, the value of the map can be a list:

```yaml
foo:
  add:
    - ${bar}
    - 1
    - 2.5
```

Beyond this syntax, which can be applied to all expression types, a subset of expressions have additional
accepted input forms, and some have specific context flags that are triggered on their value parsing. We
outline all expression types below:

##### `ADD`

Enables the context flag `recursive_list` on parsing the value.

##### `SUBTRACT`

Enables the context flag `recursive_list` on parsing the value.

##### `RESOLVE_TIMESTAMP`

**TODO**

##### `REGEX`

**TODO**

##### `COALESCE`

Enables the context flag `recursive_list` on parsing the value.

##### `CONDITIONAL`

**TODO**

##### `STRING_INTERPOLATE`

**TODO**

##### `TYPE_CAST`

**TODO**

##### `VALUE_IN_LITERAL_SET`

Enables the context flags `recursive_list` and `recurse_to_literal`.

##### `VALUE_IN_RANGE`

**TODO**

##### `NOT`/`AND`/`OR`

**TODO**

##### `PARSE_WITH_FORMAT_STRING`

**TODO**

##### `HASH_TO_INT`

**TODO**

#### A string

In many ways, the string is the most fundamental part of the simplified form, as it is where expressions,
operations, and other constructs will typically be specified. Strings are parsed according to a `lark`
grammar, which enables a variety of ways string expressions can be resolved to different forms.

**TODO**

Here are some specifications we want to support in the simplified form:

```yaml
code: "GENDER//${gender}" # String interpolate with a literal and a column
time: date_col @ 11:59:59 p.m. # Resolve a date column to a datetime with a specific time
time: ${date_col} @ 11:59:59 p.m. # Identical to above, but a more explicit column identifier?
time: admission_date + offset_to_icu_start minutes + offset_from_icu_start # Complex arithmetic with units.
text_value: "REGEX_EXTRACT(${code}, r'^[A-Z]{3}$')" # Extract a regex from a column

```
