"""Repayment, overdue and fee reduction APIs."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Path, Query
from pydantic import BaseModel, Field

from ..database import db_cursor, fetch_all, fetch_one
from ..dependencies import RequestContext, get_request_context
from ..errors import bad_request, conflict, forbidden, not_found
from ..idempotency import idempotent_result, save_idempotent_result
from ..response import ok
from ..services import (
    current_employee,
    ensure_account_by_no,
    ensure_channel,
    ensure_customer_by_no,
    ensure_loan_contract,
    insert_success_transaction,
    release_credit_limit_by_repayment,
)
from ..utils import (
    count_total,
    local_now,
    make_no,
    offset_limit,
    serialize_row,
    serialize_rows,
)

router = APIRouter(prefix="/api/v1", tags=["repayments"])


class BillGenerateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    contract_no: str = Field(description="贷款合同号")
    bill_date: date = Field(description="账单日期，格式 YYYY-MM-DD")
    period_start: int | None = Field(default=None, description="起始期数")
    period_end: int | None = Field(default=None, description="结束期数")


class RepaymentAuthorizationRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    customer_no: str = Field(description="客户号，对应 customer.customer_no")
    contract_no: str = Field(description="贷款合同号")
    account_no: str = Field(description="账户号，对应 bank_account.account_no")
    authorization_type: str = Field(description="还款授权类型")
    valid_from: date = Field(description="有效期开始日期")
    valid_to: date = Field(description="有效期结束日期")


class RepaymentCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    bill_no: str = Field(description="还款账单号")
    account_no: str = Field(description="账户号，对应 bank_account.account_no")
    repayment_amount: Decimal = Field(gt=0, description="还款金额，必须大于 0")
    repayment_type: str = Field(default="normal", description="还款类型")


class OverdueRefreshRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    contract_no: str = Field(description="贷款合同号")
    overdue_date: date = Field(description="逾期刷新日期，格式 YYYY-MM-DD")


class FeeReductionCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    bill_no: str = Field(description="还款账单号")
    reduction_type: str = Field(description="费用减免类型")
    apply_amount: Decimal = Field(gt=0, description="申请金额，必须大于 0")
    reason: str = Field(description="业务原因")


class FeeReductionApprovalRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    approval_result: str = Field(description="审批结果")
    approved_amount: Decimal = Field(ge=0, description="审批金额，必须大于或等于 0")
    reason: str | None = Field(default=None, description="业务原因")


@router.get("/loan/contracts/{contract_no}/repayment-schedules", summary="查询还款计划")
def list_repayment_schedules(
    contract_no: Annotated[str, Path(description="贷款合同号")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    contract = ensure_loan_contract(contract_no, ctx)
    rows = fetch_all(
        """
        SELECT period_no, principal_amount, interest_amount, due_date, schedule_status
        FROM repayment_schedule
        WHERE contract_id = %s
        ORDER BY schedule_version, period_no
        """,
        (contract["id"],),
    )
    return ok({"list": serialize_rows(rows)}, ctx.request_id)


@router.post("/repayment/bills/generate", summary="生成还款账单")
def generate_repayment_bills(
    body: Annotated[BillGenerateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "repayment_bill_generate", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    contract = ensure_loan_contract(body.contract_no, ctx)
    where = ["contract_id = %s", "schedule_status IN ('pending', 'billed')"]
    params: list[object] = [contract["id"]]
    if body.period_start is not None:
        where.append("period_no >= %s")
        params.append(body.period_start)
    if body.period_end is not None:
        where.append("period_no <= %s")
        params.append(body.period_end)
    schedules = fetch_all(
        f"SELECT * FROM repayment_schedule WHERE {' AND '.join(where)} ORDER BY period_no",
        tuple(params),
    )
    now = local_now()
    bill_count = 0
    with db_cursor() as (_, cursor):
        for schedule in schedules:
            total_amount = (
                Decimal(str(schedule["principal_amount"]))
                + Decimal(str(schedule["interest_amount"]))
                + Decimal(str(schedule["fee_amount"]))
            )
            cursor.execute(
                """
                INSERT INTO repayment_bill (
                    bill_no,
                    contract_id,
                    schedule_id,
                    customer_id,
                    period_no,
                    due_date,
                    currency_code,
                    principal_amount,
                    interest_amount,
                    fee_amount,
                    outstanding_amount,
                    bill_status,
                    billed_at,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'billed', %s, %s, %s)
                ON DUPLICATE KEY UPDATE updated_at = VALUES(updated_at)
                """,
                (
                    make_no("BIL"),
                    contract["id"],
                    schedule["id"],
                    contract["customer_id"],
                    schedule["period_no"],
                    schedule["due_date"],
                    schedule["currency_code"],
                    schedule["principal_amount"],
                    schedule["interest_amount"],
                    schedule["fee_amount"],
                    total_amount,
                    now,
                    now,
                    now,
                ),
            )
            cursor.execute(
                "UPDATE repayment_schedule SET schedule_status = 'billed', updated_at = %s WHERE id = %s",
                (now, schedule["id"]),
            )
            bill_count += 1
    data = {"bill_count": bill_count}
    save_idempotent_result(
        ctx.channel_code,
        "repayment_bill_generate",
        body.request_no,
        body.model_dump(),
        data,
    )
    return ok(data, ctx.request_id)


@router.get("/repayment/bills", summary="查询还款账单")
def list_repayment_bills(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    customer_no: str | None = Query(
        description="客户号，对应 customer.customer_no", default=None
    ),
    contract_no: str | None = Query(description="贷款合同号", default=None),
    bill_status: str | None = Query(description="账单状态", default=None),
    start_date: date | None = Query(
        description="开始日期，格式 YYYY-MM-DD", default=None
    ),
    end_date: date | None = Query(
        description="结束日期，格式 YYYY-MM-DD", default=None
    ),
    page_no: int = Query(description="页码，从 1 开始", default=1, ge=1),
    page_size: int = Query(
        description="每页条数，范围 1 到 100", default=20, ge=1, le=100
    ),
) -> dict[str, object]:
    where: list[str] = []
    params: list[object] = []
    if customer_no:
        customer = ensure_customer_by_no(customer_no, ctx)
        where.append("customer_id = %s")
        params.append(customer["id"])
    if contract_no:
        contract = ensure_loan_contract(contract_no, ctx)
        where.append("contract_id = %s")
        params.append(contract["id"])
    if bill_status:
        where.append("bill_status = %s")
        params.append(bill_status)
    if start_date:
        where.append("due_date >= %s")
        params.append(start_date)
    if end_date:
        where.append("due_date <= %s")
        params.append(end_date)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    offset, limit = offset_limit(page_no, page_size)
    rows = fetch_all(
        f"""
        SELECT bill_no, outstanding_amount, paid_amount, bill_status
        FROM repayment_bill
        {where_sql}
        ORDER BY due_date DESC, id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )
    total = count_total(
        f"SELECT COUNT(*) AS total FROM repayment_bill {where_sql}",
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


@router.post("/repayment/authorizations", summary="创建自动还款授权")
def create_repayment_authorization(
    body: Annotated[RepaymentAuthorizationRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "repayment_authorization", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    customer = ensure_customer_by_no(body.customer_no, ctx)
    contract = ensure_loan_contract(body.contract_no, ctx)
    account = ensure_account_by_no(body.account_no, ctx)
    if (
        contract["customer_id"] != customer["id"]
        or account["customer_id"] != customer["id"]
    ):
        raise forbidden("REPAYMENT_AUTH_SCOPE_FORBIDDEN", "授权主体不一致")
    if body.valid_to < body.valid_from:
        raise bad_request("INVALID_AUTHORIZATION_PERIOD", "授权有效期不合法")
    now = local_now()
    authorization_no = make_no("AUT")
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO repayment_authorization (
                authorization_no,
                contract_id,
                customer_id,
                account_id,
                authorization_type,
                authorization_status,
                valid_from,
                valid_to,
                signed_at,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, 'active', %s, %s, %s, %s, %s)
            """,
            (
                authorization_no,
                contract["id"],
                customer["id"],
                account["id"],
                body.authorization_type,
                body.valid_from,
                body.valid_to,
                now,
                now,
                now,
            ),
        )
    data = {"authorization_no": authorization_no, "authorization_status": "active"}
    save_idempotent_result(
        ctx.channel_code,
        "repayment_authorization",
        body.request_no,
        body.model_dump(),
        data,
    )
    return ok(data, ctx.request_id)


@router.post("/repayments", summary="发起正常还款")
def create_repayment(
    body: Annotated[RepaymentCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "repayment", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    bill = _bill_by_no(body.bill_no, ctx)
    account = ensure_account_by_no(body.account_no, ctx)
    if account["customer_id"] != bill["customer_id"]:
        raise forbidden("ACCOUNT_CUSTOMER_MISMATCH", "还款账户不属于账单客户")
    if body.repayment_amount > Decimal(str(bill["outstanding_amount"])):
        raise bad_request("REPAYMENT_AMOUNT_EXCEEDED", "还款金额不能超过账单未还金额")
    channel = ensure_channel(ctx.channel_code)
    now = local_now()
    repayment_no = make_no("RPM")
    with db_cursor() as (_, cursor):
        tx = insert_success_transaction(
            cursor,
            account=account,
            channel=channel,
            request_no=body.request_no,
            transaction_type="repayment",
            amount=body.repayment_amount,
            direction="debit",
            related_type="repayment_bill",
            related_id=int(bill["id"]),
            occurred_at=now,
        )
        principal_paid = min(
            body.repayment_amount, Decimal(str(bill["principal_amount"]))
        )
        remain = body.repayment_amount - principal_paid
        interest_paid = min(remain, Decimal(str(bill["interest_amount"])))
        remain -= interest_paid
        fee_paid = min(remain, Decimal(str(bill["fee_amount"])))
        remain -= fee_paid
        penalty_paid = max(remain, Decimal("0.00"))
        cursor.execute(
            """
            INSERT INTO repayment_record (
                repayment_no,
                bill_id,
                contract_id,
                customer_id,
                account_id,
                transaction_id,
                repayment_type,
                currency_code,
                repayment_amount,
                principal_paid_amount,
                interest_paid_amount,
                fee_paid_amount,
                penalty_paid_amount,
                repayment_status,
                repaid_at,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'success', %s, %s, %s)
            """,
            (
                repayment_no,
                bill["id"],
                bill["contract_id"],
                bill["customer_id"],
                account["id"],
                tx["transaction_id"],
                body.repayment_type,
                bill["currency_code"],
                body.repayment_amount,
                principal_paid,
                interest_paid,
                fee_paid,
                penalty_paid,
                now,
                now,
                now,
            ),
        )
        repayment_id = int(cursor.lastrowid)
        cursor.execute(
            """
            INSERT INTO repayment_allocation (
                allocation_no,
                repayment_id,
                bill_id,
                contract_id,
                period_no,
                currency_code,
                principal_amount,
                interest_amount,
                fee_amount,
                penalty_amount,
                allocated_amount,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                make_no("ALC"),
                repayment_id,
                bill["id"],
                bill["contract_id"],
                bill["period_no"],
                bill["currency_code"],
                principal_paid,
                interest_paid,
                fee_paid,
                penalty_paid,
                body.repayment_amount,
                now,
            ),
        )
        outstanding = Decimal(str(bill["outstanding_amount"])) - body.repayment_amount
        status = "paid" if outstanding <= 0 else "partial_paid"
        cursor.execute(
            """
            UPDATE repayment_bill
            SET paid_amount = paid_amount + %s,
                outstanding_amount = %s,
                bill_status = %s,
                paid_at = CASE WHEN %s = 'paid' THEN %s ELSE paid_at END,
                updated_at = %s
            WHERE id = %s
            """,
            (body.repayment_amount, outstanding, status, status, now, now, bill["id"]),
        )
        cursor.execute(
            """
            UPDATE repayment_schedule
            SET schedule_status = %s, updated_at = %s
            WHERE id = %s
            """,
            (status, now, bill["schedule_id"]),
        )
        cursor.execute(
            """
            UPDATE overdue_record
            SET paid_amount = paid_amount + %s,
                outstanding_amount = GREATEST(outstanding_amount - %s, 0),
                overdue_status = CASE
                    WHEN GREATEST(outstanding_amount - %s, 0) = 0 THEN 'settled'
                    ELSE overdue_status
                END,
                settled_at = CASE
                    WHEN GREATEST(outstanding_amount - %s, 0) = 0 THEN %s
                    ELSE settled_at
                END,
                updated_at = %s
            WHERE bill_id = %s
            """,
            (
                body.repayment_amount,
                body.repayment_amount,
                body.repayment_amount,
                body.repayment_amount,
                now,
                now,
                bill["id"],
            ),
        )
        if bill["contract_id"]:
            cursor.execute(
                """
                UPDATE loan_contract
                SET outstanding_principal_amount =
                        GREATEST(outstanding_principal_amount - %s, 0),
                    contract_status = CASE
                        WHEN GREATEST(outstanding_principal_amount - %s, 0) = 0
                        THEN 'completed'
                        ELSE contract_status
                    END,
                    updated_at = %s
                WHERE id = %s
                """,
                (principal_paid, principal_paid, now, bill["contract_id"]),
            )
            release_credit_limit_by_repayment(
                cursor,
                contract_id=int(bill["contract_id"]),
                repayment_id=repayment_id,
                amount=principal_paid,
                now=now,
            )
    data = {
        "repayment_no": repayment_no,
        "repayment_status": "success",
        "transaction_no": tx["transaction_no"],
    }
    save_idempotent_result(
        ctx.channel_code, "repayment", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.get("/repayments/{repayment_no}", summary="查询还款详情")
def get_repayment(
    repayment_no: Annotated[str, Path(description="还款编号")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    row = fetch_one(
        "SELECT * FROM repayment_record WHERE repayment_no = %s", (repayment_no,)
    )
    if row is None:
        raise not_found("REPAYMENT_NOT_FOUND", "还款记录不存在")
    if ctx.auth_type == "customer":
        customer = fetch_one(
            "SELECT customer_no FROM customer WHERE id = %s", (row["customer_id"],)
        )
        if customer is None or customer["customer_no"] != ctx.principal_no:
            raise forbidden("CUSTOMER_SCOPE_FORBIDDEN", "客户只能访问本人业务对象")
    allocations = fetch_all(
        "SELECT * FROM repayment_allocation WHERE repayment_id = %s", (row["id"],)
    )
    tx = fetch_one(
        "SELECT * FROM account_transaction WHERE id = %s", (row["transaction_id"],)
    )
    reconcile = fetch_one(
        "SELECT process_status FROM reconciliation_result WHERE transaction_id = %s ORDER BY id DESC LIMIT 1",
        (row["transaction_id"],),
    )
    return ok(
        {
            "repayment_status": row["repayment_status"],
            "allocations": serialize_rows(allocations),
            "transaction": serialize_row(tx) if tx else None,
            "reconcile_status": reconcile["process_status"] if reconcile else None,
        },
        ctx.request_id,
    )


@router.get("/overdues", summary="查询逾期记录")
def list_overdues(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    customer_no: str | None = Query(
        description="客户号，对应 customer.customer_no", default=None
    ),
    contract_no: str | None = Query(description="贷款合同号", default=None),
    overdue_level: str | None = Query(description="逾期等级", default=None),
    overdue_status: str | None = Query(description="逾期状态", default=None),
    page_no: int = Query(description="页码，从 1 开始", default=1, ge=1),
    page_size: int = Query(
        description="每页条数，范围 1 到 100", default=20, ge=1, le=100
    ),
) -> dict[str, object]:
    where: list[str] = []
    params: list[object] = []
    if customer_no:
        customer = ensure_customer_by_no(customer_no, ctx)
        where.append("overdue.customer_id = %s")
        params.append(customer["id"])
    if contract_no:
        contract = ensure_loan_contract(contract_no, ctx)
        where.append("overdue.contract_id = %s")
        params.append(contract["id"])
    if overdue_level:
        where.append("overdue.overdue_level = %s")
        params.append(overdue_level)
    if overdue_status:
        where.append("overdue.overdue_status = %s")
        params.append(overdue_status)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    offset, limit = offset_limit(page_no, page_size)
    rows = fetch_all(
        f"""
        SELECT
            overdue.overdue_no,
            overdue.overdue_days,
            overdue.overdue_total_amount,
            COALESCE(collection.case_status, 'unassigned') AS collection_status
        FROM overdue_record AS overdue
        LEFT JOIN collection_case AS collection ON collection.overdue_id = overdue.id
        {where_sql}
        ORDER BY overdue.created_at DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )
    total = count_total(
        f"SELECT COUNT(*) AS total FROM overdue_record AS overdue {where_sql}",
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


@router.post("/overdues/refresh", summary="刷新逾期记录")
def refresh_overdues(
    body: Annotated[OverdueRefreshRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "overdue_refresh", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    contract = ensure_loan_contract(body.contract_no, ctx)
    bills = fetch_all(
        """
        SELECT *
        FROM repayment_bill
        WHERE contract_id = %s
          AND outstanding_amount > 0
          AND due_date < %s
        """,
        (contract["id"], body.overdue_date),
    )
    now = local_now()
    count = 0
    with db_cursor() as (_, cursor):
        for bill in bills:
            overdue_days = (body.overdue_date - bill["due_date"]).days
            overdue_total = Decimal(str(bill["outstanding_amount"]))
            cursor.execute(
                """
                INSERT INTO overdue_record (
                    overdue_no,
                    bill_id,
                    contract_id,
                    customer_id,
                    period_no,
                    overdue_start_date,
                    overdue_days,
                    currency_code,
                    overdue_principal_amount,
                    overdue_interest_amount,
                    overdue_fee_amount,
                    penalty_amount,
                    overdue_total_amount,
                    outstanding_amount,
                    overdue_level,
                    overdue_status,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, %s)
                ON DUPLICATE KEY UPDATE
                    overdue_days = VALUES(overdue_days),
                    outstanding_amount = VALUES(outstanding_amount),
                    overdue_status = 'active',
                    updated_at = VALUES(updated_at)
                """,
                (
                    make_no("OVD"),
                    bill["id"],
                    bill["contract_id"],
                    bill["customer_id"],
                    bill["period_no"],
                    bill["due_date"],
                    overdue_days,
                    bill["currency_code"],
                    bill["principal_amount"],
                    bill["interest_amount"],
                    bill["fee_amount"],
                    bill["penalty_amount"],
                    overdue_total,
                    overdue_total,
                    _overdue_level(overdue_days),
                    now,
                    now,
                ),
            )
            cursor.execute(
                "UPDATE repayment_bill SET bill_status = 'overdue', updated_at = %s WHERE id = %s",
                (now, bill["id"]),
            )
            count += 1
    data = {"overdue_count": count}
    save_idempotent_result(
        ctx.channel_code, "overdue_refresh", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post("/fee-reductions", summary="发起费用减免申请")
def create_fee_reduction(
    body: Annotated[FeeReductionCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "fee_reduction", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    bill = _bill_by_no(body.bill_no, ctx)
    if body.apply_amount > Decimal(str(bill["outstanding_amount"])):
        raise bad_request("REDUCTION_AMOUNT_EXCEEDED", "减免金额不能超过账单未还金额")
    now = local_now()
    reduction_no = make_no("RED")
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO fee_reduction (
                reduction_no,
                bill_id,
                contract_id,
                customer_id,
                reduction_type,
                currency_code,
                apply_amount,
                reduction_status,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'submitted', %s, %s)
            """,
            (
                reduction_no,
                bill["id"],
                bill["contract_id"],
                bill["customer_id"],
                body.reduction_type,
                bill["currency_code"],
                body.apply_amount,
                now,
                now,
            ),
        )
    data = {"reduction_no": reduction_no, "reduction_status": "submitted"}
    save_idempotent_result(
        ctx.channel_code, "fee_reduction", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post("/fee-reductions/{reduction_no}/approval", summary="提交费用减免审批")
def approve_fee_reduction(
    reduction_no: Annotated[str, Path(description="减免申请编号")],
    body: Annotated[FeeReductionApprovalRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "fee_reduction_approval", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    reduction = fetch_one(
        "SELECT * FROM fee_reduction WHERE reduction_no = %s", (reduction_no,)
    )
    if reduction is None:
        raise not_found("FEE_REDUCTION_NOT_FOUND", "费用减免申请不存在")
    if reduction["reduction_status"] != "submitted":
        raise conflict("FEE_REDUCTION_STATUS_FORBIDDEN", "费用减免状态不允许审批")
    if body.approval_result not in {"approved", "rejected"}:
        raise bad_request("INVALID_APPROVAL_RESULT", "审批结果不合法")
    employee = current_employee(ctx)
    if employee is None:
        raise forbidden("EMPLOYEE_AUTH_REQUIRED", "审批接口需要员工身份")
    bill = _bill_by_id(int(reduction["bill_id"]))
    if body.approved_amount > Decimal(str(reduction["apply_amount"])):
        raise bad_request(
            "REDUCTION_APPROVED_AMOUNT_EXCEEDED", "审批金额不能超过申请金额"
        )
    now = local_now()
    status = "approved" if body.approval_result == "approved" else "rejected"
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            UPDATE fee_reduction
            SET approved_amount = %s,
                reduction_status = %s,
                approved_by = %s,
                approval_comment = %s,
                approved_at = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (
                body.approved_amount,
                status,
                employee["id"],
                body.reason,
                now,
                now,
                reduction["id"],
            ),
        )
        if status == "approved":
            outstanding = max(
                Decimal(str(bill["outstanding_amount"])) - body.approved_amount,
                Decimal("0.00"),
            )
            cursor.execute(
                """
                UPDATE repayment_bill
                SET reduced_amount = reduced_amount + %s,
                    outstanding_amount = %s,
                    bill_status = CASE WHEN %s = 0 THEN 'paid' ELSE bill_status END,
                    updated_at = %s
                WHERE id = %s
                """,
                (body.approved_amount, outstanding, outstanding, now, bill["id"]),
            )
    data = {
        "reduction_no": reduction_no,
        "reduction_status": status,
        "bill_amount": str(bill["outstanding_amount"]),
    }
    save_idempotent_result(
        ctx.channel_code,
        "fee_reduction_approval",
        body.request_no,
        body.model_dump(),
        data,
    )
    return ok(data, ctx.request_id)


def _bill_by_no(bill_no: str, ctx: RequestContext) -> dict[str, Any]:
    row = fetch_one("SELECT * FROM repayment_bill WHERE bill_no = %s", (bill_no,))
    if row is None:
        raise not_found("REPAYMENT_BILL_NOT_FOUND", "还款账单不存在")
    if ctx.auth_type == "customer":
        customer = fetch_one(
            "SELECT customer_no FROM customer WHERE id = %s", (row["customer_id"],)
        )
        if customer is None or customer["customer_no"] != ctx.principal_no:
            raise forbidden("CUSTOMER_SCOPE_FORBIDDEN", "客户只能访问本人业务对象")
    return row


def _bill_by_id(bill_id: int) -> dict[str, Any]:
    row = fetch_one("SELECT * FROM repayment_bill WHERE id = %s", (bill_id,))
    if row is None:
        raise not_found("REPAYMENT_BILL_NOT_FOUND", "还款账单不存在")
    return row


def _overdue_level(days: int) -> str:
    if days >= 90:
        return "M3"
    if days >= 60:
        return "M2"
    if days >= 30:
        return "M1"
    return "M0"
