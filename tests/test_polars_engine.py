import pytest

pytest.importorskip("polars")

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
    a: charttime @ "11:59:59 p.m."
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


def test_polars_boolean_symbol_forms():
    text = """
    a: flag1 && flag2
    b: flag1 || flag2
    c: "!flag1"
    """
    schema = {"flag1": "bool", "flag2": "bool"}
    result = from_yaml(text, input_schema=schema)
    df = pl.DataFrame({"flag1": [True, False], "flag2": [True, True]})
    out = df.with_columns(
        a=to_polars(result["a"]),
        b=to_polars(result["b"]),
        c=to_polars(result["c"]),
    )
    assert out.get_column("a").to_list() == [True, False]
    assert out.get_column("b").to_list() == [True, True]
    assert out.get_column("c").to_list() == [False, True]


def test_polars_nested_parentheses_operations():
    text = """
    a: (col1 + col2) - (col3 + col4)
    b: flag1 and (flag2 or flag3)
    c: not (flag1 or flag2)
    """
    schema = {
        "col1": "int",
        "col2": "int",
        "col3": "int",
        "col4": "int",
        "flag1": "bool",
        "flag2": "bool",
        "flag3": "bool",
    }
    result = from_yaml(text, input_schema=schema)
    df = pl.DataFrame(
        {
            "col1": [1, 2],
            "col2": [3, 4],
            "col3": [5, 6],
            "col4": [7, 8],
            "flag1": [True, False],
            "flag2": [False, True],
            "flag3": [True, False],
        }
    )
    out = df.with_columns(
        a=to_polars(result["a"]),
        b=to_polars(result["b"]),
        c=to_polars(result["c"]),
    )
    assert out.get_column("a").to_list() == [-8, -8]
    assert out.get_column("b").to_list() == [True, False]
    assert out.get_column("c").to_list() == [False, False]


def test_polars_in_operator_string_forms():
    text = """
    a: col1 in {1, 3}
    b: col1 in (0, 2]
    """
    result = from_yaml(text, input_schema={"col1": "int"})
    df = pl.DataFrame({"col1": [1, 2, 3]})
    out = df.with_columns(
        a=to_polars(result["a"]),
        b=to_polars(result["b"]),
    )
    assert out.get_column("a").to_list() == [True, False, True]
    assert out.get_column("b").to_list() == [True, True, False]


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


def test_polars_parse_with_format_string_forms():
    text = """
    a:
      parse_with_format_string:
        input: dt
        output_type: datetime
        format: '%Y-%m-%d %H:%M:%S'
    b: "dt as '%Y-%m-%d %H:%M:%S'"
    """
    result = from_yaml(text, input_schema={"dt": "str"})
    df = pl.DataFrame({"dt": ["2024-01-01 12:00:00", "2024-02-01 13:30:00"]})
    out = df.with_columns(
        a=to_polars(result["a"]),
        b=to_polars(result["b"]),
    )
    assert out.get_column("a").dtype == pl.Datetime
    assert out.get_column("a").to_list() == out.get_column("b").to_list()


def test_polars_parse_numeric_and_duration_forms():
    text = """
    a:
      parse_with_format_string:
        input: num
        numeric_format: '%d'
    b: "num as '%d'"
    c:
      parse_with_format_string:
        input: dur
        duration_format: '%H:%M:%S'
    d: "dur as '%H:%M:%S'"
    """
    result = from_yaml(text, input_schema={"num": "str", "dur": "str"})
    df = pl.DataFrame({"num": ["1", "2"], "dur": ["01:00:00", "02:30:00"]})
    out = df.with_columns(
        a=to_polars(result["a"]),
        b=to_polars(result["b"]),
        c=to_polars(result["c"]),
        d=to_polars(result["d"]),
    )
    assert out.get_column("a").dtype == pl.Float64
    assert out.get_column("a").to_list() == [1.0, 2.0]
    assert out.get_column("b").to_list() == [1, 2]
    assert out.get_column("c").dtype == pl.Duration
    assert out.get_column("c").to_list() == out.get_column("d").to_list()


