"""Loan product, credit, application and contract APIs."""

from __future__ import annotations

from datetime import timedelta
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
    ensure_credit_limit,
    ensure_customer_by_no,
    ensure_loan_contract,
    insert_success_transaction,
    occupy_credit_limit_for_contract,
)
from ..utils import (
    local_now,
    make_no,
    serialize_row,
    serialize_rows,
)

router = APIRouter(prefix="/api/v1", tags=["loans"])


class MaterialPayload(BaseModel):
    material_type: str = Field(description="材料类型")
    material_name: str = Field(description="材料名称")
    file_url: str | None = Field(default=None, description="材料文件地址")
    file_hash: str | None = Field(default=None, description="材料文件摘要")


class CreditApplicationCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    customer_no: str = Field(description="客户号，对应 customer.customer_no")
    product_code: str = Field(description="产品编码")
    apply_limit_amount: Decimal = Field(gt=0, description="申请授信额度，必须大于 0")
    materials: list[MaterialPayload] = Field(
        default_factory=list, description="申请材料列表"
    )


class CreditApprovalRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    approval_node: str = Field(description="审批节点")
    approval_result: str = Field(description="审批结果")
    approved_limit_amount: Decimal = Field(
        ge=0, description="审批授信额度，必须大于或等于 0"
    )
    approval_comment: str | None = Field(default=None, description="审批意见")


class LoanApplicationCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    customer_no: str = Field(description="客户号，对应 customer.customer_no")
    limit_no: str = Field(description="授信额度编号")
    apply_amount: Decimal = Field(gt=0, description="申请金额，必须大于 0")
    apply_term_months: int = Field(gt=0, description="申请期限月数，必须大于 0")
    repayment_method: str = Field(description="还款方式")
    loan_purpose: str = Field(default="consume", description="贷款用途")
    materials: list[MaterialPayload] = Field(
        default_factory=list, description="申请材料列表"
    )


class LoanApplicationStatusChangeRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    target_status: str = Field(description="目标状态")
    reason: str = Field(description="业务原因")


class LoanApprovalRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    approval_node: str = Field(description="审批节点")
    approval_result: str = Field(description="审批结果")
    approved_amount: Decimal = Field(ge=0, description="审批金额，必须大于或等于 0")
    approved_rate: Decimal = Field(ge=0, description="审批利率，必须大于或等于 0")
    approved_term_months: int | None = Field(default=None, description="审批期限月数")
    approval_comment: str | None = Field(default=None, description="审批意见")


class ContractSignRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    document_no: str = Field(description="合同文件编号")
    signer_type: str = Field(description="签署人类型")
    signer_name: str = Field(description="签署人姓名")
    sign_method: str = Field(description="签署方式")
    sign_result: str = Field(description="签署结果")


class DisbursementCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    account_no: str = Field(description="账户号，对应 bank_account.account_no")
    disbursement_amount: Decimal = Field(gt=0, description="放款金额，必须大于 0")


@router.get("/loan/products", summary="查询贷款产品")
def list_loan_products(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    loan_type: str | None = Query(description="贷款类型", default=None),
    currency_code: str | None = Query(
        description="币种编码，对应 dim_currency.currency_code", default=None
    ),
    product_status: str | None = Query(description="产品状态", default=None),
) -> dict[str, object]:
    where: list[str] = []
    params: list[object] = []
    if loan_type:
        where.append("product.loan_type = %s")
        params.append(loan_type)
    if currency_code:
        where.append("product.currency_code = %s")
        params.append(currency_code)
    if product_status:
        where.append("product.product_status = %s")
        params.append(product_status)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    rows = fetch_all(
        f"""
        SELECT
            product.product_code,
            product.min_interest_rate,
            product.max_interest_rate,
            product.min_term_months,
            product.max_term_months
        FROM loan_product AS product
        {where_sql}
        ORDER BY product.product_code
        """,
        tuple(params),
    )
    return ok(
        {
            "list": [
                {
                    "product_code": row["product_code"],
                    "eligibility_rules": [],
                    "rate_range": {
                        "min": str(row["min_interest_rate"]),
                        "max": str(row["max_interest_rate"]),
                    },
                    "term_range": {
                        "min": row["min_term_months"],
                        "max": row["max_term_months"],
                    },
                }
                for row in rows
            ]
        },
        ctx.request_id,
    )


