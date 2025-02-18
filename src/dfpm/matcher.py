"""Module for code that provides a structured DSL to specify columns of dataframes or operations on said.

Matchers are used to specify conditionals over dataframes. They are expressed simply as mappings from
parseable column expressions to parseable column expressions. They return True when the two expressions yield
the same value for a given row in the dataframe.
"""
from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

import polars as pl
from omegaconf import DictConfig, ListConfig, OmegaConf


def is_matcher(matcher_cfg: dict[str, Any]) -> bool:
    """Checks if a dictionary is a valid matcher configuration.

    Args:
        matcher_cfg: A dictionary of key-value pairs to match against.

    Returns:
        bool: True if the input is a valid matcher configuration, False otherwise.

    Examples:
        >>> is_matcher({"foo": "bar"})
        True
        >>> is_matcher(DictConfig({"foo": "bar"}))
        True
        >>> is_matcher({"foo": "bar", 32: "baz"})
        False
        >>> is_matcher(["foo", "bar"])
        False
        >>> is_matcher({})
        True
    """
    return isinstance(matcher_cfg, (dict, DictConfig)) and all(isinstance(k, str) for k in matcher_cfg.keys())


def matcher_to_expr(matcher_cfg: DictConfig | dict) -> tuple[pl.Expr, set[str]]:
    """Returns an expression and the necessary columns to match a collection of key-value pairs.

    Currently, this only supports checking for equality between column names and values.
    TODO: Expand (as needed only) to support other types of matchers.

    Args:
        matcher_cfg: A dictionary of key-value pairs to match against.

    Raises:
        ValueError: If the matcher configuration is not a dictionary.

    Returns:
        pl.Expr: A Polars expression that matches the key-value pairs in the input dictionary.
        set[str]: The set of input columns needed to form the returned expression.

    Examples:
        >>> expr, cols = matcher_to_expr({"foo": "bar", "buzz": "baz"})
        >>> print(expr)
        [(col("foo")) == (String(bar))].all_horizontal([[(col("buzz")) == (String(baz))]])
        >>> sorted(cols)
        ['buzz', 'foo']
        >>> expr, cols = matcher_to_expr(DictConfig({"foo": "bar", "buzz": "baz"}))
        >>> print(expr)
        [(col("foo")) == (String(bar))].all_horizontal([[(col("buzz")) == (String(baz))]])
        >>> sorted(cols)
        ['buzz', 'foo']
        >>> matcher_to_expr(["foo", "bar"])
        Traceback (most recent call last):
            ...
        ValueError: Matcher configuration must be a dictionary with string keys. Got: ['foo', 'bar']
    """
    if not is_matcher(matcher_cfg):
        raise ValueError(f"Matcher configuration must be a dictionary with string keys. Got: {matcher_cfg}")

    return pl.all_horizontal((pl.col(k) == v) for k, v in matcher_cfg.items()), set(matcher_cfg.keys())
