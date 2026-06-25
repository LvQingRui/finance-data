"""Shared business helpers for API handlers."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from .database import fetch_one
from .dependencies import RequestContext
from .errors import conflict, forbidden, not_found
from .utils import make_no


def ensure_channel(channel_code: str) -> dict[str, Any]:
    row = fetch_one(
        """
        SELECT *
        FROM dim_channel
        WHERE channel_code = %s AND channel_status = 'active' AND yn = 1
        """,
        (channel_code,),
    )
    if row is None:
        raise not_found("CHANNEL_NOT_AVAILABLE", "渠道不存在或不可用")
    return row


def ensure_employee(employee_no: str | None) -> dict[str, Any] | None:
    if not employee_no:
        return None
    row = fetch_one(
        """
        SELECT *
        FROM dim_employee
        WHERE employee_no = %s AND employee_status = 'active'
        """,
        (employee_no,),
    )
    if row is None:
        raise forbidden("EMPLOYEE_NOT_AVAILABLE", "员工不存在或不可用")
    return row


def current_employee(ctx: RequestContext) -> dict[str, Any] | None:
    employee_no = ctx.operator_no if ctx.operator_no else ctx.principal_no
    return ensure_employee(employee_no)


def ensure_customer_by_no(customer_no: str, ctx: RequestContext) -> dict[str, Any]:
    row = fetch_one("SELECT * FROM customer WHERE customer_no = %s", (customer_no,))
    if row is None:
        raise not_found("CUSTOMER_NOT_FOUND", "客户不存在")
    ensure_customer_scope(int(row["id"]), ctx)
    if row["customer_status"] in {"closed", "cancelled", "blacklisted"}:
        raise forbidden("CUSTOMER_STATUS_FORBIDDEN", "客户状态不允许办理当前业务")
    return row


def ensure_customer_scope(customer_id: int, ctx: RequestContext) -> None:
    if ctx.auth_type != "customer":
        return
    row = fetch_one("SELECT customer_no FROM customer WHERE id = %s", (customer_id,))
    if row is None or row["customer_no"] != ctx.principal_no:
        raise forbidden("CUSTOMER_SCOPE_FORBIDDEN", "客户只能访问本人业务对象")


def ensure_account_by_no(account_no: str, ctx: RequestContext) -> dict[str, Any]:
    row = fetch_one("SELECT * FROM bank_account WHERE account_no = %s", (account_no,))
    if row is None:
        raise not_found("ACCOUNT_NOT_FOUND", "账户不存在")
    ensure_customer_scope(int(row["customer_id"]), ctx)
    return row


def ensure_credit_limit(limit_no: str, ctx: RequestContext) -> dict[str, Any]:
    row = fetch_one("SELECT * FROM credit_limit WHERE limit_no = %s", (limit_no,))
    if row is None:
        raise not_found("CREDIT_LIMIT_NOT_FOUND", "授信额度不存在")
    ensure_customer_scope(int(row["customer_id"]), ctx)
    return row


def ensure_loan_contract(contract_no: str, ctx: RequestContext) -> dict[str, Any]:
    row = fetch_one("SELECT * FROM loan_contract WHERE contract_no = %s", (contract_no,))
    if row is None:
        raise not_found("LOAN_CONTRACT_NOT_FOUND", "贷款合同不存在")
    ensure_customer_scope(int(row["customer_id"]), ctx)
    return row


def get_or_create_reconciliation_batch(
    cursor: Any, channel_id: int, reconcile_date: date, now: datetime
) -> int:
    cursor.execute(
        """
        SELECT id
        FROM reconciliation_batch
        WHERE channel_id = %s
          AND reconcile_date = %s
          AND batch_status IN ('created', 'processing', 'completed')
        LIMIT 1
        """,
        (channel_id, reconcile_date),
    )
    row = cursor.fetchone()
    if row:
        return int(row["id"])
    batch_no = make_no("BAT")
    cursor.execute(
        """
        INSERT INTO reconciliation_batch (
            batch_no,
            channel_id,
            reconcile_date,
            file_name,
            batch_status,
            started_at,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, 'created', %s, %s, %s)
        """,
        (batch_no, channel_id, reconcile_date, f"{batch_no}.csv", now, now, now),
    )
    return int(cursor.lastrowid)


def insert_success_transaction(
    cursor: Any,
    *,
    account: dict[str, Any],
    channel: dict[str, Any],
    request_no: str,
    transaction_type: str,
    amount: Decimal,
    direction: str,
    related_type: str,
    related_id: int | None,
    occurred_at: datetime,
) -> dict[str, Any]:
    if direction not in {"credit", "debit"}:
        raise ValueError("direction must be credit or debit")
    if direction == "debit" and Decimal(str(account["available_amount"])) < amount:
        raise conflict("INSUFFICIENT_AVAILABLE_AMOUNT", "账户可用余额不足")
    transaction_no = make_no("TXN")
    channel_txn_no = make_no("CHN")
    amount_delta = amount if direction == "credit" else -amount
    balance_after = Decimal(str(account["balance_amount"])) + amount_delta
    available_after = Decimal(str(account["available_amount"])) + amount_delta
    cursor.execute(
        """
        INSERT INTO account_transaction (
            transaction_no,
            customer_id,
            from_account_id,
            to_account_id,
            channel_id,
            transaction_type,
            transaction_status,
            reconcile_status,
            currency_code,
            transaction_amount,
            related_type,
            related_id,
            transaction_at,
            created_at,
            updated_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, 'success', 'pending',
            %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            transaction_no,
            account["customer_id"],
            account["id"] if direction == "debit" else None,
            account["id"] if direction == "credit" else None,
            channel["id"],
            transaction_type,
            account["currency_code"],
            amount,
            related_type,
            related_id,
            occurred_at,
            occurred_at,
            occurred_at,
        ),
    )
    transaction_id = int(cursor.lastrowid)
    cursor.execute(
        """
        INSERT INTO channel_transaction (
            channel_txn_no,
            channel_id,
            transaction_id,
            channel_trade_no,
            request_no,
            request_type,
            request_status,
            callback_status,
            reconcile_status,
            currency_code,
            channel_amount,
            requested_at,
            responded_at,
            callback_at,
            created_at,
            updated_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, 'success', 'success', 'pending',
            %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            channel_txn_no,
            channel["id"],
            transaction_id,
            channel_txn_no,
            request_no,
            transaction_type,
            account["currency_code"],
            amount,
            occurred_at,
            occurred_at,
            occurred_at,
            occurred_at,
            occurred_at,
        ),
    )
    channel_transaction_id = int(cursor.lastrowid)
    cursor.execute(
        """
        UPDATE bank_account
        SET balance_amount = %s, available_amount = %s, updated_at = %s
        WHERE id = %s
        """,
        (balance_after, available_after, occurred_at, account["id"]),
    )
    cursor.execute(
        """
        INSERT INTO account_ledger (
            ledger_no,
            account_id,
            customer_id,
            transaction_id,
            ledger_type,
            currency_code,
            amount_delta,
            frozen_delta,
            balance_after,
            frozen_after,
            available_after,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, '0.00', %s, %s, %s, %s)
        """,
        (
            make_no("LED"),
            account["id"],
            account["customer_id"],
            transaction_id,
            direction,
            account["currency_code"],
            str(amount_delta),
            str(balance_after),
            str(account["frozen_amount"]),
            str(available_after),
            occurred_at,
        ),
    )
    ledger_id = int(cursor.lastrowid)
    batch_id = get_or_create_reconciliation_batch(
        cursor, int(channel["id"]), occurred_at.date(), occurred_at
    )
    cursor.execute(
        """
        INSERT INTO reconciliation_result (
            result_no,
            batch_id,
            transaction_id,
            channel_transaction_id,
            result_type,
            difference_amount,
            process_status,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, 'matched', 0, 'closed', %s, %s)
        """,
        (make_no("REC"), batch_id, transaction_id, channel_transaction_id, occurred_at, occurred_at),
    )
    return {
        "transaction_id": transaction_id,
        "transaction_no": transaction_no,
        "channel_txn_no": channel_txn_no,
        "ledger_id": ledger_id,
        "balance_after": balance_after,
        "available_after": available_after,
    }


def fetch_account_for_update(cursor: Any, account_id: int) -> dict[str, Any]:
    cursor.execute("SELECT * FROM bank_account WHERE id = %s FOR UPDATE", (account_id,))
    row = cursor.fetchone()
    if row is None:
        raise not_found("ACCOUNT_NOT_FOUND", "账户不存在")
    return row


def release_fund_freeze(
    cursor: Any,
    *,
    freeze_id: int,
    account: dict[str, Any],
    amount: Decimal,
    operation_type: str,
    reason: str,
    now: datetime,
) -> dict[str, Any]:
    cursor.execute("SELECT * FROM fund_freeze WHERE id = %s FOR UPDATE", (freeze_id,))
    freeze = cursor.fetchone()
    if freeze is None:
        raise not_found("FUND_FREEZE_NOT_FOUND", "资金冻结不存在")
    frozen_balance = Decimal(str(freeze["freeze_amount"])) - Decimal(
        str(freeze["released_amount"])
    )
    if amount > frozen_balance:
        raise conflict("FREEZE_BALANCE_NOT_ENOUGH", "冻结余额不足")
    before_frozen = Decimal(str(account["frozen_amount"]))
    before_available = Decimal(str(account["available_amount"]))
    after_frozen = before_frozen - amount
    after_available = before_available + amount
    released_amount = Decimal(str(freeze["released_amount"])) + amount
    freeze_status = (
        "released"
        if released_amount >= Decimal(str(freeze["freeze_amount"]))
        else "active"
    )
    operation_no = make_no("FOP")
    cursor.execute(
        """
        INSERT INTO fund_freeze_operation (
            operation_no,
            freeze_id,
            account_id,
            customer_id,
            related_type,
            related_id,
            operation_type,
            currency_code,
            operation_amount,
            before_frozen_amount,
            after_frozen_amount,
            operation_source,
            operation_reason,
            operated_at,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'api', %s, %s, %s)
        """,
        (
            operation_no,
            freeze_id,
            account["id"],
            account["customer_id"],
            freeze["related_type"],
            freeze["related_id"],
            operation_type,
            account["currency_code"],
            amount,
            before_frozen,
            after_frozen,
            reason,
            now,
            now,
        ),
    )
    operation_id = int(cursor.lastrowid)
    cursor.execute(
        """
        UPDATE fund_freeze
        SET
            released_amount = %s,
            freeze_status = %s,
            released_at = CASE WHEN %s = 'released' THEN %s ELSE released_at END,
            updated_at = %s
        WHERE id = %s
        """,
        (released_amount, freeze_status, freeze_status, now, now, freeze_id),
    )
    cursor.execute(
        """
        UPDATE bank_account
        SET frozen_amount = %s, available_amount = %s, updated_at = %s
        WHERE id = %s
        """,
        (after_frozen, after_available, now, account["id"]),
    )
    cursor.execute(
        """
        INSERT INTO account_ledger (
            ledger_no,
            account_id,
            customer_id,
            freeze_id,
            freeze_operation_id,
            ledger_type,
            currency_code,
            amount_delta,
            frozen_delta,
            balance_after,
            frozen_after,
            available_after,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, '0.00', %s, %s, %s, %s, %s)
        """,
        (
            make_no("LED"),
            account["id"],
            account["customer_id"],
            freeze_id,
            operation_id,
            operation_type,
            account["currency_code"],
            str(-amount),
            str(account["balance_amount"]),
            str(after_frozen),
            str(after_available),
            now,
        ),
    )
    return {
        "operation_no": operation_no,
        "freeze_status": freeze_status,
        "frozen_balance": frozen_balance - amount,
        "available_after": after_available,
        "frozen_after": after_frozen,
    }


def next_credit_limit_change_seq(cursor: Any, credit_limit_id: int) -> int:
    cursor.execute(
        """
        SELECT COALESCE(MAX(change_seq), 0) + 1 AS next_seq
        FROM credit_limit_change_log
        WHERE credit_limit_id = %s
        FOR UPDATE
        """,
        (credit_limit_id,),
    )
    return int(cursor.fetchone()["next_seq"])


def insert_credit_limit_change_log(
    cursor: Any,
    *,
    limit_row: dict[str, Any],
    change_type: str,
    change_amount: Decimal,
    before_used: Decimal,
    after_used: Decimal,
    before_frozen: Decimal,
    after_frozen: Decimal,
    before_available: Decimal,
    after_available: Decimal,
    now: datetime,
    credit_application_id: int | None = None,
    loan_application_id: int | None = None,
    contract_id: int | None = None,
    repayment_id: int | None = None,
) -> None:
    cursor.execute(
        """
        INSERT INTO credit_limit_change_log (
            change_no,
            credit_limit_id,
            change_seq,
            credit_application_id,
            loan_application_id,
            contract_id,
            repayment_id,
            change_type,
            currency_code,
            change_amount,
            before_total_amount,
            after_total_amount,
            before_used_amount,
            after_used_amount,
            before_frozen_amount,
            after_frozen_amount,
            before_available_amount,
            after_available_amount,
            changed_at,
            created_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            make_no("LCL"),
            limit_row["id"],
            next_credit_limit_change_seq(cursor, int(limit_row["id"])),
            credit_application_id,
            loan_application_id,
            contract_id,
            repayment_id,
            change_type,
            limit_row["currency_code"],
            change_amount,
            limit_row["total_limit_amount"],
            limit_row["total_limit_amount"],
            before_used,
            after_used,
            before_frozen,
            after_frozen,
            before_available,
            after_available,
            now,
            now,
        ),
    )


