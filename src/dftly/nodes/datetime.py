"""Nodes relating to dates, times, and durations."""

from typing import ClassVar

from .base import ArgsOnlyFn, BinaryOp
import polars as pl


class SetTime(BinaryOp):
    """This non-terminal node sets the time part of a date or datetime.

    Example:
        >>> from dftly.nodes import Literal
        >>> from datetime import date, time, datetime
        >>> node = SetTime(Literal(date(2023, 1, 1)), Literal(time(12, 10)))
        >>> node
        SetTime(Literal(datetime.date(2023, 1, 1)), Literal(datetime.time(12, 10)))
        >>> pl.select(node.polars_expr).item()
        datetime.datetime(2023, 1, 1, 12, 10)

    It also works with datetime inputs (time is replaced):

        >>> node = SetTime(Literal(datetime(2023, 6, 15, 8, 0)), Literal(time(23, 59, 59)))
        >>> pl.select(node.polars_expr).item()
        datetime.datetime(2023, 6, 15, 23, 59, 59)
    """

    KEY = "set_time"
    SYM = "@"

    @property
    def polars_expr(self) -> pl.Expr:
        date_expr = self.args[0].polars_expr
        time_expr = self.args[1].polars_expr
        return date_expr.dt.combine(time_expr)


class _DtAccessor(ArgsOnlyFn):
    """Base class for datetime and duration accessor nodes.

    Each subclass wraps a single argument and delegates to
    ``input.polars_expr.dt.<PL_METHOD>()``. Two families of subclasses live here:

    - **Datetime component extraction** (Datetime → int): hour-of-day, day-of-month, etc.
    - **Duration total** (Duration → int/float): total seconds, total days, etc.

    Each subclass defines:

    - ``KEY``: the function-call and dict-form name (e.g. ``"dt_hour_of_day"``).
      Prefixed with ``dt_`` to prevent collisions with unrelated nodes.
    - ``PL_METHOD``: the polars ``.dt.*`` method name (e.g. ``"hour"``).
    - ``CAST_NAME``: the RHS name accepted by cast syntax in both ``::`` and ``as`` forms
      (e.g. ``"hour_of_day"`` → ``$event::hour_of_day`` or ``$event as hour_of_day``).
      Accessor dispatch is shared between both cast operators because they are semantically
      equivalent in dftly and differ only in grammar precedence. May be ``None`` if no
      cast form is wanted; set ``None`` when the accessor should only be reachable via
      the function-call form (``dt_<name>($x)``).

    The shared arity-1 validation, ``from_lark`` wrapping, and ``polars_expr`` dispatch all
    live here. Subclasses are typically four lines each.

    Shared arity validation (exercised here so subclasses don't need to repeat the doctest):

        >>> from dftly.nodes import Literal
        >>> DtHourOfDay(Literal(datetime(2024, 1, 1, 14, 30)), Literal(datetime(2024, 1, 2)))
        Traceback (most recent call last):
            ...
        ValueError: dt_hour_of_day requires exactly one argument; got 2
        >>> DtTotalSeconds()
        Traceback (most recent call last):
            ...
        ValueError: dt_total_seconds requires exactly one argument; got 0

    Shared ``from_lark`` accepts both list and non-list inputs, consistent with ``Hash``:

        >>> DtHourOfDay.from_lark([{"literal": {"datetime": datetime(2024, 1, 1, 14, 30)}}])
        {'dt_hour_of_day': [{'literal': {'datetime': datetime.datetime(2024, 1, 1, 14, 30)}}]}
        >>> DtHourOfDay.from_lark({"literal": {"datetime": datetime(2024, 1, 1, 14, 30)}})
        {'dt_hour_of_day': [{'literal': {'datetime': datetime.datetime(2024, 1, 1, 14, 30)}}]}
    """

    PL_METHOD: ClassVar[str]
    CAST_NAME: ClassVar[str | None] = None

    def __post_init__(self):
        super().__post_init__()
        if len(self.args) != 1:
            raise ValueError(
                f"{self.KEY} requires exactly one argument; got {len(self.args)}"
            )

    @classmethod
    def from_lark(cls, items):
        if not isinstance(items, list):
            items = [items]
        return {cls.KEY: items}

    @property
    def polars_expr(self) -> pl.Expr:
        return getattr(self.args[0].polars_expr.dt, self.PL_METHOD)()


# ---------------------------------------------------------------------------
# Datetime component accessors
# ---------------------------------------------------------------------------


