import pytest
from dftly import from_yaml, Column, Expression, Literal


def test_parse_addition():
    text = "a: col1 + col2"
    result = from_yaml(text, input_schema={"col1": "int", "col2": "int"})
    expr = result["a"]
    assert isinstance(expr, Expression)
    assert expr.type == "ADD"
    args = expr.arguments
    assert isinstance(args, list)
    assert isinstance(args[0], Column)
    assert args[0].name == "col1"
    assert isinstance(args[1], Column)
    assert args[1].name == "col2"


def test_parse_function_call():
    text = "a: add(col1, col2)"
    result = from_yaml(text, input_schema={"col1": "int", "col2": "int"})
    expr = result["a"]
    assert isinstance(expr, Expression)
    assert expr.type == "ADD"
    args = expr.arguments
    assert isinstance(args, list) and len(args) == 2
    assert isinstance(args[0], Column) and args[0].name == "col1"
    assert isinstance(args[1], Column) and args[1].name == "col2"


def test_parse_literal_string():
    text = "a: hello"
    result = from_yaml(text)
    lit = result["a"]
    assert isinstance(lit, Literal)
    assert lit.value == "hello"


def test_parse_string_interpolate_dict_and_string_forms():
    text = """
    a:
      string_interpolate:
        pattern: "hello {col1}"
        inputs:
          col1: col1
    b: "hello {col1}"
    """
    schema = {"col1": "int"}
    result = from_yaml(text, input_schema=schema)

    a_expr = result["a"]
    assert isinstance(a_expr, Expression)
    assert a_expr.type == "STRING_INTERPOLATE"
    assert isinstance(a_expr.arguments["pattern"], Literal)
    assert a_expr.arguments["pattern"].value == "hello {col1}"
    assert isinstance(a_expr.arguments["inputs"]["col1"], Column)

    b_expr = result["b"]
    assert isinstance(b_expr, Expression)
    assert b_expr.type == "STRING_INTERPOLATE"


def test_parse_subtract_and_cast_and_conditional():
    text = """
    a: col1 - col2
    b: col3 as float
    c: col1 if flag else col2
    """
    schema = {"col1": "int", "col2": "int", "col3": "str", "flag": "bool"}
    result = from_yaml(text, input_schema=schema)

    sub = result["a"]
    assert isinstance(sub, Expression)
    assert sub.type == "SUBTRACT"

    cast = result["b"]
    assert isinstance(cast, Expression)
    assert cast.type == "TYPE_CAST"

    cond = result["c"]
    assert isinstance(cond, Expression)
    assert cond.type == "CONDITIONAL"


def test_parse_resolve_timestamp_string_form():
    text = """
    a: charttime @ 11:59:59 p.m.
    b: birth_year @ January 1, 12:00 a.m.
    """
    schema = {"charttime": "date", "birth_year": "int"}
    result = from_yaml(text, input_schema=schema)

    a_expr = result["a"]
    assert isinstance(a_expr, Expression)
    assert a_expr.type == "RESOLVE_TIMESTAMP"
    a_args = a_expr.arguments
    assert "date" in a_args and "time" in a_args
    assert isinstance(a_args["date"], Column)
    assert a_args["date"].name == "charttime"
    time_args = a_args["time"]
    assert time_args["hour"].value == 23
    assert time_args["minute"].value == 59
    assert time_args["second"].value == 59

    b_expr = result["b"]
    assert isinstance(b_expr, Expression)
    assert b_expr.type == "RESOLVE_TIMESTAMP"
    b_args = b_expr.arguments
    date_args = b_args["date"]
    assert date_args["year"].name == "birth_year"
    assert date_args["month"].value == 1
    assert date_args["day"].value == 1


def test_parse_boolean_and_coalesce():
    text = """
    a: flag1 and flag2
    b: flag1 or flag2
    c: not flag1
    d:
      - col1
      - col2
    """
    schema = {"flag1": "bool", "flag2": "bool", "col1": "int", "col2": "int"}
    result = from_yaml(text, input_schema=schema)

    and_expr = result["a"]
    assert isinstance(and_expr, Expression)
    assert and_expr.type == "AND"

    or_expr = result["b"]
    assert isinstance(or_expr, Expression)
    assert or_expr.type == "OR"

    not_expr = result["c"]
    assert isinstance(not_expr, Expression)
    assert not_expr.type == "NOT"

    coalesce_expr = result["d"]
    assert isinstance(coalesce_expr, Expression)
    assert coalesce_expr.type == "COALESCE"


def test_parse_value_in_set_and_range():
    text = """
    a:
      value_in_literal_set:
        value: col1
        set: [1, 2]
    b:
      value_in_range:
        value: col1
        min: 0
        max: 10
    """
    schema = {"col1": "int"}
    result = from_yaml(text, input_schema=schema)

    in_set = result["a"]
    assert isinstance(in_set, Expression)
    assert in_set.type == "VALUE_IN_LITERAL_SET"

    in_range = result["b"]
    assert isinstance(in_range, Expression)
    assert in_range.type == "VALUE_IN_RANGE"


