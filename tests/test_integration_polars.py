import io
import polars as pl
from datetime import datetime
from dftly import from_yaml
from dftly.polars import map_to_polars


CSV_TEXT = """col1,col2,col3,flag,chartdate
1,2,0,True,2024-01-01
5,1,,False,2024-02-01
-1,3,5,True,2024-03-01
10,0,,False,2024-04-01
"""

YAML_TEXT = """
a:
  expression:
    type: ADD
    arguments:
      - col1
      - {literal: 2}
      - {column: col2}
b:
  - col3
  - {literal: 3}
c:
  conditional:
    if: flag
    then:
      expression:
        type: SUBTRACT
        arguments:
          - col1
          - 1
    else: col2
d:
  value_in_range:
    value: col1
    min: 0
    max: 10
e: chartdate @ 11:59:59 p.m.
"""

SCHEMA = {
    "col1": "int",
    "col2": "int",
    "col3": "int",
    "flag": "bool",
    "chartdate": "date",
}


def test_polars_integration_complex_csv_yaml():
    df = pl.read_csv(
        io.StringIO(CSV_TEXT), dtypes={"flag": pl.Boolean, "chartdate": pl.Date}
    )
    result = from_yaml(YAML_TEXT, input_schema=SCHEMA)
    exprs = map_to_polars(result)
    out = df.with_columns(**exprs)

    expected_a = [5, 8, 4, 12]
    expected_b = [0, 3, 5, 3]
    expected_c = [0, 1, -2, 0]
    expected_d = [True, True, False, True]
    expected_e = [
        datetime(2024, 1, 1, 23, 59, 59),
        datetime(2024, 2, 1, 23, 59, 59),
        datetime(2024, 3, 1, 23, 59, 59),
        datetime(2024, 4, 1, 23, 59, 59),
    ]

    assert out.get_column("a").to_list() == expected_a
    assert out.get_column("b").to_list() == expected_b
    assert out.get_column("c").to_list() == expected_c
    assert out.get_column("d").to_list() == expected_d
    assert out.get_column("e").to_list() == expected_e
