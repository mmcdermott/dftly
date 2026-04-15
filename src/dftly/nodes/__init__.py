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
    Power,
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
from .types import Cast, TYPES

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
    Power,
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


# Datetime/duration accessors reachable via `::<name>` cast syntax. Built from the nodes
# registered in ``__nodes`` that subclass ``_DtAccessor`` and declare a non-None
# ``CAST_NAME``. ``DtYear`` uses ``::year_of_date`` rather than ``::year`` because
# ``::year`` is already the integer→date cast (see ``nodes.types.Cast``). The builder
# raises at import time if any ``CAST_NAME`` collides with another accessor or with a
# registered type/unit in ``types.TYPES``, so cast-syntax dispatch can never be silently
# shadowed by a future addition to either side.
def _build_dt_cast_accessors() -> dict[str, type]:
    accessors: dict[str, type] = {}
    for cls in __nodes:
        if not issubclass(cls, _DtAccessor) or cls.CAST_NAME is None:
            continue
        if cls.CAST_NAME in accessors:
            raise ValueError(
                f"Duplicate datetime cast accessor name {cls.CAST_NAME!r}: "
                f"{accessors[cls.CAST_NAME].__name__} and {cls.__name__}"
            )
        if cls.CAST_NAME in TYPES:
            raise ValueError(
                f"Datetime cast accessor name {cls.CAST_NAME!r} for "
                f"{cls.__name__} collides with a registered type/unit in "
                f"nodes.types.TYPES"
            )
        accessors[cls.CAST_NAME] = cls
    return accessors


DT_CAST_ACCESSORS: dict[str, type] = _build_dt_cast_accessors()
