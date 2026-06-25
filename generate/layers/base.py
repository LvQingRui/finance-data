"""Base class for data generators."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, time
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from ..config import LAYERS
from ..insert_support import insert_dict_rows_stream
from ..progress import (
    complete_progress_tasks,
    console_print,
    is_table_completed,
    reset_progress_tasks,
)

LOCAL_TZ = ZoneInfo("Asia/Shanghai")


class BaseGenerator(ABC):
    layer: int = 0
    layer_name: str = ""

    def local_now(self) -> datetime:
        if not hasattr(self, "_local_now"):
            now = datetime.now(LOCAL_TZ)
            batch_end = datetime.combine(
                now.date(),
                time(23, 59, 59),
                tzinfo=LOCAL_TZ,
            )
            self._local_now = max(now, batch_end).replace(
                tzinfo=None,
                microsecond=0,
            )
        return self._local_now

    def log(self, message: str) -> None:
        console_print(message)

    def header(self) -> None:
        reset_progress_tasks()
        name = self.layer_name or LAYERS[self.layer]["name"]
        console_print(f"\n{'=' * 64}")
        console_print(f"Layer {self.layer}: {name}")
        console_print(f"{'=' * 64}")

    def log_table_counts(self, counts: dict[str, int]) -> None:
        for table in LAYERS[self.layer]["tables"]:
            if not is_table_completed(table):
                console_print(f"  [OK] {table}: {counts.get(table, 0):,} rows")
        complete_progress_tasks()

    def stream_rows(
        self,
        table_name: str,
        rows: Iterable[dict[str, Any]],
        *,
        total_rows: int | None = None,
        build_step_name: str | None = None,
    ) -> int:
        return insert_dict_rows_stream(
            table_name,
            rows,
            total_rows=total_rows,
            build_step_name=build_step_name,
        )

    @abstractmethod
    def run(self) -> None:
        """Run generator."""
