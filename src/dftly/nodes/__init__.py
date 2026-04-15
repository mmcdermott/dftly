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
from .datetime import SetTime
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
]

NODES = NodeBase.unique_dict_by_prop(__nodes)

__binary_ops = [node for node in __nodes if issubclass(node, BinaryOp)]
__binary_ops.extend(
    [Add, Multiply, And, Or]
)  # Additional n-ary ops that can be used as binary ops

BINARY_OPS = NodeBase.unique_dict_by_prop(__binary_ops, "SYM")

__unary_ops = [node for node in __nodes if issubclass(node, UnaryOp)]
UNARY_OPS = NodeBase.unique_dict_by_prop(__unary_ops, "SYM")
