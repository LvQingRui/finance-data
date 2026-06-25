"""Foundation configuration APIs."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from ..database import fetch_all
from ..dependencies import RequestContext, get_request_context
from ..response import ok
from ..utils import serialize_rows

router = APIRouter(prefix="/api/v1", tags=["foundation"])


@router.get("/branches", summary="查询可用机构树")
def list_branches(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    branch_status: str | None = Query(description="机构状态", default=None),
    province: str | None = Query(description="省份", default=None),
    city: str | None = Query(description="城市", default=None),
) -> dict[str, object]:
    where = ["branch_code <> 'ALL'"]
    params: list[object] = []
    if branch_status:
        where.append("branch_status = %s")
        params.append(branch_status)
    if province:
        where.append("province = %s")
        params.append(province)
    if city:
        where.append("city = %s")
        params.append(city)
    rows = fetch_all(
        f"""
        SELECT
            id,
            parent_id,
            branch_code,
            branch_name,
            branch_level,
            province,
            city,
            service_phone,
            branch_status
        FROM dim_branch
        WHERE {" AND ".join(where)}
        ORDER BY branch_level, branch_code
        """,
        tuple(params),
    )
    return ok({"list": _build_branch_tree(rows)}, ctx.request_id)


@router.get("/channels", summary="查询可用业务渠道")
def list_channels(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    channel_type: str | None = Query(description="渠道类型", default=None),
    channel_status: str | None = Query(description="渠道状态", default=None),
) -> dict[str, object]:
    where = ["channel_code <> 'ALL'"]
    params: list[object] = []
    if channel_type:
        where.append("channel_type = %s")
        params.append(channel_type)
    if channel_status:
        where.append("channel_status = %s")
        params.append(channel_status)
    rows = fetch_all(
        f"""
        SELECT
            channel_code,
            channel_name,
            channel_type,
            channel_status,
            yn
        FROM dim_channel
        WHERE {" AND ".join(where)}
        ORDER BY channel_code
        """,
        tuple(params),
    )
    return ok({"list": serialize_rows(rows)}, ctx.request_id)


@router.get("/currencies", summary="查询可用币种")
def list_currencies(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    yn: int | None = Query(description="有效标识，1 有效，0 无效", default=None),
) -> dict[str, object]:
    where: list[str] = []
    params: list[object] = []
    if yn is not None:
        where.append("yn = %s")
        params.append(yn)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    rows = fetch_all(
        f"""
        SELECT
            currency_code,
            currency_name,
            symbol,
            precision_scale,
            yn
        FROM dim_currency
        {where_sql}
        ORDER BY currency_code
        """,
        tuple(params),
    )
    return ok({"list": serialize_rows(rows)}, ctx.request_id)


@router.get("/risk-levels", summary="查询风险等级")
def list_risk_levels(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    risk_level_type: str | None = Query(description="风险等级类型", default=None),
) -> dict[str, object]:
    where = ["yn = 1"]
    params: list[object] = []
    if risk_level_type:
        where.append("risk_level_type = %s")
        params.append(risk_level_type)
    rows = fetch_all(
        f"""
        SELECT
            risk_level_code,
            risk_level_name,
            risk_level_type,
            risk_score_min,
            risk_score_max,
            sort_no,
            yn
        FROM dim_risk_level
        WHERE {" AND ".join(where)}
        ORDER BY risk_level_type, sort_no
        """,
        tuple(params),
    )
    return ok({"list": serialize_rows(rows)}, ctx.request_id)


@router.get("/account-products", summary="查询账户产品")
def list_account_products(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    account_type: str | None = Query(description="账户类型", default=None),
    currency_code: str | None = Query(
        description="币种编码，对应 dim_currency.currency_code", default=None
    ),
) -> dict[str, object]:
    where = ["category.yn = 1", "currency.yn = 1"]
    params: list[object] = []
    if account_type:
        where.append("product.account_type = %s")
        params.append(account_type)
    if currency_code:
        where.append("product.currency_code = %s")
        params.append(currency_code)
    rows = fetch_all(
        f"""
        SELECT
            product.product_code,
            product.product_name,
            product.account_type,
            product.currency_code,
            product.min_open_amount,
            product.daily_transfer_limit,
            product.daily_withdraw_limit,
            product.product_status
        FROM account_product AS product
        JOIN dim_product_category AS category ON category.id = product.category_id
        JOIN dim_currency AS currency
            ON currency.currency_code = product.currency_code
        WHERE {" AND ".join(where)}
        ORDER BY product.product_code
        """,
        tuple(params),
    )
    return ok({"list": serialize_rows(rows)}, ctx.request_id)


@router.get("/service-products", summary="查询服务产品")
def list_service_products(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    service_type: str | None = Query(description="服务类型", default=None),
    service_status: str | None = Query(description="服务状态", default=None),
) -> dict[str, object]:
    where = ["category.yn = 1"]
    params: list[object] = []
    if service_type:
        where.append("service.service_type = %s")
        params.append(service_type)
    if service_status:
        where.append("service.service_status = %s")
        params.append(service_status)
    rows = fetch_all(
        f"""
        SELECT
            service.service_code,
            service.service_name,
            service.service_type,
            service.fee_amount,
            service.service_status
        FROM service_product AS service
        JOIN dim_product_category AS category ON category.id = service.category_id
        WHERE {" AND ".join(where)}
        ORDER BY service.service_code
        """,
        tuple(params),
    )
    return ok({"list": serialize_rows(rows)}, ctx.request_id)


@router.get("/employees", summary="查询员工基础信息")
def list_employees(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    employee_role: str | None = Query(description="员工角色", default=None),
    branch_code: str | None = Query(
        description="机构编码，对应 dim_branch.branch_code", default=None
    ),
    employee_status: str | None = Query(description="员工状态", default=None),
) -> dict[str, object]:
    where: list[str] = []
    params: list[object] = []
    if employee_role:
        where.append("employee.employee_role = %s")
        params.append(employee_role)
    if branch_code:
        where.append("branch.branch_code = %s")
        params.append(branch_code)
    if employee_status:
        where.append("employee.employee_status = %s")
        params.append(employee_status)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    rows = fetch_all(
        f"""
        SELECT
            employee.employee_no,
            employee.employee_name,
            branch.branch_code,
            branch.branch_name,
            employee.employee_role,
            employee.permission_codes,
            employee.employee_status
        FROM dim_employee AS employee
        JOIN dim_branch AS branch ON branch.id = employee.branch_id
        {where_sql}
        ORDER BY branch.branch_code, employee.employee_no
        """,
        tuple(params),
    )
    payload = []
    for row in rows:
        item = dict(row)
        item["permission_codes"] = _json_list(item["permission_codes"])
        payload.append(item)
    return ok({"list": serialize_rows(payload)}, ctx.request_id)


def _build_branch_tree(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    nodes: dict[int, dict[str, object]] = {}
    roots: list[dict[str, object]] = []
    for row in rows:
        node = {
            "branch_code": row["branch_code"],
            "branch_name": row["branch_name"],
            "branch_level": row["branch_level"],
            "province": row["province"],
            "city": row["city"],
            "service_phone": row["service_phone"],
            "branch_status": row["branch_status"],
            "children": [],
        }
        nodes[int(str(row["id"]))] = node
    for row in rows:
        node = nodes[int(str(row["id"]))]
        parent_id = row["parent_id"]
        if parent_id is None or int(str(parent_id)) not in nodes:
            roots.append(node)
        else:
            children = nodes[int(str(parent_id))]["children"]
            if isinstance(children, list):
                children.append(node)
    return roots


def _json_list(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        loaded = json.loads(value)
        return loaded if isinstance(loaded, list) else []
    return []
