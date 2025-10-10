from .base import ArgsOnlyFn, Literal, KwargsOnlyFn, NodeBase
from typing import ClassVar, Any
import polars as pl
import string
from .types import DATE_TIME_TYPES


class StringInterpolate(ArgsOnlyFn):
    """This non-terminal node represents an f-string interpolation.

    The arguments passed upon construction are (1) the pattern string and (2) the fields used to fill that
    pattern string. Note that during normal construction, the fields cannot be inferred from the pattern
    string; however, this can be done when parsing from a string via the `from_lark` class method used for
    string -> dictionary form conversion.

    Example:
        >>> from dftly.nodes import Literal, Column
        >>> df = pl.DataFrame({"name": ["Alice", "Bob"]})
        >>> df
        shape: (2, 1)
        ┌───────┐
        │ name  │
        │ ---   │
        │ str   │
        ╞═══════╡
        │ Alice │
        │ Bob   │
        └───────┘
        >>> df.select(StringInterpolate(Literal("hello {}"), Column("name")).polars_expr)
        shape: (2, 1)
        ┌─────────────┐
        │ literal     │
        │ ---         │
        │ str         │
        ╞═════════════╡
        │ hello Alice │
        │ hello Bob   │
        └─────────────┘

    The pattern string can also be constructed from other nodes that evaluate to strings:

        >>> from dftly.nodes import Add
        >>> df.select(StringInterpolate(Add(Literal("hello "), Literal("{}")), Column("name")).polars_expr)
        shape: (2, 1)
        ┌─────────────┐
        │ literal     │
        │ ---         │
        │ str         │
        ╞═════════════╡
        │ hello Alice │
        │ hello Bob   │
        └─────────────┘
    """

    KEY = "string_interpolate"

    def __post_init__(self):
        super().__post_init__()

        if len(self.args) <= 1:
            raise ValueError(
                "StringInterpolate requires more than one argument; it takes both the pattern string (first) "
                "and the fields to interpolate into the pattern (subsequent). "
                f"Got {len(self.args)} argument(s): {self.args}. "
                'If you want to infer the fields from the pattern, use a string (e.g., \'f"foo{@bar}" and '
                "the fields will be inferred automatically."
            )

        pattern = self.args[0]

        try:
            pattern = pl.select(pattern.polars_expr).item()
        except Exception as e:
            raise ValueError(
                "The pattern argument must be a string, Literal, or Literal-evaluatable instance. "
                "This `NodeBase` instance can't be evaluated to a string literal."
            ) from e

        if not isinstance(pattern, str):
            raise ValueError(
                "The pattern argument must be a string, Literal, or Literal-evaluatable instance that "
                f"evaluates to a string. This `NodeBase` instance evaluates to a {type(pattern)} instead."
            )

        self.pattern = pattern
        self.fields = [a.polars_expr for a in self.args[1:]]

    @classmethod
    def from_lark(cls, pattern: str | dict) -> dict[str, list]:
        if isinstance(pattern, dict):
            if not Literal.matches(pattern):
                raise ValueError(
                    "When using `from_lark` with a dictionary, the dictionary must resolve to a Literal node."
                )
            pattern = Literal.args_from_value(pattern)[0][0]
        fields = []
        fmt_parts = []
        for literal, field, _, _ in string.Formatter().parse(pattern):
            fmt_parts.append(literal)
            if field is not None:
                fmt_parts.append("{}")
                fields.append(field)

        pattern = "".join(fmt_parts)
        pattern_lit = {"literal": pattern}

        return {cls.KEY: [pattern_lit] + fields}

    @property
    def polars_expr(self) -> pl.Expr:
        return pl.format(self.pattern, *self.fields)


