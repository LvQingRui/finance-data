"""In-process idempotency support for API handlers."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .errors import conflict

_RECORDS: dict[tuple[str, str, str], tuple[str, dict[str, Any]]] = {}


def idempotent_result(
    channel_code: str,
    business_type: str,
    request_no: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    request_hash = _request_hash(payload)
    key = (channel_code, business_type, request_no)
    record = _RECORDS.get(key)
    if record is None:
        return None
    recorded_hash, response = record
    if recorded_hash != request_hash:
        raise conflict("IDEMPOTENCY_PAYLOAD_MISMATCH", "幂等号对应请求内容不一致")
    return response


def save_idempotent_result(
    channel_code: str,
    business_type: str,
    request_no: str,
    payload: dict[str, Any],
    response: dict[str, Any],
) -> None:
    _RECORDS[(channel_code, business_type, request_no)] = (
        _request_hash(payload),
        response,
    )


def _request_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
