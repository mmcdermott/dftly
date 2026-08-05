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

# Every terminal and rule in grammar.lark appears below, so a splitter that mishandles any construct
# dftly can express has a chance of being caught. Two things are deliberately absent: an expression
# containing the wrapper's own quote character (`"`), which the f-string form genuinely cannot hold
# (#75), and a second level of f-string nesting, since the grammar has only two quote characters to
# nest with.

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
        "2023-01-01",  # DATE
        "2023-01-01 12:34:56",  # DATETIME
        "11:32",  # TIME
        "11:32 a.m.",  # TIME with meridiem
        "MEDS_BIRTH",  # bare word
        "min()",  # a call with no arguments at all -- `[args]` is optional in the grammar
        "f'plain'",  # an f-string with no fields at all
        "f'{$a}'",  # a nested f-string, one level down
        "f'x{$a}y{$b}'",
    ]
)

# Regex bodies stay within what the REGEX_LITERAL terminal accepts (no `/`, backslash, or newline)
# and lean on the characters that matter here: braces, both balanced and not.
REGEX_BODIES = st.text(alphabet="ab01{}()|.^$*+?-", min_size=1, max_size=6)

# Dtype names, implicit unit names, and the datetime/duration accessors -- every name the cast forms
# accept -- plus the `?` prefix that marks a cast non-strict.
CAST_TARGETS = st.sampled_from(
    [
        "int",
        "str",
        "float64",
        "?float64",
        "days",
        "milliseconds",
        "year",
        "date",
        "hour_of_day",
        "year_of_date",
        "total_seconds",
        "total_microseconds",
    ]
)

STRPTIME_FORMATS = st.sampled_from(["'%Y-%m-%d'", "'%Y-%m-%d %H:%M:%S'", "?'%Y'"])

TIMES = st.sampled_from(["11:30", "11:30 a.m.", "23:59:59"])

BINARY_OPS = st.sampled_from(
    [
        "+",
        "-",
        "*",
        "/",
        "**",
        "==",
        "!=",
        ">",
        "<",
        ">=",
        "<=",
        "and",
        "&&",
        "or",
        "||",
        "??",
    ]
)

UNARY_OPS = st.sampled_from(["not ", "!", "-", "+"])

# Function-call syntax is open to every registered node, so a representative call of each arity is
# generated rather than all fifty names: the splitter cannot distinguish them, but it can trip over
# the commas, nesting, and quoted arguments they introduce.
#
# `negate($a)` and other one-argument calls do not resolve today, for a reason unrelated to
# interpolation: the grammar inlines a one-element `args` rule into a bare dict, which the parser
# reads as keyword arguments (#109). They are generated anyway -- the property below is that a field
# behaves as the expression does alone, which covers expressions that legitimately fail.
CALLS_1 = st.sampled_from(
    ["hash", "signed_hash", "len_chars", "not", "dt_year", "negate", "min"]
)
CALLS_2 = st.sampled_from(["min", "max", "mean", "coalesce", "power"])


