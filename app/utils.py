"""Utility helpers for API handlers."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Asia/Shanghai")


def local_now() -> datetime:
    return datetime.now(LOCAL_TZ).replace(tzinfo=None)


def offset_limit(page_no: int, page_size: int) -> tuple[int, int]:
    normalized_page_no = max(page_no, 1)
    normalized_page_size = max(min(page_size, 100), 1)
    return (normalized_page_no - 1) * normalized_page_size, normalized_page_size


def format_datetime(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value is not None else None


def format_date(value: date | None) -> str | None:
    return value.strftime("%Y-%m-%d") if value is not None else None


def format_time(value: time | timedelta | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return value.strftime("%H:%M:%S")


def money(value: Decimal | float | int | None) -> str | None:
    if value is None:
        return None
    return f"{Decimal(str(value)):.2f}"


def make_no(prefix: str) -> str:
    return f"{prefix}{local_now().strftime('%Y%m%d%H%M%S%f')}"


def serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return format_datetime(value)
    if isinstance(value, date):
        return format_date(value)
    if isinstance(value, (time, timedelta)):
        return format_time(value)
    if isinstance(value, Decimal):
        return str(value)
    return value


def serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: serialize_value(value) for key, value in row.items()}


def serialize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [serialize_row(row) for row in rows]


def count_total(sql: str, params: Any | None = None) -> int:
    from .database import fetch_one

    row = fetch_one(sql, params)
    if row is None or row["total"] is None:
        return 0
    return int(row["total"])
