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


def test_polars_function_call():
    text = "a: add(col1, col2)"
    result = from_yaml(text, input_schema={"col1": "int", "col2": "int"})
    expr = to_polars(result["a"])

    df = pl.DataFrame({"col1": [1, 2], "col2": [3, 4]})
    out = df.with_columns(a=expr).get_column("a")
    assert out.to_list() == [4, 6]


def test_polars_datetime_plus_duration():
    text = "a: dt + dur"
    result = from_yaml(text, input_schema={"dt": "datetime", "dur": "duration"})
    expr = to_polars(result["a"])

    from datetime import datetime, timedelta

    df = pl.DataFrame(
        {
            "dt": [
                datetime(2024, 1, 1, 1, 0, 0),
                datetime(2024, 1, 1, 2, 0, 0),
            ],
            "dur": [timedelta(minutes=30), timedelta(minutes=45)],
        }
    )
    out = df.with_columns(a=expr).get_column("a")
    assert out[0] == datetime(2024, 1, 1, 1, 30, 0)
    assert out[1] == datetime(2024, 1, 1, 2, 45, 0)


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


def test_polars_boolean_and_coalesce_and_membership():
    text = """
    a: flag1 and flag2
    b: not flag1
    c:
      - col1
      - col2
    d:
      value_in_literal_set:
        value: col1
        set: [1, 2]
    e:
      value_in_range:
        value: col1
        min: 0
        max: 2
    """
    schema = {
        "flag1": "bool",
        "flag2": "bool",
        "col1": "int",
        "col2": "int",
    }
    result = from_yaml(text, input_schema=schema)
    df = pl.DataFrame(
        {
            "flag1": [True, False],
            "flag2": [True, True],
            "col1": [1, 3],
            "col2": [5, 6],
        }
    )
    out = df.with_columns(
        a=to_polars(result["a"]),
        b=to_polars(result["b"]),
        c=to_polars(result["c"]),
        d=to_polars(result["d"]),
        e=to_polars(result["e"]),
    )
    assert out.get_column("a").to_list() == [True, False]
    assert out.get_column("b").to_list() == [False, True]
    assert out.get_column("c").to_list() == [1, 3]
    assert out.get_column("d").to_list() == [True, False]
    assert out.get_column("e").to_list() == [True, False]


def test_polars_string_interpolate():
    text = """
    a:
      string_interpolate:
        pattern: "hello {col1}!"
        inputs:
          col1: col1
    b: "hey {col1}!"
    """
    result = from_yaml(text, input_schema={"col1": "int"})
    df = pl.DataFrame({"col1": [1, 2]})
    out = df.with_columns(
        a=to_polars(result["a"]),
        b=to_polars(result["b"]),
    )
    assert out.get_column("a").to_list() == ["hello 1!", "hello 2!"]
    assert out.get_column("b").to_list() == ["hey 1!", "hey 2!"]


def test_polars_regex_operations():
    text = """
    a: extract (\\d+) from col1
    b: match foo against col2
    c: not match foo against col2
    """
    result = from_yaml(text, input_schema={"col1": "str", "col2": "str"})
    df = pl.DataFrame({"col1": ["abc123", "def456"], "col2": ["foo", "bar"]})
    out = df.with_columns(
        a=to_polars(result["a"]),
        b=to_polars(result["b"]),
        c=to_polars(result["c"]),
    )
    assert out.get_column("a").to_list() == ["123", "456"]
    assert out.get_column("b").to_list() == [True, False]
    assert out.get_column("c").to_list() == [False, True]
