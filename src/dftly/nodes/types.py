"""Nodes relating to type casting."""

from typing import Callable
from .base import BinaryOp, NodeBase
import polars as pl

NUMERIC_TYPES: dict[str, pl.DataType] = {
    "uint8": pl.UInt8,
    "uint16": pl.UInt16,
    "uint": pl.UInt32,
    "uint32": pl.UInt32,
    "uint64": pl.UInt64,
    "int8": pl.Int8,
    "int16": pl.Int16,
    "int": pl.Int32,
    "int32": pl.Int32,
    "integer": pl.Int32,
    "int64": pl.Int32,
    "long": pl.Int64,
    "int128": pl.Int128,
    "float": pl.Float32,
    "float32": pl.Float32,
    "float64": pl.Float64,
    "double": pl.Float64,
}

BOOLEAN_TYPES: dict[str, pl.DataType] = {
    "bool": pl.Boolean,
    "boolean": pl.Boolean,
}

STRING_TYPES: dict[str, pl.DataType] = {
    "str": pl.Utf8,
    "string": pl.Utf8,
    "utf8": pl.Utf8,
}

DATE_TIME_TYPES: dict[str, pl.DataType] = {
    "date": pl.Date,
    "datetime": pl.Datetime,
    "duration": pl.Duration,
    "time": pl.Time,
}

# Implicit types

SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 60 * SECONDS_PER_MINUTE
SECONDS_PER_DAY = 24 * SECONDS_PER_HOUR
SECONDS_PER_YEAR = 365.25 * SECONDS_PER_DAY
SECONDS_PER_MONTH = SECONDS_PER_YEAR / 12

IMPLICIT_DURATION_TYPES: dict[str, Callable[[pl.Expr], pl.Expr]] = {
    "seconds": lambda x: pl.duration(seconds=x),
    "minutes": lambda x: pl.duration(minutes=x),
    "hours": lambda x: pl.duration(hours=x),
    "days": lambda x: pl.duration(days=x),
    "weeks": lambda x: pl.duration(weeks=x),
    "months": lambda x: pl.duration(seconds=(SECONDS_PER_MONTH * x)),
    "years": lambda x: pl.duration(seconds=(SECONDS_PER_YEAR * x)),
}

TYPES: dict[str, pl.DataType] = {}
TYPES.update(NUMERIC_TYPES)
TYPES.update(BOOLEAN_TYPES)
TYPES.update(STRING_TYPES)
TYPES.update(DATE_TIME_TYPES)
TYPES.update({k: pl.Duration for k in IMPLICIT_DURATION_TYPES})


class Cast(BinaryOp):
    """This non-terminal node casts the left expression to the type specified by the right expression.

    The right node of this expression must evaluate to a string literal outside of any specific polars context
    that is one of the supported types defined in the `TYPES` dictionary. Most of the supported types are
    standard polars types, but some common aliases are also supported (e.g. "int" for "Int32", "float" for
    "Float32", and "str" for "Utf8").

    In addition, some custom types are added which resolve to standard polars types through a more complex
    mapping; in particular:


    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(Literal("3").polars_expr).item()
        '3'
        >>> out = pl.select(Cast(Literal("3"), Literal("int")).polars_expr).item()
        >>> type(out)
        <class 'int'>
        >>> out
        3

    This class can also be used to convert numeric types into duration types by specifying their unit:

        >>> pl.select(Cast(Literal(3), Literal("days")).polars_expr).item()
        datetime.timedelta(days=3)
        >>> pl.select(Cast(Literal(3), Literal("minutes")).polars_expr).item()
        datetime.timedelta(seconds=180)

    This will work so long as polars understands such a conversion, which can include, e.g., direct string to
    duration conversion:

        >>> pl.select(Cast(Literal("4"), Literal("weeks")).polars_expr).item()
        datetime.timedelta(days=28)

    Months and years are approximated as 30.4375 days and 365.25 days, respectively:

        >>> pl.select(Cast(Literal(1.5), Literal("years")).polars_expr).item()
        datetime.timedelta(days=547, seconds=75600)
        >>> pl.select(Cast(Literal(-0.1), Literal("months")).polars_expr).item()
        datetime.timedelta(days=-4, seconds=82620)
    """

    KEY = "cast"
    SYM = "::"

    def __post_init__(self):
        if self.output_type not in TYPES:
            raise ValueError(f"Unsupported type: {self.output_type}")

    @property
    def input(self) -> NodeBase:
        return self.args[0]

    @property
    def output_type(self) -> str:
        try:
            return pl.select(self.args[1].polars_expr).item()
        except Exception as e:
            raise ValueError(
                "The right node of a Cast operation must evaluate to a string literal."
            ) from e

    @property
    def polars_expr(self) -> pl.Expr:
        if self.output_type in IMPLICIT_DURATION_TYPES:
            return IMPLICIT_DURATION_TYPES[self.output_type](self.input.polars_expr)
        else:
            return self.input.polars_expr.cast(TYPES[self.output_type])
