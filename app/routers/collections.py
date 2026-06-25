"""Collection case, action, recovery and disposal APIs."""

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

router = APIRouter(prefix="/api/v1", tags=["collections"])


class CollectionCaseCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    overdue_no: str = Field(description="逾期编号")
    collector_no: str = Field(description="催收员编号")
    collection_stage: str = Field(description="催收阶段")


class CollectionActionCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    action_type: str = Field(description="催收动作类型")
    action_result: str = Field(description="催收动作结果")


class CollectionContactCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    contact_method: str = Field(description="联系渠道")
    contact_result: str = Field(description="联系结果")
    contact_content: str = Field(description="联系内容")
    next_contact_at: str | None = Field(default=None, description="下次联系时间")


class RepaymentPromiseCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    promise_amount: Decimal = Field(gt=0, description="承诺还款金额，必须大于 0")
    promise_date: date = Field(description="承诺还款日期")


class CollectionRepaymentRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    bill_no: str = Field(description="还款账单号")
    account_no: str = Field(description="账户号，对应 bank_account.account_no")
    repayment_amount: Decimal = Field(gt=0, description="还款金额，必须大于 0")
    promise_no: str | None = Field(default=None, description="承诺还款编号")


class LegalCaseCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    legal_type: str = Field(description="法诉类型")
    claim_amount: Decimal = Field(gt=0, description="诉讼标的金额，必须大于 0")


class WriteOffCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    apply_amount: Decimal = Field(gt=0, description="申请金额，必须大于 0")


class WriteOffApprovalRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    approval_result: str = Field(description="审批结果")
    approved_amount: Decimal = Field(ge=0, description="审批金额，必须大于或等于 0")
    approval_comment: str | None = Field(default=None, description="审批意见")


class WriteOffPostRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    post_date: date = Field(description="入账日期，格式 YYYY-MM-DD")


class RestructureCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    restructure_principal_amount: Decimal = Field(
        gt=0, description="重组本金金额，必须大于 0"
    )
    new_term_months: int = Field(gt=0, description="新期限月数，必须大于 0")
    new_interest_rate: Decimal = Field(ge=0, description="新利率，必须大于或等于 0")
    restructure_type: str = Field(default="extension", description="重组类型")


class RestructureApprovalRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    approval_result: str = Field(description="审批结果")
    approval_comment: str | None = Field(default=None, description="审批意见")


class RestructureEffectiveRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    effective_date: date = Field(description="生效日期，格式 YYYY-MM-DD")


class CollateralDisposalCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    collateral_no: str = Field(description="抵押物编号")
    disposal_amount: Decimal = Field(gt=0, description="处置金额，必须大于 0")
    received_amount: Decimal = Field(ge=0, description="实收金额，必须大于或等于 0")
    account_no: str = Field(description="账户号，对应 bank_account.account_no")
    disposal_method: str = Field(description="处置方式")


