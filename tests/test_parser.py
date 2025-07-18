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


def test_parse_literal_string():
    text = "a: hello"
    result = from_yaml(text)
    lit = result["a"]
    assert isinstance(lit, Literal)
    assert lit.value == "hello"


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
