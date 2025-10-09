from .base import ArgsOnlyFn
import polars as pl
import string


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
    def from_lark(cls, pattern: str) -> dict[str, list]:
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
