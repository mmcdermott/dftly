"""Property tests for f-string field splitting.

The invariant: putting an expression inside an interpolation field must not change it. Whatever
``$x`` parses to on its own, ``f"{$x}"`` must carry exactly that as its field -- so the splitter is
correct iff it finds the field boundaries and hands the contents through untouched.

Three implementations have broken that property, each in a way the previous one's tests did not cover.
``str.format``'s field rules truncated contents at the first ``:`` (``$a::int`` became ``$a``, the
cast silently discarded) and rejected a ``{2}`` quantifier as a nested field. The brace-counting
scanner that replaced it knew string literals quote their braces, but not that regex literals and
backtick-quoted column names do too. Lexing without parser state then mistook the ``/`` of a division
for the start of a regex literal, running one field's boundary into the next -- a case no one wrote
an example for, and the one this test found on its own.

That progression is the argument for generating rather than enumerating: each fix was checked against
the failures already known, and each left a differently-shaped one open. The strategy below mixes
braces into every token type that can hide them, and pairs operators whose characters overlap, so the
gap does not have to be anticipated to be found.

The generated expressions only need to *parse*; they are never evaluated, and no claim is made about
what they mean. Regenerating them as text and re-parsing is enough to catch a splitter that drops,
truncates, or rewrites what it was given.
"""

import warnings

import pytest
from hypothesis import assume, example, given, settings
from hypothesis import strategies as st

from dftly import Parser
from dftly.str_form.parser import DftlyGrammar

# Column references, including backtick-quoted names holding the braces and spaces that a naive
# scanner would mistake for field delimiters.
COLUMNS = st.sampled_from(
    ["$a", "$b", "$col_1", "$`Variable Name`", "$`{weird}`", "$`a}b`", "$`{`"]
)

# String literals are single-quoted throughout: the wrapper below is a double-quoted f-string, and
# the grammar lexes it as one STRING token, so a `"` anywhere inside would end it early. That is a
# real limitation of the f-string form (see #75), not something this test should paper over.
LITERALS = st.sampled_from(
    [
        "1",
        "42",
        "1.5",
        "true",
        "false",
        "'plain'",
        "'has {brace}'",
        "'}'",
        "'{'",
        "'{{'",
        "'a b'",
    ]
)

# Regex bodies stay within what the REGEX_LITERAL terminal accepts (no `/`, backslash, or newline)
# and lean on the characters that matter here: braces, both balanced and not.
REGEX_BODIES = st.text(alphabet="ab01{}()|.^$*+?-", min_size=1, max_size=6)

CAST_TARGETS = st.sampled_from(["int", "str", "float64", "?float64", "days", "year"])


def _extend(children: st.SearchStrategy[str]) -> st.SearchStrategy[str]:
    """Build a larger expression from smaller ones.

    Compound forms are parenthesized so that every draw parses regardless of how its parts bind -- precedence
    is not what is under test here, and an unparsable draw would only be thrown away.
    """
    return st.one_of(
        st.tuples(
            children,
            st.sampled_from(["+", "-", "*", "/", "==", ">", "and", "or", "??"]),
            children,
        ).map(lambda t: f"({t[0]} {t[1]} {t[2]})"),
        st.tuples(children, CAST_TARGETS).map(lambda t: f"({t[0]})::{t[1]}"),
        st.tuples(children, children).map(lambda t: f"coalesce({t[0]}, {t[1]})"),
        st.tuples(children, children).map(lambda t: f"min({t[0]}, {t[1]})"),
        st.tuples(REGEX_BODIES, children).map(
            lambda t: f"extract /{t[0]}/ from {t[1]}"
        ),
        st.tuples(st.integers(0, 2), REGEX_BODIES, children).map(
            lambda t: f"extract group {t[0]} of /{t[1]}/ from {t[2]}"
        ),
        st.tuples(REGEX_BODIES, children).map(lambda t: f"/{t[0]}/ in {t[1]}"),
        st.tuples(children, st.integers(0, 3), st.integers(4, 9)).map(
            lambda t: f"({t[0]})[{t[1]}:{t[2]}]"
        ),
        st.tuples(children, children, children).map(
            lambda t: f"({t[0]} if {t[1]} else {t[2]})"
        ),
    )


EXPRESSIONS = st.recursive(st.one_of(COLUMNS, LITERALS), _extend, max_leaves=4)

# Literal stretches of an f-string pattern, including the doubled braces that stand for one brace.
LITERAL_TEXT = st.lists(
    st.sampled_from(["", "OBS//", " ", "x", "{{", "}}", "-", "{{}}"]), max_size=3
).map("".join)


def _parses(expression: str) -> bool:
    try:
        DftlyGrammar.parse_str(expression)
    except Exception:
        return False
    return True


# Capture groups without a `group_index` warn by design (#99); the strategy generates them freely.
pytestmark = pytest.mark.filterwarnings("ignore::UserWarning")


@settings(deadline=None, max_examples=150)
@given(expression=EXPRESSIONS)
@example(
    expression="$a::int"
)  # cast: silently truncated by `str.format` field splitting
@example(
    expression="extract /^([0-9]{2})/ from $a"
)  # quantifier: rejected as a nested field
@example(
    expression="/}/ in $a"
)  # brace inside a regex literal: truncated by brace counting
@example(expression="$`a}b`")  # brace inside a backtick column name: likewise
@example(expression="($a ?? '}')")  # brace inside a string literal
def test_field_holds_the_same_expression_it_would_alone(expression: str) -> None:
    """``f"{e}"`` interpolates exactly the node ``e`` parses to on its own."""
    assume(_parses(expression))

    interpolated = DftlyGrammar.parse_str(f'f"{{{expression}}}"')

    # The base form keeps fields as raw text for the Parser to resolve, so the text must survive
    # verbatim -- this is the assertion that a truncating splitter fails.
    assert interpolated == {"string_interpolate": [{"literal": "{}"}, expression]}

    # ... and resolving it must give back the very tree the expression yields when parsed alone.
    parser = Parser()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        node = parser(interpolated)
        alone = parser(expression)
    assert repr(node.args[1]) == repr(alone)


@settings(deadline=None, max_examples=75)
@given(
    first=EXPRESSIONS,
    second=EXPRESSIONS,
    prefix=LITERAL_TEXT,
    middle=LITERAL_TEXT,
    suffix=LITERAL_TEXT,
)
# Division in one field and a regex literal in the next: lexing without parser state read the two
# slashes as one regex literal spanning the brace between them. Found by this test, pinned here.
@example(
    first="($a / $a)",
    second="extract /0/ from $a",
    prefix="",
    middle="",
    suffix="",
)
def test_fields_and_literal_text_separate_cleanly(
    first: str, second: str, prefix: str, middle: str, suffix: str
) -> None:
    """Literal text keeps its place around fields, with ``{{``/``}}`` standing for single braces."""
    assume(_parses(first) and _parses(second))

    pattern = f'f"{prefix}{{{first}}}{middle}{{{second}}}{suffix}"'
    unescape = {"{{": "{", "}}": "}"}

    def literal(text: str) -> str:
        for escaped, plain in unescape.items():
            text = text.replace(escaped, plain)
        return text

    assert DftlyGrammar.parse_str(pattern) == {
        "string_interpolate": [
            {"literal": f"{literal(prefix)}{{}}{literal(middle)}{{}}{literal(suffix)}"},
            first,
            second,
        ]
    }