class RegexExtract(KwargsOnlyFn):
    """This node extracts a regex pattern from a target node.

    This node only accepts keyword arguments, and requires "pattern" and "source" keys, with an optional
    "group_index" key. The "pattern" key is the regex pattern to extract, the "source" key is the target node to
    extract from, and the "group_index" key is the index of the regex group to extract. If not provided, the
    entire match is extracted.

    The group_index, if provided, must be or evaluate (outside of a polars context) to a non-negative integer.

    Example:
        >>> from dftly.nodes import Literal, Column
        >>> df = pl.DataFrame({"text": ["foo123bar", "baz456qux"]})
        >>> df
        shape: (2, 1)
        ┌───────────┐
        │ text      │
        │ ---       │
        │ str       │
        ╞═══════════╡
        │ foo123bar │
        │ baz456qux │
        └───────────┘
        >>> pattern = Literal(r"([a-z]+)([0-9]+)([a-z]+)")
        >>> df.select(RegexExtract(pattern=pattern, source=Column("text")).polars_expr)
        shape: (2, 1)
        ┌───────────┐
        │ text      │
        │ ---       │
        │ str       │
        ╞═══════════╡
        │ foo123bar │
        │ baz456qux │
        └───────────┘
        >>> group = Literal(1)
        >>> df.select(RegexExtract(pattern=pattern, source=Column("text"), group_index=group).polars_expr)
        shape: (2, 1)
        ┌──────┐
        │ text │
        │ ---  │
        │ str  │
        ╞══════╡
        │ foo  │
        │ baz  │
        └──────┘
    """

    KEY = "regex_extract"
    REQUIRED_KWARGS = {"pattern", "source"}
    OPTIONAL_KWARGS = {"group_index"}

    def __post_init__(self):
        super().__post_init__()

        if not isinstance(self.group_index, int):
            raise ValueError(
                "The group_index argument must be an integer or a NodeBase instance that evaluates "
                f"to an integer. This `NodeBase` instance evaluates to a {type(self.group_index)} instead."
            )
        if self.group_index < 0:
            raise ValueError("The group_index argument must be a non-negative integer.")

    @property
    def group_index(self) -> int:
        group_index = self.kwargs.get("group_index", 0)

        if isinstance(group_index, int):
            return group_index

        if not isinstance(group_index, NodeBase):
            raise ValueError(
                "The group_index argument must be an integer or a NodeBase instance that evaluates "
                f"to an integer. Got {type(group_index)} instead."
            )

        try:
            return pl.select(group_index.polars_expr).item()
        except Exception as e:
            raise ValueError(
                "The group_index argument must be an integer or a NodeBase instance that evaluates "
                "to an integer. This `NodeBase` instance can't be evaluated to an integer."
            ) from e

    @property
    def polars_expr(self) -> pl.Expr:
        source_expr = self.kwargs["source"].polars_expr
        pattern = self.kwargs["pattern"].polars_expr
        return source_expr.str.extract(pattern, self.group_index)

    @classmethod
    def from_lark(cls, items: list[Any]) -> dict[str, Any]:
        if len(items) == 2:
            kwargs = {"pattern": items[0], "source": items[1]}
        elif len(items) == 3:
            kwargs = {"pattern": items[1], "source": items[2], "group_index": items[0]}

        return {cls.KEY: kwargs}


class RegexMatch(KwargsOnlyFn):
    """This node matches a regex pattern against a target node.

    This node only accepts keyword arguments, and requires "pattern" and "from" keys. The "pattern" key is the
    regex pattern to match, and the "from" key is the target node to match against. The result is a boolean
    indicating whether the pattern matches the target.

    Example:
        >>> from dftly.nodes import Literal, Column
        >>> df = pl.DataFrame({"text": ["foo123bar", "baz456qux", "no_digits"]})
        >>> df
        shape: (3, 1)
        ┌───────────┐
        │ text      │
        │ ---       │
        │ str       │
        ╞═══════════╡
        │ foo123bar │
        │ baz456qux │
        │ no_digits │
        └───────────┘
        >>> pattern = Literal(r"[0-9]+")
        >>> df.select(RegexMatch(pattern=pattern, source=Column("text")).polars_expr)
        shape: (3, 1)
        ┌───────┐
        │ text  │
        │ ---   │
        │ bool  │
        ╞═══════╡
        │ true  │
        │ true  │
        │ false │
        └───────┘
    """

    KEY = "regex_match"
    REQUIRED_KWARGS = {"pattern", "source"}

    @property
    def polars_expr(self) -> pl.Expr:
        source_expr = self.kwargs["source"].polars_expr
        pattern = self.kwargs["pattern"].polars_expr
        return source_expr.str.contains(pattern, literal=False)

    @classmethod
    def from_lark(cls, items: list[Any]) -> dict[str, Any]:
        pattern, source = items

        return {cls.KEY: {"pattern": pattern, "source": source}}


