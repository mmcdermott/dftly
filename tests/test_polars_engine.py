import pytest

# allow pytest.importorskip before importing polars
# ruff: noqa: E402

polars = pytest.importorskip("polars")
import polars as pl

from dftly import from_yaml
from dftly.polars import to_polars


def test_polars_addition():
    text = "a: col1 + col2"
    result = from_yaml(text, input_schema={"col1": "int", "col2": "int"})
    expr = to_polars(result["a"])

    df = pl.DataFrame({"col1": [1, 2], "col2": [3, 4]})
    out = df.with_columns(a=expr).get_column("a")
    assert out.to_list() == [4, 6]


def test_polars_subtract():
    text = "a: col1 - col2"
    result = from_yaml(text, input_schema={"col1": "int", "col2": "int"})
    expr = to_polars(result["a"])

    df = pl.DataFrame({"col1": [5, 10], "col2": [3, 4]})
    out = df.with_columns(a=expr).get_column("a")
    assert out.to_list() == [2, 6]


def test_polars_type_cast():
    text = "a: col1 as float"
    result = from_yaml(text, input_schema={"col1": "int"})
    expr = to_polars(result["a"])

    df = pl.DataFrame({"col1": [1, 2]})
    out = df.with_columns(a=expr).get_column("a")
    assert out.dtype == pl.Float64


def test_polars_conditional():
    text = "a: col1 if flag else col2"
    schema = {"col1": "int", "col2": "int", "flag": "bool"}
    result = from_yaml(text, input_schema=schema)
    expr = to_polars(result["a"])

    df = pl.DataFrame({"col1": [1, 2], "col2": [3, 4], "flag": [True, False]})
    out = df.with_columns(a=expr).get_column("a")
    assert out.to_list() == [1, 4]


def test_polars_resolve_timestamp():
    text = """
    a: charttime @ 11:59:59 p.m.
    """
    schema = {"charttime": "date"}
    result = from_yaml(text, input_schema=schema)
    expr = to_polars(result["a"])

    from datetime import date

    df = pl.DataFrame({"charttime": [date(2020, 1, 1), date(2021, 1, 1)]})
    out = df.with_columns(a=expr).get_column("a")
    assert out[0].hour == 23 and out[0].minute == 59 and out[0].second == 59
    assert out[1].hour == 23 and out[1].minute == 59 and out[1].second == 59
