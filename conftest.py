"""Test set-up and fixtures code."""

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
import polars as pl

import pytest


@pytest.fixture(scope="session", autouse=True)
def __setup_doctest_namespace(
    doctest_namespace: dict[str, Any],
):
    doctest_namespace.update(
        {
            "datetime": datetime,
            "tempfile": tempfile,
            "pl": pl,
            "Path": Path,
        }
    )