class Strptime(KwargsOnlyFn):
    """This node parses a string into a datetime using a specified format.

    This node only accepts keyword arguments, and requires "format" and "source" keys. The "format" key is the
    datetime format string, and the "source" key is the target node to parse. The result will be either a
    date, time, or datetime type, depending on the format string.

    Example:
        >>> from dftly.nodes import Literal
        >>> date = Strptime(format=Literal("%Y-%m-%d"), source=Literal("2023-01-01"))
        >>> pl.select(date.polars_expr).item()
        datetime.date(2023, 1, 1)
        >>> time = Strptime(format=Literal("%H:%M:%S"), source=Literal("12:34:56"))
        >>> pl.select(time.polars_expr).item()
        datetime.time(12, 34, 56)
        >>> datetime = Strptime(format=Literal("%Y-%m-%d %H:%M:%S"), source=Literal("2023-01-01 12:34:56"))
        >>> pl.select(datetime.polars_expr).item()
        datetime.datetime(2023, 1, 1, 12, 34, 56)

    Note that this can result in ambiguous values given the format string. For example, the example below
    parses a year followed by an hour, which means the resulting datetime will have inferred months and days.

        >>> pl.select(Strptime(format=Literal("%Y %H:%M"), source=Literal("2023 12:11")).polars_expr).item()
        datetime.datetime(2023, 1, 1, 12, 11)
    """

    KEY = "strptime"
    REQUIRED_KWARGS = {"format", "source"}

    # See https://docs.rs/chrono/latest/chrono/format/strftime/index.html
    DATE_PARTS: ClassVar[set[str]] = {
        "Y",  # Year with century
        "G",  # ISO 8601 year with century
        "C",  # Century
        "q",  # Quarter
        "y",  # Year without century
        "g",  # ISO 8601 year without century
        "m",  # Month as a zero-padded decimal number
        "b",  # Abbreviated month name
        "B",  # Full month name
        "h",  # Abbreviated month name
        "d",  # Day of the month as a zero-padded decimal number
        "e",  # Day of the month as a decimal number
        "a",  # Abbreviated weekday name
        "A",  # Full weekday name
        "w",  # Weekday as a decimal number (0=Sunday, 6=Saturday)
        "u",  # Weekday as a decimal number (1=Monday, 7=Sunday)
        "j",  # Day of the year as a zero-padded decimal number
        "U",  # Week number of the year (Sunday as the first day of the week)
        "W",  # Week number of the year (Monday as the first day of the week)
        "V",  # ISO 8601 week number of the year (Monday as the first day of the week)
        "D",  # Equivalent to %m/%d/%y
        "x",  # Locale's appropriate date representation
        "F",  # Equivalent to %Y-%m-%d
        "v",  # VMS date format (%e-%b-%Y)
    }

    TIME_PARTS: ClassVar[set[str]] = {
        "H",  # Hour (24-hour clock) as a zero-padded decimal number
        "k",  # Hour (24-hour clock) as a decimal number
        "I",  # Hour (12-hour clock) as a zero-padded decimal number
        "l",  # Hour (12-hour clock) as a decimal number
        "M",  # Minute as a zero-padded decimal number
        "S",  # Second as a zero-padded decimal number
        "f",  # Microsecond as a decimal number, zero-padded on the left
        "3f",  # Millisecond as a decimal number, zero-padded on the left
        "6f",  # Microsecond as a decimal number, zero-padded on the left
        "9f",  # Nanosecond as a decimal number, zero-padded on the left
        "p",  # AM or PM
        "P",  # am or pm
        "r",  # Equivalent to %I:%M:%S %p
        "R",  # Equivalent to %H:%M
        "T",  # Equivalent to %H:%M:%S
        "X",  # Locale's appropriate time representation
        "z",  # UTC offset in the form +HHMM or -HHMM
        ":z",  # UTC offset in the form +HH:MM or -HH:MM
        "::z",  # UTC offset in the form +HH:MM:SS or -HH:MM:SS
        ":::z",  # UTC offset in the form +HH
        "Z",  # Time zone name
    }

    DATETIME_PARTS: ClassVar[set[str]] = {
        "c",  # Locale's appropriate date and time representation
        "+",  # Equivalent to %Y-%m-%dT%H:%M:%S%:z
        "s",  # Unix timestamp (seconds since January 1, 1970 0:00:00 UTC)
    }

    def __post_init__(self):
        super().__post_init__()

        if not isinstance(self.format_str, str):
            raise ValueError(
                "The format argument must be a NodeBase instance that evaluates to a string. "
                f"This `NodeBase` instance evaluates to a {type(self.format_str)} instead."
            )

    @property
    def format_str(self) -> str:
        fmt = self.kwargs["format"]

        if not isinstance(fmt, NodeBase):
            raise ValueError(
                "The format argument must be a NodeBase instance that evaluates to a string. "
                f"Got {type(fmt)} instead."
            )

        try:
            return pl.select(fmt.polars_expr).item()
        except Exception as e:
            raise ValueError(
                "The format argument must be a NodeBase instance that evaluates to a string. "
                "This `NodeBase` instance can't be evaluated to a string."
            ) from e

    @property
    def output_type(self) -> str:
        fmt = self.format_str
        has_date = any(f"%{part}" in fmt for part in self.DATE_PARTS)
        has_time = any(f"%{part}" in fmt for part in self.TIME_PARTS)
        has_datetime = any(f"%{part}" in fmt for part in self.DATETIME_PARTS)

        if has_datetime or (has_date and has_time):
            return "datetime"
        elif has_date:
            return "date"
        elif has_time:
            return "time"
        else:
            raise ValueError(
                "The format string must contain at least one date or time component. The format string "
                "should be in the syntax used by the `chrono` crate: "
                "https://docs.rs/chrono/latest/chrono/format/strftime/index.html"
            )

    @property
    def polars_expr(self) -> pl.Expr:
        source_expr = self.kwargs["source"].polars_expr

        return source_expr.str.strptime(
            dtype=DATE_TIME_TYPES[self.output_type], format=self.format_str
        )

    @classmethod
    def from_lark(cls, items: list[Any]) -> dict[str, Any]:
        source, format = items

        return {cls.KEY: {"format": format, "source": source}}