def credit_limit_for_contract(cursor: Any, contract_id: int) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT limit_row.*
        FROM credit_limit AS limit_row
        JOIN loan_application AS application
          ON application.credit_limit_id = limit_row.id
        JOIN loan_contract AS contract
          ON contract.application_id = application.id
        WHERE contract.id = %s
        FOR UPDATE
        """,
        (contract_id,),
    )
    return cursor.fetchone()


def occupy_credit_limit_for_contract(
    cursor: Any,
    *,
    contract: dict[str, Any],
    amount: Decimal,
    now: datetime,
) -> None:
    limit_row = credit_limit_for_contract(cursor, int(contract["id"]))
    if limit_row is None:
        return
    before_used = Decimal(str(limit_row["used_limit_amount"]))
    before_frozen = Decimal(str(limit_row["frozen_limit_amount"]))
    before_available = Decimal(str(limit_row["available_limit_amount"]))
    after_used = before_used + amount
    after_frozen = max(before_frozen - amount, Decimal("0.00"))
    after_available = before_available
    cursor.execute(
        """
        UPDATE credit_limit
        SET used_limit_amount = %s,
            frozen_limit_amount = %s,
            available_limit_amount = %s,
            updated_at = %s
        WHERE id = %s
        """,
        (after_used, after_frozen, after_available, now, limit_row["id"]),
    )
    insert_credit_limit_change_log(
        cursor,
        limit_row=limit_row,
        change_type="occupy",
        change_amount=amount,
        before_used=before_used,
        after_used=after_used,
        before_frozen=before_frozen,
        after_frozen=after_frozen,
        before_available=before_available,
        after_available=after_available,
        contract_id=int(contract["id"]),
        loan_application_id=int(contract["application_id"])
        if contract["application_id"]
        else None,
        now=now,
    )


def release_credit_limit_by_repayment(
    cursor: Any,
    *,
    contract_id: int,
    repayment_id: int,
    amount: Decimal,
    now: datetime,
) -> None:
    if amount <= 0:
        return
    limit_row = credit_limit_for_contract(cursor, contract_id)
    if limit_row is None:
        return
    before_used = Decimal(str(limit_row["used_limit_amount"]))
    before_frozen = Decimal(str(limit_row["frozen_limit_amount"]))
    before_available = Decimal(str(limit_row["available_limit_amount"]))
    after_used = max(before_used - amount, Decimal("0.00"))
    after_frozen = before_frozen
    after_available = before_available + amount
    cursor.execute(
        """
        UPDATE credit_limit
        SET used_limit_amount = %s,
            available_limit_amount = %s,
            updated_at = %s
        WHERE id = %s
        """,
        (after_used, after_available, now, limit_row["id"]),
    )
    insert_credit_limit_change_log(
        cursor,
        limit_row=limit_row,
        change_type="repayment_release",
        change_amount=amount,
        before_used=before_used,
        after_used=after_used,
        before_frozen=before_frozen,
        after_frozen=after_frozen,
        before_available=before_available,
        after_available=after_available,
        repayment_id=repayment_id,
        contract_id=contract_id,
        now=now,
    )


def create_workflow(
    cursor: Any,
    *,
    workflow_type: str,
    related_type: str,
    related_id: int,
    initiator_type: str,
    initiator_no: str,
    assignee_id: int | None,
    now: datetime,
) -> dict[str, str]:
    instance_no = make_no("WFI")
    task_no = make_no("WFT")
    cursor.execute(
        """
        INSERT INTO workflow_instance (
            instance_no,
            workflow_type,
            related_type,
            related_id,
            initiator_type,
            initiator_no,
            instance_status,
            started_at,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, 'running', %s, %s, %s)
        """,
        (
            instance_no,
            workflow_type,
            related_type,
            related_id,
            initiator_type,
            initiator_no,
            now,
            now,
            now,
        ),
    )
    instance_id = int(cursor.lastrowid)
    cursor.execute(
        """
        INSERT INTO workflow_task (
            task_no,
            instance_id,
            node_code,
            node_name,
            assignee_id,
            task_status,
            assigned_at,
            created_at,
            updated_at
        )
        VALUES (%s, %s, 'initial_review', '初审', %s, 'pending', %s, %s, %s)
        """,
        (task_no, instance_id, assignee_id, now, now, now),
    )
    return {"instance_no": instance_no, "task_no": task_no}