def _extend(children: st.SearchStrategy[str]) -> st.SearchStrategy[str]:
    """Build a larger expression from smaller ones.

    Compound forms are parenthesized so that every draw parses regardless of how its parts bind -- precedence
    is not what is under test here, and an unparsable draw would only be thrown away.
    """
    return st.one_of(
        st.tuples(children, BINARY_OPS, children).map(
            lambda t: f"({t[0]} {t[1]} {t[2]})"
        ),
        st.tuples(UNARY_OPS, children).map(lambda t: f"({t[0]}{t[1]})"),
        # Both cast spellings, over dtypes, implicit units, and datetime accessors.
        st.tuples(children, CAST_TARGETS).map(lambda t: f"({t[0]})::{t[1]}"),
        st.tuples(children, CAST_TARGETS).map(lambda t: f"({t[0]}) as {t[1]}"),
        # Strptime, which is a cast whose target is a format string.
        st.tuples(children, STRPTIME_FORMATS).map(lambda t: f"({t[0]})::{t[1]}"),
        st.tuples(children, STRPTIME_FORMATS).map(lambda t: f"({t[0]}) as {t[1]}"),
        # `@` set-time, whose right operand is a bare TIME token.
        st.tuples(children, TIMES).map(lambda t: f"({t[0]} @ {t[1]})"),
        st.tuples(CALLS_1, children).map(lambda t: f"{t[0]}({t[1]})"),
        st.tuples(CALLS_2, children, children).map(lambda t: f"{t[0]}({t[1]}, {t[2]})"),
        st.tuples(children, children).map(lambda t: f"substring({t[0]}, 0, 3)"),
        st.tuples(children).map(lambda t: f"split({t[0]}, ',')"),
        st.tuples(REGEX_BODIES, children).map(
            lambda t: f"extract /{t[0]}/ from {t[1]}"
        ),
        st.tuples(st.integers(0, 2), REGEX_BODIES, children).map(
            lambda t: f"extract group {t[0]} of /{t[1]}/ from {t[2]}"
        ),
        st.tuples(REGEX_BODIES, children).map(lambda t: f"/{t[0]}/ in {t[1]}"),
        # All four slice spellings: [i:j], [i:], [:j], [:].
        st.tuples(children, st.integers(0, 3), st.integers(4, 9)).map(
            lambda t: f"({t[0]})[{t[1]}:{t[2]}]"
        ),
        st.tuples(children, st.integers(0, 3)).map(lambda t: f"({t[0]})[{t[1]}:]"),
        st.tuples(children, st.integers(4, 9)).map(lambda t: f"({t[0]})[:{t[1]}]"),
        st.tuples(children).map(lambda t: f"({t[0]})[:]"),
        st.tuples(children, children, children).map(
            lambda t: f"({t[0]} if {t[1]} else {t[2]})"
        ),
        st.tuples(children, children).map(lambda t: f"({t[0]} if {t[1]})"),
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


def _resolve(expression_or_tree) -> tuple[str, object]:
    """Resolve to a node and build its polars expression, or report the failure.

    Both are outcomes a field must reproduce. Building the polars expression is part of it because
    ``StringInterpolate`` builds one for each of its fields as it is constructed, so an expression
    that resolves but cannot lower -- ``min()`` with no arguments, say -- has to be compared at the
    same depth on both sides to be compared fairly.

    Only success or failure is compared, not the exception type: a field's failure is re-raised by
    the parser as it tries to match the enclosing ``string_interpolate``, so the same underlying
    problem legitimately surfaces under a different class on the two sides.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            node = Parser()(expression_or_tree)
            node.polars_expr
            return "ok", node
        except Exception:  # noqa: BLE001 -- that it failed is the observation, not how
            return "error", None


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
@example(expression="negate($a)")  # does not resolve on its own either (#109)
def test_field_holds_the_same_expression_it_would_alone(expression: str) -> None:
    """``f"{e}"`` interpolates exactly what ``e`` means on its own -- errors included."""
    assume(_parses(expression))

    interpolated = DftlyGrammar.parse_str(f'f"{{{expression}}}"')

    # The base form keeps fields as raw text for the Parser to resolve, so the text must survive
    # verbatim -- this is the assertion that a truncating splitter fails, and it holds whether or
    # not the expression goes on to resolve.
    assert interpolated == {"string_interpolate": [{"literal": "{}"}, expression]}

    # Resolving the field must then reach the very tree the expression yields when parsed alone.
    # Expressions that do not resolve at all (#109, and f-strings with no fields) must not resolve
    # here either: a splitter that quietly rewrote its input could turn one of those into something
    # that works, which would be just as wrong as truncating it.
    alone_outcome, alone = _resolve(expression)
    field_outcome, interpolation = _resolve(interpolated)
    assert field_outcome == alone_outcome
    if alone_outcome == "ok":
        assert repr(interpolation.args[1]) == repr(alone)


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
