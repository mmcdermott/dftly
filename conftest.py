"""Test set-up and fixtures code."""

import os
import tempfile
from datetime import datetime, timedelta
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
            "timedelta": timedelta,
            "tempfile": tempfile,
            "os": os,
            "pl": pl,
            "Path": Path,
        }
    )
