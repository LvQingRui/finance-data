"""FastAPI dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Header

from .database import fetch_one
from .errors import forbidden, not_found, unauthorized


@dataclass(frozen=True)
class RequestContext:
    request_id: str | None
    channel_code: str
    auth_type: str
    principal_no: str
    operator_no: str | None


AuthorizationHeader = Annotated[
    str | None,
    Header(
        alias="Authorization",
        description="Bearer token；当前直接使用客户号、员工编号或系统服务账号员工编号",
    ),
]
RequestIdHeader = Annotated[
    str | None,
    Header(alias="X-Request-Id", description="请求追踪号，用于链路排查和响应回传"),
]
ChannelCodeHeader = Annotated[
    str | None,
    Header(
        alias="X-Channel-Code", description="渠道编码，对应 dim_channel.channel_code"
    ),
]
OperatorNoHeader = Annotated[
    str | None,
    Header(alias="X-Operator-No", description="人工操作人编号，用于员工端操作审计"),
]


def get_request_context(
    authorization: AuthorizationHeader = None,
    x_request_id: RequestIdHeader = None,
    x_channel_code: ChannelCodeHeader = None,
    x_operator_no: OperatorNoHeader = None,
) -> RequestContext:
    channel_code = _require_header(x_channel_code, "X-Channel-Code")
    _ensure_channel(channel_code)
    if x_operator_no:
        _ensure_employee(x_operator_no)

    token = _parse_bearer_token(authorization)
    customer = fetch_one(
        """
        SELECT customer_no, customer_status
        FROM customer
        WHERE customer_no = %s
        """,
        (token,),
    )
    if customer is not None:
        if customer["customer_status"] in {"closed", "cancelled", "blacklisted"}:
            raise forbidden("CUSTOMER_STATUS_FORBIDDEN", "当前客户状态不允许办理业务")
        return RequestContext(
            request_id=x_request_id,
            channel_code=channel_code,
            auth_type="customer",
            principal_no=token,
            operator_no=x_operator_no,
        )

    employee = fetch_one(
        """
        SELECT employee_no
        FROM dim_employee
        WHERE employee_no = %s AND employee_status = 'active'
        """,
        (token,),
    )
    if employee is not None:
        return RequestContext(
            request_id=x_request_id,
            channel_code=channel_code,
            auth_type="employee",
            principal_no=token,
            operator_no=x_operator_no,
        )

    raise unauthorized("PRINCIPAL_NOT_FOUND", "登录态对应客户或员工不存在")


def ensure_customer_access(customer_no: str, ctx: RequestContext) -> dict[str, Any]:
    row = fetch_one(
        """
        SELECT *
        FROM customer
        WHERE customer_no = %s
        """,
        (customer_no,),
    )
    if row is None:
        raise not_found("CUSTOMER_NOT_FOUND", "客户不存在")
    if ctx.auth_type == "customer" and ctx.principal_no != customer_no:
        raise forbidden("CUSTOMER_SCOPE_FORBIDDEN", "客户只能访问本人业务对象")
    if row["customer_status"] in {"closed", "cancelled", "blacklisted"}:
        raise forbidden("CUSTOMER_STATUS_FORBIDDEN", "客户状态不允许办理当前业务")
    return row


def ensure_employee_access(ctx: RequestContext) -> dict[str, Any]:
    employee_no = ctx.operator_no or ctx.principal_no
    employee = _ensure_employee(employee_no)
    if ctx.auth_type == "customer":
        raise forbidden("EMPLOYEE_AUTH_REQUIRED", "当前接口需要员工身份")
    return employee


def _require_header(value: str | None, name: str) -> str:
    if value is None or not value.strip():
        raise unauthorized("MISSING_HEADER", f"缺少请求头 {name}")
    return value.strip()


def _parse_bearer_token(authorization: str | None) -> str:
    if authorization is None or not authorization.strip():
        raise unauthorized("MISSING_AUTHORIZATION", "缺少请求头 Authorization")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise unauthorized(
            "INVALID_AUTHORIZATION", "Authorization 必须使用 Bearer 格式"
        )
    token = authorization[len(prefix) :].strip()
    if not token:
        raise unauthorized("INVALID_AUTHORIZATION", "Bearer token 不能为空")
    return token


def _ensure_channel(channel_code: str) -> None:
    row = fetch_one(
        """
        SELECT channel_code
        FROM dim_channel
        WHERE channel_code = %s
          AND channel_status = 'active'
          AND yn = 1
        """,
        (channel_code,),
    )
    if row is None:
        raise forbidden("CHANNEL_NOT_AVAILABLE", "渠道不存在或不可用")


def _ensure_employee(employee_no: str) -> dict[str, Any]:
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
