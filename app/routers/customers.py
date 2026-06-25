"""Customer APIs."""

from __future__ import annotations

from datetime import date
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
from ..utils import format_datetime, local_now, make_no, serialize_row, serialize_rows

router = APIRouter(prefix="/api/v1", tags=["customers"])


class CustomerCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    customer_type: str = Field(description="客户类型")
    customer_name: str = Field(description="客户名称")
    branch_code: str = Field(description="机构编码，对应 dim_branch.branch_code")
    channel_code: str = Field(description="渠道编码，对应 dim_channel.channel_code")
    company_name: str | None = Field(default=None, description="企业名称")
    uniform_social_credit_code: str | None = Field(
        default=None, description="统一社会信用代码"
    )
    registered_capital_amount: Decimal | None = Field(
        default=None, description="注册资本金额"
    )
    registered_capital_currency_code: str | None = Field(
        default=None, description="注册资本币种"
    )
    established_date: date | None = Field(
        default=None, description="成立日期，格式 YYYY-MM-DD"
    )
    registered_address: str | None = Field(default=None, description="注册地址")
    business_scope: str | None = Field(default=None, description="经营范围")
    industry: str | None = Field(default=None, description="所属行业")


class CustomerUpdateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    customer_name: str | None = Field(default=None, description="客户名称")
    branch_code: str | None = Field(
        default=None, description="机构编码，对应 dim_branch.branch_code"
    )


class IdentityUpsertRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    identity_type: str = Field(description="证件类型")
    identity_no: str = Field(description="证件号码")
    legal_name: str = Field(description="证件姓名或法定名称")
    legal_representative: str | None = Field(default=None, description="法定代表人")
    identity_valid_from: date | None = Field(
        default=None, description="证件有效期开始日期"
    )
    identity_valid_to: date | None = Field(
        default=None, description="证件有效期结束日期"
    )


class ContactUpsertRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    contact_type: str = Field(description="联系方式类型")
    contact_value: str = Field(description="联系方式内容")
    is_primary: bool = Field(description="是否默认联系方式")
    contact_name: str | None = Field(default=None, description="联系人姓名")


class DeviceUpsertRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    device_no: str = Field(description="设备编号")
    device_type: str = Field(description="设备类型")
    device_fingerprint: str = Field(description="设备指纹")
    push_token: str | None = Field(default=None, description="推送令牌")
    device_name: str = Field(default="unknown", description="设备名称")
    app_version: str | None = Field(default=None, description="App 版本")
    os_version: str | None = Field(default=None, description="操作系统版本")
    ip_address: str | None = Field(default=None, description="IP 地址")
    geo_location: str | None = Field(default=None, description="地理位置")


class KycUpsertRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    occupation: str = Field(description="职业")
    industry: str = Field(description="所属行业")
    annual_income_amount: Decimal = Field(
        ge=0, description="年收入金额，必须大于或等于 0"
    )
    income_currency_code: str = Field(description="收入币种编码")
    fund_source: str = Field(description="资金来源")
    employment_status: str = Field(description="就业状态")


class BeneficialOwnerUpsertRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    owner_type: str = Field(description="受益人类型")
    owner_name: str = Field(description="受益人姓名")
    identity_type: str = Field(description="证件类型")
    identity_no: str = Field(description="证件号码")
    ownership_ratio: Decimal = Field(
        ge=0, le=100, description="持股或受益比例，范围 0 到 100"
    )
    control_description: str = Field(description="控制关系说明")
    authorization_valid_from: date | None = Field(
        default=None, description="授权有效期开始日期"
    )
    authorization_valid_to: date | None = Field(
        default=None, description="授权有效期结束日期"
    )
    mobile: str | None = Field(default=None, description="手机号")
    email: str | None = Field(default=None, description="电子邮箱")


class RiskAssessmentCreateRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    assessment_type: str = Field(description="测评类型")
    assessment_score: int = Field(ge=0, description="测评分数")
    valid_from: date = Field(description="有效期开始日期")
    valid_to: date = Field(description="有效期结束日期")
    adjust_reason: str | None = Field(default=None, description="调整原因")


class CustomerTagUpsertRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    tag_code: str = Field(description="标签编码")
    source_type: str = Field(description="来源类型")
    source_id: int | None = Field(default=None, description="来源对象 ID")
    source_ref: str | None = Field(default=None, description="来源业务编号")


@router.post("/customers", summary="创建个人或企业客户")
def create_customer(
    body: Annotated[CustomerCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "customer_create", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    if ctx.channel_code != body.channel_code:
        raise bad_request("CHANNEL_MISMATCH", "请求渠道与业务渠道不一致")
    branch = _ensure_branch(body.branch_code)
    channel = _ensure_channel(body.channel_code)
    risk_level = _default_customer_risk_level()
    now = local_now()
    customer_no = make_no("CUS")
    enterprise_payload = _validate_enterprise_payload(body)
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO customer (
                customer_no,
                customer_type,
                customer_name,
                branch_id,
                register_channel_id,
                risk_level_id,
                customer_status,
                opened_at,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'active', %s, %s, %s)
            """,
            (
                customer_no,
                body.customer_type,
                body.customer_name,
                branch["id"],
                channel["id"],
                risk_level["id"],
                now,
                now,
                now,
            ),
        )
        customer_id = int(cursor.lastrowid)
        cursor.execute(
            """
            INSERT INTO customer_status_history (
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
            VALUES (%s, 1, 'none', 'active', 'customer_create', 'customer', %s, %s, %s)
            """,
            (customer_id, customer_id, now, now),
        )
        if enterprise_payload is not None:
            cursor.execute(
                """
                INSERT INTO enterprise_profile (
                    customer_id,
                    company_name,
                    uniform_social_credit_code,
                    registered_capital_amount,
                    registered_capital_currency_code,
                    established_date,
                    registered_address,
                    business_scope,
                    industry,
                    business_status,
                    compliance_status,
                    created_at,
                    updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    'active', 'pending', %s, %s
                )
                """,
                (
                    customer_id,
                    enterprise_payload["company_name"],
                    enterprise_payload["uniform_social_credit_code"],
                    enterprise_payload["registered_capital_amount"],
                    enterprise_payload["registered_capital_currency_code"],
                    enterprise_payload["established_date"],
                    enterprise_payload["registered_address"],
                    enterprise_payload["business_scope"],
                    enterprise_payload["industry"],
                    now,
                    now,
                ),
            )
    data = {
        "customer_no": customer_no,
        "customer_status": "active",
        "created_at": format_datetime(now),
    }
    save_idempotent_result(
        ctx.channel_code, "customer_create", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.get("/customers/{customer_no}", summary="查询客户档案")
def get_customer(
    customer_no: Annotated[str, Path(description="客户号，对应 customer.customer_no")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    customer = ensure_customer_access(customer_no, ctx)
    kyc = fetch_one(
        """
        SELECT kyc_status, compliance_status
        FROM customer_kyc
        WHERE customer_id = %s
        """,
        (customer["id"],),
    )
    risk = fetch_one(
        """
        SELECT risk_level_code, risk_level_name
        FROM dim_risk_level
        WHERE id = %s
        """,
        (customer["risk_level_id"],),
    )
    profile = serialize_row(customer)
    return ok(
        {
            "customer_profile": profile,
            "customer_status": customer["customer_status"],
            "risk_level": serialize_row(risk) if risk else None,
            "kyc_status": kyc["kyc_status"] if kyc else None,
        },
        ctx.request_id,
    )


@router.patch("/customers/{customer_no}", summary="更新客户基础信息")
def update_customer(
    customer_no: Annotated[str, Path(description="客户号，对应 customer.customer_no")],
    body: Annotated[CustomerUpdateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "customer_update", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    customer = ensure_customer_access(customer_no, ctx)
    updates: list[str] = []
    params: list[object] = []
    if body.customer_name is not None:
        updates.append("customer_name = %s")
        params.append(body.customer_name)
    if body.branch_code is not None:
        branch = _ensure_branch(body.branch_code)
        updates.append("branch_id = %s")
        params.append(branch["id"])
    if not updates:
        raise bad_request("EMPTY_UPDATE", "没有可更新的客户基础字段")
    now = local_now()
    updates.append("updated_at = %s")
    params.append(now)
    params.append(customer["id"])
    with db_cursor() as (_, cursor):
        cursor.execute(
            f"""
            UPDATE customer
            SET {", ".join(updates)}
            WHERE id = %s
            """,
            tuple(params),
        )
    data = {"customer_no": customer_no, "updated_at": format_datetime(now)}
    save_idempotent_result(
        ctx.channel_code, "customer_update", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post("/customers/{customer_no}/identities", summary="提交实名认证信息")
def upsert_identity(
    customer_no: Annotated[str, Path(description="客户号，对应 customer.customer_no")],
    body: Annotated[IdentityUpsertRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "customer_identity", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    customer = ensure_customer_access(customer_no, ctx)
    if body.identity_valid_to and body.identity_valid_to < date.today():
        raise bad_request("IDENTITY_EXPIRED", "证件有效期已过期")
    now = local_now()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            SELECT id
            FROM customer_identity
            WHERE customer_id = %s AND current_flag = 1
            FOR UPDATE
            """,
            (customer["id"],),
        )
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                """
                UPDATE customer_identity
                SET
                    identity_type = %s,
                    identity_no = %s,
                    legal_name = %s,
                    legal_representative = %s,
                    identity_valid_from = %s,
                    identity_valid_to = %s,
                    verification_status = 'verified',
                    verified_at = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (
                    body.identity_type,
                    body.identity_no,
                    body.legal_name,
                    body.legal_representative,
                    body.identity_valid_from,
                    body.identity_valid_to,
                    now,
                    now,
                    existing["id"],
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO customer_identity (
                    customer_id,
                    identity_type,
                    identity_no,
                    legal_name,
                    legal_representative,
                    identity_valid_from,
                    identity_valid_to,
                    verification_status,
                    current_flag,
                    verified_at,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'verified', 1, %s, %s, %s)
                """,
                (
                    customer["id"],
                    body.identity_type,
                    body.identity_no,
                    body.legal_name,
                    body.legal_representative,
                    body.identity_valid_from,
                    body.identity_valid_to,
                    now,
                    now,
                    now,
                ),
            )
    data = {"identity_no": body.identity_no, "verification_status": "verified"}
    save_idempotent_result(
        ctx.channel_code, "customer_identity", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post("/customers/{customer_no}/contacts", summary="新增客户联系方式")
def upsert_contact(
    customer_no: Annotated[str, Path(description="客户号，对应 customer.customer_no")],
    body: Annotated[ContactUpsertRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "customer_contact", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    customer = ensure_customer_access(customer_no, ctx)
    is_primary = "1" if body.is_primary else "0"
    now = local_now()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO customer_contact (
                customer_id,
                contact_type,
                contact_value,
                contact_name,
                is_primary,
                verified_flag,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, 0, %s, %s)
            ON DUPLICATE KEY UPDATE
                contact_value = VALUES(contact_value),
                contact_name = VALUES(contact_name),
                verified_flag = 0,
                updated_at = VALUES(updated_at)
            """,
            (
                customer["id"],
                body.contact_type,
                body.contact_value,
                body.contact_name,
                is_primary,
                now,
                now,
            ),
        )
        cursor.execute(
            """
            SELECT id, verified_flag
            FROM customer_contact
            WHERE customer_id = %s
              AND contact_type = %s
              AND is_primary = %s
            """,
            (customer["id"], body.contact_type, is_primary),
        )
        contact = cursor.fetchone()
    data = {"contact_id": contact["id"], "verified_flag": contact["verified_flag"]}
    save_idempotent_result(
        ctx.channel_code, "customer_contact", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post("/customers/{customer_no}/devices", summary="绑定客户设备")
def upsert_device(
    customer_no: Annotated[str, Path(description="客户号，对应 customer.customer_no")],
    body: Annotated[DeviceUpsertRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "customer_device", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    if body.device_type not in {"ios", "android", "web", "tablet"}:
        raise bad_request("INVALID_DEVICE_TYPE", "设备类型不符合接口约束")
    customer = ensure_customer_access(customer_no, ctx)
    now = local_now()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO customer_device (
                device_no,
                customer_id,
                device_fingerprint,
                device_type,
                device_name,
                app_version,
                os_version,
                push_token,
                ip_address,
                geo_location,
                first_seen_at,
                last_seen_at,
                trusted_flag,
                risk_status,
                created_at,
                updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, 1, 'normal', %s, %s
            )
            ON DUPLICATE KEY UPDATE
                device_no = VALUES(device_no),
                device_type = VALUES(device_type),
                device_name = VALUES(device_name),
                app_version = VALUES(app_version),
                os_version = VALUES(os_version),
                push_token = VALUES(push_token),
                ip_address = VALUES(ip_address),
                geo_location = VALUES(geo_location),
                last_seen_at = VALUES(last_seen_at),
                trusted_flag = 1,
                risk_status = 'normal',
                updated_at = VALUES(updated_at)
            """,
            (
                body.device_no,
                customer["id"],
                body.device_fingerprint,
                body.device_type,
                body.device_name,
                body.app_version,
                body.os_version,
                body.push_token,
                body.ip_address,
                body.geo_location,
                now,
                now,
                now,
                now,
            ),
        )
    data = {
        "device_no": body.device_no,
        "trusted_flag": 1,
        "risk_status": "normal",
    }
    save_idempotent_result(
        ctx.channel_code, "customer_device", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post("/customers/{customer_no}/kyc", summary="提交 KYC 信息")
def upsert_kyc(
    customer_no: Annotated[str, Path(description="客户号，对应 customer.customer_no")],
    body: Annotated[KycUpsertRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "customer_kyc", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    customer = ensure_customer_access(customer_no, ctx)
    _ensure_currency(body.income_currency_code)
    now = local_now()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO customer_kyc (
                customer_id,
                occupation,
                industry,
                annual_income_amount,
                income_currency_code,
                fund_source,
                employment_status,
                kyc_status,
                compliance_status,
                review_result,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'submitted', 'pending', 'pending', %s, %s)
            ON DUPLICATE KEY UPDATE
                occupation = VALUES(occupation),
                industry = VALUES(industry),
                annual_income_amount = VALUES(annual_income_amount),
                income_currency_code = VALUES(income_currency_code),
                fund_source = VALUES(fund_source),
                employment_status = VALUES(employment_status),
                kyc_status = 'submitted',
                compliance_status = 'pending',
                review_result = 'pending',
                updated_at = VALUES(updated_at)
            """,
            (
                customer["id"],
                body.occupation,
                body.industry,
                body.annual_income_amount,
                body.income_currency_code,
                body.fund_source,
                body.employment_status,
                now,
                now,
            ),
        )
        cursor.execute(
            "SELECT id, kyc_status, compliance_status FROM customer_kyc WHERE customer_id = %s",
            (customer["id"],),
        )
        kyc = cursor.fetchone()
    data = {
        "kyc_id": kyc["id"],
        "kyc_status": kyc["kyc_status"],
        "compliance_status": kyc["compliance_status"],
    }
    save_idempotent_result(
        ctx.channel_code, "customer_kyc", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post("/customers/{customer_no}/beneficial-owners", summary="维护企业受益人")
def upsert_beneficial_owner(
    customer_no: Annotated[str, Path(description="客户号，对应 customer.customer_no")],
    body: Annotated[BeneficialOwnerUpsertRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "beneficial_owner", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    customer = ensure_customer_access(customer_no, ctx)
    if customer["customer_type"] != "enterprise":
        raise forbidden("ENTERPRISE_CUSTOMER_REQUIRED", "只有企业客户可维护受益人")
    if (
        body.authorization_valid_from
        and body.authorization_valid_to
        and body.authorization_valid_to < body.authorization_valid_from
    ):
        raise bad_request("INVALID_AUTHORIZATION_PERIOD", "授权有效期不合法")
    now = local_now()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO beneficial_owner (
                customer_id,
                owner_type,
                owner_name,
                identity_type,
                identity_no,
                mobile,
                email,
                ownership_ratio,
                control_description,
                authorization_valid_from,
                authorization_valid_to,
                verification_status,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s)
            ON DUPLICATE KEY UPDATE
                owner_name = VALUES(owner_name),
                mobile = VALUES(mobile),
                email = VALUES(email),
                ownership_ratio = VALUES(ownership_ratio),
                control_description = VALUES(control_description),
                authorization_valid_from = VALUES(authorization_valid_from),
                authorization_valid_to = VALUES(authorization_valid_to),
                verification_status = 'pending',
                updated_at = VALUES(updated_at)
            """,
            (
                customer["id"],
                body.owner_type,
                body.owner_name,
                body.identity_type,
                body.identity_no,
                body.mobile,
                body.email,
                body.ownership_ratio,
                body.control_description,
                body.authorization_valid_from,
                body.authorization_valid_to,
                now,
                now,
            ),
        )
        cursor.execute(
            """
            SELECT id, verification_status
            FROM beneficial_owner
            WHERE customer_id = %s
              AND owner_type = %s
              AND identity_type = %s
              AND identity_no = %s
            """,
            (customer["id"], body.owner_type, body.identity_type, body.identity_no),
        )
        owner = cursor.fetchone()
    data = {
        "beneficial_owner_id": owner["id"],
        "verification_status": owner["verification_status"],
    }
    save_idempotent_result(
        ctx.channel_code, "beneficial_owner", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post("/customers/{customer_no}/risk-assessments", summary="提交客户风险测评")
def create_risk_assessment(
    customer_no: Annotated[str, Path(description="客户号，对应 customer.customer_no")],
    body: Annotated[RiskAssessmentCreateRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "customer_risk_assessment", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    if body.valid_to < body.valid_from:
        raise bad_request("INVALID_ASSESSMENT_PERIOD", "风险测评有效期不合法")
    customer = ensure_customer_access(customer_no, ctx)
    risk_level = _risk_level_by_score(body.assessment_score)
    now = local_now()
    assessment_no = make_no("CRA")
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO customer_risk_assessment (
                assessment_no,
                customer_id,
                risk_level_id,
                assessment_score,
                assessment_type,
                assessment_status,
                valid_from,
                valid_to,
                adjust_reason,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, 'active', %s, %s, %s, %s, %s)
            """,
            (
                assessment_no,
                customer["id"],
                risk_level["id"],
                body.assessment_score,
                body.assessment_type,
                body.valid_from,
                body.valid_to,
                body.adjust_reason,
                now,
                now,
            ),
        )
        cursor.execute(
            """
            UPDATE customer
            SET risk_level_id = %s, updated_at = %s
            WHERE id = %s
            """,
            (risk_level["id"], now, customer["id"]),
        )
    data = {
        "assessment_no": assessment_no,
        "score": body.assessment_score,
        "risk_level": risk_level["risk_level_code"],
    }
    save_idempotent_result(
        ctx.channel_code,
        "customer_risk_assessment",
        body.request_no,
        body.model_dump(),
        data,
    )
    return ok(data, ctx.request_id)


@router.post("/customers/{customer_no}/tags", summary="维护客户标签")
def upsert_customer_tag(
    customer_no: Annotated[str, Path(description="客户号，对应 customer.customer_no")],
    body: Annotated[CustomerTagUpsertRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "customer_tag", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    customer = ensure_customer_access(customer_no, ctx)
    tag = fetch_one(
        "SELECT id, tag_code FROM customer_tag WHERE tag_code = %s AND yn = 1",
        (body.tag_code,),
    )
    if tag is None:
        raise not_found("CUSTOMER_TAG_NOT_FOUND", "客户标签不存在或不可用")
    now = local_now()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO customer_tag_rel (
                customer_id,
                tag_id,
                source_type,
                source_id,
                source_ref,
                effective_from,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                source_id = VALUES(source_id),
                source_ref = VALUES(source_ref),
                effective_from = VALUES(effective_from)
            """,
            (
                customer["id"],
                tag["id"],
                body.source_type,
                body.source_id,
                body.source_ref,
                now.date(),
                now,
            ),
        )
        cursor.execute(
            """
            SELECT id
            FROM customer_tag_rel
            WHERE customer_id = %s AND tag_id = %s AND source_type = %s
            """,
            (customer["id"], tag["id"], body.source_type),
        )
        rel = cursor.fetchone()
    data = {"tag_rel_id": rel["id"], "tag_code": body.tag_code}
    save_idempotent_result(
        ctx.channel_code, "customer_tag", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.get("/customers/{customer_no}/status-history", summary="查询客户状态历史")
def list_customer_status_history(
    customer_no: Annotated[str, Path(description="客户号，对应 customer.customer_no")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    start_date: date | None = Query(
        description="开始日期，格式 YYYY-MM-DD", default=None
    ),
    end_date: date | None = Query(
        description="结束日期，格式 YYYY-MM-DD", default=None
    ),
) -> dict[str, object]:
    customer = ensure_customer_access(customer_no, ctx)
    where = ["customer_id = %s"]
    params: list[object] = [customer["id"]]
    if start_date:
        where.append("changed_at >= %s")
        params.append(start_date)
    if end_date:
        where.append("changed_at < DATE_ADD(%s, INTERVAL 1 DAY)")
        params.append(end_date)
    rows = fetch_all(
        f"""
        SELECT
            change_seq,
            from_status,
            to_status,
            change_reason,
            related_type,
            related_id,
            changed_at
        FROM customer_status_history
        WHERE {" AND ".join(where)}
        ORDER BY change_seq
        """,
        tuple(params),
    )
    return ok({"list": serialize_rows(rows)}, ctx.request_id)


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


def _ensure_currency(currency_code: str) -> None:
    row = fetch_one(
        """
        SELECT currency_code
        FROM dim_currency
        WHERE currency_code = %s AND yn = 1
        """,
        (currency_code,),
    )
    if row is None:
        raise not_found("CURRENCY_NOT_AVAILABLE", "币种不存在或不可用")


def _default_customer_risk_level() -> dict[str, Any]:
    row = fetch_one(
        """
        SELECT *
        FROM dim_risk_level
        WHERE risk_level_type = 'customer' AND yn = 1
        ORDER BY sort_no
        LIMIT 1
        """
    )
    if row is None:
        raise conflict("RISK_LEVEL_MISSING", "缺少可用客户风险等级")
    return row


def _risk_level_by_score(score: int) -> dict[str, Any]:
    row = fetch_one(
        """
        SELECT *
        FROM dim_risk_level
        WHERE risk_level_type = 'customer'
          AND yn = 1
          AND %s BETWEEN risk_score_min AND risk_score_max
        ORDER BY sort_no
        LIMIT 1
        """,
        (score,),
    )
    if row is None:
        raise bad_request("RISK_SCORE_OUT_OF_RANGE", "风险评分不在客户风险等级区间内")
    return row


def _validate_enterprise_payload(
    body: CustomerCreateRequest,
) -> dict[str, object] | None:
    if body.customer_type != "enterprise":
        return None
    required = {
        "company_name": body.company_name,
        "uniform_social_credit_code": body.uniform_social_credit_code,
        "registered_capital_currency_code": body.registered_capital_currency_code,
        "established_date": body.established_date,
        "registered_address": body.registered_address,
        "business_scope": body.business_scope,
        "industry": body.industry,
    }
    missing = [key for key, value in required.items() if value in (None, "")]
    if missing:
        raise bad_request(
            "ENTERPRISE_FIELD_MISSING", f"企业客户缺少字段: {','.join(missing)}"
        )
    if body.registered_capital_currency_code:
        _ensure_currency(body.registered_capital_currency_code)
    return {
        "company_name": body.company_name,
        "uniform_social_credit_code": body.uniform_social_credit_code,
        "registered_capital_amount": body.registered_capital_amount or Decimal("0"),
        "registered_capital_currency_code": body.registered_capital_currency_code,
        "established_date": body.established_date,
        "registered_address": body.registered_address,
        "business_scope": body.business_scope,
        "industry": body.industry,
    }
