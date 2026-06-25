"""Workflow, notification, support ticket and metric APIs."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Path, Query
from pydantic import BaseModel, Field

from ..database import db_cursor, fetch_all, fetch_one
from ..dependencies import RequestContext, get_request_context
from ..errors import bad_request, conflict, forbidden, not_found
from ..idempotency import idempotent_result, save_idempotent_result
from ..response import ok
from ..services import (
    create_workflow,
    current_employee,
    ensure_channel,
    ensure_customer_by_no,
)
from ..utils import (
    count_total,
    local_now,
    make_no,
    offset_limit,
    serialize_row,
    serialize_rows,
)

router = APIRouter(prefix="/api/v1", tags=["operations"])


class WorkflowInstanceCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    workflow_type: str = Field(description="流程类型")
    related_type: str = Field(description="关联业务对象类型")
    related_id: int = Field(description="关联业务对象 ID")
    initiator_type: str = Field(description="发起人类型")
    initiator_no: str = Field(description="发起人编号")


class WorkflowTaskCompleteRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    task_result: str = Field(description="任务处理结果")
    task_comment: str | None = Field(default=None, description="任务处理意见")


class NotificationCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    customer_no: str = Field(description="客户号，对应 customer.customer_no")
    message_type: str = Field(description="消息类型")
    send_channel: str = Field(description="发送渠道")
    related_type: str = Field(description="关联业务对象类型")
    related_id: int | None = Field(default=None, description="关联业务对象 ID")
    message_title: str = Field(description="消息标题")
    message_content: str = Field(description="消息内容")


class SupportTicketCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    customer_no: str = Field(description="客户号，对应 customer.customer_no")
    ticket_type: str = Field(description="工单类型")
    ticket_title: str = Field(description="工单标题")
    ticket_content: str = Field(description="工单内容")
    related_type: str = Field(description="关联业务对象类型")
    related_id: int | None = Field(default=None, description="关联业务对象 ID")


class SupportTicketFeedbackRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    confirm_status: str = Field(description="确认状态")
    satisfaction_score: int | None = Field(
        default=None, ge=1, le=5, description="满意度评分，范围 1 到 5"
    )
    feedback_content: str = Field(description="反馈内容")


@router.post("/workflow/instances", summary="创建流程实例")
def create_workflow_instance(
    body: Annotated[WorkflowInstanceCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "workflow_instance", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    _ensure_workflow_related(body.workflow_type, body.related_type, body.related_id)
    employee = current_employee(ctx)
    now = local_now()
    with db_cursor() as (_, cursor):
        workflow = create_workflow(
            cursor,
            workflow_type=body.workflow_type,
            related_type=body.related_type,
            related_id=body.related_id,
            initiator_type=body.initiator_type,
            initiator_no=body.initiator_no,
            assignee_id=employee["id"] if employee else None,
            now=now,
        )
    data = {"instance_no": workflow["instance_no"], "instance_status": "running"}
    save_idempotent_result(
        ctx.channel_code, "workflow_instance", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.get("/workflow/instances/{instance_no}", summary="查询流程实例详情")
def get_workflow_instance(
    instance_no: Annotated[str, Path(description="流程实例编号")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    instance = fetch_one(
        "SELECT * FROM workflow_instance WHERE instance_no = %s", (instance_no,)
    )
    if instance is None:
        raise not_found("WORKFLOW_INSTANCE_NOT_FOUND", "流程实例不存在")
    tasks = fetch_all(
        "SELECT * FROM workflow_task WHERE instance_id = %s ORDER BY id",
        (instance["id"],),
    )
    return ok(
        {
            "instance_status": instance["instance_status"],
            "tasks": serialize_rows(tasks),
            "task_records": serialize_rows(tasks),
        },
        ctx.request_id,
    )


@router.post("/workflow/tasks/{task_no}/complete", summary="完成流程任务")
def complete_workflow_task(
    task_no: Annotated[str, Path(description="流程任务编号")],
    body: Annotated[WorkflowTaskCompleteRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "workflow_task_complete", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    if body.task_result not in {"approved", "rejected", "skipped", "cancelled"}:
        raise bad_request("INVALID_TASK_RESULT", "流程任务处理结果不合法")
    employee = current_employee(ctx)
    task = fetch_one(
        """
        SELECT task.*, instance.instance_no, instance.related_type, instance.related_id
        FROM workflow_task AS task
        JOIN workflow_instance AS instance ON instance.id = task.instance_id
        WHERE task.task_no = %s
        """,
        (task_no,),
    )
    if task is None:
        raise not_found("WORKFLOW_TASK_NOT_FOUND", "流程任务不存在")
    if task["task_status"] not in {"pending", "processing"}:
        raise conflict("WORKFLOW_TASK_STATUS_FORBIDDEN", "流程任务状态不允许处理")
    now = local_now()
    instance_status = "approved" if body.task_result == "approved" else body.task_result
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            UPDATE workflow_task
            SET assignee_id = %s,
                task_status = %s,
                task_result = %s,
                task_comment = %s,
                completed_at = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (
                employee["id"] if employee else task["assignee_id"],
                body.task_result,
                body.task_result,
                body.task_comment,
                now,
                now,
                task["id"],
            ),
        )
        cursor.execute(
            """
            UPDATE workflow_instance
            SET instance_status = %s,
                completed_at = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (instance_status, now, now, task["instance_id"]),
        )
        _update_workflow_related_status(
            cursor,
            str(task["related_type"]),
            int(task["related_id"]),
            instance_status,
            now,
        )
    data = {
        "task_no": task_no,
        "task_status": body.task_result,
        "instance_status": instance_status,
        "related_type": task["related_type"],
        "related_no": str(task["related_id"]) if task["related_id"] else None,
        "business_status": instance_status,
    }
    save_idempotent_result(
        ctx.channel_code,
        "workflow_task_complete",
        body.request_no,
        body.model_dump(),
        data,
    )
    return ok(data, ctx.request_id)