@router.post("/collection/cases", summary="创建催收案件")
def create_collection_case(
    body: Annotated[CollectionCaseCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "collection_case", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    overdue = _overdue_by_no(body.overdue_no, ctx)
    collector = _employee_by_no(body.collector_no)
    now = local_now()
    case_no = make_no("COL")
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO collection_case (
                case_no,
                overdue_id,
                contract_id,
                customer_id,
                collector_id,
                collection_stage,
                case_status,
                case_amount,
                assigned_at,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'active', %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                collector_id = VALUES(collector_id),
                collection_stage = VALUES(collection_stage),
                case_status = 'active',
                updated_at = VALUES(updated_at)
            """,
            (
                case_no,
                overdue["id"],
                overdue["contract_id"],
                overdue["customer_id"],
                collector["id"],
                body.collection_stage,
                overdue["outstanding_amount"],
                now,
                now,
                now,
            ),
        )
        cursor.execute(
            "SELECT case_no, case_status FROM collection_case WHERE overdue_id = %s",
            (overdue["id"],),
        )
        row = cursor.fetchone()
    data = {"case_no": row["case_no"], "case_status": row["case_status"]}
    save_idempotent_result(
        ctx.channel_code, "collection_case", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.get("/collection/cases/{case_no}", summary="查询催收案件详情")
def get_collection_case(
    case_no: Annotated[str, Path(description="案件编号")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    case = _collection_case_by_no(case_no, ctx)
    actions = fetch_all(
        "SELECT * FROM collection_action WHERE case_id = %s", (case["id"],)
    )
    contacts = fetch_all(
        "SELECT * FROM collection_contact_record WHERE case_id = %s", (case["id"],)
    )
    promises = fetch_all(
        "SELECT * FROM repayment_promise WHERE case_id = %s", (case["id"],)
    )
    return ok(
        {
            "case_info": serialize_row(case),
            "actions": serialize_rows(actions),
            "contacts": serialize_rows(contacts),
            "promises": serialize_rows(promises),
        },
        ctx.request_id,
    )


@router.post("/collection/cases/{case_no}/actions", summary="记录催收动作")
def create_collection_action(
    case_no: Annotated[str, Path(description="案件编号")],
    body: Annotated[CollectionActionCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "collection_action", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    case = _collection_case_by_no(case_no, ctx)
    employee = current_employee(ctx)
    now = local_now()
    action_no = make_no("ACT")
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO collection_action (
                action_no,
                case_id,
                customer_id,
                contract_id,
                action_type,
                action_status,
                action_result,
                operator_id,
                action_at,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, 'completed', %s, %s, %s, %s, %s)
            """,
            (
                action_no,
                case["id"],
                case["customer_id"],
                case["contract_id"],
                body.action_type,
                body.action_result,
                employee["id"] if employee else None,
                now,
                now,
                now,
            ),
        )
    data = {"action_no": action_no, "action_status": "completed"}
    save_idempotent_result(
        ctx.channel_code, "collection_action", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post("/collection/cases/{case_no}/contacts", summary="记录催收联系")
def create_collection_contact(
    case_no: Annotated[str, Path(description="案件编号")],
    body: Annotated[CollectionContactCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "collection_contact", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    case = _collection_case_by_no(case_no, ctx)
    collector_id = case["collector_id"]
    now = local_now()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO collection_contact_record (
                case_id,
                collector_id,
                assistant_collector_id,
                contact_method,
                contact_result,
                contact_content,
                contacted_at,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                case["id"],
                collector_id,
                collector_id,
                body.contact_method,
                body.contact_result,
                body.contact_content,
                now,
                now,
            ),
        )
        contact_id = int(cursor.lastrowid)
    data = {"contact_id": contact_id, "contact_result": body.contact_result}
    save_idempotent_result(
        ctx.channel_code, "collection_contact", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post("/collection/cases/{case_no}/promises", summary="记录承诺还款")
def create_repayment_promise(
    case_no: Annotated[str, Path(description="案件编号")],
    body: Annotated[RepaymentPromiseCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "repayment_promise", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    case = _collection_case_by_no(case_no, ctx)
    now = local_now()
    promise_no = make_no("PRM")
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO repayment_promise (
                promise_no,
                case_id,
                customer_id,
                currency_code,
                promise_amount,
                promise_date,
                promise_status,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'active', %s, %s)
            """,
            (
                promise_no,
                case["id"],
                case["customer_id"],
                _case_currency(case),
                body.promise_amount,
                body.promise_date,
                now,
                now,
            ),
        )
    data = {"promise_no": promise_no, "promise_status": "active"}
    save_idempotent_result(
        ctx.channel_code, "repayment_promise", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post("/collection/cases/{case_no}/repayments", summary="记录催收回款")
def create_collection_repayment(
    case_no: Annotated[str, Path(description="案件编号")],
    body: Annotated[CollectionRepaymentRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "collection_repayment", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    case = _collection_case_by_no(case_no, ctx)
    bill = _bill_by_no(body.bill_no)
    if (
        bill["contract_id"] != case["contract_id"]
        or bill["customer_id"] != case["customer_id"]
    ):
        raise forbidden("COLLECTION_BILL_SCOPE_FORBIDDEN", "账单与催收案件不一致")
    account = ensure_account_by_no(body.account_no, ctx)
    if account["customer_id"] != case["customer_id"]:
        raise forbidden("ACCOUNT_CUSTOMER_MISMATCH", "回款账户不属于催收案件客户")
    if body.repayment_amount > Decimal(str(bill["outstanding_amount"])):
        raise bad_request("REPAYMENT_AMOUNT_EXCEEDED", "回款金额不能超过账单未还金额")
    promise = _promise_by_no(body.promise_no, case) if body.promise_no else None
    channel = ensure_channel(ctx.channel_code)
    now = local_now()
    repayment_no = make_no("RPM")
    with db_cursor() as (_, cursor):
        tx = insert_success_transaction(
            cursor,
            account=account,
            channel=channel,
            request_no=body.request_no,
            transaction_type="collection_repayment",
            amount=body.repayment_amount,
            direction="debit",
            related_type="collection_case",
            related_id=int(case["id"]),
            occurred_at=now,
        )
        cursor.execute(
            """
            INSERT INTO repayment_record (
                repayment_no,
                bill_id,
                contract_id,
                customer_id,
                account_id,
                transaction_id,
                collection_case_id,
                repayment_promise_id,
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
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, 'collection', %s, %s,
                %s, %s, %s, %s, 'success', %s, %s, %s
            )
            """,
            (
                repayment_no,
                bill["id"],
                case["contract_id"],
                case["customer_id"],
                account["id"],
                tx["transaction_id"],
                case["id"],
                promise["id"] if promise else None,
                account["currency_code"],
                body.repayment_amount,
                min(body.repayment_amount, Decimal(str(bill["principal_amount"]))),
                min(
                    max(
                        body.repayment_amount - Decimal(str(bill["principal_amount"])),
                        Decimal("0.00"),
                    ),
                    Decimal(str(bill["interest_amount"])),
                ),
                Decimal("0.00"),
                Decimal("0.00"),
                now,
                now,
                now,
            ),
        )
        repayment_id = int(cursor.lastrowid)
        principal_paid = min(
            body.repayment_amount, Decimal(str(bill["principal_amount"]))
        )
        interest_paid = min(
            body.repayment_amount - principal_paid,
            Decimal(str(bill["interest_amount"])),
        )
        fee_paid = min(
            max(
                body.repayment_amount - principal_paid - interest_paid, Decimal("0.00")
            ),
            Decimal(str(bill["fee_amount"])),
        )
        penalty_paid = max(
            body.repayment_amount - principal_paid - interest_paid - fee_paid,
            Decimal("0.00"),
        )
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
        bill_status = "paid" if outstanding <= 0 else "partial_paid"
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
            (
                body.repayment_amount,
                outstanding,
                bill_status,
                bill_status,
                now,
                now,
                bill["id"],
            ),
        )
        cursor.execute(
            """
            UPDATE overdue_record
            SET paid_amount = paid_amount + %s,
                recovered_amount = recovered_amount + %s,
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
            WHERE id = %s
            """,
            (
                body.repayment_amount,
                body.repayment_amount,
                body.repayment_amount,
                body.repayment_amount,
                body.repayment_amount,
                now,
                now,
                case["overdue_id"],
            ),
        )
        if promise:
            promise_status = (
                "fulfilled"
                if body.repayment_amount >= Decimal(str(promise["promise_amount"]))
                else "partial_fulfilled"
            )
            cursor.execute(
                """
                UPDATE repayment_promise
                SET fulfilled_amount = fulfilled_amount + %s,
                    fulfilled_repayment_id = %s,
                    promise_status = %s,
                    fulfilled_at = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (
                    body.repayment_amount,
                    repayment_id,
                    promise_status,
                    now,
                    now,
                    promise["id"],
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
        cursor.execute(
            """
            UPDATE collection_case
            SET case_amount = GREATEST(case_amount - %s, 0),
                case_status = CASE WHEN case_amount <= %s THEN 'closed' ELSE case_status END,
                updated_at = %s
            WHERE id = %s
            """,
            (body.repayment_amount, body.repayment_amount, now, case["id"]),
        )
    data = {
        "repayment_no": repayment_no,
        "repayment_status": "success",
        "transaction_no": tx["transaction_no"],
    }
    save_idempotent_result(
        ctx.channel_code,
        "collection_repayment",
        body.request_no,
        body.model_dump(),
        data,
    )
    return ok(data, ctx.request_id)


@router.post("/collection/cases/{case_no}/legal-cases", summary="发起法诉案件")
def create_legal_case(
    case_no: Annotated[str, Path(description="案件编号")],
    body: Annotated[LegalCaseCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "legal_case", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    case = _collection_case_by_no(case_no, ctx)
    now = local_now()
    legal_case_no = make_no("LEG")
    with db_cursor() as (_, cursor):
        action_id = _create_action(cursor, case, "legal", "legal case created", now)
        cursor.execute(
            """
            INSERT INTO legal_case (
                legal_case_no,
                action_id,
                case_id,
                contract_id,
                customer_id,
                legal_type,
                legal_status,
                claim_amount,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'submitted', %s, %s, %s)
            """,
            (
                legal_case_no,
                action_id,
                case["id"],
                case["contract_id"],
                case["customer_id"],
                body.legal_type,
                body.claim_amount,
                now,
                now,
            ),
        )
        cursor.execute(
            "UPDATE collection_case SET case_status = 'legal', updated_at = %s WHERE id = %s",
            (now, case["id"]),
        )
    data = {"legal_case_no": legal_case_no, "legal_status": "submitted"}
    save_idempotent_result(
        ctx.channel_code, "legal_case", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post("/collection/cases/{case_no}/write-offs", summary="发起贷款核销")
def create_write_off(
    case_no: Annotated[str, Path(description="案件编号")],
    body: Annotated[WriteOffCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "write_off", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    case = _collection_case_by_no(case_no, ctx)
    if body.apply_amount > Decimal(str(case["case_amount"])):
        raise bad_request("WRITE_OFF_AMOUNT_EXCEEDED", "核销金额不能超过案件未收金额")
    now = local_now()
    write_off_no = make_no("WOF")
    with db_cursor() as (_, cursor):
        action_id = _create_action(
            cursor, case, "write_off", "write off submitted", now
        )
        cursor.execute(
            """
            INSERT INTO loan_write_off (
                write_off_no,
                action_id,
                case_id,
                contract_id,
                customer_id,
                currency_code,
                apply_amount,
                write_off_status,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'submitted', %s, %s)
            """,
            (
                write_off_no,
                action_id,
                case["id"],
                case["contract_id"],
                case["customer_id"],
                _case_currency(case),
                body.apply_amount,
                now,
                now,
            ),
        )
        cursor.execute(
            "UPDATE collection_case SET case_status = 'write_off_submitted', updated_at = %s WHERE id = %s",
            (now, case["id"]),
        )
    data = {"write_off_no": write_off_no, "write_off_status": "submitted"}
    save_idempotent_result(
        ctx.channel_code, "write_off", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post("/collection/write-offs/{write_off_no}/approval", summary="审批贷款核销")
def approve_write_off(
    write_off_no: Annotated[str, Path(description="核销编号")],
    body: Annotated[WriteOffApprovalRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "write_off_approval", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    write_off = _write_off_by_no(write_off_no)
    if write_off["write_off_status"] != "submitted":
        raise conflict("WRITE_OFF_STATUS_FORBIDDEN", "核销状态不允许审批")
    if body.approval_result not in {"approved", "rejected"}:
        raise bad_request("INVALID_APPROVAL_RESULT", "审批结果不合法")
    if body.approved_amount > Decimal(str(write_off["apply_amount"])):
        raise bad_request(
            "WRITE_OFF_APPROVED_AMOUNT_EXCEEDED", "审批金额不能超过申请金额"
        )
    employee = current_employee(ctx)
    now = local_now()
    status = "approved" if body.approval_result == "approved" else "rejected"
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            UPDATE loan_write_off
            SET approved_amount = %s,
                write_off_status = %s,
                approved_by = %s,
                approval_comment = %s,
                approved_at = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (
                body.approved_amount,
                status,
                employee["id"] if employee else None,
                body.approval_comment,
                now,
                now,
                write_off["id"],
            ),
        )
    data = {"write_off_no": write_off_no, "write_off_status": status}
    save_idempotent_result(
        ctx.channel_code, "write_off_approval", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post("/collection/write-offs/{write_off_no}/post", summary="核销入账")
def post_write_off(
    write_off_no: Annotated[str, Path(description="核销编号")],
    body: Annotated[WriteOffPostRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "write_off_post", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    write_off = _write_off_by_no(write_off_no)
    if write_off["write_off_status"] != "approved":
        raise conflict("WRITE_OFF_STATUS_FORBIDDEN", "只有已审批核销可以入账")
    now = local_now()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            UPDATE loan_write_off
            SET write_off_status = 'posted', posted_at = %s, updated_at = %s
            WHERE id = %s
            """,
            (now, now, write_off["id"]),
        )
        if write_off["contract_id"]:
            cursor.execute(
                """
                UPDATE loan_contract
                SET written_off_principal_amount = written_off_principal_amount + %s,
                    outstanding_principal_amount = GREATEST(outstanding_principal_amount - %s, 0),
                    contract_status = 'written_off',
                    updated_at = %s
                WHERE id = %s
                """,
                (
                    write_off["approved_amount"],
                    write_off["approved_amount"],
                    now,
                    write_off["contract_id"],
                ),
            )
        _apply_write_off_to_case(cursor, write_off, now)
    data = {
        "write_off_no": write_off_no,
        "write_off_status": "posted",
        "contract_status": "written_off",
    }
    save_idempotent_result(
        ctx.channel_code, "write_off_post", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post("/collection/cases/{case_no}/restructures", summary="发起贷款重组")
def create_restructure(
    case_no: Annotated[str, Path(description="案件编号")],
    body: Annotated[RestructureCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "restructure", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    case = _collection_case_by_no(case_no, ctx)
    contract = fetch_one(
        "SELECT * FROM loan_contract WHERE id = %s", (case["contract_id"],)
    )
    if contract is None:
        raise not_found("LOAN_CONTRACT_NOT_FOUND", "催收案件缺少贷款合同")
    now = local_now()
    restructure_no = make_no("RST")
    with db_cursor() as (_, cursor):
        action_id = _create_action(
            cursor, case, "restructure", "restructure submitted", now
        )
        cursor.execute(
            """
            INSERT INTO loan_restructure (
                restructure_no,
                action_id,
                case_id,
                contract_id,
                customer_id,
                before_outstanding_principal_amount,
                after_outstanding_principal_amount,
                original_schedule_version,
                new_schedule_version,
                restructure_type,
                new_term_months,
                new_interest_rate,
                restructure_status,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 1, 2, %s, %s, %s, 'submitted', %s, %s)
            """,
            (
                restructure_no,
                action_id,
                case["id"],
                contract["id"],
                case["customer_id"],
                contract["outstanding_principal_amount"],
                body.restructure_principal_amount,
                body.restructure_type,
                body.new_term_months,
                body.new_interest_rate,
                now,
                now,
            ),
        )
        cursor.execute(
            "UPDATE collection_case SET case_status = 'restructure_submitted', updated_at = %s WHERE id = %s",
            (now, case["id"]),
        )
    data = {"restructure_no": restructure_no, "restructure_status": "submitted"}
    save_idempotent_result(
        ctx.channel_code, "restructure", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post(
    "/collection/restructures/{restructure_no}/approval", summary="审批贷款重组"
)
def approve_restructure(
    restructure_no: Annotated[str, Path(description="重组编号")],
    body: Annotated[RestructureApprovalRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "restructure_approval", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    restructure = _restructure_by_no(restructure_no)
    if restructure["restructure_status"] != "submitted":
        raise conflict("RESTRUCTURE_STATUS_FORBIDDEN", "重组状态不允许审批")
    if body.approval_result not in {"approved", "rejected"}:
        raise bad_request("INVALID_APPROVAL_RESULT", "审批结果不合法")
    employee = current_employee(ctx)
    now = local_now()
    status = "approved" if body.approval_result == "approved" else "rejected"
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            UPDATE loan_restructure
            SET restructure_status = %s,
                approved_by = %s,
                approved_at = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (status, employee["id"] if employee else None, now, now, restructure["id"]),
        )
    data = {"restructure_no": restructure_no, "restructure_status": status}
    save_idempotent_result(
        ctx.channel_code,
        "restructure_approval",
        body.request_no,
        body.model_dump(),
        data,
    )
    return ok(data, ctx.request_id)


@router.post("/collection/restructures/{restructure_no}/effective", summary="重组生效")
def effective_restructure(
    restructure_no: Annotated[str, Path(description="重组编号")],
    body: Annotated[RestructureEffectiveRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "restructure_effective", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    restructure = _restructure_by_no(restructure_no)
    if restructure["restructure_status"] != "approved":
        raise conflict("RESTRUCTURE_STATUS_FORBIDDEN", "只有已审批重组可以生效")
    now = local_now()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            UPDATE loan_restructure
            SET restructure_status = 'effective',
                effective_at = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (now, now, restructure["id"]),
        )
        cursor.execute(
            """
            UPDATE loan_contract
            SET restructured_principal_amount = %s,
                outstanding_principal_amount = %s,
                contract_status = 'restructured',
                updated_at = %s
            WHERE id = %s
            """,
            (
                restructure["after_outstanding_principal_amount"],
                restructure["after_outstanding_principal_amount"],
                now,
                restructure["contract_id"],
            ),
        )
        new_schedule = _create_restructure_schedule(
            cursor, restructure, body.effective_date, now
        )
        cursor.execute(
            """
            UPDATE repayment_bill
            SET restructured_amount = outstanding_amount,
                outstanding_amount = 0,
                bill_status = 'restructured',
                updated_at = %s
            WHERE contract_id = %s AND outstanding_amount > 0
            """,
            (now, restructure["contract_id"]),
        )
        cursor.execute(
            """
            UPDATE overdue_record
            SET restructured_amount = outstanding_amount,
                outstanding_amount = 0,
                overdue_status = 'restructured',
                settled_at = %s,
                updated_at = %s
            WHERE contract_id = %s AND outstanding_amount > 0
            """,
            (now, now, restructure["contract_id"]),
        )
        cursor.execute(
            "UPDATE collection_case SET case_status = 'closed', closed_at = %s, updated_at = %s WHERE id = %s",
            (now, now, restructure["case_id"]),
        )
    data = {
        "restructure_no": restructure_no,
        "restructure_status": "effective",
        "new_repayment_schedule": new_schedule,
    }
    save_idempotent_result(
        ctx.channel_code,
        "restructure_effective",
        body.request_no,
        body.model_dump(),
        data,
    )
    return ok(data, ctx.request_id)


@router.post(
    "/collection/cases/{case_no}/collateral-disposals", summary="记录抵押物处置"
)
def create_collateral_disposal(
    case_no: Annotated[str, Path(description="案件编号")],
    body: Annotated[CollateralDisposalCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "collateral_disposal", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    case = _collection_case_by_no(case_no, ctx)
    collateral = fetch_one(
        "SELECT * FROM collateral_asset WHERE collateral_no = %s", (body.collateral_no,)
    )
    if collateral is None:
        raise not_found("COLLATERAL_NOT_FOUND", "抵押物不存在")
    account = ensure_account_by_no(body.account_no, ctx)
    if account["customer_id"] != case["customer_id"]:
        raise forbidden("ACCOUNT_CUSTOMER_MISMATCH", "回款账户不属于催收案件客户")
    channel = ensure_channel(ctx.channel_code)
    now = local_now()
    disposal_no = make_no("DSP")
    with db_cursor() as (_, cursor):
        action_id = _create_action(
            cursor, case, "collateral_disposal", "collateral disposed", now
        )
        tx_id = None
        ledger_id = None
        repayment_id = None
        if body.received_amount > 0:
            tx = insert_success_transaction(
                cursor,
                account=account,
                channel=channel,
                request_no=body.request_no,
                transaction_type="collateral_disposal",
                amount=body.received_amount,
                direction="credit",
                related_type="collection_case",
                related_id=int(case["id"]),
                occurred_at=now,
            )
            tx_id = tx["transaction_id"]
            ledger_id = tx["ledger_id"]
            repayment_id = _insert_disposal_repayment(
                cursor,
                case,
                account,
                tx_id,
                body.received_amount,
                now,
            )
        cursor.execute(
            """
            INSERT INTO collateral_disposal (
                disposal_no,
                action_id,
                case_id,
                collateral_id,
                contract_id,
                customer_id,
                repayment_id,
                transaction_id,
                ledger_id,
                currency_code,
                disposal_method,
                disposal_amount,
                received_amount,
                disposal_status,
                completed_at,
                created_at,
                updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                'completed', %s, %s, %s
            )
            """,
            (
                disposal_no,
                action_id,
                case["id"],
                collateral["id"],
                case["contract_id"],
                case["customer_id"],
                repayment_id,
                tx_id,
                ledger_id,
                collateral["currency_code"],
                body.disposal_method,
                body.disposal_amount,
                body.received_amount,
                now,
                now,
                now,
            ),
        )
        cursor.execute(
            "UPDATE collateral_asset SET collateral_status = 'disposed', updated_at = %s WHERE id = %s",
            (now, collateral["id"]),
        )
    data = {
        "disposal_no": disposal_no,
        "collateral_status": "disposed",
        "received_amount": str(body.received_amount),
    }
    save_idempotent_result(
        ctx.channel_code,
        "collateral_disposal",
        body.request_no,
        body.model_dump(),
        data,
    )
    return ok(data, ctx.request_id)


@router.get("/collection/performance-daily", summary="查询催收绩效日统计")
def list_collection_performance(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    stat_date: date | None = Query(
        description="统计日期，格式 YYYY-MM-DD", default=None
    ),
    employee_no: str | None = Query(description="员工编号", default=None),
    collection_stage: str | None = Query(description="催收阶段", default=None),
    currency_code: str | None = Query(
        description="币种编码，对应 dim_currency.currency_code", default=None
    ),
    page_no: int = Query(description="页码，从 1 开始", default=1, ge=1),
    page_size: int = Query(
        description="每页条数，范围 1 到 100", default=20, ge=1, le=100
    ),
) -> dict[str, object]:
    where: list[str] = []
    params: list[object] = []
    if stat_date:
        where.append("perf.stat_date = %s")
        params.append(stat_date)
    if employee_no:
        where.append("employee.employee_no = %s")
        params.append(employee_no)
    if collection_stage:
        where.append("perf.collection_stage = %s")
        params.append(collection_stage)
    if currency_code:
        where.append("perf.currency_code = %s")
        params.append(currency_code)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    offset, limit = offset_limit(page_no, page_size)
    rows = fetch_all(
        f"""
        SELECT
            perf.stat_date,
            employee.employee_no,
            perf.collection_stage,
            perf.currency_code,
            perf.assigned_amount,
            perf.recovered_amount,
            perf.recovery_rate
        FROM collection_performance_daily AS perf
        JOIN dim_employee AS employee ON employee.id = perf.collector_id
        {where_sql}
        ORDER BY perf.stat_date DESC, employee.employee_no
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )
    total = count_total(
        f"""
        SELECT COUNT(*) AS total
        FROM collection_performance_daily AS perf
        JOIN dim_employee AS employee ON employee.id = perf.collector_id
        {where_sql}
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


def _collection_case_by_no(case_no: str, ctx: RequestContext) -> dict[str, Any]:
    row = fetch_one("SELECT * FROM collection_case WHERE case_no = %s", (case_no,))
    if row is None:
        raise not_found("COLLECTION_CASE_NOT_FOUND", "催收案件不存在")
    if ctx.auth_type == "customer":
        customer = fetch_one(
            "SELECT customer_no FROM customer WHERE id = %s", (row["customer_id"],)
        )
        if customer is None or customer["customer_no"] != ctx.principal_no:
            raise forbidden("CUSTOMER_SCOPE_FORBIDDEN", "客户只能访问本人业务对象")
    return row


def _overdue_by_no(overdue_no: str, ctx: RequestContext) -> dict[str, Any]:
    row = fetch_one("SELECT * FROM overdue_record WHERE overdue_no = %s", (overdue_no,))
    if row is None:
        raise not_found("OVERDUE_NOT_FOUND", "逾期记录不存在")
    if ctx.auth_type == "customer":
        customer = fetch_one(
            "SELECT customer_no FROM customer WHERE id = %s", (row["customer_id"],)
        )
        if customer is None or customer["customer_no"] != ctx.principal_no:
            raise forbidden("CUSTOMER_SCOPE_FORBIDDEN", "客户只能访问本人业务对象")
    return row


def _employee_by_no(employee_no: str) -> dict[str, Any]:
    row = fetch_one(
        "SELECT * FROM dim_employee WHERE employee_no = %s AND employee_status = 'active'",
        (employee_no,),
    )
    if row is None:
        raise not_found("EMPLOYEE_NOT_FOUND", "员工不存在或不可用")
    return row


def _case_currency(case: dict[str, Any]) -> str:
    overdue = fetch_one(
        "SELECT currency_code FROM overdue_record WHERE id = %s", (case["overdue_id"],)
    )
    return str(overdue["currency_code"] if overdue else "CNY")


def _bill_by_no(bill_no: str) -> dict[str, Any]:
    row = fetch_one("SELECT * FROM repayment_bill WHERE bill_no = %s", (bill_no,))
    if row is None:
        raise not_found("REPAYMENT_BILL_NOT_FOUND", "还款账单不存在")
    return row


def _promise_by_no(promise_no: str | None, case: dict[str, Any]) -> dict[str, Any]:
    row = fetch_one(
        "SELECT * FROM repayment_promise WHERE promise_no = %s", (promise_no,)
    )
    if row is None:
        raise not_found("REPAYMENT_PROMISE_NOT_FOUND", "承诺还款不存在")
    if row["case_id"] != case["id"]:
        raise forbidden("REPAYMENT_PROMISE_SCOPE_FORBIDDEN", "承诺还款不属于催收案件")
    return row


def _create_action(
    cursor: Any, case: dict[str, Any], action_type: str, result: str, now: Any
) -> int:
    cursor.execute(
        """
        INSERT INTO collection_action (
            action_no,
            case_id,
            customer_id,
            contract_id,
            action_type,
            action_status,
            action_result,
            action_at,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, 'completed', %s, %s, %s, %s)
        """,
        (
            make_no("ACT"),
            case["id"],
            case["customer_id"],
            case["contract_id"],
            action_type,
            result,
            now,
            now,
            now,
        ),
    )
    return int(cursor.lastrowid)


def _write_off_by_no(write_off_no: str) -> dict[str, Any]:
    row = fetch_one(
        "SELECT * FROM loan_write_off WHERE write_off_no = %s", (write_off_no,)
    )
    if row is None:
        raise not_found("WRITE_OFF_NOT_FOUND", "核销申请不存在")
    return row


def _restructure_by_no(restructure_no: str) -> dict[str, Any]:
    row = fetch_one(
        "SELECT * FROM loan_restructure WHERE restructure_no = %s", (restructure_no,)
    )
    if row is None:
        raise not_found("RESTRUCTURE_NOT_FOUND", "重组申请不存在")
    return row


def _apply_write_off_to_case(cursor: Any, write_off: dict[str, Any], now: Any) -> None:
    amount = Decimal(str(write_off["approved_amount"]))
    if amount <= 0:
        return
    cursor.execute(
        "SELECT * FROM collection_case WHERE id = %s FOR UPDATE",
        (write_off["case_id"],),
    )
    case = cursor.fetchone()
    if case is None:
        return
    cursor.execute(
        """
        UPDATE repayment_bill
        SET written_off_amount = written_off_amount + %s,
            outstanding_amount = GREATEST(outstanding_amount - %s, 0),
            bill_status = CASE
                WHEN GREATEST(outstanding_amount - %s, 0) = 0 THEN 'written_off'
                ELSE bill_status
            END,
            updated_at = %s
        WHERE id = (
            SELECT bill_id FROM overdue_record WHERE id = %s
        )
        """,
        (amount, amount, amount, now, case["overdue_id"]),
    )
    cursor.execute(
        """
        UPDATE overdue_record
        SET written_off_amount = written_off_amount + %s,
            outstanding_amount = GREATEST(outstanding_amount - %s, 0),
            overdue_status = CASE
                WHEN GREATEST(outstanding_amount - %s, 0) = 0 THEN 'written_off'
                ELSE overdue_status
            END,
            settled_at = CASE
                WHEN GREATEST(outstanding_amount - %s, 0) = 0 THEN %s
                ELSE settled_at
            END,
            updated_at = %s
        WHERE id = %s
        """,
        (amount, amount, amount, amount, now, now, case["overdue_id"]),
    )
    cursor.execute(
        """
        UPDATE collection_case
        SET case_amount = GREATEST(case_amount - %s, 0),
            case_status = CASE
                WHEN GREATEST(case_amount - %s, 0) = 0 THEN 'closed'
                ELSE 'write_off_posted'
            END,
            closed_at = CASE
                WHEN GREATEST(case_amount - %s, 0) = 0 THEN %s
                ELSE closed_at
            END,
            updated_at = %s
        WHERE id = %s
        """,
        (amount, amount, amount, now, now, case["id"]),
    )


def _create_restructure_schedule(
    cursor: Any,
    restructure: dict[str, Any],
    effective_date: date,
    now: Any,
) -> list[dict[str, object]]:
    principal = Decimal(str(restructure["after_outstanding_principal_amount"]))
    term_months = max(int(restructure["new_term_months"]), 1)
    principal_per_period = (principal / Decimal(term_months)).quantize(Decimal("0.01"))
    rows: list[dict[str, object]] = []
    for period_no in range(1, term_months + 1):
        due_date = effective_date + date.resolution * 30 * period_no
        interest = (
            principal * Decimal(str(restructure["new_interest_rate"])) / Decimal("12")
        ).quantize(Decimal("0.01"))
        total_amount = principal_per_period + interest
        cursor.execute(
            """
            INSERT INTO repayment_schedule (
                contract_id,
                customer_id,
                schedule_version,
                period_no,
                due_date,
                currency_code,
                principal_amount,
                interest_amount,
                total_amount,
                schedule_status,
                created_at,
                updated_at
            )
            SELECT
                contract.id,
                contract.customer_id,
                %s,
                %s,
                %s,
                contract.currency_code,
                %s,
                %s,
                %s,
                'pending',
                %s,
                %s
            FROM loan_contract AS contract
            WHERE contract.id = %s
            """,
            (
                restructure["new_schedule_version"],
                period_no,
                due_date,
                principal_per_period,
                interest,
                total_amount,
                now,
                now,
                restructure["contract_id"],
            ),
        )
        rows.append(
            {
                "period_no": period_no,
                "due_date": due_date.isoformat(),
                "principal_amount": str(principal_per_period),
                "interest_amount": str(interest),
                "total_amount": str(total_amount),
            }
        )
    return rows


def _insert_disposal_repayment(
    cursor: Any,
    case: dict[str, Any],
    account: dict[str, Any],
    transaction_id: int,
    amount: Decimal,
    now: Any,
) -> int:
    cursor.execute(
        "SELECT * FROM overdue_record WHERE id = %s FOR UPDATE", (case["overdue_id"],)
    )
    overdue = cursor.fetchone()
    if overdue is None or overdue["bill_id"] is None:
        raise not_found("OVERDUE_NOT_FOUND", "催收案件缺少逾期账单")
    cursor.execute(
        "SELECT * FROM repayment_bill WHERE id = %s FOR UPDATE", (overdue["bill_id"],)
    )
    bill = cursor.fetchone()
    if bill is None:
        raise not_found("REPAYMENT_BILL_NOT_FOUND", "还款账单不存在")
    principal_paid = min(amount, Decimal(str(bill["principal_amount"])))
    interest_paid = min(amount - principal_paid, Decimal(str(bill["interest_amount"])))
    fee_paid = min(
        max(amount - principal_paid - interest_paid, Decimal("0.00")),
        Decimal(str(bill["fee_amount"])),
    )
    penalty_paid = max(
        amount - principal_paid - interest_paid - fee_paid, Decimal("0.00")
    )
    repayment_no = make_no("RPM")
    cursor.execute(
        """
        INSERT INTO repayment_record (
            repayment_no,
            bill_id,
            contract_id,
            customer_id,
            account_id,
            transaction_id,
            collection_case_id,
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
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, 'collateral_disposal', %s, %s,
            %s, %s, %s, %s, 'success', %s, %s, %s
        )
        """,
        (
            repayment_no,
            bill["id"],
            bill["contract_id"],
            case["customer_id"],
            account["id"],
            transaction_id,
            case["id"],
            account["currency_code"],
            amount,
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
            amount,
            now,
        ),
    )
    outstanding = Decimal(str(bill["outstanding_amount"])) - amount
    status = "paid" if outstanding <= 0 else "partial_paid"
    cursor.execute(
        """
        UPDATE repayment_bill
        SET paid_amount = paid_amount + %s,
            outstanding_amount = GREATEST(outstanding_amount - %s, 0),
            bill_status = %s,
            paid_at = CASE WHEN %s = 'paid' THEN %s ELSE paid_at END,
            updated_at = %s
        WHERE id = %s
        """,
        (amount, amount, status, status, now, now, bill["id"]),
    )
    cursor.execute(
        """
        UPDATE overdue_record
        SET paid_amount = paid_amount + %s,
            recovered_amount = recovered_amount + %s,
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
        WHERE id = %s
        """,
        (amount, amount, amount, amount, amount, now, now, overdue["id"]),
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
    cursor.execute(
        """
        UPDATE collection_case
        SET case_amount = GREATEST(case_amount - %s, 0),
            case_status = CASE
                WHEN GREATEST(case_amount - %s, 0) = 0 THEN 'closed'
                ELSE case_status
            END,
            closed_at = CASE
                WHEN GREATEST(case_amount - %s, 0) = 0 THEN %s
                ELSE closed_at
            END,
            updated_at = %s
        WHERE id = %s
        """,
        (amount, amount, amount, now, now, case["id"]),
    )
    return repayment_id
