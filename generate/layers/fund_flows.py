"""Shared fund flow row builders."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .common import code, dt

AmountFunc = Callable[[int, dict[str, Any]], float]
TransactionType = str | Callable[[int], str]
TimeFunc = Callable[[int, dict[str, Any]], Any]


def flow_related_id(offset: int, related_id_start: int, related_ids: list[int] | None) -> int:
    if related_ids is not None:
        return related_ids[offset]
    return related_id_start + offset


def flow_time(offset: int, tx_days: int, amount_id: int, account: dict[str, Any], time_func: TimeFunc | None) -> Any:
    if time_func is not None:
        return time_func(amount_id, account)
    return dt(offset % tx_days, 10 + offset % 6)


def is_inflow_type(transaction_type: str) -> bool:
    return transaction_type in {
        "deposit",
        "loan_disbursement",
        "wealth_redeem",
        "wealth_income",
        "refund",
        "collateral_disposal",
    }


def iter_account_transactions(
    *,
    start_id: int,
    total: int,
    accounts: list[dict[str, Any]],
    channel_ids: list[int],
    tx_days: int,
    related_type: str,
    transaction_type: TransactionType,
    prefix: str,
    amount_func: AmountFunc,
    local_now: Callable[[], Any],
    related_id_start: int = 1,
    amount_id_start: int = 1,
    related_ids: list[int] | None = None,
    amount_ids: list[int] | None = None,
    time_func: TimeFunc | None = None,
):
    for offset in range(total):
        row_id = start_id + offset
        related_id = flow_related_id(offset, related_id_start, related_ids)
        amount_id = amount_ids[offset] if amount_ids is not None else (
            related_id if related_ids is not None else amount_id_start + offset
        )
        account = accounts[offset % len(accounts)]
        current_transaction_type = transaction_type(related_id) if callable(transaction_type) else transaction_type
        is_inflow = is_inflow_type(current_transaction_type)
        amount = amount_func(amount_id, account)
        transaction_at = flow_time(offset, tx_days, amount_id, account, time_func)
        yield {
            "id": row_id,
            "transaction_no": code(prefix, row_id, 12),
            "customer_id": account["customer_id"],
            "from_account_id": None if is_inflow else account["id"],
            "to_account_id": account["id"] if is_inflow else None,
            "card_id": None,
            "channel_id": channel_ids[offset % len(channel_ids)],
            "original_transaction_id": None,
            "biz_order_no": code(f"{prefix}B", row_id, 12),
            "external_order_no": code(f"{prefix}E", row_id, 12),
            "merchant_no": f"M{row_id % 1000:06d}",
            "merchant_name": "中州银行",
            "counterparty_name": "中州银行",
            "counterparty_account_no": code(f"{prefix}C", row_id, 12),
            "counterparty_bank_name": "中州银行",
            "transaction_type": current_transaction_type,
            "transaction_status": "success",
            "reconcile_status": "matched",
            "currency_code": account["currency_code"],
            "transaction_amount": amount,
            "fee_amount": 0,
            "related_type": related_type,
            "related_id": related_id,
            "transaction_at": transaction_at,
            "created_at": transaction_at,
            "updated_at": transaction_at,
        }


def iter_channel_transactions(
    *,
    start_id: int,
    transaction_start_id: int,
    total: int,
    accounts: list[dict[str, Any]],
    channel_ids: list[int],
    tx_days: int,
    prefix: str,
    amount_func: AmountFunc,
    local_now: Callable[[], Any],
    amount_id_start: int = 1,
    related_ids: list[int] | None = None,
    amount_ids: list[int] | None = None,
    transaction_prefix: str | None = None,
    time_func: TimeFunc | None = None,
):
    for offset in range(total):
        row_id = start_id + offset
        transaction_id = transaction_start_id + offset
        amount_id = amount_ids[offset] if amount_ids is not None else flow_related_id(offset, amount_id_start, related_ids)
        account = accounts[offset % len(accounts)]
        amount = amount_func(amount_id, account)
        requested_at = flow_time(offset, tx_days, amount_id, account, time_func)
        order_prefix = transaction_prefix or prefix
        yield {
            "id": row_id,
            "channel_txn_no": code(prefix, row_id, 12),
            "channel_id": channel_ids[offset % len(channel_ids)],
            "transaction_id": transaction_id,
            "channel_order_no": code(f"{order_prefix}E", transaction_id, 12),
            "channel_trade_no": code(f"{prefix}T", row_id, 12),
            "request_no": code(f"{prefix}R", row_id, 12),
            "request_type": "payment",
            "request_status": "success",
            "callback_status": "verified",
            "reconcile_status": "matched",
            "currency_code": account["currency_code"],
            "channel_amount": amount,
            "channel_fee_amount": 0,
            "error_code": None,
            "error_message": None,
            "requested_at": requested_at,
            "responded_at": requested_at,
            "callback_at": requested_at,
            "created_at": requested_at,
            "updated_at": requested_at,
        }


def iter_account_ledgers(
    *,
    start_id: int,
    transaction_start_id: int,
    total: int,
    accounts: list[dict[str, Any]],
    tx_days: int,
    prefix: str,
    amount_func: AmountFunc,
    amount_id_start: int = 1,
    related_ids: list[int] | None = None,
    amount_ids: list[int] | None = None,
    transaction_type: TransactionType = "transfer",
    time_func: TimeFunc | None = None,
):
    for offset in range(total):
        row_id = start_id + offset
        transaction_id = transaction_start_id + offset
        amount_id = amount_ids[offset] if amount_ids is not None else flow_related_id(offset, amount_id_start, related_ids)
        account = accounts[offset % len(accounts)]
        current_transaction_type = transaction_type(amount_id) if callable(transaction_type) else transaction_type
        amount = amount_func(amount_id, account)
        ledger_type = "credit" if is_inflow_type(current_transaction_type) else "debit"
        amount_delta = amount if ledger_type == "credit" else -amount
        balance = 5000 + (int(account["id"]) % 200) * 100 + amount
        created_at = flow_time(offset, tx_days, amount_id, account, time_func)
        yield {
            "id": row_id,
            "ledger_no": code(prefix, row_id, 12),
            "account_id": account["id"],
            "customer_id": account["customer_id"],
            "transaction_id": transaction_id,
            "freeze_id": None,
            "freeze_operation_id": None,
            "ledger_type": ledger_type,
            "currency_code": account["currency_code"],
            "amount_delta": str(amount_delta),
            "frozen_delta": "0",
            "balance_after": str(balance),
            "frozen_after": "0",
            "available_after": str(balance),
            "created_at": created_at,
        }


def iter_reconciliation_results(
    *,
    start_id: int,
    transaction_start_id: int,
    channel_transaction_start_id: int,
    total: int,
    channel_ids: list[int],
    tx_days: int,
    prefix: str,
    local_now: Callable[[], Any],
    result_type_func: Callable[[int], str] | None = None,
):
    for offset in range(total):
        row_id = start_id + offset
        channel_index = offset % len(channel_ids)
        day_offset = offset % tx_days
        batch_id = channel_index * tx_days + day_offset + 1
        processed_at = dt(day_offset, 3)
        result_type = result_type_func(offset + 1) if result_type_func else "matched"
        yield {
            "id": row_id,
            "result_no": code(prefix, row_id, 12),
            "batch_id": batch_id,
            "transaction_id": transaction_start_id + offset,
            "channel_transaction_id": channel_transaction_start_id + offset,
            "result_type": result_type,
            "difference_amount": 0,
            "process_status": "closed",
            "process_comment": "自动对账完成",
            "created_at": processed_at,
            "updated_at": processed_at,
        }
