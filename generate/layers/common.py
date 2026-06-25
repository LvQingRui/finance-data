"""Shared generation helpers."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from ..db import db


def clear_tables(tables: list[str]) -> None:
    row = db.fetch_one("SELECT @@FOREIGN_KEY_CHECKS AS foreign_key_checks")
    original = int(row["foreign_key_checks"]) if row else 1
    db.execute("SET FOREIGN_KEY_CHECKS = 0")
    try:
        for table in reversed(tables):
            db.execute(f"TRUNCATE TABLE `{table}`")
    finally:
        db.execute(f"SET FOREIGN_KEY_CHECKS = {original}")


def table_count(table: str) -> int:
    row = db.fetch_one(f"SELECT COUNT(*) AS cnt FROM `{table}`")
    return int(row["cnt"]) if row else 0


def max_id(table: str) -> int:
    row = db.fetch_one(f"SELECT COALESCE(MAX(id), 0) AS max_id FROM `{table}`")
    return int(row["max_id"]) if row else 0


def id_cycle(ids: list[int], index: int) -> int:
    if not ids:
        raise ValueError("id list is empty")
    return ids[index % len(ids)]


def fetch_ids(table: str, where: str = "1 = 1") -> list[int]:
    rows = db.fetch_all(f"SELECT id FROM `{table}` WHERE {where} ORDER BY id")
    return [int(row["id"]) for row in rows]


def fetch_id_values(
    table: str,
    columns: list[str],
    where: str = "1 = 1",
    limit: int | None = None,
) -> list[dict[str, Any]]:
    column_sql = ", ".join(columns)
    sql = f"SELECT {column_sql} FROM `{table}` WHERE {where} ORDER BY id"
    if limit:
        sql += f" LIMIT {limit}"
    return db.fetch_all(sql)


def start_date(days: int) -> date:
    return date.today() - timedelta(days=days)


def dt(days_ago: int, hour: int = 9, minute: int = 0) -> datetime:
    base = date.today() - timedelta(days=days_ago)
    return datetime(base.year, base.month, base.day, hour, minute, 0)


def money(value: int | float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def code(prefix: str, value: int, width: int = 8) -> str:
    return f"{prefix}{value:0{width}d}"
