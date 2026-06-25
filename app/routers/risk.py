"""Risk control and AML APIs."""

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
from ..services import current_employee, ensure_customer_by_no
from ..utils import (
    count_total,
    local_now,
    make_no,
    offset_limit,
    serialize_row,
    serialize_rows,
)

router = APIRouter(prefix="/api/v1", tags=["risk"])


class RiskEventCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    customer_no: str = Field(description="客户号，对应 customer.customer_no")
    related_type: str = Field(description="关联业务对象类型")
    related_id: int | None = Field(default=None, description="关联业务对象 ID")
    event_type: str = Field(description="风险事件类型")
    risk_score: int = Field(ge=0, description="风险分值，必须大于或等于 0")


class ManualReviewCompleteRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    review_result: str = Field(description="复核结果")
    review_comment: str | None = Field(default=None, description="复核意见")


class BlacklistCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    subject_type: str = Field(description="黑名单主体类型")
    subject_value: str = Field(description="黑名单主体值")
    risk_level_code: str = Field(description="风险等级编码")
    reason: str = Field(description="业务原因")
    effective_from: date = Field(description="生效日期，格式 YYYY-MM-DD")
    effective_to: date | None = Field(
        default=None, description="失效日期，格式 YYYY-MM-DD"
    )


class AmlCaseTransactionPayload(BaseModel):
    transaction_no: str = Field(
        description="账户交易号，对应 account_transaction.transaction_no"
    )
    included_flag: int = Field(default=1, description="是否纳入案件，1 是，0 否")
    include_reason: str = Field(description="纳入原因")


class AmlCaseCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    customer_no: str = Field(description="客户号，对应 customer.customer_no")
    risk_event_no: str = Field(description="风险事件号")
    case_type: str = Field(description="案件类型")
    suspicious_reason: str = Field(description="可疑原因")
    transactions: list[AmlCaseTransactionPayload] = Field(
        default_factory=list, description="涉案交易列表"
    )


class AmlReviewRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    review_result: str = Field(description="复核结果")
    report_flag: bool = Field(default=False, description="是否生成可疑交易报告")
    review_comment: str | None = Field(default=None, description="复核意见")


