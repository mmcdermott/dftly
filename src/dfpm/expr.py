"""Module for code that provides a structured DSL to specify an expression to extract from a dataframe.

Column expressions currently support the following types:
  - COL (`'col'`): A column expression that extracts a specified column.
  - STR (`'str'`): A column expression that is a string, with interpolation allowed to other column names via
    python's f-string syntax.
  - LITERAL (`'literal'`): A column expression that is a literal value regardless of type. No interpolation is
    allowed here.

Column expressions can be expressed either dictionary or via a shorthand string. If a structured dictionary,
the dictionary has length 1 and the key is one of the column expression types and the value is the expression
target (e.g., the column to load for `COL`, the string to interpolate with `{...}` escaped interpolation
targets for `STR`, or the literal value for `LITERAL`). If a string, the string is interpreted as a `COL` if
it has no interpolation targets, and as a `STR` otherwise.
"""
from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

import polars as pl
from omegaconf import DictConfig, ListConfig, OmegaConf

STR_INTERPOLATION_REGEX = r"\{([^}]+)\}"


class ColExprType(StrEnum):
    """Enumeration of the different types of column expressions that can be parsed.

    Attributes:
        COL: A specified column.
        STR: A string, with interpolation allowed to other column names via python's f-string syntax.
        LITERAL: A literal value regardless of type. No interpolation is allowed.
        REGEX_EXTRACT: A column expression that extracts a substring from a column using a regular expression.
    """

    COL = "col"
    STR = "str"
    LITERAL = "literal"
    REGEX_EXTRACT = "regex_extract"

    @classmethod
    def _is_valid_regex_extract_cfg(cls, expr_val: Any) -> tuple[bool, str | None]:
        """Checks if a expression value is a valid regex extract configuration.

        Args:
            expr_val: The value of the column expression.

        Returns:
            bool: True if the input is a valid regex extract configuration, False otherwise.
            str | None: The reason the input is invalid, if it is invalid.

        Examples:
            >>> ColExprType._is_valid_regex_extract_cfg("foo")
            (False, "Regex extract expressions must be a dictionary. Got foo")
            >>> ColExprType._is_valid_regex_extract_cfg({"col": "foo"})
            (False, "Regex extract expressions must have both a 'col' and 'regex' key. Missing 'regex'")
            >>> ColExprType._is_valid_regex_extract_cfg({"col": "foo", "regex": "bar"})
            (True, None)
            >>> ColExprType._is_valid_regex_extract_cfg({"col": "foo", "regex": 32})
            (False, "Regex extract expressions must have a string value for 'regex'. Got 32")
            >>> ColExprType._is_valid_regex_extract_cfg({"col": 32, "regex": "bar"})
            (False, "Regex extract expressions must have a string value for 'col'. Got 32")
            >>> ColExprType._is_valid_regex_extract_cfg({"col": "foo", "regex": "bar", "replacement": 32})
            (False, "Regex extract expressions must have only 'col' and 'regex' keys. Also got 'replacement'")
        """
        MANDATORY_KEYS = {"col", "regex"}

        if not isinstance(expr_val, dict):
            return False, f"Regex extract expressions must be a dictionary. Got {expr_val}"
        if not MANDATORY_KEYS.issubset(expr_val.keys())
            missing_keys = sorted(list(MANDATORY_KEYS - set(expr_val.keys())))
            missing_keys = "', '".join(missing_keys)
            return (
                False,
                f"Regex extract expressions must have both a 'col' and 'regex' key. Missing '{missing_keys}'"
            )
        if len(expr_val) > 2:
            extra_keys = sorted(list(set(expr_val.keys()) - MANDATORY_KEYS))
            extra_keys = "', '".join(extra_keys)
            return (
                False,
                f"Regex extract expressions must have only 'col' and 'regex' keys. Also got '{extra_keys}'"
            )
        if not isinstance(expr_val["col"], str):
            return (
                False,
                f"Regex extract expressions must have a string value for 'col'. Got {expr_val['col']}"
            )
        if not isinstance(expr_val["regex"], str):
            return (
                False,
                f"Regex extract expressions must have a string value for 'regex'. Got {expr_val['regex']}"
            )
        return True, None

    @classmethod
    def is_valid(cls, expr_dict: dict[ColExprType, Any]) -> tuple[bool, str | None]:
        """Checks if a dictionary of expression key to value is a valid column expression.

        Args:
            expr_dict: A dictionary of column expression type to value.

        Returns:
            bool: True if the input is a valid column expression, False otherwise.
            str | None: The reason the input is invalid, if it is invalid.

        Examples:
            >>> ColExprType.is_valid({"col": "foo"})
            (True, None)
            >>> ColExprType.is_valid({"col": 32})
            (False, 'Column expressions must have a string value. Got 32')
            >>> ColExprType.is_valid({ColExprType.STR: "bar//{foo}"})
            (True, None)
            >>> ColExprType.is_valid({ColExprType.STR: ["bar//{foo}"]})
            (False, "String interpolation expressions must have a string value. Got ['bar//{foo}']")
            >>> ColExprType.is_valid({"literal": ["baz", 32]})
            (True, None)
            >>> ColExprType.is_valid({"col": "foo", "str": "bar"}) # doctest: +NORMALIZE_WHITESPACE
            (False, "Column expressions can only contain a single key-value pair.
                    Got {'col': 'foo', 'str': 'bar'}")
            >>> ColExprType.is_valid({"foo": "bar"})
            (False, "Column expressions must have a key in ColExprType: ['col', 'str', 'literal']. Got foo")
            >>> ColExprType.is_valid([("col", "foo")])
            (False, "Column expressions must be a dictionary. Got [('col', 'foo')]")
        """

        if not isinstance(expr_dict, dict):
            return False, f"Column expressions must be a dictionary. Got {expr_dict}"
        if len(expr_dict) != 1:
            return False, f"Column expressions can only contain a single key-value pair. Got {expr_dict}"

        expr_type, expr_val = next(iter(expr_dict.items()))
        match expr_type:
            case cls.COL if isinstance(expr_val, str):
                return True, None
            case cls.COL:
                return False, f"Column expressions must have a string value. Got {expr_val}"
            case cls.STR if isinstance(expr_val, str):
                return True, None
            case cls.STR:
                return False, f"String interpolation expressions must have a string value. Got {expr_val}"
            case cls.LITERAL:
                return True, None
            case cls.REGEX_EXTRACT:
                return cls._is_valid_regex_extract_cfg(expr_val)
            case _:
                return (
                    False,
                    f"Column expressions must have a key in ColExprType: {[x.value for x in cls]}. Got "
                    f"{expr_type}",
                )

    @classmethod
    def to_pl_expr(cls, expr_type: ColExprType, expr_val: Any) -> tuple[pl.Expr, set[str]]:
        """Converts a column expression type and value to a Polars expression.

        Args:
            expr_type: The type of column expression.
            expr_val: The value of the column expression.

        Returns:
            pl.Expr: A Polars expression that extracts the column from the metadata DataFrame.
            set[str]: The set of input columns needed to form the returned expression.

        Raises:
            ValueError: If the column expression type is invalid.

        Examples:
            >>> print(*ColExprType.to_pl_expr(ColExprType.COL, "foo"))
            col("foo") {'foo'}
            >>> expr, cols = ColExprType.to_pl_expr(ColExprType.STR, "bar//{foo}//{baz}")
            >>> print(expr)
            String(bar//).str.concat_horizontal([col("foo"), String(//), col("baz")])
            >>> sorted(cols)
            ['baz', 'foo']
            >>> expr, cols = ColExprType.to_pl_expr(ColExprType.LITERAL, ListConfig(["foo", "bar"]))
            >>> print(expr)
            Series[literal]
            >>> pl.select(expr).item().to_list()
            ['foo', 'bar']
            >>> cols
            set()
            >>> ColExprType.to_pl_expr(ColExprType.COL, 32)
            Traceback (most recent call last):
                ...
            ValueError: ...
        """
        is_valid, err_msg = cls.is_valid({expr_type: expr_val})
        if not is_valid:
            raise ValueError(err_msg)

        match expr_type:
            case cls.COL:
                return pl.col(expr_val), {expr_val}
            case cls.STR:
                cols = list(re.findall(STR_INTERPOLATION_REGEX, expr_val))
                expr_val = re.sub(STR_INTERPOLATION_REGEX, "{}", expr_val)
                return pl.format(expr_val, *cols), set(cols)
            case cls.LITERAL:
                if isinstance(expr_val, ListConfig):
                    expr_val = OmegaConf.to_object(expr_val)
                return pl.lit(expr_val), set()

    @classmethod
    def _is_parsable_regex_extract(cls, cfg: str) -> bool:
        """Checks if a column expression is a regex extract expression in string form.

        Args:
            cfg: A column expression configuration object.

        Returns:
            bool: True if the column expression is a regex extract expression, False otherwise.

        Examples:
            >>> ColExprType._is_parsable_regex_extract("foo")
            False
            >>> ColExprType._is_parsable_regex_extract("regex_extract(foo, r'bar')")
            True
            >>> ColExprType._is_parsable_regex_extract("bar//{foo}")
            False
        """
        try:
            parsed = cls._parse_regex_extract(cfg)
            return True
        except ValueError:
            return False

    @classmethod
    def _parse_regex_extract(cls, cfg: str) -> dict:
        """Parses a regex extract column expression configuration object into structured form.

        Args:
            cfg: A column expression configuration string.

        Returns:
            dict: A dictionary specifying the desired regex extract expression.

        Raises:
            ValueError: If the column expression is not a valid regex extract configuration.

        Examples:
            >>> ColExprType._parse_regex_extract("regex_extract(foo, r'bar')")
            {'col': 'foo', 'regex': 'bar'}
            >>> ColExprType._parse_regex_extract("regex_extract(foo, r'bar', replacement='baz')")
            Traceback (most recent call last):
                ...
            ValueError: Invalid regex extract expression: regex_extract(foo, r'bar', replacement='baz')
            >>> ColExprType._parse_regex_extract("regex_extract(foo, r'bar', r'baz')")
            Traceback (most recent call last):
                ...
            ValueError: Invalid regex extract expression: regex_extract(foo, r'bar', r'baz')
        """
        match re.match(r"regex_extract\((.+),\s*r'(.+)'\)", cfg):
            case None:
                raise ValueError(f"Invalid regex extract expression: {cfg}")
            case match:
                col, regex = match.groups()
                return {"col": col, "regex": regex}

    @classmethod
    def parse(cls, cfg: Any) -> dict:
        """Parses a column expression configuration object into a dictionary expressing the desired expression.

        Args:
            col_expr: A configuration object that specifies how to extract a column from the metadata. See the
                module docstring for formatting details.

        Returns:
            A dictionary specifying, in a structured form, the desired column expression.

        Raises:
            ValueError: If the column expression is not a valid configuration.

        Examples:
            >>> ColExprType.parse("foo")
            {'col': 'foo'}
            >>> ColExprType.parse("regex_extract(foo, r'bar')")
            {'regex_extract': {'col': 'foo', 'regex': 'bar'}}
            >>> ColExprType.parse("bar//{foo}")
            {'str': 'bar//{foo}'}
            >>> ColExprType.parse({'col': 'bar//{foo}'})
            {'col': 'bar//{foo}'}
            >>> ColExprType.parse({"literal": ["foo", "bar"]})
            {'literal': ['foo', 'bar']}
            >>> ColExprType.parse({"foo": "bar", "buzz": "baz", "fuzz": "fizz"}) # doctest: +NORMALIZE_WHITESPACE
            Traceback (most recent call last):
                ...
            ValueError: Dictionary column expression must be a simple column expression with a single
                        key-value pair where the key is a column expression type. Got a dictionary with 3
                        elements: {'foo': 'bar', 'buzz': 'baz', 'fuzz': 'fizz'}
            >>> ColExprType.parse(('foo', 'bar')) # doctest: +NORMALIZE_WHITESPACE
            Traceback (most recent call last):
                ...
            ValueError: A simple column expression must be a string or dictionary.
                        Got <class 'tuple'>: ('foo', 'bar')
            >>> ColExprType.parse({"col": "foo", "str": "bar"}) # doctest: +NORMALIZE_WHITESPACE
            Traceback (most recent call last):
                ...
            ValueError: Dictionary column expression must be a simple column expression with a single
                        key-value pair where the key is a column expression type. Got a dictionary with 2
                        elements: {'col': 'foo', 'str': 'bar'}
        """
        match cfg:
            case str() if cls._is_parsable_regex_extract(cfg):
                return {cls.REGEX_EXTRACT: cls._parse_regex_extract(cfg)}
            case str() if re.search(STR_INTERPOLATION_REGEX, cfg):
                return {cls.STR: cfg}
            case str():
                return {cls.COL: cfg}
            case dict() | DictConfig() if len(cfg) == 1 and ColExprType.is_valid(cfg)[0]:
                return cfg
            case dict() | DictConfig():
                raise ValueError(
                    "Dictionary column expression must be a simple column expression with a single key-value "
                    f"pair where the key is a column expression type. Got a dictionary with {len(cfg)} "
                    f"elements: {cfg}"
                )
            case _:
                raise ValueError(
                    f"A simple column expression must be a string or dictionary. Got {type(cfg)}: {cfg}"
                )