class DtYear(_DtAccessor):
    """Extract the calendar year (e.g. ``2024``) from a datetime or date.

    The cast form is ``::year_of_date``, not ``::year``: ``::year`` is already the
    integer→date construction (``2024::year`` → ``date(2024, 1, 1)``). The
    ``year_of_date`` name keeps the direction unambiguous — "the year component of a
    date" — and stays consistent with the ``_of_`` naming pattern used by the rest of
    the datetime accessor family.

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(DtYear(Literal(datetime(2024, 6, 15, 14, 30))).polars_expr).item()
        2024

    Cast form:

        >>> from dftly import Parser
        >>> df = pl.DataFrame({"event": [datetime(2024, 6, 15, 14, 30)]})
        >>> df.select(y=Parser.expr_to_polars("$event::year_of_date"))["y"].item()
        2024

    Function form:

        >>> df.select(y=Parser.expr_to_polars("dt_year($event)"))["y"].item()
        2024

    ``::year`` still resolves to the integer→date constructor, not this accessor:

        >>> pl.select(Parser.expr_to_polars("2024::year")).item()
        datetime.date(2024, 1, 1)
    """

    KEY = "dt_year"
    PL_METHOD = "year"
    CAST_NAME = "year_of_date"


class DtMonthOfYear(_DtAccessor):
    """Extract the month (1-12) from a datetime or date.

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(DtMonthOfYear(Literal(datetime(2024, 6, 15))).polars_expr).item()
        6

    Cast form:

        >>> from dftly import Parser
        >>> df = pl.DataFrame({"event": [datetime(2024, 6, 15)]})
        >>> df.select(m=Parser.expr_to_polars("$event::month_of_year"))["m"].item()
        6

    Function form:

        >>> df.select(m=Parser.expr_to_polars("dt_month_of_year($event)"))["m"].item()
        6
    """

    KEY = "dt_month_of_year"
    PL_METHOD = "month"
    CAST_NAME = "month_of_year"


class DtDayOfMonth(_DtAccessor):
    """Extract the day-of-month (1-31) from a datetime or date.

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(DtDayOfMonth(Literal(datetime(2024, 6, 15))).polars_expr).item()
        15
    """

    KEY = "dt_day_of_month"
    PL_METHOD = "day"
    CAST_NAME = "day_of_month"


class DtDayOfWeek(_DtAccessor):
    """Extract the day-of-week (1=Monday, 7=Sunday) from a datetime or date.

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(DtDayOfWeek(Literal(datetime(2024, 6, 15))).polars_expr).item()
        6
    """

    KEY = "dt_day_of_week"
    PL_METHOD = "weekday"
    CAST_NAME = "day_of_week"


class DtDayOfYear(_DtAccessor):
    """Extract the ordinal day-of-year (1-366) from a datetime or date.

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(DtDayOfYear(Literal(datetime(2024, 6, 15))).polars_expr).item()
        167
    """

    KEY = "dt_day_of_year"
    PL_METHOD = "ordinal_day"
    CAST_NAME = "day_of_year"


class DtHourOfDay(_DtAccessor):
    """Extract the hour-of-day (0-23) from a datetime or time.

    Motivating example from MEDS_transforms ``add_time_derived_measurements`` — entire
    time-of-day bucketing logic reduces to a YAML ``Conditional`` once this accessor exists:

        >>> from dftly.nodes import Literal
        >>> pl.select(DtHourOfDay(Literal(datetime(2024, 6, 15, 14, 30))).polars_expr).item()
        14

    Cast form (the primary ergonomic path) — works in both the ``::`` and ``as`` cast
    forms, which are semantically equivalent in dftly and differ only in grammar
    precedence (``::`` binds tight, ``as`` binds loose):

        >>> from dftly import Parser
        >>> df = pl.DataFrame({"event": [datetime(2024, 6, 15, 14, 30)]})
        >>> df.select(h=Parser.expr_to_polars("$event::hour_of_day"))["h"].item()
        14
        >>> df.select(h=Parser.expr_to_polars("$event as hour_of_day"))["h"].item()
        14

    Both forms parse to the same accessor node:

        >>> from dftly.str_form.parser import DftlyGrammar
        >>> DftlyGrammar.parse_str("$event::hour_of_day")
        {'dt_hour_of_day': [{'column': 'event'}]}
        >>> DftlyGrammar.parse_str("$event as hour_of_day")
        {'dt_hour_of_day': [{'column': 'event'}]}

    Function form:

        >>> df.select(h=Parser.expr_to_polars("dt_hour_of_day($event)"))["h"].item()
        14
    """

    KEY = "dt_hour_of_day"
    PL_METHOD = "hour"
    CAST_NAME = "hour_of_day"


class DtMinuteOfHour(_DtAccessor):
    """Extract the minute-of-hour (0-59) from a datetime or time.

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(DtMinuteOfHour(Literal(datetime(2024, 6, 15, 14, 30))).polars_expr).item()
        30
    """

    KEY = "dt_minute_of_hour"
    PL_METHOD = "minute"
    CAST_NAME = "minute_of_hour"


