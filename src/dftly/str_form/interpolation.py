"""Splitting ``f"..."`` patterns into a format string and the expressions that fill it.

The grammar lexes an f-string as one opaque ``STRING`` token, so the field boundaries have to be
recovered from the text afterwards. That question -- "where does this expression end?" -- is a
lexing question, and the answer is taken from dftly's own lexer rather than re-derived here: a
``}`` inside a string literal, a regex literal, or a backtick-quoted column name is *inside a
token*, so the lexer walks past it, and the first ``}`` it cannot lex is the one that closes the
field. Nothing in this module needs to know how those forms quote or escape their contents.
"""

from __future__ import annotations

from functools import cache
from importlib.resources import files

from lark import Lark
from lark.exceptions import UnexpectedCharacters

GRAMMAR_TEXT = files(__package__).joinpath("grammar.lark").read_text()


@cache
def _field_lexer() -> Lark:
    """A lexer-only view of the grammar, used to find where an interpolation field ends.

    Built on first use rather than at import: it costs a grammar compile, and an expression set
    with no f-strings never needs it. ``parser=None`` skips the LALR table construction, and the
    basic lexer is used because the contextual one resolves terminals from parser state that does
    not exist here -- irrelevant either way, since only the *position* at which lexing stops is
    read, never the tokens.
    """
    return Lark(GRAMMAR_TEXT, parser=None, lexer="basic")


def _find_field_end(pattern: str, start: int) -> int:
    """Return the index of the ``}`` closing the field whose contents begin at ``start``.

    Examples:
        >>> _find_field_end("{$a} rest", 1)
        3

    Braces that belong to a token rather than to the f-string are skipped, because the lexer
    consumes the whole token -- this is the entire reason for lexing rather than counting braces:

        >>> _find_field_end("{extract /a{2}/ from $x}", 1)   # regex quantifier
        23
        >>> _find_field_end("{/}/ in $x}", 1)                # brace inside a regex literal
        10
        >>> _find_field_end("{$a ?? '}'}", 1)                # brace inside a string literal
        10
        >>> _find_field_end("{$`}`}", 1)                     # brace inside a quoted column name
        5

    A field that is never closed, and a character dftly cannot lex at all, are both errors:

        >>> _find_field_end("{$a", 1)
        Traceback (most recent call last):
            ...
        ValueError: Unterminated interpolation field starting at position 0 of '{$a'; ...
        >>> _find_field_end("{$a # 1}", 1)
        Traceback (most recent call last):
            ...
        ValueError: Cannot lex '#' at position 4 of '{$a # 1}'...
    """
    try:
        list(_field_lexer().lex(pattern[start:]))
    except UnexpectedCharacters as e:
        stop = start + e.pos_in_stream
        if pattern[stop] != "}":
            raise ValueError(
                f"Cannot lex {pattern[stop]!r} at position {stop} of {pattern!r}. Interpolation "
                "fields hold dftly expressions; literal text belongs outside the `{...}`."
            ) from e
        return stop

    raise ValueError(
        f"Unterminated interpolation field starting at position {start - 1} of {pattern!r}; "
        "every `{` must be closed by a matching `}`, or doubled (`{{`) for a literal brace."
    )


def split_interpolation(pattern: str) -> tuple[str, list[str]]:
    """Split an f-string pattern into a ``pl.format`` pattern and its field expressions.

    Each ``{...}`` becomes a ``{}`` placeholder and contributes its contents, verbatim, as a field
    for the parser to resolve as a full dftly expression. ``{{`` and ``}}`` are literal braces, as
    in Python.

        >>> split_interpolation("hello {$name}")
        ('hello {}', ['$name'])
        >>> split_interpolation("{{literal}} {$a} and {$b}")
        ('{literal} {} and {}', ['$a', '$b'])

    Contents are *not* split on ``:`` or ``!`` the way ``str.format`` separates a field from its
    format spec and conversion. Those are ordinary dftly syntax -- ``::`` is a cast -- and reading
    them as formatting directives silently discarded half the expression:

        >>> split_interpolation("{$dose::?float64} {$code[0:3]}")
        ('{} {}', ['$dose::?float64', '$code[0:3]'])

    A lone closing brace, and an empty field, are errors:

        >>> split_interpolation("a } b")
        Traceback (most recent call last):
            ...
        ValueError: Unmatched `}` at position 2 of 'a } b'; write `}}` for a literal brace.
        >>> split_interpolation("a {} b")
        Traceback (most recent call last):
            ...
        ValueError: Empty interpolation field at position 2 of 'a {} b'; ...
    """
    out: list[str] = []
    fields: list[str] = []
    i = 0

    while i < len(pattern):
        char = pattern[i]

        if char == "{":
            if pattern.startswith("{{", i):
                out.append("{")
                i += 2
                continue

            stop = _find_field_end(pattern, i + 1)
            field = pattern[i + 1 : stop]
            if not field.strip():
                raise ValueError(
                    f"Empty interpolation field at position {i} of {pattern!r}; each `{{...}}` "
                    "must hold a dftly expression."
                )
            fields.append(field)
            out.append("{}")
            i = stop + 1
            continue

        if char == "}":
            if pattern.startswith("}}", i):
                out.append("}")
                i += 2
                continue
            raise ValueError(
                f"Unmatched `}}` at position {i} of {pattern!r}; write `}}}}` for a literal brace."
            )

        out.append(char)
        i += 1

    return "".join(out), fields
