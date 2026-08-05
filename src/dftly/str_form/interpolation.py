"""Splitting ``f"..."`` patterns into a format string and the expressions that fill it.

The grammar lexes an f-string as one opaque ``STRING`` token, so field boundaries have to be
recovered from the text afterwards. That question -- "where does this expression end?" -- is answered
by handing the text to dftly's own parser and seeing where it stops, rather than by scanning for
braces here. ``}`` is not a terminal anywhere in the grammar, and a ``}`` belonging to a string
literal, a regex literal, or a backtick-quoted column name is *inside* a token, so the first ``}``
the parser cannot consume is exactly the one that closes the field.

It has to be the parser and not a bare lexer. dftly's terminals are ambiguous without parser state --
``/`` starts a regex literal in one position and divides in another -- so lexing alone reads
``f"{($a / $a)}{extract /0/ from $x}"`` as holding one regex literal that runs from the division
slash to the one in ``extract``, swallowing the brace that ends the first field. Lark's contextual
lexer only offers terminals the parser can accept next, which settles it.
"""

from __future__ import annotations

from lark.exceptions import UnexpectedCharacters, UnexpectedInput

from .grammar import GRAMMAR


def _find_field_end(pattern: str, start: int) -> int:
    """Return the index of the ``}`` closing the field whose contents begin at ``start``.

    Examples:
        >>> _find_field_end("{$a} rest", 1)
        3

    Braces belonging to a token rather than to the f-string are passed over, because the parser
    consumes the whole token -- this is the entire reason for parsing rather than counting braces:

        >>> _find_field_end("{extract /a{2}/ from $x}", 1)   # regex quantifier
        23
        >>> _find_field_end("{/}/ in $x}", 1)                # brace inside a regex literal
        10
        >>> _find_field_end("{$a ?? '}'}", 1)                # brace inside a string literal
        10
        >>> _find_field_end("{$`}`}", 1)                     # brace inside a quoted column name
        5

    Division does not open a regex literal, though the two share a character. Only the parser state
    distinguishes them, which is why this cannot be a lexer-only scan:

        >>> _find_field_end("{($a / $a)}{extract /0/ from $x}", 1)
        10

    A field that is never closed, and an expression the grammar rejects outright, are both errors:

        >>> _find_field_end("{$a", 1)
        Traceback (most recent call last):
            ...
        ValueError: Unterminated interpolation field starting at position 0 of '{$a'; ...
        >>> _find_field_end("{$a $b}", 1)
        Traceback (most recent call last):
            ...
        ValueError: Invalid expression in the interpolation field starting at position 0 of ...
    """
    try:
        for _ in GRAMMAR.parse_interactive(pattern[start:]).iter_parse():
            pass
    except UnexpectedCharacters as e:
        stop = start + e.pos_in_stream
        if pattern[stop] == "}":
            return stop
        raise ValueError(
            f"Cannot lex {pattern[stop]!r} at position {stop} of {pattern!r}. Interpolation "
            "fields hold dftly expressions; literal text belongs outside the `{...}`."
        ) from e
    except UnexpectedInput as e:
        # The parser rejected a token before reaching any `}`, so the field is not a dftly
        # expression at all. Only the field text can be at fault: whatever follows it begins with
        # the `}` that the *lexer* refuses, which is the branch above.
        raise ValueError(
            f"Invalid expression in the interpolation field starting at position {start - 1} of "
            f"{pattern!r}: {e}"
        ) from e

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