class DtSecondOfMinute(_DtAccessor):
    """Extract the second-of-minute (0-59) from a datetime or time.

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(DtSecondOfMinute(Literal(datetime(2024, 6, 15, 14, 30, 45))).polars_expr).item()
        45
    """

    KEY = "dt_second_of_minute"
    PL_METHOD = "second"
    CAST_NAME = "second_of_minute"


class DtWeekOfYear(_DtAccessor):
    """Extract the ISO week-of-year (1-53) from a datetime or date.

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(DtWeekOfYear(Literal(datetime(2024, 6, 15))).polars_expr).item()
        24
    """

    KEY = "dt_week_of_year"
    PL_METHOD = "week"
    CAST_NAME = "week_of_year"


class DtQuarterOfYear(_DtAccessor):
    """Extract the quarter-of-year (1-4) from a datetime or date.

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(DtQuarterOfYear(Literal(datetime(2024, 6, 15))).polars_expr).item()
        2
    """

    KEY = "dt_quarter_of_year"
    PL_METHOD = "quarter"
    CAST_NAME = "quarter_of_year"


# ---------------------------------------------------------------------------
# Duration total accessors
# ---------------------------------------------------------------------------


class DtTotalSeconds(_DtAccessor):
    """Project a Duration to total seconds (Duration → Int64).

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(DtTotalSeconds(Literal(timedelta(hours=2, minutes=30))).polars_expr).item()
        9000

    Cast form (the primary ergonomic path — dual to the existing ``42::seconds`` construction):

        >>> from dftly import Parser
        >>> df = pl.DataFrame({"t": [timedelta(hours=2, minutes=30)]})
        >>> df.select(s=Parser.expr_to_polars("$t::total_seconds"))["s"].item()
        9000
    """

    KEY = "dt_total_seconds"
    PL_METHOD = "total_seconds"
    CAST_NAME = "total_seconds"


class DtTotalMilliseconds(_DtAccessor):
    """Project a Duration to total milliseconds (Duration → Int64).

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(DtTotalMilliseconds(Literal(timedelta(seconds=1.5))).polars_expr).item()
        1500
    """

    KEY = "dt_total_milliseconds"
    PL_METHOD = "total_milliseconds"
    CAST_NAME = "total_milliseconds"


class DtTotalMicroseconds(_DtAccessor):
    """Project a Duration to total microseconds (Duration → Int64).

    Motivating example from MEDS_transforms ``add_time_derived_measurements/age.py``:
    age computation as ``(event_time - dob) / <microseconds per year>``. Expressible
    entirely in config once this accessor exists:

        >>> from dftly.nodes import Literal
        >>> pl.select(DtTotalMicroseconds(Literal(timedelta(days=1))).polars_expr).item()
        86400000000

    Cast-form via string parser, reproducing the MEDS age formula:

        >>> from dftly import Parser
        >>> df = pl.DataFrame({
        ...     "event_time": [datetime(2030, 1, 1)],
        ...     "dob":        [datetime(2000, 1, 1)],
        ... })
        >>> age_years = Parser.expr_to_polars(
        ...     "($event_time - $dob)::total_microseconds / 31557600000000"
        ... )
        >>> round(df.select(age=age_years)["age"].item(), 4)
        30.0014
    """

    KEY = "dt_total_microseconds"
    PL_METHOD = "total_microseconds"
    CAST_NAME = "total_microseconds"


class DtTotalNanoseconds(_DtAccessor):
    """Project a Duration to total nanoseconds (Duration → Int64).

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(DtTotalNanoseconds(Literal(timedelta(microseconds=1))).polars_expr).item()
        1000
    """

    KEY = "dt_total_nanoseconds"
    PL_METHOD = "total_nanoseconds"
    CAST_NAME = "total_nanoseconds"


class DtTotalMinutes(_DtAccessor):
    """Project a Duration to total minutes (Duration → Int64).

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(DtTotalMinutes(Literal(timedelta(hours=2, minutes=30))).polars_expr).item()
        150
    """

    KEY = "dt_total_minutes"
    PL_METHOD = "total_minutes"
    CAST_NAME = "total_minutes"


class DtTotalHours(_DtAccessor):
    """Project a Duration to total hours (Duration → Int64).

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(DtTotalHours(Literal(timedelta(days=1, hours=6))).polars_expr).item()
        30
    """

    KEY = "dt_total_hours"
    PL_METHOD = "total_hours"
    CAST_NAME = "total_hours"


class DtTotalDays(_DtAccessor):
    """Project a Duration to total days (Duration → Int64).

    Example:
        >>> from dftly.nodes import Literal
        >>> pl.select(DtTotalDays(Literal(timedelta(days=30, hours=12))).polars_expr).item()
        30
    """

    KEY = "dt_total_days"
    PL_METHOD = "total_days"
    CAST_NAME = "total_days"