@router.post("/notifications", summary="发送业务通知")
def create_notification(
    body: Annotated[NotificationCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "notification", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    customer = ensure_customer_by_no(body.customer_no, ctx)
    if body.related_type == "none" and body.related_id is not None:
        raise bad_request(
            "NOTIFICATION_RELATED_ID_FORBIDDEN", "无关联系统通知不得传关联对象编号"
        )
    if body.related_type != "none" and body.related_id is None:
        raise bad_request(
            "NOTIFICATION_RELATED_ID_REQUIRED", "业务通知必须传关联对象编号"
        )
    if body.related_type != "none":
        related_id = body.related_id
        if related_id is None:
            raise bad_request(
                "NOTIFICATION_RELATED_ID_REQUIRED", "业务通知必须传关联对象编号"
            )
        _ensure_related_object(body.related_type, related_id)
    if body.send_channel == "app_push" and not _has_push_device(int(customer["id"])):
        raise conflict("APP_PUSH_DEVICE_UNAVAILABLE", "客户没有可用 App 推送设备")
    now = local_now()
    message_no = make_no("MSG")
    send_status = (
        "success" if body.send_channel in {"site_message", "app_push"} else "pending"
    )
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO notification_message (
                message_no,
                customer_id,
                related_type,
                related_id,
                message_type,
                send_channel,
                message_title,
                message_content,
                send_status,
                sent_at,
                read_status,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'unread', %s, %s)
            """,
            (
                message_no,
                customer["id"],
                body.related_type,
                body.related_id,
                body.message_type,
                body.send_channel,
                body.message_title,
                body.message_content,
                send_status,
                now if send_status == "success" else None,
                now,
                now,
            ),
        )
    data = {"message_no": message_no, "send_status": send_status}
    save_idempotent_result(
        ctx.channel_code, "notification", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.get("/customers/{customer_no}/notifications", summary="查询客户通知")
def list_notifications(
    customer_no: Annotated[str, Path(description="客户号，对应 customer.customer_no")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    message_type: str | None = Query(description="消息类型", default=None),
    send_status: str | None = Query(description="发送状态", default=None),
    page_no: int = Query(description="页码，从 1 开始", default=1, ge=1),
    page_size: int = Query(
        description="每页条数，范围 1 到 100", default=20, ge=1, le=100
    ),
) -> dict[str, object]:
    customer = ensure_customer_by_no(customer_no, ctx)
    where = ["customer_id = %s"]
    params: list[object] = [customer["id"]]
    if message_type:
        where.append("message_type = %s")
        params.append(message_type)
    if send_status:
        where.append("send_status = %s")
        params.append(send_status)
    offset, limit = offset_limit(page_no, page_size)
    rows = fetch_all(
        f"""
        SELECT *
        FROM notification_message
        WHERE {" AND ".join(where)}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )
    total = count_total(
        f"SELECT COUNT(*) AS total FROM notification_message WHERE {' AND '.join(where)}",
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


@router.post("/support/tickets", summary="创建客服工单")
def create_support_ticket(
    body: Annotated[SupportTicketCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "support_ticket", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    customer = ensure_customer_by_no(body.customer_no, ctx)
    if body.related_type != "none":
        if body.related_id is None:
            raise bad_request("SUPPORT_RELATED_ID_REQUIRED", "工单关联对象编号不能为空")
        _ensure_related_object(body.related_type, int(body.related_id))
    channel = ensure_channel(ctx.channel_code)
    employee = current_employee(ctx)
    now = local_now()
    ticket_no = make_no("TKT")
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO support_ticket (
                ticket_no,
                customer_id,
                channel_id,
                assignee_id,
                ticket_type,
                related_type,
                related_id,
                ticket_title,
                ticket_content,
                ticket_status,
                handle_result,
                submitted_at,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'submitted', '', %s, %s, %s)
            """,
            (
                ticket_no,
                customer["id"],
                channel["id"],
                employee["id"] if employee else None,
                body.ticket_type,
                body.related_type,
                body.related_id,
                body.ticket_title,
                body.ticket_content,
                now,
                now,
                now,
            ),
        )
        ticket_id = int(cursor.lastrowid)
        create_workflow(
            cursor,
            workflow_type="support_ticket",
            related_type="support_ticket",
            related_id=ticket_id,
            initiator_type=ctx.auth_type,
            initiator_no=ctx.principal_no,
            assignee_id=employee["id"] if employee else None,
            now=now,
        )
    data = {"ticket_no": ticket_no, "ticket_status": "submitted"}
    save_idempotent_result(
        ctx.channel_code, "support_ticket", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.get("/support/tickets/{ticket_no}", summary="查询客服工单详情")
def get_support_ticket(
    ticket_no: Annotated[str, Path(description="工单编号")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    ticket = _ticket_by_no(ticket_no, ctx)
    handler = (
        fetch_one(
            "SELECT employee_no, employee_name FROM dim_employee WHERE id = %s",
            (ticket["assignee_id"],),
        )
        if ticket["assignee_id"]
        else None
    )
    feedback = fetch_one(
        "SELECT * FROM support_ticket_feedback WHERE ticket_id = %s", (ticket["id"],)
    )
    return ok(
        {
            "ticket_info": serialize_row(ticket),
            "handler": serialize_row(handler) if handler else None,
            "process_result": ticket["handle_result"],
            "feedback": serialize_row(feedback) if feedback else None,
        },
        ctx.request_id,
    )


@router.post("/support/tickets/{ticket_no}/feedback", summary="提交工单反馈")
def create_support_feedback(
    ticket_no: Annotated[str, Path(description="工单编号")],
    body: Annotated[SupportTicketFeedbackRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "support_ticket_feedback", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    ticket = _ticket_by_no(ticket_no, ctx)
    now = local_now()
    feedback_no = make_no("FBK")
    confirmed_at = now if body.confirm_status == "confirmed" else None
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO support_ticket_feedback (
                feedback_no,
                ticket_id,
                customer_id,
                confirm_status,
                satisfaction_score,
                feedback_content,
                confirmed_at,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                confirm_status = VALUES(confirm_status),
                satisfaction_score = VALUES(satisfaction_score),
                feedback_content = VALUES(feedback_content),
                confirmed_at = VALUES(confirmed_at),
                updated_at = VALUES(updated_at)
            """,
            (
                feedback_no,
                ticket["id"],
                ticket["customer_id"],
                body.confirm_status,
                body.satisfaction_score,
                body.feedback_content,
                confirmed_at,
                now,
                now,
            ),
        )
        cursor.execute(
            """
            SELECT feedback_no, confirm_status
            FROM support_ticket_feedback
            WHERE ticket_id = %s
            """,
            (ticket["id"],),
        )
        feedback = cursor.fetchone()
    data = {
        "feedback_no": feedback["feedback_no"],
        "confirm_status": feedback["confirm_status"],
    }
    save_idempotent_result(
        ctx.channel_code,
        "support_ticket_feedback",
        body.request_no,
        body.model_dump(),
        data,
    )
    return ok(data, ctx.request_id)


@router.get("/metrics/daily", summary="查询业务日统计")
def list_metrics_daily(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    stat_date: date | None = Query(
        description="统计日期，格式 YYYY-MM-DD", default=None
    ),
    stat_domain: str | None = Query(description="统计域", default=None),
    metric_code: str | None = Query(description="指标编码", default=None),
    branch_code: str | None = Query(
        description="机构编码，对应 dim_branch.branch_code", default=None
    ),
    channel_code: str | None = Query(
        description="渠道编码，对应 dim_channel.channel_code", default=None
    ),
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
        where.append("stat.stat_date = %s")
        params.append(stat_date)
    if stat_domain:
        where.append("stat.stat_domain = %s")
        params.append(stat_domain)
    if metric_code:
        where.append("stat.metric_code = %s")
        params.append(metric_code)
    if branch_code:
        where.append("branch.branch_code = %s")
        params.append(branch_code)
    if channel_code:
        where.append("channel.channel_code = %s")
        params.append(channel_code)
    if currency_code:
        where.append("stat.currency_code = %s")
        params.append(currency_code)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    offset, limit = offset_limit(page_no, page_size)
    rows = fetch_all(
        f"""
        SELECT
            stat.stat_date,
            stat.stat_domain,
            stat.metric_code,
            branch.branch_code,
            channel.channel_code,
            stat.currency_code,
            stat.metric_value
        FROM business_stat_daily AS stat
        JOIN dim_branch AS branch ON branch.id = stat.branch_id
        JOIN dim_channel AS channel ON channel.id = stat.channel_id
        JOIN business_metric_dict AS metric ON metric.id = stat.metric_id
        {where_sql}
        ORDER BY stat.stat_date DESC, stat.metric_code
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )
    total = count_total(
        f"""
        SELECT COUNT(*) AS total
        FROM business_stat_daily AS stat
        JOIN dim_branch AS branch ON branch.id = stat.branch_id
        JOIN dim_channel AS channel ON channel.id = stat.channel_id
        JOIN business_metric_dict AS metric ON metric.id = stat.metric_id
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


def _ensure_workflow_related(
    workflow_type: str, related_type: str, related_id: int
) -> None:
    mapping = {
        "loan_approval": {"credit_application", "loan_application"},
        "wealth_review": {"wealth_order", "risk_event"},
        "fee_reduction": {"fee_reduction"},
        "risk_review": {"risk_event"},
        "support_ticket": {"support_ticket"},
    }
    if workflow_type not in mapping or related_type not in mapping[workflow_type]:
        raise bad_request(
            "WORKFLOW_RELATED_TYPE_MISMATCH", "流程类型与关联对象类型不匹配"
        )
    table = {
        "credit_application": "credit_application",
        "loan_application": "loan_application",
        "wealth_order": "wealth_order",
        "fee_reduction": "fee_reduction",
        "risk_event": "risk_event",
        "support_ticket": "support_ticket",
    }[related_type]
    row = fetch_one(f"SELECT id FROM {table} WHERE id = %s", (related_id,))
    if row is None:
        raise not_found("WORKFLOW_RELATED_OBJECT_NOT_FOUND", "流程关联业务对象不存在")


def _ensure_related_object(related_type: str, related_id: int) -> None:
    mapping = {
        "account_transaction": "account_transaction",
        "wealth_order": "wealth_order",
        "loan_contract": "loan_contract",
        "loan_application": "loan_application",
        "repayment_bill": "repayment_bill",
        "collection_case": "collection_case",
        "support_ticket": "support_ticket",
        "risk_event": "risk_event",
        "fee_reduction": "fee_reduction",
    }
    table = mapping.get(related_type)
    if table is None:
        raise bad_request("RELATED_TYPE_UNSUPPORTED", "关联对象类型不支持")
    row = fetch_one(f"SELECT id FROM {table} WHERE id = %s", (related_id,))
    if row is None:
        raise not_found("RELATED_OBJECT_NOT_FOUND", "关联业务对象不存在")


def _update_workflow_related_status(
    cursor: Any,
    related_type: str,
    related_id: int,
    status: str,
    now: Any,
) -> None:
    status_mapping = {
        "credit_application": ("credit_application", "application_status"),
        "loan_application": ("loan_application", "application_status"),
        "wealth_order": ("wealth_order", "order_status"),
        "fee_reduction": ("fee_reduction", "reduction_status"),
        "risk_event": ("risk_event", "event_status"),
        "support_ticket": ("support_ticket", "ticket_status"),
    }
    target = status_mapping.get(related_type)
    if target is None:
        return
    table, column = target
    cursor.execute(
        f"UPDATE {table} SET {column} = %s, updated_at = %s WHERE id = %s",
        (status, now, related_id),
    )


def _has_push_device(customer_id: int) -> bool:
    row = fetch_one(
        """
        SELECT id
        FROM customer_device
        WHERE customer_id = %s
          AND device_type IN ('ios', 'android')
          AND push_token IS NOT NULL
          AND risk_status <> 'blacklisted'
        LIMIT 1
        """,
        (customer_id,),
    )
    return row is not None


def _ticket_by_no(ticket_no: str, ctx: RequestContext) -> dict[str, Any]:
    row = fetch_one("SELECT * FROM support_ticket WHERE ticket_no = %s", (ticket_no,))
    if row is None:
        raise not_found("SUPPORT_TICKET_NOT_FOUND", "客服工单不存在")
    if ctx.auth_type == "customer":
        customer = fetch_one(
            "SELECT customer_no FROM customer WHERE id = %s", (row["customer_id"],)
        )
        if customer is None or customer["customer_no"] != ctx.principal_no:
            raise forbidden("CUSTOMER_SCOPE_FORBIDDEN", "客户只能访问本人业务对象")
    return row
