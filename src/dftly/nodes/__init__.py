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
from .str import (
    StringInterpolate,
    RegexExtract,
    RegexMatch,
    Strptime,
    LenChars,
    Substring,
    Split,
)
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
    LenChars,
    Substring,
    Split,
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
# ``Cast`` carries SYM = "::" but is a KwargsOnlyFn (its canonical base form is
# ``{source, type, strict}``), so it is registered here explicitly rather than being picked up by
# the BinaryOp scan above. Its ``from_lark`` still accepts the ``[left, right]`` pair that the
# binary-op dispatch would hand it.
__binary_ops.append(Cast)

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
def _build_dt_cast_accessors(nodes: list[type] | None = None) -> dict[str, type]:
    """Map ``CAST_NAME`` to accessor class for every registered ``_DtAccessor``.

    Args:
        nodes: The node classes to scan. Defaults to the registered node list; it is a parameter
            so the collision guards below can be exercised without registering a broken node.

    Returns:
        A mapping of cast name to accessor class.

    Raises:
        ValueError: If two accessors declare the same ``CAST_NAME``, or if a ``CAST_NAME``
            collides with a registered type/unit in ``types.TYPES``.

    Examples:
        >>> sorted(_build_dt_cast_accessors())[:3]
        ['day_of_month', 'day_of_week', 'day_of_year']

    Nodes that are not accessors, or that opt out with ``CAST_NAME = None``, are skipped:

        >>> _build_dt_cast_accessors([Add, Column])
        {}

    Two accessors claiming one name is caught rather than silently letting the later win:

        >>> class Dupe(DtYear):
        ...     KEY = "dupe"
        >>> _build_dt_cast_accessors([DtYear, Dupe])
        Traceback (most recent call last):
            ...
        ValueError: Duplicate datetime cast accessor name 'year_of_date': DtYear and Dupe

    So is a name that would be shadowed by a cast target in ``types.TYPES``:

        >>> class Shadowed(DtYear):
        ...     KEY = "shadowed"
        ...     CAST_NAME = "minutes"
        >>> _build_dt_cast_accessors([Shadowed])
        Traceback (most recent call last):
            ...
        ValueError: Datetime cast accessor name 'minutes' for Shadowed collides with a
        registered type/unit in nodes.types.TYPES
    """
    if nodes is None:
        nodes = __nodes
    accessors: dict[str, type] = {}
    for cls in nodes:
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
