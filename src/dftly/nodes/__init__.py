from .base import BinaryOp, UnaryOp, Literal, Column, NodeBase
from .arithmetic import (
    Hash,
    SignedHash,
    Not,
    Negate,
    And,
    Or,
    Add,
    Subtract,
    Multiply,
    Divide,
    Mean,
    Min,
    Max,
    Coalesce,
)
from .comparison import (
    GreaterThan,
    LessThan,
    Equal,
    NotEqual,
    GreaterThanOrEqual,
    LessThanOrEqual,
)
from .datetime import (
    SetTime,
    _DtAccessor,
    DtYear,
    DtMonthOfYear,
    DtDayOfMonth,
    DtDayOfWeek,
    DtDayOfYear,
    DtHourOfDay,
    DtMinuteOfHour,
    DtSecondOfMinute,
    DtWeekOfYear,
    DtQuarterOfYear,
    DtTotalSeconds,
    DtTotalMilliseconds,
    DtTotalMicroseconds,
    DtTotalNanoseconds,
    DtTotalMinutes,
    DtTotalHours,
    DtTotalDays,
)
from .str import StringInterpolate, RegexExtract, RegexMatch, Strptime
from .conditional import Conditional
from .types import Cast

__nodes = [
    Literal,
    Column,
    Hash,
    SignedHash,
    Not,
    Negate,
    And,
    Or,
    Mean,
    Min,
    Max,
    Coalesce,
    Add,
    Subtract,
    Multiply,
    Divide,
    GreaterThan,
    LessThan,
    Equal,
    NotEqual,
    GreaterThanOrEqual,
    LessThanOrEqual,
    StringInterpolate,
    RegexExtract,
    RegexMatch,
    Conditional,
    Cast,
    Strptime,
    SetTime,
    DtYear,
    DtMonthOfYear,
    DtDayOfMonth,
    DtDayOfWeek,
    DtDayOfYear,
    DtHourOfDay,
    DtMinuteOfHour,
    DtSecondOfMinute,
    DtWeekOfYear,
    DtQuarterOfYear,
    DtTotalSeconds,
    DtTotalMilliseconds,
    DtTotalMicroseconds,
    DtTotalNanoseconds,
    DtTotalMinutes,
    DtTotalHours,
    DtTotalDays,
]

NODES = NodeBase.unique_dict_by_prop(__nodes)

__binary_ops = [node for node in __nodes if issubclass(node, BinaryOp)]
__binary_ops.extend(
    [Add, Multiply, And, Or]
)  # Additional n-ary ops that can be used as binary ops

BINARY_OPS = NodeBase.unique_dict_by_prop(__binary_ops, "SYM")

__unary_ops = [node for node in __nodes if issubclass(node, UnaryOp)]
UNARY_OPS = NodeBase.unique_dict_by_prop(__unary_ops, "SYM")

# Datetime/duration accessors reachable via `::<name>` cast syntax. Built by scanning every
# `_DtAccessor` subclass with a non-None ``CAST_NAME``; ``DtYear`` is excluded because
# ``::year`` is already the integer→date cast (see ``nodes.types.Cast``).
DT_CAST_ACCESSORS: dict[str, type] = {
    cls.CAST_NAME: cls
    for cls in __nodes
    if issubclass(cls, _DtAccessor) and cls.CAST_NAME is not None
}
