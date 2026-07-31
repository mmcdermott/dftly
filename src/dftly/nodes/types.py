"""Nodes relating to type casting."""

from typing import Any, Callable
from .base import KwargsOnlyFn, NodeBase
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
    "int64": pl.Int64,
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

IMPLICIT_DATE_TYPES: dict[str, Callable[[pl.Expr], pl.Expr]] = {
    "year": lambda x: pl.date(year=x, month=1, day=1),
}

TYPES: dict[str, pl.DataType] = {}
TYPES.update(NUMERIC_TYPES)
TYPES.update(BOOLEAN_TYPES)
TYPES.update(STRING_TYPES)
TYPES.update(DATE_TIME_TYPES)
TYPES.update({k: pl.Duration for k in IMPLICIT_DURATION_TYPES})
TYPES.update({k: pl.Date for k in IMPLICIT_DATE_TYPES})


class Cast(KwargsOnlyFn):
    """This non-terminal node casts a source expression to the type named by its ``type`` argument.

    The ``type`` node must evaluate to a string literal outside of any specific polars context that is one of
    the supported types defined in the `TYPES` dictionary. Most of the supported types are standard polars
    types, but some common aliases are also supported (e.g. "int" for "Int32", "float" for "Float32", and
    "str" for "Utf8").

    In addition, some custom types are added which resolve to standard polars types through a more complex
    mapping; in particular, duration units ("seconds", "minutes", "hours", "days", "weeks", "months", "years")
    convert numeric values into durations, and "year" converts an integer into a date at the start of that year.

    The optional ``strict`` argument controls what happens to values that cannot be converted. It mirrors
    :class:`~dftly.nodes.str.Strptime`'s ``strict`` argument, and for the same reason -- both lower onto a
    polars ``strict=`` parameter meaning "on failure, produce null instead of raising":

    ==============================  ===============================  ==================
    dftly                           polars                           ``strict=False``
    ==============================  ===============================  ==================
    ``$x::?"%Y-%m-%d"``             ``.str.strptime(..., strict=)``   unparsable -> null
    ``$x::?float64``                ``.cast(..., strict=)``           unconvertible -> null
    ==============================  ===============================  ==================

    ``strict`` defaults to ``True`` (raise), matching polars.

    For convenience, this node also accepts its two required arguments positionally -- ``Cast(source, type)``
    and the base form ``{"cast": [source, type]}`` are sugar for the canonical keyword form. Positional form
    cannot carry ``strict``; use the keyword form for that.

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(Literal("3").polars_expr).item()
        '3'
        >>> out = pl.select(Cast(Literal("3"), Literal("int")).polars_expr).item()
        >>> type(out)
        <class 'int'>
        >>> out
        3

    Standard polars type aliases work as expected:

        >>> pl.select(Cast(Literal("3"), Literal("int64")).polars_expr).item()
        3
        >>> pl.select(Cast(Literal("3.14"), Literal("float64")).polars_expr).item()
        3.14
        >>> pl.select(Cast(Literal(1), Literal("bool")).polars_expr).item()
        True
        >>> pl.select(Cast(Literal(42), Literal("str")).polars_expr).item()
        '42'

    The positional form above is sugar for the canonical keyword form, and normalizes to it:

        >>> Cast(Literal("3"), Literal("int"))
        Cast(source=Literal('3'), type=Literal('int'))
        >>> Cast(source=Literal("3"), type=Literal("int"))
        Cast(source=Literal('3'), type=Literal('int'))

    By default a cast is strict, so a value that cannot be converted raises:

        >>> pl.select(Cast(Literal("1000 MG"), Literal("float64")).polars_expr)
        Traceback (most recent call last):
            ...
        polars.exceptions.InvalidOperationError: conversion from `str` to `f64` failed ...

    Passing ``strict=Literal(False)`` nulls unconvertible values instead. This is the natural
    counterpart to non-strict strptime, and is what ``$x::?float64`` parses to:

        >>> lenient = Cast(source=Literal("1000 MG"), type=Literal("float64"), strict=Literal(False))
        >>> print(pl.select(lenient.polars_expr).item())
        None
        >>> df = pl.DataFrame({"dose": ["25", "1000 MG", "", "1.5E-3", "+5", "inf"]})
        >>> from dftly.nodes import Column
        >>> node = Cast(source=Column("dose"), type=Literal("float64"), strict=Literal(False))
        >>> df.select(node.polars_expr)["dose"].to_list()
        [25.0, None, None, 0.0015, 5.0, inf]

    Unsupported types raise an error:

        >>> Cast(Literal("3"), Literal("unsupported_type"))
        Traceback (most recent call last):
            ...
        ValueError: Unsupported type: unsupported_type

    A non-evaluatable type argument raises an error:

        >>> Cast(Literal("3"), Column("x"))
        Traceback (most recent call last):
            ...
        ValueError: The type argument of a Cast operation must evaluate to a string literal.

    Positional form requires exactly two arguments, and cannot be mixed with the keyword form:

        >>> Cast(Literal("3"))
        Traceback (most recent call last):
            ...
        ValueError: cast requires exactly two positional arguments (source, type); got 1
        >>> Cast(Literal("3"), Literal("int"), source=Literal("4"))
        Traceback (most recent call last):
            ...
        ValueError: cast cannot mix positional and keyword arguments; got positional args with {'source'}

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

    Similarly, numeric types can be converted into date types by specifying the unit as "year", which will
    create a date at the start of that year:

        >>> pl.select(Cast(Literal(2023), Literal("year")).polars_expr).item()
        datetime.date(2023, 1, 1)

    Those implicit units do not lower to a polars ``.cast()`` -- they build a value via
    ``pl.duration()`` / ``pl.date()``, which have no ``strict`` parameter to forward. Rather than
    silently ignoring the flag, asking for a non-strict conversion to one of them is an error:

        >>> Cast(source=Literal(3), type=Literal("minutes"), strict=Literal(False))
        Traceback (most recent call last):
            ...
        ValueError: Non-strict casting is not supported for unit 'minutes'; `strict` applies only to
        dtype casts...

    A non-boolean ``strict`` value raises an error:

        >>> Cast(source=Literal("3"), type=Literal("int"), strict=Literal("yes"))
        Traceback (most recent call last):
            ...
        ValueError: The strict argument must be a boolean, ...
    """

    KEY = "cast"
    SYM = "::"
    REQUIRED_KWARGS = {"source", "type"}
    OPTIONAL_KWARGS = {"strict"}

    def __post_init__(self):
        # `Cast(source, type)` is positional sugar for the canonical keyword form; normalize it
        # before the KwargsOnlyFn validators run (they reject positional args outright).
        if self.args:
            if self.kwargs:
                raise ValueError(
                    f"{self.KEY} cannot mix positional and keyword arguments; got positional args "
                    f"with {set(self.kwargs)}"
                )
            if len(self.args) != 2:
                raise ValueError(
                    f"{self.KEY} requires exactly two positional arguments (source, type); "
                    f"got {len(self.args)}"
                )
            source, output_type = self.args
            self.args = ()
            self.kwargs = {"source": source, "type": output_type}

        super().__post_init__()

        if self.output_type not in TYPES:
            raise ValueError(f"Unsupported type: {self.output_type}")

        if not self.strict and not self._lowers_to_cast:
            raise ValueError(
                f"Non-strict casting is not supported for unit {self.output_type!r}; `strict` "
                "applies only to dtype casts. This unit is built with pl.duration()/pl.date(), "
                "which have no `strict` parameter to forward."
            )

    @property
    def input(self) -> NodeBase:
        return self.kwargs["source"]

    @property
    def output_type(self) -> str:
        try:
            return pl.select(self.kwargs["type"].polars_expr).item()
        except Exception as e:
            raise ValueError(
                "The type argument of a Cast operation must evaluate to a string literal."
            ) from e

    @property
    def _lowers_to_cast(self) -> bool:
        """Whether this node compiles to a real ``.cast()`` (rather than an implicit unit builder)."""
        return (
            self.output_type not in IMPLICIT_DURATION_TYPES
            and self.output_type not in IMPLICIT_DATE_TYPES
        )

    @property
    def strict(self) -> bool:
        strict_node = self.kwargs.get("strict", None)
        if strict_node is None:
            return True  # default: strict=True, matching polars
        if not isinstance(strict_node, NodeBase):
            raise ValueError(
                "The strict argument must be a NodeBase instance that evaluates to a boolean."
            )
        try:
            val = pl.select(strict_node.polars_expr).item()
        except Exception as e:
            raise ValueError("The strict argument must evaluate to a boolean.") from e
        if not isinstance(val, bool):
            raise ValueError(f"The strict argument must be a boolean, got {type(val)}")
        return val

    @property
    def polars_expr(self) -> pl.Expr:
        if self.output_type in IMPLICIT_DURATION_TYPES:
            return IMPLICIT_DURATION_TYPES[self.output_type](self.input.polars_expr)
        elif self.output_type in IMPLICIT_DATE_TYPES:
            return IMPLICIT_DATE_TYPES[self.output_type](self.input.polars_expr)
        else:
            return self.input.polars_expr.cast(
                TYPES[self.output_type], strict=self.strict
            )

    @classmethod
    def from_lark(cls, items: list[Any]) -> dict[str, Any]:
        """Build the canonical keyword base form from the grammar's ``[source, type]`` pair.

        Examples:
            >>> Cast.from_lark([{"column": "dose"}, {"literal": "float64"}])
            {'cast': {'source': {'column': 'dose'}, 'type': {'literal': 'float64'}}}
        """
        source, output_type = items
        return {cls.KEY: {"source": source, "type": output_type}}
