import polars as pl

from dftly.parser import Parser
from dftly.nodes import Add, Column, Literal, StringInterpolate


def test_dollar_column_expression_parses_to_nodes():
    parser = Parser()
    node = parser("$foo + $bar")

    assert isinstance(node, Add)
    assert all(isinstance(arg, Column) for arg in node.args)


def test_string_interpolation_with_dollar_columns_evaluates():
    parser = Parser()
    node = parser('f"hello {$foo} {$bar}"')

    assert isinstance(node, StringInterpolate)
    pattern, *_ = node.args
    assert isinstance(pattern, Literal)

    df = pl.DataFrame({"foo": ["Alice", "Bob"], "bar": ["Cooper", "Dylan"]})

    result = df.select(node.polars_expr.alias("greeting"))
    assert result.to_dicts() == [
        {"greeting": "hello Alice Cooper"},
        {"greeting": "hello Bob Dylan"},
    ]
