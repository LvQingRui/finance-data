"""Unified response helpers."""

from __future__ import annotations

from typing import Any


def ok(data: Any = None, request_id: str | None = None) -> dict[str, Any]:
    return {"code": 0, "message": "ok", "request_id": request_id, "data": data}


def fail(code: str, message: str, request_id: str | None = None) -> dict[str, Any]:
    return {"code": code, "message": message, "request_id": request_id, "data": None}
