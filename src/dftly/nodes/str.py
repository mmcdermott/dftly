from .base import ArgsOnlyFn, NodeBase
import polars as pl
import string


class StringInterpolate(ArgsOnlyFn):
    """This non-terminal node represents an f-string interpolation.

    Example:
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
        >>> df.select(StringInterpolate(Literal("hello {name}")).polars_expr)
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
        >>> df.select(StringInterpolate(Add(Literal("hello "), Literal("{name}"))).polars_expr)
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

        if len(self.args) != 1:
            raise ValueError(
                "StringInterpolate requires exactly one argument: the pattern string."
            )

        pattern = self.args[0]

        if isinstance(pattern, str):
            self.pattern = pattern
            return

        if not isinstance(pattern, NodeBase):
            raise ValueError(
                "The pattern argument must be a string, Literal, or Literal-evaluatable instance."
                f" Got {type(pattern)}."
            )

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

    @property
    def polars_expr(self) -> pl.Expr:
        order = []
        fmt_parts = []
        for literal, field, _, _ in string.Formatter().parse(self.pattern):
            fmt_parts.append(literal)
            if field is not None:
                fmt_parts.append("{}")
                order.append(field)
        pattern = "".join(fmt_parts)

        exprs = [pl.col(field) for field in order] if order else []
        return pl.format(pattern, *exprs)
