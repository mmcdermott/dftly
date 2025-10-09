from .base import BinaryOp, UnaryOp, Literal, Column
from .arithmetic import Add, Subtract, Multiply, Divide
from .comparison import (
    GreaterThan,
    LessThan,
    Equal,
    NotEqual,
    GreaterThanOrEqual,
    LessThanOrEqual,
)

__nodes = [
    Literal,
    Column,
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
]

NODES = {node.KEY: node for node in __nodes}

__binary_ops = [node for node in __nodes if issubclass(node, BinaryOp)]
__binary_ops.extend([Add, Multiply])  # Add and Multiply are n-ary but also binary
BINARY_OPS = {node.SYM: node for node in __binary_ops}
UNARY_OPS = {node.SYM: node for node in __nodes if issubclass(node, UnaryOp)}
