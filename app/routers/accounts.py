"""Account, transaction and reconciliation APIs."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Path, Query
from pydantic import BaseModel, Field

from ..database import db_cursor, fetch_all, fetch_one
from ..dependencies import (
    RequestContext,
    ensure_customer_access,
    get_request_context,
)
from ..errors import bad_request, conflict, forbidden, not_found
from ..idempotency import idempotent_result, save_idempotent_result
from ..response import ok
from ..utils import (
    count_total,
    format_datetime,
    local_now,
    make_no,
    offset_limit,
    serialize_row,
    serialize_rows,
)

router = APIRouter(prefix="/api/v1", tags=["accounts"])


class AccountCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    customer_no: str = Field(description="客户号，对应 customer.customer_no")
    product_code: str = Field(description="产品编码")
    currency_code: str = Field(description="币种编码，对应 dim_currency.currency_code")
    branch_code: str = Field(description="机构编码，对应 dim_branch.branch_code")
    channel_code: str = Field(description="渠道编码，对应 dim_channel.channel_code")
    open_amount: Decimal = Field(
        default=Decimal("0.00"), ge=0, description="开户初始金额，必须大于或等于 0"
    )


class CardCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    card_type: str = Field(description="银行卡类型")
    card_level: str = Field(default="standard", description="银行卡等级")


class AccountStatusChangeRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    target_status: str = Field(description="目标状态")
    reason: str = Field(description="业务原因")


class TransactionCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    customer_no: str = Field(description="客户号，对应 customer.customer_no")
    account_no: str = Field(description="账户号，对应 bank_account.account_no")
    transaction_type: str = Field(description="交易类型")
    amount: Decimal = Field(gt=0, description="交易金额，必须大于 0")
    currency_code: str = Field(description="币种编码，对应 dim_currency.currency_code")
    related_type: str = Field(default="none", description="关联业务对象类型")
    related_id: int | None = Field(default=None, description="关联业务对象 ID")
    counterparty_name: str | None = Field(default=None, description="交易对手名称")
    counterparty_account_no: str | None = Field(
        default=None, description="交易对手账号"
    )
    counterparty_bank_name: str | None = Field(
        default=None, description="交易对手开户行"
    )
    merchant_no: str | None = Field(default=None, description="商户编号")
    merchant_name: str | None = Field(default=None, description="商户名称")
    external_order_no: str | None = Field(default=None, description="外部订单号")


class FundFreezeCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    account_no: str = Field(description="账户号，对应 bank_account.account_no")
    freeze_amount: Decimal = Field(gt=0, description="冻结金额，必须大于 0")
    freeze_type: str = Field(default="business", description="冻结类型")
    freeze_reason: str = Field(description="冻结原因")
    related_type: str = Field(description="关联业务对象类型")
    related_id: int | None = Field(default=None, description="关联业务对象 ID")


class FundFreezeOperationRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    operation_type: str = Field(description="冻结操作类型")
    amount: Decimal = Field(gt=0, description="交易金额，必须大于 0")
    reason: str = Field(description="业务原因")


class ReconciliationBatchCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    channel_code: str = Field(description="渠道编码，对应 dim_channel.channel_code")
    reconcile_date: date = Field(description="对账日期，格式 YYYY-MM-DD")
    file_name: str | None = Field(default=None, description="对账文件名")
    file_hash: str | None = Field(default=None, description="材料文件摘要")


class ReconciliationResultCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    batch_no: str = Field(description="对账批次号")
    transaction_no: str | None = Field(
        default=None, description="账户交易号，对应 account_transaction.transaction_no"
    )
    channel_txn_no: str | None = Field(default=None, description="渠道流水号")
    result_type: str = Field(description="对账结果类型")


class ReconciliationAdjustmentCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    result_no: str = Field(description="对账结果编号")
    adjustment_amount: Decimal = Field(gt=0, description="调账金额，必须大于 0")
    adjustment_reason: str = Field(description="调账原因")
    adjustment_direction: str = Field(default="credit", description="调账方向")


class ReconciliationAdjustmentApprovalRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    approval_result: str = Field(description="审批结果")
    approval_amount: Decimal = Field(ge=0, description="审批金额，必须大于或等于 0")
    approval_comment: str | None = Field(default=None, description="审批意见")


class ReconciliationAdjustmentPostRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    account_no: str = Field(description="账户号，对应 bank_account.account_no")
    post_amount: Decimal = Field(gt=0, description="入账金额，必须大于 0")
    post_date: date = Field(description="入账日期，格式 YYYY-MM-DD")


@router.post("/accounts", summary="开立银行账户")
def create_account(
    body: Annotated[AccountCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "account_create", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    if body.channel_code != ctx.channel_code:
        raise bad_request("CHANNEL_MISMATCH", "请求渠道与开户渠道不一致")
    customer = ensure_customer_access(body.customer_no, ctx)
    branch = _ensure_branch(body.branch_code)
    channel = _ensure_channel(body.channel_code)
    product = _ensure_account_product(body.product_code, body.currency_code)
    if product["currency_code"] != body.currency_code:
        raise bad_request("PRODUCT_CURRENCY_MISMATCH", "账户产品币种与开户币种不一致")
    now = local_now()
    account_no = make_no("ACC")
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO bank_account (
                account_no,
                customer_id,
                branch_id,
                open_channel_id,
                account_product_id,
                currency_code,
                account_type,
                account_status,
                balance_amount,
                frozen_amount,
                available_amount,
                opened_at,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'active', %s, 0, %s, %s, %s, %s)
            """,
            (
                account_no,
                customer["id"],
                branch["id"],
                channel["id"],
                product["id"],
                body.currency_code,
                product["account_type"],
                body.open_amount,
                body.open_amount,
                now,
                now,
                now,
            ),
        )
        account_id = int(cursor.lastrowid)
        cursor.execute(
            """
            INSERT INTO bank_account_status_history (
                account_id,
                customer_id,
                change_seq,
                from_status,
                to_status,
                change_reason,
                related_type,
                related_id,
                changed_at,
                created_at
            )
            VALUES (%s, %s, 1, 'none', 'active', 'account_create', 'bank_account', %s, %s, %s)
            """,
            (account_id, customer["id"], account_id, now, now),
        )
    data = {
        "account_no": account_no,
        "account_status": "active",
        "opened_at": format_datetime(now),
    }
    save_idempotent_result(
        ctx.channel_code, "account_create", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.get("/accounts/{account_no}", summary="查询账户详情")
def get_account(
    account_no: Annotated[
        str, Path(description="账户号，对应 bank_account.account_no")
    ],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    account = _ensure_account_access(account_no, ctx)
    product = fetch_one(
        """
        SELECT product_code, product_name, account_type, product_status
        FROM account_product
        WHERE id = %s
        """,
        (account["account_product_id"],),
    )
    return ok(
        {
            "account_status": account["account_status"],
            "balance_amount": str(account["balance_amount"]),
            "frozen_amount": str(account["frozen_amount"]),
            "account_product": serialize_row(product) if product else None,
        },
        ctx.request_id,
    )


@router.get("/customers/{customer_no}/accounts", summary="查询客户账户列表")
def list_customer_accounts(
    customer_no: Annotated[str, Path(description="客户号，对应 customer.customer_no")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    account_status: str | None = Query(description="账户状态", default=None),
) -> dict[str, object]:
    customer = ensure_customer_access(customer_no, ctx)
    where = ["account.customer_id = %s"]
    params: list[object] = [customer["id"]]
    if account_status:
        where.append("account.account_status = %s")
        params.append(account_status)
    rows = fetch_all(
        f"""
        SELECT
            account.account_no,
            account.balance_amount,
            account.currency_code,
            product.product_code,
            product.product_name
        FROM bank_account AS account
        JOIN account_product AS product ON product.id = account.account_product_id
        WHERE {" AND ".join(where)}
        ORDER BY account.opened_at DESC, account.id DESC
        """,
        tuple(params),
    )
    data = [
        {
            "account_no": row["account_no"],
            "balance_amount": str(row["balance_amount"]),
            "currency_code": row["currency_code"],
            "account_product": {
                "product_code": row["product_code"],
                "product_name": row["product_name"],
            },
        }
        for row in rows
    ]
    return ok({"list": data}, ctx.request_id)


@router.post("/accounts/{account_no}/cards", summary="绑定银行卡")
def create_card(
    account_no: Annotated[
        str, Path(description="账户号，对应 bank_account.account_no")
    ],
    body: Annotated[CardCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "card_create", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    account = _ensure_account_access(account_no, ctx)
    if account["account_status"] != "active":
        raise forbidden("ACCOUNT_STATUS_FORBIDDEN", "账户状态不允许绑卡")
    now = local_now()
    card_no = make_no("CARD")
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO bank_card (
                card_no,
                customer_id,
                account_id,
                card_type,
                card_level,
                card_status,
                issued_at,
                expired_at,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, 'active', %s, %s, %s, %s)
            """,
            (
                card_no,
                account["customer_id"],
                account["id"],
                body.card_type,
                body.card_level,
                now,
                now + timedelta(days=365 * 10),
                now,
                now,
            ),
        )
    data = {
        "card_no": card_no,
        "card_status": "active",
        "issued_at": format_datetime(now),
    }
    save_idempotent_result(
        ctx.channel_code, "card_create", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post("/accounts/{account_no}/status-changes", summary="变更账户状态")
def change_account_status(
    account_no: Annotated[
        str, Path(description="账户号，对应 bank_account.account_no")
    ],
    body: Annotated[AccountStatusChangeRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "account_status_change", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    account = _ensure_account_access(account_no, ctx)
    if body.target_status == account["account_status"]:
        raise conflict("ACCOUNT_STATUS_UNCHANGED", "目标状态与当前状态一致")
    now = local_now()
    operator = _operator(ctx)
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT COALESCE(MAX(change_seq), 0) + 1 AS next_seq
            FROM bank_account_status_history
            WHERE account_id = %s
            FOR UPDATE
            """,
            (account["id"],),
        )
        seq = int(cursor.fetchone()["next_seq"])
        cursor.execute(
            """
            INSERT INTO bank_account_status_history (
                account_id,
                customer_id,
                change_seq,
                from_status,
                to_status,
                change_reason,
                related_type,
                related_id,
                operator_id,
                changed_at,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'bank_account', %s, %s, %s, %s)
            """,
            (
                account["id"],
                account["customer_id"],
                seq,
                account["account_status"],
                body.target_status,
                body.reason,
                account["id"],
                operator["id"] if operator else None,
                now,
                now,
            ),
        )
        history_id = int(cursor.lastrowid)
        cursor.execute(
            """
            UPDATE bank_account
            SET account_status = %s, updated_at = %s
            WHERE id = %s
            """,
            (body.target_status, now, account["id"]),
        )
    data = {
        "status_history_id": history_id,
        "change_seq": seq,
        "current_status": body.target_status,
    }
    save_idempotent_result(
        ctx.channel_code,
        "account_status_change",
        body.request_no,
        body.model_dump(),
        data,
    )
    return ok(data, ctx.request_id)


@router.post("/transactions", summary="发起普通账户交易")
def create_transaction(
    body: Annotated[TransactionCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "account_transaction", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    customer = ensure_customer_access(body.customer_no, ctx)
    account = _ensure_account_access(body.account_no, ctx)
    if account["customer_id"] != customer["id"]:
        raise forbidden("ACCOUNT_CUSTOMER_MISMATCH", "账户不属于请求客户")
    if account["currency_code"] != body.currency_code:
        raise bad_request("CURRENCY_MISMATCH", "交易币种与账户币种不一致")
    if account["account_status"] != "active":
        raise forbidden("ACCOUNT_STATUS_FORBIDDEN", "账户状态不允许交易")
    channel = _ensure_channel(ctx.channel_code)
    now = local_now()
    is_credit = body.transaction_type in {
        "deposit",
        "refund",
        "loan_disbursement",
        "wealth_redeem",
        "income_settle",
        "adjustment_credit",
    }
    available = Decimal(str(account["available_amount"]))
    success = is_credit or available >= body.amount
    transaction_status = "success" if success else "failed"
    transaction_no = make_no("TXN")
    channel_txn_no = make_no("CHN")
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO account_transaction (
                transaction_no,
                customer_id,
                from_account_id,
                to_account_id,
                channel_id,
                external_order_no,
                merchant_no,
                merchant_name,
                counterparty_name,
                counterparty_account_no,
                counterparty_bank_name,
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
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, 'pending', %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                transaction_no,
                customer["id"],
                None if is_credit else account["id"],
                account["id"] if is_credit else None,
                channel["id"],
                body.external_order_no,
                body.merchant_no,
                body.merchant_name,
                body.counterparty_name,
                body.counterparty_account_no,
                body.counterparty_bank_name,
                body.transaction_type,
                transaction_status,
                body.currency_code,
                body.amount,
                body.related_type,
                body.related_id,
                now,
                now,
                now,
            ),
        )
        transaction_id = int(cursor.lastrowid)
        cursor.execute(
            """
            INSERT INTO channel_transaction (
                channel_txn_no,
                channel_id,
                transaction_id,
                channel_order_no,
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
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                channel_txn_no,
                channel["id"],
                transaction_id,
                body.external_order_no,
                channel_txn_no,
                body.request_no,
                body.transaction_type,
                transaction_status,
                transaction_status,
                body.currency_code,
                body.amount,
                now,
                now,
                now,
                now,
                now,
            ),
        )
        channel_transaction_id = int(cursor.lastrowid)
        if success:
            balance_after = Decimal(str(account["balance_amount"])) + (
                body.amount if is_credit else -body.amount
            )
            available_after = Decimal(str(account["available_amount"])) + (
                body.amount if is_credit else -body.amount
            )
            cursor.execute(
                """
                UPDATE bank_account
                SET balance_amount = %s, available_amount = %s, updated_at = %s
                WHERE id = %s
                """,
                (balance_after, available_after, now, account["id"]),
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
                    customer["id"],
                    transaction_id,
                    "credit" if is_credit else "debit",
                    body.currency_code,
                    str(body.amount if is_credit else -body.amount),
                    str(balance_after),
                    str(account["frozen_amount"]),
                    str(available_after),
                    now,
                ),
            )
            batch_id = _get_or_create_batch(cursor, channel["id"], now.date(), now)
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
                (
                    make_no("REC"),
                    batch_id,
                    transaction_id,
                    channel_transaction_id,
                    now,
                    now,
                ),
            )
    data = {
        "transaction_no": transaction_no,
        "transaction_status": transaction_status,
        "channel_txn_no": channel_txn_no,
        "related_type": body.related_type,
        "related_no": str(body.related_id) if body.related_id is not None else None,
    }
    save_idempotent_result(
        ctx.channel_code,
        "account_transaction",
        body.request_no,
        body.model_dump(),
        data,
    )
    return ok(data, ctx.request_id)


@router.get("/transactions/{transaction_no}", summary="查询账户交易详情")
def get_transaction(
    transaction_no: Annotated[
        str, Path(description="账户交易号，对应 account_transaction.transaction_no")
    ],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    tx = fetch_one(
        """
        SELECT *
        FROM account_transaction
        WHERE transaction_no = %s
        """,
        (transaction_no,),
    )
    if tx is None:
        raise not_found("TRANSACTION_NOT_FOUND", "账户交易不存在")
    _ensure_customer_scope(int(tx["customer_id"]), ctx)
    channel_txn = fetch_one(
        """
        SELECT *
        FROM channel_transaction
        WHERE transaction_id = %s
        ORDER BY id DESC
        LIMIT 1
        """,
        (tx["id"],),
    )
    reconcile = fetch_one(
        """
        SELECT process_status, result_type
        FROM reconciliation_result
        WHERE transaction_id = %s
        ORDER BY id DESC
        LIMIT 1
        """,
        (tx["id"],),
    )
    return ok(
        {
            "transaction_status": tx["transaction_status"],
            "amount": str(tx["transaction_amount"]),
            "channel_transaction": serialize_row(channel_txn) if channel_txn else None,
            "reconcile_status": reconcile["process_status"] if reconcile else None,
        },
        ctx.request_id,
    )


@router.get("/accounts/{account_no}/transactions", summary="查询账户交易明细")
def list_account_transactions(
    account_no: Annotated[
        str, Path(description="账户号，对应 bank_account.account_no")
    ],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    start_time: datetime | None = Query(
        description="开始时间，ISO 8601 本地时间格式", default=None
    ),
    end_time: datetime | None = Query(
        description="结束时间，ISO 8601 本地时间格式", default=None
    ),
    transaction_type: str | None = Query(description="交易类型", default=None),
    transaction_status: str | None = Query(description="交易状态", default=None),
    page_no: int = Query(description="页码，从 1 开始", default=1, ge=1),
    page_size: int = Query(
        description="每页条数，范围 1 到 100", default=20, ge=1, le=100
    ),
) -> dict[str, object]:
    account = _ensure_account_access(account_no, ctx)
    where = ["(from_account_id = %s OR to_account_id = %s)"]
    params: list[object] = [account["id"], account["id"]]
    if start_time:
        where.append("transaction_at >= %s")
        params.append(start_time)
    if end_time:
        where.append("transaction_at <= %s")
        params.append(end_time)
    if transaction_type:
        where.append("transaction_type = %s")
        params.append(transaction_type)
    if transaction_status:
        where.append("transaction_status = %s")
        params.append(transaction_status)
    offset, limit = offset_limit(page_no, page_size)
    rows = fetch_all(
        f"""
        SELECT *
        FROM account_transaction
        WHERE {" AND ".join(where)}
        ORDER BY transaction_at DESC, id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )
    total = count_total(
        f"""
        SELECT COUNT(*) AS total
        FROM account_transaction
        WHERE {" AND ".join(where)}
        """,
        tuple(params),
    )
    return ok(
        {
            "list": serialize_rows(rows),
            "page_no": page_no,
            "page_size": page_size,
            "total_count": total,
        },
        ctx.request_id,
    )


@router.get("/accounts/{account_no}/ledgers", summary="查询账户资金流水")
def list_account_ledgers(
    account_no: Annotated[
        str, Path(description="账户号，对应 bank_account.account_no")
    ],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    start_time: datetime | None = Query(
        description="开始时间，ISO 8601 本地时间格式", default=None
    ),
    end_time: datetime | None = Query(
        description="结束时间，ISO 8601 本地时间格式", default=None
    ),
    ledger_type: str | None = Query(description="流水类型", default=None),
    page_no: int = Query(description="页码，从 1 开始", default=1, ge=1),
    page_size: int = Query(
        description="每页条数，范围 1 到 100", default=20, ge=1, le=100
    ),
) -> dict[str, object]:
    account = _ensure_account_access(account_no, ctx)
    where = ["account_id = %s"]
    params: list[object] = [account["id"]]
    if start_time:
        where.append("created_at >= %s")
        params.append(start_time)
    if end_time:
        where.append("created_at <= %s")
        params.append(end_time)
    if ledger_type:
        where.append("ledger_type = %s")
        params.append(ledger_type)
    offset, limit = offset_limit(page_no, page_size)
    rows = fetch_all(
        f"""
        SELECT *
        FROM account_ledger
        WHERE {" AND ".join(where)}
        ORDER BY created_at DESC, id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )
    total = count_total(
        f"""
        SELECT COUNT(*) AS total
        FROM account_ledger
        WHERE {" AND ".join(where)}
        """,
        tuple(params),
    )
    return ok(
        {
            "list": serialize_rows(rows),
            "page_no": page_no,
            "page_size": page_size,
            "total_count": total,
        },
        ctx.request_id,
    )


@router.post("/fund-freezes", summary="新增资金冻结")
def create_fund_freeze(
    body: Annotated[FundFreezeCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "fund_freeze", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    account = _ensure_account_access(body.account_no, ctx)
    if Decimal(str(account["available_amount"])) < body.freeze_amount:
        raise conflict("INSUFFICIENT_AVAILABLE_AMOUNT", "账户可用余额不足")
    now = local_now()
    freeze_no = make_no("FRZ")
    operation_no = make_no("FOP")
    after_frozen = Decimal(str(account["frozen_amount"])) + body.freeze_amount
    after_available = Decimal(str(account["available_amount"])) - body.freeze_amount
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO fund_freeze (
                freeze_no,
                account_id,
                customer_id,
                freeze_type,
                related_type,
                related_id,
                currency_code,
                freeze_amount,
                freeze_status,
                frozen_at,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, %s, %s)
            """,
            (
                freeze_no,
                account["id"],
                account["customer_id"],
                body.freeze_type,
                body.related_type,
                body.related_id,
                account["currency_code"],
                body.freeze_amount,
                now,
                now,
                now,
            ),
        )
        freeze_id = int(cursor.lastrowid)
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
            VALUES (%s, %s, %s, %s, %s, %s, 'freeze', %s, %s, %s, %s, 'api', %s, %s, %s)
            """,
            (
                operation_no,
                freeze_id,
                account["id"],
                account["customer_id"],
                body.related_type,
                body.related_id,
                account["currency_code"],
                body.freeze_amount,
                account["frozen_amount"],
                after_frozen,
                body.freeze_reason,
                now,
                now,
            ),
        )
        operation_id = int(cursor.lastrowid)
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
            VALUES (%s, %s, %s, %s, %s, 'freeze', %s, '0.00', %s, %s, %s, %s, %s)
            """,
            (
                make_no("LED"),
                account["id"],
                account["customer_id"],
                freeze_id,
                operation_id,
                account["currency_code"],
                str(body.freeze_amount),
                str(account["balance_amount"]),
                str(after_frozen),
                str(after_available),
                now,
            ),
        )
    data = {"freeze_no": freeze_no, "freeze_status": "active"}
    save_idempotent_result(
        ctx.channel_code, "fund_freeze", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post("/fund-freezes/{freeze_no}/operations", summary="解冻或释放冻结")
def operate_fund_freeze(
    freeze_no: Annotated[
        str, Path(description="资金冻结编号，对应 fund_freeze.freeze_no")
    ],
    body: Annotated[FundFreezeOperationRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "fund_freeze_operation", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    if body.operation_type not in {"unfreeze", "release", "cancel"}:
        raise bad_request("INVALID_FREEZE_OPERATION", "冻结操作类型不合法")
    freeze = _ensure_freeze_access(freeze_no, ctx)
    frozen_balance = Decimal(str(freeze["freeze_amount"])) - Decimal(
        str(freeze["released_amount"])
    )
    if body.amount > frozen_balance:
        raise conflict("FREEZE_BALANCE_NOT_ENOUGH", "冻结余额不足")
    account = _account_by_id(int(freeze["account_id"]))
    now = local_now()
    after_frozen = Decimal(str(account["frozen_amount"])) - body.amount
    after_available = Decimal(str(account["available_amount"])) + body.amount
    released_amount = Decimal(str(freeze["released_amount"])) + body.amount
    freeze_status = (
        "released"
        if released_amount >= Decimal(str(freeze["freeze_amount"]))
        else "active"
    )
    operation_no = make_no("FOP")
    with db_cursor() as (_, cursor):
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
                freeze["id"],
                account["id"],
                account["customer_id"],
                freeze["related_type"],
                freeze["related_id"],
                body.operation_type,
                account["currency_code"],
                body.amount,
                account["frozen_amount"],
                after_frozen,
                body.reason,
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
            (released_amount, freeze_status, freeze_status, now, now, freeze["id"]),
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
                freeze["id"],
                operation_id,
                body.operation_type,
                account["currency_code"],
                str(-body.amount),
                str(account["balance_amount"]),
                str(after_frozen),
                str(after_available),
                now,
            ),
        )
    data = {
        "operation_no": operation_no,
        "frozen_balance": str(Decimal(str(frozen_balance)) - body.amount),
        "freeze_status": freeze_status,
    }
    save_idempotent_result(
        ctx.channel_code,
        "fund_freeze_operation",
        body.request_no,
        body.model_dump(),
        data,
    )
    return ok(data, ctx.request_id)


@router.post("/reconciliation/batches", summary="创建对账批次")
def create_reconciliation_batch(
    body: Annotated[ReconciliationBatchCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "reconciliation_batch", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    channel = _ensure_channel(body.channel_code)
    now = local_now()
    with db_cursor() as (_, cursor):
        batch_id = _get_or_create_batch(cursor, channel["id"], body.reconcile_date, now)
        cursor.execute(
            "SELECT batch_no, batch_status FROM reconciliation_batch WHERE id = %s",
            (batch_id,),
        )
        batch = cursor.fetchone()
    data = {"batch_no": batch["batch_no"], "batch_status": batch["batch_status"]}
    save_idempotent_result(
        ctx.channel_code,
        "reconciliation_batch",
        body.request_no,
        body.model_dump(),
        data,
    )
    return ok(data, ctx.request_id)


@router.post("/reconciliation/results", summary="写入对账结果")
def create_reconciliation_result(
    body: Annotated[ReconciliationResultCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "reconciliation_result", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    batch = _batch_by_no(body.batch_no)
    tx = _transaction_by_no(body.transaction_no) if body.transaction_no else None
    channel_txn = (
        _channel_transaction_by_no(body.channel_txn_no) if body.channel_txn_no else None
    )
    difference_amount, process_status = _reconciliation_outcome(
        body.result_type, tx, channel_txn
    )
    now = local_now()
    result_no = make_no("REC")
    with db_cursor() as (_, cursor):
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
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                result_no,
                batch["id"],
                tx["id"] if tx else None,
                channel_txn["id"] if channel_txn else None,
                body.result_type,
                difference_amount,
                process_status,
                now,
                now,
            ),
        )
    data = {"result_no": result_no, "process_status": process_status}
    save_idempotent_result(
        ctx.channel_code,
        "reconciliation_result",
        body.request_no,
        body.model_dump(),
        data,
    )
    return ok(data, ctx.request_id)


@router.post("/reconciliation/adjustments", summary="发起调账")
def create_reconciliation_adjustment(
    body: Annotated[
        ReconciliationAdjustmentCreateRequest, Body(description="接口请求体")
    ],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code,
        "reconciliation_adjustment",
        body.request_no,
        body.model_dump(),
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    result = _result_by_no(body.result_no)
    if result["process_status"] == "closed":
        raise conflict("RECONCILIATION_RESULT_CLOSED", "已关闭对账结果不可调账")
    if body.adjustment_amount > Decimal(str(result["difference_amount"])):
        raise bad_request("ADJUSTMENT_AMOUNT_EXCEEDED", "调账金额不能超过差错金额")
    tx = (
        _transaction_by_id(result["transaction_id"])
        if result["transaction_id"]
        else None
    )
    channel_txn = (
        _channel_transaction_by_id(result["channel_transaction_id"])
        if result["channel_transaction_id"]
        else None
    )
    if tx is None and channel_txn is None:
        raise bad_request(
            "RECONCILIATION_SIDE_REQUIRED", "调账必须存在银行侧或渠道侧流水"
        )
    if tx is not None:
        currency_code = tx["currency_code"]
    else:
        assert channel_txn is not None
        currency_code = channel_txn["currency_code"]
    now = local_now()
    adjustment_no = make_no("ADJ")
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO reconciliation_adjustment (
                adjustment_no,
                result_id,
                transaction_id,
                currency_code,
                adjustment_amount,
                adjustment_direction,
                adjustment_status,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'submitted', %s, %s)
            """,
            (
                adjustment_no,
                result["id"],
                tx["id"] if tx else None,
                currency_code,
                body.adjustment_amount,
                body.adjustment_direction,
                now,
                now,
            ),
        )
    data = {"adjustment_no": adjustment_no, "adjustment_status": "submitted"}
    save_idempotent_result(
        ctx.channel_code,
        "reconciliation_adjustment",
        body.request_no,
        body.model_dump(),
        data,
    )
    return ok(data, ctx.request_id)


@router.post("/reconciliation/adjustments/{adjustment_no}/approval", summary="审批调账")
def approve_reconciliation_adjustment(
    adjustment_no: Annotated[
        str, Path(description="调账编号，对应 reconciliation_adjustment.adjustment_no")
    ],
    body: Annotated[
        ReconciliationAdjustmentApprovalRequest, Body(description="接口请求体")
    ],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code,
        "reconciliation_adjustment_approval",
        body.request_no,
        body.model_dump(),
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    adjustment = _adjustment_by_no(adjustment_no)
    if adjustment["adjustment_status"] != "submitted":
        raise conflict("ADJUSTMENT_STATUS_FORBIDDEN", "调账状态不允许审批")
    if body.approval_result not in {"approved", "rejected"}:
        raise bad_request("INVALID_APPROVAL_RESULT", "审批结果不合法")
    if body.approval_amount > Decimal(str(adjustment["adjustment_amount"])):
        raise bad_request("APPROVAL_AMOUNT_EXCEEDED", "审批金额不能超过申请金额")
    operator = _operator(ctx)
    now = local_now()
    status = "approved" if body.approval_result == "approved" else "rejected"
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            UPDATE reconciliation_adjustment
            SET
                adjustment_amount = %s,
                adjustment_status = %s,
                approved_by = %s,
                approved_at = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (
                body.approval_amount,
                status,
                operator["id"] if operator else None,
                now,
                now,
                adjustment["id"],
            ),
        )
    data = {"adjustment_no": adjustment_no, "adjustment_status": status}
    save_idempotent_result(
        ctx.channel_code,
        "reconciliation_adjustment_approval",
        body.request_no,
        body.model_dump(),
        data,
    )
    return ok(data, ctx.request_id)


@router.post("/reconciliation/adjustments/{adjustment_no}/post", summary="调账入账")
def post_reconciliation_adjustment(
    adjustment_no: Annotated[
        str, Path(description="调账编号，对应 reconciliation_adjustment.adjustment_no")
    ],
    body: Annotated[
        ReconciliationAdjustmentPostRequest, Body(description="接口请求体")
    ],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code,
        "reconciliation_adjustment_post",
        body.request_no,
        body.model_dump(),
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    adjustment = _adjustment_by_no(adjustment_no)
    if adjustment["adjustment_status"] != "approved":
        raise conflict("ADJUSTMENT_STATUS_FORBIDDEN", "只有已审批调账可以入账")
    if body.post_amount != Decimal(str(adjustment["adjustment_amount"])):
        raise bad_request("POST_AMOUNT_MISMATCH", "入账金额必须等于审批调账金额")
    account = _ensure_account_access(body.account_no, ctx)
    tx_response = _post_adjustment_transaction(
        account,
        adjustment,
        body.request_no,
        body.post_amount,
        body.post_date,
        ctx,
    )
    now = local_now()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            UPDATE reconciliation_adjustment
            SET adjustment_status = 'posted', posted_at = %s, updated_at = %s
            WHERE id = %s
            """,
            (now, now, adjustment["id"]),
        )
        cursor.execute(
            """
            UPDATE reconciliation_result
            SET process_status = 'closed', updated_at = %s
            WHERE id = %s
            """,
            (now, adjustment["result_id"]),
        )
    data = {
        "adjustment_no": adjustment_no,
        "adjustment_status": "posted",
        "transaction_no": tx_response["transaction_no"],
    }
    save_idempotent_result(
        ctx.channel_code,
        "reconciliation_adjustment_post",
        body.request_no,
        body.model_dump(),
        data,
    )
    return ok(data, ctx.request_id)


def _ensure_account_access(account_no: str, ctx: RequestContext) -> dict[str, Any]:
    row = fetch_one("SELECT * FROM bank_account WHERE account_no = %s", (account_no,))
    if row is None:
        raise not_found("ACCOUNT_NOT_FOUND", "账户不存在")
    _ensure_customer_scope(int(row["customer_id"]), ctx)
    return row


def _ensure_customer_scope(customer_id: int, ctx: RequestContext) -> None:
    if ctx.auth_type != "customer":
        return
    row = fetch_one("SELECT customer_no FROM customer WHERE id = %s", (customer_id,))
    if row is None or row["customer_no"] != ctx.principal_no:
        raise forbidden("CUSTOMER_SCOPE_FORBIDDEN", "客户只能访问本人业务对象")


def _account_by_id(account_id: int) -> dict[str, Any]:
    row = fetch_one("SELECT * FROM bank_account WHERE id = %s", (account_id,))
    if row is None:
        raise not_found("ACCOUNT_NOT_FOUND", "账户不存在")
    return row


def _ensure_branch(branch_code: str) -> dict[str, Any]:
    row = fetch_one(
        """
        SELECT *
        FROM dim_branch
        WHERE branch_code = %s AND branch_status = 'active'
        """,
        (branch_code,),
    )
    if row is None:
        raise not_found("BRANCH_NOT_AVAILABLE", "机构不存在或不可用")
    return row


def _ensure_channel(channel_code: str) -> dict[str, Any]:
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


def _ensure_account_product(product_code: str, currency_code: str) -> dict[str, Any]:
    row = fetch_one(
        """
        SELECT product.*
        FROM account_product AS product
        JOIN dim_currency AS currency
            ON currency.currency_code = product.currency_code
        JOIN dim_product_category AS category ON category.id = product.category_id
        WHERE product.product_code = %s
          AND product.currency_code = %s
          AND product.product_status = 'active'
          AND currency.yn = 1
          AND category.yn = 1
        """,
        (product_code, currency_code),
    )
    if row is None:
        raise not_found("ACCOUNT_PRODUCT_NOT_AVAILABLE", "账户产品不存在或不可用")
    return row


def _ensure_freeze_access(freeze_no: str, ctx: RequestContext) -> dict[str, Any]:
    row = fetch_one("SELECT * FROM fund_freeze WHERE freeze_no = %s", (freeze_no,))
    if row is None:
        raise not_found("FUND_FREEZE_NOT_FOUND", "资金冻结记录不存在")
    _ensure_customer_scope(int(row["customer_id"]), ctx)
    if row["freeze_status"] not in {"active", "partial_released"}:
        raise conflict("FREEZE_STATUS_FORBIDDEN", "冻结状态不允许操作")
    return row


def _operator(ctx: RequestContext) -> dict[str, Any] | None:
    employee_no = ctx.operator_no if ctx.operator_no else ctx.principal_no
    row = fetch_one(
        "SELECT * FROM dim_employee WHERE employee_no = %s AND employee_status = 'active'",
        (employee_no,),
    )
    return row


def _get_or_create_batch(
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
    existing = cursor.fetchone()
    if existing:
        return int(existing["id"])
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
        (
            batch_no,
            channel_id,
            reconcile_date,
            f"{batch_no}.csv",
            now,
            now,
            now,
        ),
    )
    return int(cursor.lastrowid)


def _batch_by_no(batch_no: str) -> dict[str, Any]:
    row = fetch_one(
        "SELECT * FROM reconciliation_batch WHERE batch_no = %s", (batch_no,)
    )
    if row is None:
        raise not_found("RECONCILIATION_BATCH_NOT_FOUND", "对账批次不存在")
    return row


def _transaction_by_no(transaction_no: str | None) -> dict[str, Any]:
    row = fetch_one(
        "SELECT * FROM account_transaction WHERE transaction_no = %s",
        (transaction_no,),
    )
    if row is None:
        raise not_found("TRANSACTION_NOT_FOUND", "账户交易不存在")
    return row


def _transaction_by_id(transaction_id: int) -> dict[str, Any]:
    row = fetch_one(
        "SELECT * FROM account_transaction WHERE id = %s", (transaction_id,)
    )
    if row is None:
        raise not_found("TRANSACTION_NOT_FOUND", "账户交易不存在")
    return row


def _channel_transaction_by_no(channel_txn_no: str | None) -> dict[str, Any]:
    row = fetch_one(
        "SELECT * FROM channel_transaction WHERE channel_txn_no = %s",
        (channel_txn_no,),
    )
    if row is None:
        raise not_found("CHANNEL_TRANSACTION_NOT_FOUND", "渠道流水不存在")
    return row


def _channel_transaction_by_id(channel_transaction_id: int) -> dict[str, Any]:
    row = fetch_one(
        "SELECT * FROM channel_transaction WHERE id = %s",
        (channel_transaction_id,),
    )
    if row is None:
        raise not_found("CHANNEL_TRANSACTION_NOT_FOUND", "渠道流水不存在")
    return row


def _result_by_no(result_no: str) -> dict[str, Any]:
    row = fetch_one(
        "SELECT * FROM reconciliation_result WHERE result_no = %s",
        (result_no,),
    )
    if row is None:
        raise not_found("RECONCILIATION_RESULT_NOT_FOUND", "对账结果不存在")
    return row


def _adjustment_by_no(adjustment_no: str) -> dict[str, Any]:
    row = fetch_one(
        "SELECT * FROM reconciliation_adjustment WHERE adjustment_no = %s",
        (adjustment_no,),
    )
    if row is None:
        raise not_found("RECONCILIATION_ADJUSTMENT_NOT_FOUND", "调账申请不存在")
    return row


def _reconciliation_outcome(
    result_type: str,
    tx: dict[str, Any] | None,
    channel_txn: dict[str, Any] | None,
) -> tuple[Decimal, str]:
    if result_type in {"matched", "amount_mismatch", "status_mismatch"}:
        if tx is None or channel_txn is None:
            raise bad_request(
                "RECONCILIATION_BOTH_SIDE_REQUIRED", "该匹配结果必须同时提供两侧流水"
            )
    if result_type == "bank_only":
        if tx is None or channel_txn is not None:
            raise bad_request(
                "RECONCILIATION_BANK_ONLY_INVALID", "银行单边结果只能提供账户交易"
            )
        return Decimal(str(tx["transaction_amount"])), "pending"
    if result_type == "channel_only":
        if channel_txn is None or tx is not None:
            raise bad_request(
                "RECONCILIATION_CHANNEL_ONLY_INVALID", "渠道单边结果只能提供渠道流水"
            )
        return Decimal(str(channel_txn["channel_amount"])), "pending"
    if result_type == "matched":
        if tx is None or channel_txn is None:
            raise bad_request(
                "RECONCILIATION_BOTH_SIDE_REQUIRED", "该匹配结果必须同时提供两侧流水"
            )
        if Decimal(str(tx["transaction_amount"])) != Decimal(
            str(channel_txn["channel_amount"])
        ):
            raise bad_request(
                "RECONCILIATION_AMOUNT_MISMATCH", "matched 结果金额必须一致"
            )
        return Decimal("0.00"), "closed"
    if result_type == "amount_mismatch":
        if tx is None or channel_txn is None:
            raise bad_request(
                "RECONCILIATION_BOTH_SIDE_REQUIRED", "该匹配结果必须同时提供两侧流水"
            )
        return abs(
            Decimal(str(tx["transaction_amount"]))
            - Decimal(str(channel_txn["channel_amount"]))
        ), "pending"
    if result_type == "status_mismatch":
        return Decimal("0.00"), "pending"
    raise bad_request("INVALID_RECONCILIATION_RESULT_TYPE", "对账匹配结果不合法")


def _post_adjustment_transaction(
    account: dict[str, Any],
    adjustment: dict[str, Any],
    request_no: str,
    amount: Decimal,
    post_date: date,
    ctx: RequestContext,
) -> dict[str, object]:
    channel = _ensure_channel(ctx.channel_code)
    now = local_now()
    transaction_no = make_no("TXN")
    channel_txn_no = make_no("CHN")
    is_credit = adjustment["adjustment_direction"] == "credit"
    balance_after = Decimal(str(account["balance_amount"])) + (
        amount if is_credit else -amount
    )
    available_after = Decimal(str(account["available_amount"])) + (
        amount if is_credit else -amount
    )
    with db_cursor() as (_, cursor):
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
            VALUES (%s, %s, %s, %s, %s, 'adjustment', 'success', 'pending', %s, %s, 'reconciliation_adjustment', %s, %s, %s, %s)
            """,
            (
                transaction_no,
                account["customer_id"],
                None if is_credit else account["id"],
                account["id"] if is_credit else None,
                channel["id"],
                account["currency_code"],
                amount,
                adjustment["id"],
                datetime.combine(post_date, datetime.min.time()),
                now,
                now,
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
            VALUES (%s, %s, %s, %s, %s, 'adjustment', 'success', 'success', 'pending', %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                channel_txn_no,
                channel["id"],
                transaction_id,
                channel_txn_no,
                request_no,
                account["currency_code"],
                amount,
                now,
                now,
                now,
                now,
                now,
            ),
        )
        channel_transaction_id = int(cursor.lastrowid)
        cursor.execute(
            """
            UPDATE bank_account
            SET balance_amount = %s, available_amount = %s, updated_at = %s
            WHERE id = %s
            """,
            (balance_after, available_after, now, account["id"]),
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
                "credit" if is_credit else "debit",
                account["currency_code"],
                str(amount if is_credit else -amount),
                str(balance_after),
                str(account["frozen_amount"]),
                str(available_after),
                now,
            ),
        )
        batch_id = _get_or_create_batch(cursor, channel["id"], post_date, now)
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
            (
                make_no("REC"),
                batch_id,
                transaction_id,
                channel_transaction_id,
                now,
                now,
            ),
        )
    return {"transaction_no": transaction_no, "channel_txn_no": channel_txn_no}