@router.post("/risk/events", summary="创建风险事件")
def create_risk_event(
    body: Annotated[RiskEventCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "risk_event", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    customer = ensure_customer_by_no(body.customer_no, ctx)
    if body.related_type != "none":
        _ensure_risk_related_object(
            body.related_type, body.related_id, int(customer["id"])
        )
    strategy = _risk_strategy(body.event_type)
    risk_level = _risk_level_by_score(body.risk_score)
    rules = _risk_rules(strategy["id"], body.risk_score)
    decision_action = rules[0]["decision_action"] if rules else "pass"
    now = local_now()
    event_no = make_no("RKE")
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO risk_event (
                event_no,
                customer_id,
                event_type,
                related_type,
                related_id,
                strategy_id,
                risk_level_id,
                risk_score,
                decision_action,
                hit_flag,
                no_hit_reason,
                decision_reason,
                event_status,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'created', %s, %s)
            """,
            (
                event_no,
                customer["id"],
                body.event_type,
                body.related_type,
                body.related_id,
                strategy["id"],
                risk_level["id"],
                body.risk_score,
                decision_action,
                1 if rules else 0,
                None if rules else "no_rule_hit",
                "api risk decision",
                now,
                now,
            ),
        )
        event_id = int(cursor.lastrowid)
        for rule in rules:
            cursor.execute(
                """
                INSERT INTO risk_hit_record (
                    event_id,
                    rule_id,
                    hit_score,
                    hit_detail,
                    decision_action,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    event_id,
                    rule["id"],
                    body.risk_score,
                    rule["rule_expression"],
                    rule["decision_action"],
                    now,
                ),
            )
        if decision_action == "manual_review":
            cursor.execute(
                """
                INSERT INTO manual_review_task (
                    task_no,
                    customer_id,
                    risk_event_id,
                    related_type,
                    related_id,
                    task_type,
                    task_status,
                    assigned_at,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, 'risk_event', %s, 'risk_review', 'pending', %s, %s, %s)
                """,
                (make_no("MRT"), customer["id"], event_id, event_id, now, now, now),
            )
    data = {
        "event_no": event_no,
        "decision_action": decision_action,
        "hit_rules": [row["rule_code"] for row in rules],
    }
    save_idempotent_result(
        ctx.channel_code, "risk_event", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.get("/risk/events/{event_no}", summary="查询风险事件详情")
def get_risk_event(
    event_no: Annotated[str, Path(description="风险事件号")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    event = _risk_event_by_no(event_no, ctx)
    hits = fetch_all(
        """
        SELECT hit.*, rule.rule_code, rule.rule_name
        FROM risk_hit_record AS hit
        JOIN risk_rule AS rule ON rule.id = hit.rule_id
        WHERE hit.event_id = %s
        """,
        (event["id"],),
    )
    task = fetch_one(
        "SELECT * FROM manual_review_task WHERE risk_event_id = %s ORDER BY id DESC LIMIT 1",
        (event["id"],),
    )
    return ok(
        {
            "event_info": serialize_row(event),
            "hit_records": serialize_rows(hits),
            "disposal_result": event["decision_action"],
            "manual_review_task": serialize_row(task) if task else None,
        },
        ctx.request_id,
    )


@router.post("/manual-review/tasks/{task_no}/complete", summary="完成人工复核任务")
def complete_manual_review(
    task_no: Annotated[str, Path(description="流程任务编号")],
    body: Annotated[ManualReviewCompleteRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "manual_review_complete", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    if body.review_result not in {"approved", "rejected"}:
        raise bad_request("INVALID_REVIEW_RESULT", "复核结果不合法")
    employee = current_employee(ctx)
    if employee is None:
        raise forbidden("EMPLOYEE_AUTH_REQUIRED", "人工复核接口需要员工身份")
    task = fetch_one("SELECT * FROM manual_review_task WHERE task_no = %s", (task_no,))
    if task is None:
        raise not_found("MANUAL_REVIEW_TASK_NOT_FOUND", "人工复核任务不存在")
    if task["task_status"] not in {"pending", "processing"}:
        raise conflict(
            "MANUAL_REVIEW_TASK_STATUS_FORBIDDEN", "人工复核任务状态不允许处理"
        )
    now = local_now()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            UPDATE manual_review_task
            SET assignee_id = %s,
                task_status = %s,
                review_result = %s,
                review_comment = %s,
                completed_at = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (
                employee["id"],
                body.review_result,
                body.review_result,
                body.review_comment,
                now,
                now,
                task["id"],
            ),
        )
        if task["risk_event_id"]:
            cursor.execute(
                """
                UPDATE risk_event
                SET event_status = %s, updated_at = %s
                WHERE id = %s
                """,
                (body.review_result, now, task["risk_event_id"]),
            )
    data = {
        "task_no": task_no,
        "task_status": body.review_result,
        "related_type": task["related_type"],
        "related_no": str(task["related_id"]) if task["related_id"] else None,
        "business_status": body.review_result,
    }
    save_idempotent_result(
        ctx.channel_code,
        "manual_review_complete",
        body.request_no,
        body.model_dump(),
        data,
    )
    return ok(data, ctx.request_id)


@router.get("/blacklists", summary="查询黑名单记录")
def list_blacklists(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    customer_no: str | None = Query(
        description="客户号，对应 customer.customer_no", default=None
    ),
    identity_no: str | None = Query(description="证件号码", default=None),
    mobile: str | None = Query(description="手机号", default=None),
    blacklist_status: str | None = Query(description="黑名单状态", default=None),
    page_no: int = Query(description="页码，从 1 开始", default=1, ge=1),
    page_size: int = Query(
        description="每页条数，范围 1 到 100", default=20, ge=1, le=100
    ),
) -> dict[str, object]:
    where: list[str] = []
    params: list[object] = []
    if customer_no:
        where.append("subject_value = %s")
        params.append(customer_no)
    if identity_no:
        where.append("subject_value = %s")
        params.append(identity_no)
    if mobile:
        where.append("subject_value = %s")
        params.append(mobile)
    if blacklist_status:
        where.append("blacklist_status = %s")
        params.append(blacklist_status)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    offset, limit = offset_limit(page_no, page_size)
    rows = fetch_all(
        f"""
        SELECT blacklist.blacklist_no, risk.risk_level_code AS risk_level, blacklist.blacklist_status
        FROM blacklist_record AS blacklist
        JOIN dim_risk_level AS risk ON risk.id = blacklist.risk_level_id
        {where_sql}
        ORDER BY blacklist.created_at DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )
    total = count_total(
        f"SELECT COUNT(*) AS total FROM blacklist_record {where_sql}",
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


@router.post("/blacklists", summary="新增黑名单记录")
def create_blacklist(
    body: Annotated[BlacklistCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "blacklist", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    risk_level = _risk_level_by_code(body.risk_level_code)
    now = local_now()
    blacklist_no = make_no("BLK")
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO blacklist_record (
                blacklist_no,
                subject_type,
                subject_value,
                risk_level_id,
                blacklist_reason,
                blacklist_status,
                effective_from,
                effective_to,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, 'active', %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                risk_level_id = VALUES(risk_level_id),
                blacklist_reason = VALUES(blacklist_reason),
                blacklist_status = 'active',
                effective_from = VALUES(effective_from),
                effective_to = VALUES(effective_to),
                updated_at = VALUES(updated_at)
            """,
            (
                blacklist_no,
                body.subject_type,
                body.subject_value,
                risk_level["id"],
                body.reason,
                body.effective_from,
                body.effective_to,
                now,
                now,
            ),
        )
        cursor.execute(
            """
            SELECT blacklist_no, blacklist_status
            FROM blacklist_record
            WHERE subject_type = %s AND subject_value = %s
            """,
            (body.subject_type, body.subject_value),
        )
        row = cursor.fetchone()
    data = {
        "blacklist_no": row["blacklist_no"],
        "blacklist_status": row["blacklist_status"],
    }
    save_idempotent_result(
        ctx.channel_code, "blacklist", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post("/aml/cases", summary="创建 AML 案件")
def create_aml_case(
    body: Annotated[AmlCaseCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "aml_case", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    customer = ensure_customer_by_no(body.customer_no, ctx)
    event = _risk_event_by_no(body.risk_event_no, ctx)
    tx_rows = [
        _transaction_by_no(item.transaction_no, ctx) for item in body.transactions
    ]
    total_amount = sum(
        (Decimal(str(row["transaction_amount"])) for row in tx_rows), Decimal("0.00")
    )
    currency_code = tx_rows[0]["currency_code"] if tx_rows else "CNY"
    risk_level = _risk_level_by_score(80)
    now = local_now()
    case_no = make_no("AML")
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO aml_case (
                case_no,
                risk_event_id,
                customer_id,
                primary_transaction_id,
                transaction_count,
                total_transaction_amount,
                currency_code,
                case_type,
                case_status,
                risk_level_id,
                case_summary,
                opened_at,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'opened', %s, %s, %s, %s, %s)
            """,
            (
                case_no,
                event["id"],
                customer["id"],
                tx_rows[0]["id"] if tx_rows else None,
                len(tx_rows),
                total_amount,
                currency_code,
                body.case_type,
                risk_level["id"],
                body.suspicious_reason,
                now,
                now,
                now,
            ),
        )
        case_id = int(cursor.lastrowid)
        for payload, tx in zip(body.transactions, tx_rows, strict=True):
            cursor.execute(
                """
                INSERT INTO aml_case_transaction (
                    aml_case_id,
                    transaction_id,
                    customer_id,
                    currency_code,
                    transaction_amount,
                    included_flag,
                    include_reason,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    case_id,
                    tx["id"],
                    customer["id"],
                    tx["currency_code"],
                    tx["transaction_amount"],
                    payload.included_flag,
                    payload.include_reason,
                    now,
                ),
            )
    data = {"case_no": case_no, "case_status": "opened"}
    save_idempotent_result(
        ctx.channel_code, "aml_case", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post("/aml/cases/{case_no}/review-results", summary="提交 AML 复核结果")
def review_aml_case(
    case_no: Annotated[str, Path(description="案件编号")],
    body: Annotated[AmlReviewRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "aml_review", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    case = _aml_case_by_no(case_no, ctx)
    employee = current_employee(ctx)
    if employee is None:
        raise forbidden("EMPLOYEE_AUTH_REQUIRED", "AML 复核接口需要员工身份")
    now = local_now()
    review_no = make_no("AMR")
    report_no = None
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO aml_review_result (
                review_no,
                aml_case_id,
                risk_event_id,
                reviewer_id,
                review_result,
                review_comment,
                reviewed_at,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                review_no,
                case["id"],
                case["risk_event_id"],
                employee["id"],
                body.review_result,
                body.review_comment,
                now,
                now,
            ),
        )
        status = "reported" if body.report_flag else body.review_result
        cursor.execute(
            "UPDATE aml_case SET case_status = %s, closed_at = %s, updated_at = %s WHERE id = %s",
            (status, now, now, case["id"]),
        )
        if body.report_flag:
            report_no = make_no("STR")
            cursor.execute(
                """
                INSERT INTO suspicious_transaction_report (
                    report_no,
                    aml_case_id,
                    customer_id,
                    transaction_count,
                    total_transaction_amount,
                    currency_code,
                    report_period_start,
                    report_period_end,
                    report_type,
                    report_status,
                    reported_at,
                    report_content,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'aml', 'reported', %s, %s, %s, %s)
                """,
                (
                    report_no,
                    case["id"],
                    case["customer_id"],
                    case["transaction_count"],
                    case["total_transaction_amount"],
                    case["currency_code"],
                    now.date(),
                    now.date(),
                    now,
                    body.review_comment or "aml suspicious transaction report",
                    now,
                    now,
                ),
            )
    data = {"review_no": review_no, "case_status": status, "report_no": report_no}
    save_idempotent_result(
        ctx.channel_code, "aml_review", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.get("/aml/reports/{report_no}", summary="查询可疑交易报告")
def get_aml_report(
    report_no: Annotated[str, Path(description="报告编号")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    report = fetch_one(
        """
        SELECT report.*, aml.case_no, aml.case_status
        FROM suspicious_transaction_report AS report
        JOIN aml_case AS aml ON aml.id = report.aml_case_id
        WHERE report.report_no = %s
        """,
        (report_no,),
    )
    if report is None:
        raise not_found("AML_REPORT_NOT_FOUND", "可疑交易报告不存在")
    return ok(serialize_row(report), ctx.request_id)


def _risk_strategy(event_type: str) -> dict[str, Any]:
    row = fetch_one(
        """
        SELECT *
        FROM risk_strategy
        WHERE applicable_event_type = %s AND strategy_status = 'active'
        ORDER BY effective_from DESC
        LIMIT 1
        """,
        (event_type,),
    )
    if row is None:
        row = fetch_one(
            "SELECT * FROM risk_strategy WHERE strategy_status = 'active' LIMIT 1"
        )
    if row is None:
        raise conflict("RISK_STRATEGY_MISSING", "缺少可用风控策略")
    return row


def _ensure_risk_related_object(
    related_type: str, related_id: int | None, customer_id: int
) -> None:
    if related_id is None:
        raise bad_request("RELATED_ID_REQUIRED", "风险事件关联对象编号不能为空")
    mapping = {
        "account_transaction": ("account_transaction", "customer_id"),
        "credit_application": ("credit_application", "customer_id"),
        "loan_application": ("loan_application", "customer_id"),
        "wealth_order": ("wealth_order", "customer_id"),
        "collection_case": ("collection_case", "customer_id"),
        "bank_account": ("bank_account", "customer_id"),
    }
    target = mapping.get(related_type)
    if target is None:
        raise bad_request("RELATED_TYPE_UNSUPPORTED", "风险事件关联对象类型不支持")
    table, customer_column = target
    row = fetch_one(
        f"SELECT id FROM {table} WHERE id = %s AND {customer_column} = %s",
        (related_id, customer_id),
    )
    if row is None:
        raise not_found("RELATED_OBJECT_NOT_FOUND", "风险事件关联业务对象不存在")


def _risk_rules(strategy_id: int, score: int) -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT rule.*
        FROM risk_strategy_rule_rel AS rel
        JOIN risk_rule AS rule ON rule.id = rel.rule_id
        WHERE rel.strategy_id = %s
          AND rel.yn = 1
          AND rule.rule_status = 'active'
          AND %s >= CAST(rule.threshold_value AS SIGNED)
        ORDER BY rel.execute_order
        """,
        (strategy_id, score),
    )


def _risk_level_by_score(score: int) -> dict[str, Any]:
    row = fetch_one(
        """
        SELECT *
        FROM dim_risk_level
        WHERE risk_level_type IN ('event', 'customer')
          AND yn = 1
          AND %s BETWEEN risk_score_min AND risk_score_max
        ORDER BY CASE WHEN risk_level_type = 'event' THEN 0 ELSE 1 END, sort_no
        LIMIT 1
        """,
        (score,),
    )
    if row is None:
        raise bad_request("RISK_SCORE_OUT_OF_RANGE", "风险评分不在风险等级区间内")
    return row


def _risk_level_by_code(code: str) -> dict[str, Any]:
    row = fetch_one(
        "SELECT * FROM dim_risk_level WHERE risk_level_code = %s AND yn = 1", (code,)
    )
    if row is None:
        raise not_found("RISK_LEVEL_NOT_FOUND", "风险等级不存在或不可用")
    return row


def _risk_event_by_no(event_no: str | None, ctx: RequestContext) -> dict[str, Any]:
    row = fetch_one("SELECT * FROM risk_event WHERE event_no = %s", (event_no,))
    if row is None:
        raise not_found("RISK_EVENT_NOT_FOUND", "风险事件不存在")
    if ctx.auth_type == "customer":
        customer = fetch_one(
            "SELECT customer_no FROM customer WHERE id = %s", (row["customer_id"],)
        )
        if customer is None or customer["customer_no"] != ctx.principal_no:
            raise forbidden("CUSTOMER_SCOPE_FORBIDDEN", "客户只能访问本人业务对象")
    return row


def _transaction_by_no(transaction_no: str, ctx: RequestContext) -> dict[str, Any]:
    row = fetch_one(
        "SELECT * FROM account_transaction WHERE transaction_no = %s", (transaction_no,)
    )
    if row is None:
        raise not_found("TRANSACTION_NOT_FOUND", "账户交易不存在")
    if ctx.auth_type == "customer":
        customer = fetch_one(
            "SELECT customer_no FROM customer WHERE id = %s", (row["customer_id"],)
        )
        if customer is None or customer["customer_no"] != ctx.principal_no:
            raise forbidden("CUSTOMER_SCOPE_FORBIDDEN", "客户只能访问本人业务对象")
    return row


def _aml_case_by_no(case_no: str, ctx: RequestContext) -> dict[str, Any]:
    row = fetch_one("SELECT * FROM aml_case WHERE case_no = %s", (case_no,))
    if row is None:
        raise not_found("AML_CASE_NOT_FOUND", "AML 案件不存在")
    if ctx.auth_type == "customer":
        customer = fetch_one(
            "SELECT customer_no FROM customer WHERE id = %s", (row["customer_id"],)
        )
        if customer is None or customer["customer_no"] != ctx.principal_no:
            raise forbidden("CUSTOMER_SCOPE_FORBIDDEN", "客户只能访问本人业务对象")
    return row
