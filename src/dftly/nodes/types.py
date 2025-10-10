"""Nodes relating to type casting."""

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

TYPES: dict[str, pl.DataType] = {}
TYPES.update(NUMERIC_TYPES)
TYPES.update(BOOLEAN_TYPES)
TYPES.update(STRING_TYPES)
TYPES.update(DATE_TIME_TYPES)


class Cast(BinaryOp):
    """This non-terminal node casts the left expression to the type specified by the right expression.

    The right node of this expression must evaluate to a string literal outside of any specific polars context
    that is one of the supported types defined in the `TYPES` dictionary.

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(Literal("3").polars_expr).item()
        '3'
        >>> out = pl.select(Cast(Literal("3"), Literal("int")).polars_expr).item()
        >>> type(out)
        <class 'int'>
        >>> out
        3
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
        return self.input.polars_expr.cast(TYPES[self.output_type])