@router.get("/loan/products/{product_code}", summary="查询贷款产品详情")
def get_loan_product(
    product_code: Annotated[str, Path(description="产品编码")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    product = _loan_product_by_code(product_code)
    rules = fetch_all(
        "SELECT * FROM loan_product_eligibility_rule WHERE product_id = %s AND yn = 1",
        (product["id"],),
    )
    tiers = fetch_all(
        "SELECT * FROM loan_product_rate_tier WHERE product_id = %s AND yn = 1",
        (product["id"],),
    )
    materials = fetch_all(
        "SELECT * FROM loan_product_required_material WHERE product_id = %s AND yn = 1",
        (product["id"],),
    )
    return ok(
        {
            "product_detail": serialize_row(product),
            "eligibility_rules": serialize_rows(rules),
            "rate_tiers": serialize_rows(tiers),
            "required_materials": serialize_rows(materials),
        },
        ctx.request_id,
    )


@router.post("/credit/applications", summary="提交授信申请")
def create_credit_application(
    body: Annotated[CreditApplicationCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "credit_application", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    customer = ensure_customer_by_no(body.customer_no, ctx)
    product = _loan_product_by_code(body.product_code)
    channel = ensure_channel(ctx.channel_code)
    _validate_loan_product_amount(product, body.apply_limit_amount)
    now = local_now()
    application_no = make_no("CRA")
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO credit_application (
                credit_application_no,
                customer_id,
                product_id,
                channel_id,
                apply_limit_amount,
                currency_code,
                application_status,
                submitted_at,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'submitted', %s, %s, %s)
            """,
            (
                application_no,
                customer["id"],
                product["id"],
                channel["id"],
                body.apply_limit_amount,
                product["currency_code"],
                now,
                now,
                now,
            ),
        )
        application_id = int(cursor.lastrowid)
        _insert_materials(
            cursor,
            "credit",
            application_id,
            int(customer["id"]),
            body.materials,
            ctx.principal_no,
            now,
        )
    data = {
        "credit_application_no": application_no,
        "application_status": "submitted",
    }
    save_idempotent_result(
        ctx.channel_code, "credit_application", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.get("/credit/applications/{credit_application_no}", summary="查询授信申请详情")
def get_credit_application(
    credit_application_no: Annotated[str, Path(description="授信申请号")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    application = _credit_application_by_no(credit_application_no, ctx)
    materials = fetch_all(
        "SELECT * FROM credit_application_material WHERE credit_application_id = %s",
        (application["id"],),
    )
    approvals = fetch_all(
        "SELECT * FROM credit_approval_record WHERE credit_application_id = %s",
        (application["id"],),
    )
    limit_row = fetch_one(
        "SELECT * FROM credit_limit WHERE credit_application_id = %s",
        (application["id"],),
    )
    return ok(
        {
            "application_info": serialize_row(application),
            "materials": serialize_rows(materials),
            "approval_records": serialize_rows(approvals),
            "credit_result": serialize_row(limit_row) if limit_row else None,
        },
        ctx.request_id,
    )


@router.post(
    "/credit/applications/{credit_application_no}/approval-records",
    summary="提交授信审批结果",
)
def approve_credit_application(
    credit_application_no: Annotated[str, Path(description="授信申请号")],
    body: Annotated[CreditApprovalRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "credit_approval", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    application = _credit_application_by_no(credit_application_no, ctx)
    if application["application_status"] not in {"submitted", "processing"}:
        raise conflict("CREDIT_APPLICATION_STATUS_FORBIDDEN", "授信申请状态不允许审批")
    if body.approval_result not in {"approved", "rejected"}:
        raise bad_request("INVALID_APPROVAL_RESULT", "审批结果不合法")
    employee = current_employee(ctx)
    if employee is None:
        raise forbidden("EMPLOYEE_AUTH_REQUIRED", "审批接口需要员工身份")
    now = local_now()
    status = "approved" if body.approval_result == "approved" else "rejected"
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT COALESCE(MAX(approval_round), 0) + 1 AS next_round
            FROM credit_approval_record
            WHERE credit_application_id = %s AND approval_node = %s
            FOR UPDATE
            """,
            (application["id"], body.approval_node),
        )
        approval_round = int(cursor.fetchone()["next_round"])
        cursor.execute(
            """
            INSERT INTO credit_approval_record (
                credit_application_id,
                approval_node,
                approval_round,
                approver_id,
                approval_result,
                approved_limit_amount,
                approval_comment,
                approved_at,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                application["id"],
                body.approval_node,
                approval_round,
                employee["id"],
                body.approval_result,
                body.approved_limit_amount,
                body.approval_comment,
                now,
                now,
            ),
        )
        approval_id = int(cursor.lastrowid)
        cursor.execute(
            """
            UPDATE credit_application
            SET application_status = %s,
                approved_at = CASE WHEN %s = 'approved' THEN %s ELSE approved_at END,
                rejected_at = CASE WHEN %s = 'rejected' THEN %s ELSE rejected_at END,
                updated_at = %s
            WHERE id = %s
            """,
            (status, status, now, status, now, now, application["id"]),
        )
        limit_status = "none"
        if status == "approved":
            limit_no = make_no("LMT")
            valid_from = now.date()
            valid_to = valid_from + timedelta(days=365)
            cursor.execute(
                """
                INSERT INTO credit_limit (
                    limit_no,
                    credit_application_id,
                    customer_id,
                    product_id,
                    currency_code,
                    total_limit_amount,
                    available_limit_amount,
                    limit_status,
                    valid_from,
                    valid_to,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'active', %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    total_limit_amount = VALUES(total_limit_amount),
                    available_limit_amount = VALUES(available_limit_amount),
                    limit_status = 'active',
                    updated_at = VALUES(updated_at)
                """,
                (
                    limit_no,
                    application["id"],
                    application["customer_id"],
                    application["product_id"],
                    application["currency_code"],
                    body.approved_limit_amount,
                    body.approved_limit_amount,
                    valid_from,
                    valid_to,
                    now,
                    now,
                ),
            )
            limit_status = "active"
    data = {
        "approval_record_id": approval_id,
        "application_status": status,
        "limit_status": limit_status,
    }
    save_idempotent_result(
        ctx.channel_code, "credit_approval", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.get("/customers/{customer_no}/credit-limits", summary="查询客户授信额度")
def list_credit_limits(
    customer_no: Annotated[str, Path(description="客户号，对应 customer.customer_no")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    product_code: str | None = Query(description="产品编码", default=None),
) -> dict[str, object]:
    customer = ensure_customer_by_no(customer_no, ctx)
    where = ["limit_row.customer_id = %s"]
    params: list[object] = [customer["id"]]
    if product_code:
        where.append("product.product_code = %s")
        params.append(product_code)
    rows = fetch_all(
        f"""
        SELECT
            limit_row.limit_no,
            limit_row.total_limit_amount,
            limit_row.available_limit_amount,
            limit_row.frozen_limit_amount,
            limit_row.valid_to,
            product.product_code
        FROM credit_limit AS limit_row
        JOIN loan_product AS product ON product.id = limit_row.product_id
        WHERE {" AND ".join(where)}
        ORDER BY limit_row.created_at DESC
        """,
        tuple(params),
    )
    return ok({"list": serialize_rows(rows)}, ctx.request_id)


@router.post("/loan/applications", summary="提交贷款申请")
def create_loan_application(
    body: Annotated[LoanApplicationCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "loan_application", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    customer = ensure_customer_by_no(body.customer_no, ctx)
    limit_row = ensure_credit_limit(body.limit_no, ctx)
    if limit_row["customer_id"] != customer["id"]:
        raise forbidden("CREDIT_LIMIT_CUSTOMER_MISMATCH", "授信额度不属于请求客户")
    if limit_row["limit_status"] != "active":
        raise conflict("CREDIT_LIMIT_STATUS_FORBIDDEN", "授信额度状态不允许贷款申请")
    if body.apply_amount > Decimal(str(limit_row["available_limit_amount"])):
        raise conflict("CREDIT_LIMIT_NOT_ENOUGH", "授信可用额度不足")
    product = _loan_product_by_id(int(limit_row["product_id"]))
    _validate_loan_product_amount(product, body.apply_amount)
    if not (
        product["min_term_months"]
        <= body.apply_term_months
        <= product["max_term_months"]
    ):
        raise bad_request("LOAN_TERM_OUT_OF_RANGE", "申请期限不在产品期限范围内")
    channel = ensure_channel(ctx.channel_code)
    now = local_now()
    application_no = make_no("LAP")
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO loan_application (
                application_no,
                customer_id,
                product_id,
                credit_limit_id,
                channel_id,
                apply_amount,
                apply_term_months,
                loan_purpose,
                application_status,
                risk_decision,
                submitted_at,
                expired_at,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'submitted', 'manual_review', %s, %s, %s, %s)
            """,
            (
                application_no,
                customer["id"],
                product["id"],
                limit_row["id"],
                channel["id"],
                body.apply_amount,
                body.apply_term_months,
                body.loan_purpose,
                now,
                now + timedelta(days=30),
                now,
                now,
            ),
        )
        application_id = int(cursor.lastrowid)
        _insert_materials(
            cursor,
            "loan",
            application_id,
            int(customer["id"]),
            body.materials,
            ctx.principal_no,
            now,
        )
        _update_limit_freeze(cursor, limit_row, body.apply_amount, application_id, now)
    data = {"application_no": application_no, "application_status": "submitted"}
    save_idempotent_result(
        ctx.channel_code, "loan_application", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.get("/loan/applications/{application_no}", summary="查询贷款申请详情")
def get_loan_application(
    application_no: Annotated[str, Path(description="申请编号")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    application = _loan_application_by_no(application_no, ctx)
    assessment = fetch_one(
        "SELECT * FROM credit_assessment WHERE application_id = %s",
        (application["id"],),
    )
    approvals = fetch_all(
        "SELECT * FROM loan_approval_record WHERE application_id = %s",
        (application["id"],),
    )
    contract = fetch_one(
        "SELECT * FROM loan_contract WHERE application_id = %s",
        (application["id"],),
    )
    return ok(
        {
            "application_info": serialize_row(application),
            "assessment_result": serialize_row(assessment) if assessment else None,
            "approval_records": serialize_rows(approvals),
            "contract_info": serialize_row(contract) if contract else None,
        },
        ctx.request_id,
    )


@router.post(
    "/loan/applications/{application_no}/status-changes",
    summary="变更贷款申请状态",
)
def change_loan_application_status(
    application_no: Annotated[str, Path(description="申请编号")],
    body: Annotated[LoanApplicationStatusChangeRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "loan_application_status", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    if body.target_status not in {"cancelled", "expired"}:
        raise bad_request(
            "INVALID_LOAN_APPLICATION_TARGET_STATUS", "目标状态只能为取消或过期"
        )
    application = _loan_application_by_no(application_no, ctx)
    if application["application_status"] in {
        "approved",
        "rejected",
        "cancelled",
        "expired",
    }:
        raise conflict("LOAN_APPLICATION_STATUS_FORBIDDEN", "贷款申请状态不允许变更")
    limit_row = ensure_credit_limit(
        _limit_no_by_id(int(application["credit_limit_id"])), ctx
    )
    now = local_now()
    with db_cursor() as (_, cursor):
        _release_limit_freeze(
            cursor,
            limit_row,
            Decimal(str(application["apply_amount"])),
            application["id"],
            now,
        )
        cursor.execute(
            """
            UPDATE loan_application
            SET application_status = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (body.target_status, now, application["id"]),
        )
    data = {
        "application_no": application_no,
        "application_status": body.target_status,
        "limit_release_status": "released",
    }
    save_idempotent_result(
        ctx.channel_code,
        "loan_application_status",
        body.request_no,
        body.model_dump(),
        data,
    )
    return ok(data, ctx.request_id)


@router.post(
    "/loan/applications/{application_no}/approval-records",
    summary="提交贷款审批结果",
)
def approve_loan_application(
    application_no: Annotated[str, Path(description="申请编号")],
    body: Annotated[LoanApprovalRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "loan_approval", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    application = _loan_application_by_no(application_no, ctx)
    if application["application_status"] not in {"submitted", "processing"}:
        raise conflict("LOAN_APPLICATION_STATUS_FORBIDDEN", "贷款申请状态不允许审批")
    if body.approval_result not in {"approved", "rejected"}:
        raise bad_request("INVALID_APPROVAL_RESULT", "审批结果不合法")
    employee = current_employee(ctx)
    if employee is None:
        raise forbidden("EMPLOYEE_AUTH_REQUIRED", "审批接口需要员工身份")
    product = _loan_product_by_id(int(application["product_id"]))
    term_months = body.approved_term_months or int(application["apply_term_months"])
    now = local_now()
    status = "approved" if body.approval_result == "approved" else "rejected"
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT COALESCE(MAX(approval_round), 0) + 1 AS next_round
            FROM loan_approval_record
            WHERE application_id = %s AND approval_node = %s
            FOR UPDATE
            """,
            (application["id"], body.approval_node),
        )
        approval_round = int(cursor.fetchone()["next_round"])
        cursor.execute(
            """
            INSERT INTO loan_approval_record (
                application_id,
                approval_node,
                approver_id,
                approval_round,
                sequence_no,
                approval_result,
                approval_comment,
                approved_amount,
                approved_term_months,
                approved_rate,
                approved_at,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                application["id"],
                body.approval_node,
                employee["id"],
                approval_round,
                approval_round,
                body.approval_result,
                body.approval_comment,
                body.approved_amount,
                term_months,
                body.approved_rate,
                now,
                now,
            ),
        )
        approval_id = int(cursor.lastrowid)
        cursor.execute(
            """
            UPDATE loan_application
            SET application_status = %s,
                approved_at = CASE WHEN %s = 'approved' THEN %s ELSE approved_at END,
                rejected_at = CASE WHEN %s = 'rejected' THEN %s ELSE rejected_at END,
                updated_at = %s
            WHERE id = %s
            """,
            (status, status, now, status, now, now, application["id"]),
        )
        if status == "approved":
            contract_no = make_no("CON")
            repayment_account = _customer_repayment_account(
                int(application["customer_id"]), str(product["currency_code"])
            )
            cursor.execute(
                """
                INSERT INTO loan_contract (
                    contract_no,
                    loan_no,
                    application_id,
                    customer_id,
                    product_id,
                    repayment_account_id,
                    currency_code,
                    principal_amount,
                    undisbursed_principal_amount,
                    outstanding_principal_amount,
                    annual_interest_rate,
                    term_months,
                    repayment_method,
                    contract_status,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending_sign', %s, %s)
                """,
                (
                    contract_no,
                    make_no("LOAN"),
                    application["id"],
                    application["customer_id"],
                    application["product_id"],
                    repayment_account["id"],
                    product["currency_code"],
                    body.approved_amount,
                    body.approved_amount,
                    body.approved_amount,
                    body.approved_rate,
                    term_months,
                    product["repayment_method"],
                    now,
                    now,
                ),
            )
        else:
            limit_row = ensure_credit_limit(
                _limit_no_by_id(int(application["credit_limit_id"])), ctx
            )
            _release_limit_freeze(
                cursor,
                limit_row,
                Decimal(str(application["apply_amount"])),
                application["id"],
                now,
            )
    data = {"approval_record_id": approval_id, "application_status": status}
    save_idempotent_result(
        ctx.channel_code, "loan_approval", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post("/loan/contracts/{contract_no}/sign-records", summary="提交合同签署记录")
def sign_contract(
    contract_no: Annotated[str, Path(description="贷款合同号")],
    body: Annotated[ContractSignRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "contract_sign", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    contract = ensure_loan_contract(contract_no, ctx)
    document = fetch_one(
        "SELECT * FROM loan_contract_document WHERE document_no = %s AND contract_id = %s",
        (body.document_no, contract["id"]),
    )
    if document is None:
        raise not_found("CONTRACT_DOCUMENT_NOT_FOUND", "合同文件不存在")
    if contract["contract_status"] not in {"pending_sign", "signed"}:
        raise conflict("CONTRACT_STATUS_FORBIDDEN", "合同状态不允许签署")
    now = local_now()
    sign_no = make_no("SGN")
    channel = ensure_channel(ctx.channel_code)
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO contract_sign_record (
                sign_no,
                contract_id,
                document_id,
                signer_type,
                signer_name,
                sign_channel_id,
                sign_method,
                sign_status,
                signed_at,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                sign_no,
                contract["id"],
                document["id"],
                body.signer_type,
                body.signer_name,
                channel["id"],
                body.sign_method,
                body.sign_result,
                now if body.sign_result == "signed" else None,
                now,
                now,
            ),
        )
        cursor.execute(
            "UPDATE loan_contract_document SET sign_status = %s, updated_at = %s WHERE id = %s",
            (body.sign_result, now, document["id"]),
        )
        contract_status = (
            "signed" if body.sign_result == "signed" else contract["contract_status"]
        )
        cursor.execute(
            "UPDATE loan_contract SET contract_status = %s, signed_at = %s, updated_at = %s WHERE id = %s",
            (
                contract_status,
                now if contract_status == "signed" else contract["signed_at"],
                now,
                contract["id"],
            ),
        )
    data = {"sign_no": sign_no, "contract_status": contract_status}
    save_idempotent_result(
        ctx.channel_code, "contract_sign", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post("/loan/contracts/{contract_no}/disbursements", summary="发起贷款放款")
def create_disbursement(
    contract_no: Annotated[str, Path(description="贷款合同号")],
    body: Annotated[DisbursementCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "loan_disbursement", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    contract = ensure_loan_contract(contract_no, ctx)
    if contract["contract_status"] not in {"signed", "active"}:
        raise conflict("CONTRACT_STATUS_FORBIDDEN", "贷款合同未签署不可放款")
    account = ensure_account_by_no(body.account_no, ctx)
    if account["customer_id"] != contract["customer_id"]:
        raise forbidden("ACCOUNT_CUSTOMER_MISMATCH", "放款账户不属于合同客户")
    if account["currency_code"] != contract["currency_code"]:
        raise bad_request("CURRENCY_MISMATCH", "放款账户币种与合同币种不一致")
    if body.disbursement_amount > Decimal(
        str(contract["undisbursed_principal_amount"])
    ):
        raise bad_request("DISBURSEMENT_AMOUNT_EXCEEDED", "放款金额超过合同未放款本金")
    channel = ensure_channel(ctx.channel_code)
    now = local_now()
    disbursement_no = make_no("DSB")
    with db_cursor() as (_, cursor):
        tx = insert_success_transaction(
            cursor,
            account=account,
            channel=channel,
            request_no=body.request_no,
            transaction_type="loan_disbursement",
            amount=body.disbursement_amount,
            direction="credit",
            related_type="loan_contract",
            related_id=int(contract["id"]),
            occurred_at=now,
        )
        cursor.execute(
            """
            INSERT INTO loan_disbursement (
                disbursement_no,
                contract_id,
                customer_id,
                account_id,
                transaction_id,
                currency_code,
                disbursement_amount,
                disbursement_status,
                disbursed_at,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'success', %s, %s, %s)
            """,
            (
                disbursement_no,
                contract["id"],
                contract["customer_id"],
                account["id"],
                tx["transaction_id"],
                contract["currency_code"],
                body.disbursement_amount,
                now,
                now,
                now,
            ),
        )
        cursor.execute(
            """
            UPDATE loan_contract
            SET disbursed_principal_amount = disbursed_principal_amount + %s,
                undisbursed_principal_amount = undisbursed_principal_amount - %s,
                contract_status = 'active',
                disbursed_at = COALESCE(disbursed_at, %s),
                updated_at = %s
            WHERE id = %s
            """,
            (
                body.disbursement_amount,
                body.disbursement_amount,
                now,
                now,
                contract["id"],
            ),
        )
        occupy_credit_limit_for_contract(
            cursor,
            contract=contract,
            amount=body.disbursement_amount,
            now=now,
        )
        _create_repayment_schedule(cursor, contract, body.disbursement_amount, now)
    data = {
        "disbursement_no": disbursement_no,
        "disbursement_status": "success",
        "transaction_no": tx["transaction_no"],
    }
    save_idempotent_result(
        ctx.channel_code, "loan_disbursement", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.get("/loan/contracts/{contract_no}", summary="查询合同借据详情")
def get_contract(
    contract_no: Annotated[str, Path(description="贷款合同号")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    contract = ensure_loan_contract(contract_no, ctx)
    disbursements = fetch_all(
        "SELECT * FROM loan_disbursement WHERE contract_id = %s ORDER BY created_at DESC",
        (contract["id"],),
    )
    return ok(
        {
            "contract_info": serialize_row(contract),
            "outstanding_principal_amount": str(
                contract["outstanding_principal_amount"]
            ),
            "repayment_status": contract["contract_status"],
            "disbursements": serialize_rows(disbursements),
        },
        ctx.request_id,
    )


def _loan_product_by_code(product_code: str) -> dict[str, Any]:
    row = fetch_one(
        "SELECT * FROM loan_product WHERE product_code = %s", (product_code,)
    )
    if row is None:
        raise not_found("LOAN_PRODUCT_NOT_FOUND", "贷款产品不存在")
    return row


def _loan_product_by_id(product_id: int) -> dict[str, Any]:
    row = fetch_one("SELECT * FROM loan_product WHERE id = %s", (product_id,))
    if row is None:
        raise not_found("LOAN_PRODUCT_NOT_FOUND", "贷款产品不存在")
    return row


def _validate_loan_product_amount(product: dict[str, Any], amount: Decimal) -> None:
    if product["product_status"] not in {"active", "selling"}:
        raise conflict("LOAN_PRODUCT_STATUS_FORBIDDEN", "贷款产品不可用")
    if amount < Decimal(str(product["min_amount"])) or amount > Decimal(
        str(product["max_amount"])
    ):
        raise bad_request("LOAN_AMOUNT_OUT_OF_RANGE", "申请金额不在产品金额范围内")


def _credit_application_by_no(
    application_no: str, ctx: RequestContext
) -> dict[str, Any]:
    row = fetch_one(
        "SELECT * FROM credit_application WHERE credit_application_no = %s",
        (application_no,),
    )
    if row is None:
        raise not_found("CREDIT_APPLICATION_NOT_FOUND", "授信申请不存在")
    if ctx.auth_type == "customer":
        customer = fetch_one(
            "SELECT customer_no FROM customer WHERE id = %s", (row["customer_id"],)
        )
        if customer is None or customer["customer_no"] != ctx.principal_no:
            raise forbidden("CUSTOMER_SCOPE_FORBIDDEN", "客户只能访问本人业务对象")
    return row


def _loan_application_by_no(application_no: str, ctx: RequestContext) -> dict[str, Any]:
    row = fetch_one(
        "SELECT * FROM loan_application WHERE application_no = %s", (application_no,)
    )
    if row is None:
        raise not_found("LOAN_APPLICATION_NOT_FOUND", "贷款申请不存在")
    if ctx.auth_type == "customer":
        customer = fetch_one(
            "SELECT customer_no FROM customer WHERE id = %s", (row["customer_id"],)
        )
        if customer is None or customer["customer_no"] != ctx.principal_no:
            raise forbidden("CUSTOMER_SCOPE_FORBIDDEN", "客户只能访问本人业务对象")
    return row


def _insert_materials(
    cursor: Any,
    material_scope: str,
    application_id: int,
    customer_id: int,
    materials: list[MaterialPayload],
    submitted_by: str,
    now: Any,
) -> None:
    for material in materials:
        if material_scope == "credit":
            cursor.execute(
                """
                INSERT INTO credit_application_material (
                    material_no,
                    credit_application_id,
                    customer_id,
                    material_type,
                    material_name,
                    file_url,
                    file_hash,
                    submitted_by,
                    verification_status,
                    submitted_at,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s)
                """,
                (
                    make_no("MAT"),
                    application_id,
                    customer_id,
                    material.material_type,
                    material.material_name,
                    material.file_url,
                    material.file_hash,
                    submitted_by,
                    now,
                    now,
                    now,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO loan_application_material (
                    material_no,
                    application_id,
                    customer_id,
                    material_type,
                    material_name,
                    file_url,
                    file_hash,
                    submitted_by,
                    verification_status,
                    submitted_at,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s)
                """,
                (
                    make_no("MAT"),
                    application_id,
                    customer_id,
                    material.material_type,
                    material.material_name,
                    material.file_url,
                    material.file_hash,
                    submitted_by,
                    now,
                    now,
                    now,
                ),
            )


def _limit_no_by_id(limit_id: int) -> str:
    row = fetch_one("SELECT limit_no FROM credit_limit WHERE id = %s", (limit_id,))
    if row is None:
        raise not_found("CREDIT_LIMIT_NOT_FOUND", "授信额度不存在")
    return str(row["limit_no"])


def _customer_repayment_account(customer_id: int, currency_code: str) -> dict[str, Any]:
    row = fetch_one(
        """
        SELECT *
        FROM bank_account
        WHERE customer_id = %s
          AND currency_code = %s
          AND account_status = 'active'
        ORDER BY opened_at DESC
        LIMIT 1
        """,
        (customer_id, currency_code),
    )
    if row is None:
        raise conflict("REPAYMENT_ACCOUNT_MISSING", "客户缺少可用还款账户")
    return row


def _update_limit_freeze(
    cursor: Any,
    limit_row: dict[str, Any],
    amount: Decimal,
    application_id: int,
    now: Any,
) -> None:
    before_frozen = Decimal(str(limit_row["frozen_limit_amount"]))
    before_available = Decimal(str(limit_row["available_limit_amount"]))
    after_frozen = before_frozen + amount
    after_available = before_available - amount
    cursor.execute(
        """
        UPDATE credit_limit
        SET frozen_limit_amount = %s,
            available_limit_amount = %s,
            updated_at = %s
        WHERE id = %s
        """,
        (after_frozen, after_available, now, limit_row["id"]),
    )
    cursor.execute(
        """
        SELECT COALESCE(MAX(change_seq), 0) + 1 AS next_seq
        FROM credit_limit_change_log
        WHERE credit_limit_id = %s
        FOR UPDATE
        """,
        (limit_row["id"],),
    )
    change_seq = int(cursor.fetchone()["next_seq"])
    cursor.execute(
        """
        INSERT INTO credit_limit_change_log (
            change_no,
            credit_limit_id,
            change_seq,
            loan_application_id,
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
        VALUES (%s, %s, %s, %s, 'freeze', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            make_no("LCL"),
            limit_row["id"],
            change_seq,
            application_id,
            limit_row["currency_code"],
            amount,
            limit_row["total_limit_amount"],
            limit_row["total_limit_amount"],
            limit_row["used_limit_amount"],
            limit_row["used_limit_amount"],
            before_frozen,
            after_frozen,
            before_available,
            after_available,
            now,
            now,
        ),
    )


def _release_limit_freeze(
    cursor: Any,
    limit_row: dict[str, Any],
    amount: Decimal,
    application_id: int,
    now: Any,
) -> None:
    before_frozen = Decimal(str(limit_row["frozen_limit_amount"]))
    before_available = Decimal(str(limit_row["available_limit_amount"]))
    after_frozen = max(before_frozen - amount, Decimal("0.00"))
    after_available = before_available + amount
    cursor.execute(
        """
        UPDATE credit_limit
        SET frozen_limit_amount = %s,
            available_limit_amount = %s,
            updated_at = %s
        WHERE id = %s
        """,
        (after_frozen, after_available, now, limit_row["id"]),
    )
    cursor.execute(
        """
        SELECT COALESCE(MAX(change_seq), 0) + 1 AS next_seq
        FROM credit_limit_change_log
        WHERE credit_limit_id = %s
        FOR UPDATE
        """,
        (limit_row["id"],),
    )
    change_seq = int(cursor.fetchone()["next_seq"])
    cursor.execute(
        """
        INSERT INTO credit_limit_change_log (
            change_no,
            credit_limit_id,
            change_seq,
            loan_application_id,
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
        VALUES (%s, %s, %s, %s, 'release', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            make_no("LCL"),
            limit_row["id"],
            change_seq,
            application_id,
            limit_row["currency_code"],
            amount,
            limit_row["total_limit_amount"],
            limit_row["total_limit_amount"],
            limit_row["used_limit_amount"],
            limit_row["used_limit_amount"],
            before_frozen,
            after_frozen,
            before_available,
            after_available,
            now,
            now,
        ),
    )


def _create_repayment_schedule(
    cursor: Any,
    contract: dict[str, Any],
    principal: Decimal,
    now: Any,
) -> None:
    term_months = max(int(contract["term_months"]), 1)
    principal_per_period = (principal / Decimal(term_months)).quantize(Decimal("0.01"))
    for period_no in range(1, term_months + 1):
        due_date = (now + timedelta(days=30 * period_no)).date()
        interest = (
            principal * Decimal(str(contract["annual_interest_rate"])) / Decimal("12")
        ).quantize(Decimal("0.01"))
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
            VALUES (%s, %s, 1, %s, %s, %s, %s, %s, %s, 'pending', %s, %s)
            ON DUPLICATE KEY UPDATE updated_at = VALUES(updated_at)
            """,
            (
                contract["id"],
                contract["customer_id"],
                period_no,
                due_date,
                contract["currency_code"],
                principal_per_period,
                interest,
                principal_per_period + interest,
                now,
                now,
            ),
        )
