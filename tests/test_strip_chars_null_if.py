"""Equivalence tests for ``strip_chars`` and ``null_if``.

``strip_chars`` promises to be exactly Polars' ``str.strip_chars()``, so it is checked against Polars
itself over inputs chosen to hit each edge: leading/trailing/both-sided whitespace, interior
whitespace, blank and empty strings, null, and Unicode whitespace that Polars and Python's
``str.strip()`` disagree on. All three forms (string, dict, class) are checked, since they must
reduce to the same tree.

``null_if`` promises SQL ``NULLIF`` semantics, so it is checked against a direct Python statement of
that rule across several dtypes, with nulls on either side.
"""

import math
from datetime import date

import polars as pl
import pytest

from dftly import Parser
from dftly.nodes import Column, NullIf, StripChars
from dftly.str_form.parser import DftlyGrammar

STRIP_INPUTS = [
    "mg",
    " mg",
    "mg ",
    "\tmg\n",
    "mL / h",
    " a  b ",
    "  ",
    "",
    None,
    " mg　",  # no-break space, ideographic space: stripped
    " mg ",  # em space, line separator: stripped
    "​mg﻿",  # zero-width space, BOM: not White_Space, kept
    "\x1cmg\x85",  # U+001C kept by Polars (Python strips it); NEL stripped
    "\r\n\v\f",  # all whitespace
]

STRIP_FORMS = {
    "string": "strip_chars($u)",
    "dict": {"strip_chars": [{"column": "u"}]},
}


@pytest.mark.parametrize("form", sorted(STRIP_FORMS))
def test_strip_chars_matches_polars(form):
    df = pl.DataFrame({"u": STRIP_INPUTS}, schema={"u": pl.String})
    expected = df.select(pl.col("u").str.strip_chars())
    got = df.select(Parser.expr_to_polars(STRIP_FORMS[form]))
    assert got.schema == expected.schema
    assert got["u"].to_list() == expected["u"].to_list()


def test_strip_chars_forms_reduce_to_same_node():
    assert DftlyGrammar.parse_str(STRIP_FORMS["string"]) == STRIP_FORMS["dict"]
    assert repr(Parser()(STRIP_FORMS["dict"])) == repr(StripChars(Column("u")))


# The helper MEDS ETL specs use today to strip a unit column: the regex matches from the first to the
# last non-whitespace character, and extracts null when there is none (blank, empty or null input).
REGEX_HELPER = r'(extract /(?s)\S(?:.*\S)?/ from $u) ?? "UNK"'
STRIP_HELPER = 'null_if(strip_chars($u), "") ?? "UNK"'


def test_null_if_strip_chars_replaces_regex_helper():
    df = pl.DataFrame(
        {"u": ["mg", " mg", "mg ", "\tmg\n", "mL / h", "  ", "", None]},
        schema={"u": pl.String},
    )
    regex = df.select(Parser.expr_to_polars(REGEX_HELPER))["u"].to_list()
    strip = df.select(Parser.expr_to_polars(STRIP_HELPER))["u"].to_list()
    assert strip == regex == ["mg", "mg", "mg", "mg", "mL / h", "UNK", "UNK", "UNK"]


def _sql_nullif(a, b):
    """SQL ``NULLIF``, with Polars' NaN == NaN equality."""
    if a is None or b is None:
        return a
    if (
        isinstance(a, float)
        and isinstance(b, float)
        and math.isnan(a)
        and math.isnan(b)
    ):
        return None
    return None if a == b else a


NULL_IF_CASES = {
    "str": (
        pl.String,
        ["mg", "", "", None, None, "N/A"],
        ["", "", None, "", None, "N/A"],
    ),
    "int": (pl.Int64, [1, 2, None, None, 0, -1], [1, None, 3, None, 0, 1]),
    "float": (
        pl.Float64,
        [1.5, float("nan"), float("nan"), None, -0.0, 2.0],
        [1.5, float("nan"), 1.0, None, 0.0, None],
    ),
    "bool": (pl.Boolean, [True, False, None, True], [True, True, False, None]),
    "date": (
        pl.Date,
        [date(2024, 1, 1), date(1900, 1, 1), None],
        [date(2024, 1, 2), date(1900, 1, 1), date(1900, 1, 1)],
    ),
}


def _same(x, y):
    if (
        isinstance(x, float)
        and isinstance(y, float)
        and math.isnan(x)
        and math.isnan(y)
    ):
        return True
    return x == y and (x is None) == (y is None)


@pytest.mark.parametrize("dtype_name", sorted(NULL_IF_CASES))
def test_null_if_matches_sql_nullif(dtype_name):
    dtype, a, b = NULL_IF_CASES[dtype_name]
    df = pl.DataFrame({"a": a, "b": b}, schema={"a": dtype, "b": dtype})
    out = df.select(Parser.expr_to_polars("null_if($a, $b)"))
    assert out.columns == ["a"]
    assert out.schema["a"] == dtype
    expected = [_sql_nullif(x, y) for x, y in zip(a, b)]
    got = out["a"].to_list()
    assert all(_same(g, e) for g, e in zip(got, expected, strict=True)), (got, expected)


def test_null_if_with_literal_second_argument():
    df = pl.DataFrame({"x": [1, -999, None, 3]})
    got = df.select(Parser.expr_to_polars("null_if($x, -999)"))["x"].to_list()
    assert got == [1, None, None, 3]


def test_null_if_forms_reduce_to_same_node():
    base = {"null_if": [{"column": "a"}, {"column": "b"}]}
    assert DftlyGrammar.parse_str("null_if($a, $b)") == base
    assert repr(Parser()(base)) == repr(NullIf(Column("a"), Column("b")))


def test_null_if_arity():
    with pytest.raises(ValueError, match="exactly two arguments; got 3"):
        Parser()("null_if($a, $b, $c)")


def test_strip_chars_arity():
    with pytest.raises(ValueError, match="exactly one argument; got 2"):
        Parser()("strip_chars($a, $b)")