def test_polars_parse_extended_numeric_and_duration_forms():
    text = """
    a:
      parse_with_format_string:
        input: hours
        duration_format: '%H hours'
    b:
      parse_with_format_string:
        input: comma_num
        numeric_format: '%,d'
    c:
      parse_with_format_string:
        input: underscore_num
        numeric_format: '%d'
    d:
      parse_with_format_string:
        input: rel
        duration_format: '%m mo %dd'
    e: "hours as '%H hours'"
    f: "comma_num as '%,d'"
    g: "underscore_num as '%d'"
    """
    schema = {
        "hours": "str",
        "comma_num": "str",
        "underscore_num": "str",
        "rel": "str",
    }
    result = from_yaml(text, input_schema=schema)
    df = pl.DataFrame(
        {
            "hours": ["3 hours"],
            "comma_num": ["4,004,240"],
            "underscore_num": ["1_000"],
            "rel": ["2 mo 5d"],
        }
    )
    out = df.with_columns(**{k: to_polars(result[k]) for k in "abcdefg"})

    assert out.get_column("a").dtype == pl.Duration
    assert out.get_column("a")[0].total_seconds() == 3 * 3600
    assert out.get_column("b")[0] == 4004240
    assert out.get_column("c")[0] == 1000
    assert out.get_column("d")[0].total_seconds() == 35 * 24 * 3600
    for key in "ae":
        assert out.get_column(key).to_list() == out.get_column("a").to_list()


def _md5_int(val: str) -> int:
    import hashlib

    h = hashlib.md5(str(val).encode())
    return int.from_bytes(h.digest()[:8], "big", signed=False)


def test_polars_hash_to_int_forms():
    text = """
    a: hash_to_int(col1)
    b:
      hash_to_int:
        input: col1
        algorithm: md5
    c: hash(col1)
    """
    result = from_yaml(text, input_schema={"col1": "str"})
    df = pl.DataFrame({"col1": ["foo", "bar"]})

    out = df.with_columns(
        a=to_polars(result["a"]),
        b=to_polars(result["b"]),
        c=to_polars(result["c"]),
    )

    expected_a = df.get_column("col1").hash().to_list()
    expected_b = [_md5_int(v) for v in ["foo", "bar"]]

    assert out.get_column("a").to_list() == expected_a
    assert out.get_column("c").to_list() == expected_a
    assert out.get_column("b").to_list() == expected_b


def test_polars_operator_precedence_arithmetic():
    text = """
    a: col1 + col2 + col3
    b: col1 + col2 - col3
    """
    result = from_yaml(text, input_schema={"col1": "int", "col2": "int", "col3": "int"})
    df = pl.DataFrame({"col1": [1, 2], "col2": [3, 4], "col3": [5, 6]})
    out = df.with_columns(a=to_polars(result["a"]), b=to_polars(result["b"]))
    assert out.get_column("a").to_list() == [9, 12]
    assert out.get_column("b").to_list() == [-1, 0]


def test_polars_operator_precedence_boolean():
    text = """
    a: flag1 and flag2 or flag3
    b: flag1 or flag2 and flag3
    c: not flag1 and flag2
    """
    schema = {"flag1": "bool", "flag2": "bool", "flag3": "bool"}
    result = from_yaml(text, input_schema=schema)
    df = pl.DataFrame(
        {
            "flag1": [True, False, False],
            "flag2": [True, False, True],
            "flag3": [False, True, True],
        }
    )
    out = df.with_columns(
        a=to_polars(result["a"]),
        b=to_polars(result["b"]),
        c=to_polars(result["c"]),
    )
    assert out.get_column("a").to_list() == [True, True, True]
    assert out.get_column("b").to_list() == [True, False, True]
    assert out.get_column("c").to_list() == [False, False, True]