def test_parse_in_operator_string_forms():
    text = """
    a: col1 in {1, 2}
    b: col1 in (0, 2]
    """
    result = from_yaml(text, input_schema={"col1": "int"})

    in_set = result["a"]
    assert isinstance(in_set, Expression)
    assert in_set.type == "VALUE_IN_LITERAL_SET"
    vals = in_set.arguments["set"]
    assert all(isinstance(v, Literal) for v in vals)
    assert [v.value for v in vals] == [1, 2]

    in_range = result["b"]
    assert isinstance(in_range, Expression)
    assert in_range.type == "VALUE_IN_RANGE"
    args = in_range.arguments
    assert args["min_inclusive"].value is False
    assert args["max_inclusive"].value is True


def test_parse_fully_resolved_forms():
    text = """
    a:
      literal: 5
    b:
      column:
        name: col1
        type: int
    c:
      expression:
        type: ADD
        arguments:
          - {column: {name: col1, type: int}}
          - {literal: 1}
    """
    schema = {"col1": "int"}
    result = from_yaml(text, input_schema=schema)

    lit = result["a"]
    assert isinstance(lit, Literal)
    assert lit.value == 5

    col = result["b"]
    assert isinstance(col, Column)
    assert col.name == "col1" and col.type == "int"

    expr = result["c"]
    assert isinstance(expr, Expression)
    assert expr.type == "ADD"
    assert isinstance(expr.arguments, list)
    assert isinstance(expr.arguments[0], Column)
    assert isinstance(expr.arguments[1], Literal)


def test_invalid_keys_raise_error():
    with pytest.raises(ValueError):
        from_yaml("a: {literal: 1, extra: 2}")

    with pytest.raises(ValueError):
        from_yaml("a: {column: col1, bad: 1}")

    with pytest.raises(ValueError):
        from_yaml("a: {column: {name: col1, type: int, extra: 1}}")

    with pytest.raises(ValueError):
        from_yaml("a: {expression: {type: ADD, arguments: [], extra: 1}}")

    with pytest.raises(ValueError):
        from_yaml("a: {expression: {arguments: []}}")


def test_parse_regex_dict_and_string_forms():
    text = """
    a:
      regex_extract:
        regex: '(\\d+)'
        input: col1
        group: 1
    b: extract (\\d+) from col1
    c: match foo against col2
    d: not match foo against col2
    """
    schema = {"col1": "str", "col2": "str"}
    result = from_yaml(text, input_schema=schema)

    a_expr = result["a"]
    assert isinstance(a_expr, Expression) and a_expr.type == "REGEX"
    assert a_expr.arguments["action"].value == "EXTRACT"

    b_expr = result["b"]
    assert isinstance(b_expr, Expression) and b_expr.type == "REGEX"
    assert b_expr.arguments["action"].value == "EXTRACT"

    c_expr = result["c"]
    assert isinstance(c_expr, Expression) and c_expr.type == "REGEX"
    assert c_expr.arguments["action"].value == "MATCH"

    d_expr = result["d"]
    assert isinstance(d_expr, Expression) and d_expr.type == "REGEX"
    assert d_expr.arguments["action"].value == "NOT_MATCH"


def test_parse_parse_with_format_string_forms():
    text = """
    a:
      parse_with_format_string:
        input: dt
        output_type: datetime
        format: '%Y-%m-%d %H:%M:%S'
    b:
      parse:
        input: dt
        output_type: datetime
        format: '%Y-%m-%d %H:%M:%S'
    c:
      parse_with_format_string:
        input: dt
        datetime_format: '%Y-%m-%d %H:%M:%S'
    d:
      dt:
        datetime_format: '%Y-%m-%d %H:%M:%S'
    e: "dt as '%Y-%m-%d'"
    """
    schema = {"dt": "str"}
    result = from_yaml(text, input_schema=schema)

    for key in ["a", "b", "c", "d", "e"]:
        expr = result[key]
        assert isinstance(expr, Expression)
        assert expr.type == "PARSE_WITH_FORMAT_STRING"
        args = expr.arguments
        assert isinstance(args["input"], Column) and args["input"].name == "dt"
        fmt = args.get("format")
        if isinstance(fmt, Literal):
            fmt = fmt.value
        assert fmt.startswith("%Y-%m-%d")


def test_parse_numeric_and_duration_formats():
    text = """
    a:
      parse_with_format_string:
        input: num
        numeric_format: '%d'
    b:
      num:
        numeric_format: '%d'
    c:
      parse_with_format_string:
        input: dur
        duration_format: '%H:%M:%S'
    d:
      dur:
        duration_format: '%H:%M:%S'
    e: "dur as '%H:%M:%S'"
    """
    schema = {"num": "str", "dur": "str"}
    result = from_yaml(text, input_schema=schema)

    for key in ["a", "b", "c", "d", "e"]:
        expr = result[key]
        assert isinstance(expr, Expression)
        assert expr.type == "PARSE_WITH_FORMAT_STRING"
        args = expr.arguments
        assert isinstance(args["input"], Column)
        if key in {"c", "d", "e"}:
            assert args["output_type"].value == "duration"
        if key in {"a", "b"}:
            assert args["output_type"].value == "float"


def test_parse_extended_numeric_and_duration_formats():
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

    for key in "abcdefg":
        expr = result[key]
        assert isinstance(expr, Expression)
        assert expr.type == "PARSE_WITH_FORMAT_STRING"
        if key in {"a", "d", "e"}:
            assert expr.arguments["output_type"].value == "duration"
        if key in {"b", "c"}:
            assert expr.arguments["output_type"].value == "float"
        if key in {"f", "g"}:
            assert expr.arguments["output_type"].value == "int"
