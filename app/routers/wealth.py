"""Wealth product, order, position and income APIs."""

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
    ensure_account_by_no,
    ensure_channel,
    ensure_customer_by_no,
    fetch_account_for_update,
    insert_success_transaction,
    release_fund_freeze,
)
from ..utils import (
    count_total,
    format_date,
    local_now,
    make_no,
    offset_limit,
    serialize_row,
    serialize_rows,
)

router = APIRouter(prefix="/api/v1", tags=["wealth"])


class WealthPurchaseRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    customer_no: str = Field(description="客户号，对应 customer.customer_no")
    account_no: str = Field(description="账户号，对应 bank_account.account_no")
    product_code: str = Field(description="产品编码")
    purchase_amount: Decimal = Field(gt=0, description="申购金额，必须大于 0")


class WealthRedeemRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    customer_no: str = Field(description="客户号，对应 customer.customer_no")
    account_no: str = Field(description="账户号，对应 bank_account.account_no")
    position_id: int = Field(description="理财持仓 ID")
    redeem_share: Decimal = Field(gt=0, description="赎回份额，必须大于 0")


class WealthOrderConfirmRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    confirmed_amount: Decimal = Field(ge=0, description="确认金额，必须大于或等于 0")
    confirmed_share: Decimal = Field(ge=0, description="确认份额，必须大于或等于 0")
    confirmed_nav: Decimal = Field(gt=0, description="确认净值，必须大于 0")
    confirmed_date: date = Field(description="确认日期，格式 YYYY-MM-DD")


class WealthOrderCancelRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    cancel_reason: str = Field(description="撤销原因")


class WealthIncomeSettleRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    settle_amount: Decimal = Field(gt=0, description="结转金额，必须大于 0")
    settle_date: date = Field(description="结转日期，格式 YYYY-MM-DD")


@router.get("/wealth/products", summary="查询可售理财产品")
def list_wealth_products(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    risk_level_code: str | None = Query(description="风险等级编码", default=None),
    currency_code: str | None = Query(
        description="币种编码，对应 dim_currency.currency_code", default=None
    ),
    product_status: str | None = Query(description="产品状态", default=None),
) -> dict[str, object]:
    where: list[str] = []
    params: list[object] = []
    if risk_level_code:
        where.append("risk.risk_level_code = %s")
        params.append(risk_level_code)
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
            product.product_name,
            risk.risk_level_code AS risk_level,
            product.expected_yield_rate,
            product.product_status AS open_status
        FROM wealth_product AS product
        JOIN dim_risk_level AS risk ON risk.id = product.risk_level_id
        {where_sql}
        ORDER BY product.product_code
        """,
        tuple(params),
    )
    return ok({"list": serialize_rows(rows)}, ctx.request_id)


@router.get("/wealth/products/{product_code}", summary="查询理财产品详情")
def get_wealth_product(
    product_code: Annotated[str, Path(description="产品编码")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    product = _wealth_product_by_code(product_code)
    open_periods = fetch_all(
        """
        SELECT *
        FROM wealth_open_period
        WHERE product_id = %s
        ORDER BY period_no
        """,
        (product["id"],),
    )
    settlement_rule = fetch_one(
        "SELECT * FROM wealth_settlement_rule WHERE product_id = %s",
        (product["id"],),
    )
    latest_nav = fetch_one(
        """
        SELECT *
        FROM wealth_nav
        WHERE product_id = %s
        ORDER BY nav_date DESC
        LIMIT 1
        """,
        (product["id"],),
    )
    notices = fetch_all(
        """
        SELECT *
        FROM wealth_product_notice
        WHERE product_id = %s
        ORDER BY published_at DESC
        LIMIT 20
        """,
        (product["id"],),
    )
    return ok(
        {
            "product_detail": serialize_row(product),
            "open_periods": serialize_rows(open_periods),
            "settlement_rule": serialize_row(settlement_rule)
            if settlement_rule
            else None,
            "latest_nav": serialize_row(latest_nav) if latest_nav else None,
            "notices": serialize_rows(notices),
        },
        ctx.request_id,
    )


@router.get("/wealth/products/{product_code}/navs", summary="查询理财净值")
def list_wealth_navs(
    product_code: Annotated[str, Path(description="产品编码")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
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
    product = _wealth_product_by_code(product_code)
    where = ["product_id = %s"]
    params: list[object] = [product["id"]]
    if start_date:
        where.append("nav_date >= %s")
        params.append(start_date)
    if end_date:
        where.append("nav_date <= %s")
        params.append(end_date)
    offset, limit = offset_limit(page_no, page_size)
    rows = fetch_all(
        f"""
        SELECT nav_date, unit_nav, accumulated_nav
        FROM wealth_nav
        WHERE {" AND ".join(where)}
        ORDER BY nav_date DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )
    total = count_total(
        f"SELECT COUNT(*) AS total FROM wealth_nav WHERE {' AND '.join(where)}",
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


@router.post("/wealth/orders/purchase", summary="发起理财申购")
def create_purchase_order(
    body: Annotated[WealthPurchaseRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "wealth_purchase", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    customer = ensure_customer_by_no(body.customer_no, ctx)
    account = ensure_account_by_no(body.account_no, ctx)
    product = _wealth_product_by_code(body.product_code)
    channel = ensure_channel(ctx.channel_code)
    if account["customer_id"] != customer["id"]:
        raise forbidden("ACCOUNT_CUSTOMER_MISMATCH", "账户不属于请求客户")
    if account["currency_code"] != product["currency_code"]:
        raise bad_request("CURRENCY_MISMATCH", "账户币种与产品币种不一致")
    if product["product_status"] not in {"selling", "active"}:
        raise conflict("WEALTH_PRODUCT_NOT_SELLING", "理财产品不可申购")
    if body.purchase_amount < Decimal(str(product["min_purchase_amount"])):
        raise bad_request("PURCHASE_AMOUNT_TOO_SMALL", "申购金额低于产品起购金额")
    _ensure_open_period(product["id"], "purchase")
    if Decimal(str(account["available_amount"])) < body.purchase_amount:
        raise conflict("INSUFFICIENT_AVAILABLE_AMOUNT", "账户可用余额不足")
    now = local_now()
    order_no = make_no("WOR")
    freeze_no = make_no("FRZ")
    after_frozen = Decimal(str(account["frozen_amount"])) + body.purchase_amount
    after_available = Decimal(str(account["available_amount"])) - body.purchase_amount
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO fund_freeze (
                freeze_no,
                account_id,
                customer_id,
                freeze_type,
                related_type,
                currency_code,
                freeze_amount,
                freeze_status,
                frozen_at,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, 'wealth_purchase', 'wealth_order', %s, %s, 'active', %s, %s, %s)
            """,
            (
                freeze_no,
                account["id"],
                customer["id"],
                account["currency_code"],
                body.purchase_amount,
                now,
                now,
                now,
            ),
        )
        freeze_id = int(cursor.lastrowid)
        cursor.execute(
            """
            INSERT INTO wealth_order (
                order_no,
                customer_id,
                account_id,
                product_id,
                channel_id,
                freeze_id,
                order_type,
                order_status,
                currency_code,
                order_amount,
                submitted_at,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'purchase', 'submitted', %s, %s, %s, %s, %s)
            """,
            (
                order_no,
                customer["id"],
                account["id"],
                product["id"],
                channel["id"],
                freeze_id,
                account["currency_code"],
                body.purchase_amount,
                now,
                now,
                now,
            ),
        )
        order_id = int(cursor.lastrowid)
        cursor.execute(
            "UPDATE fund_freeze SET related_id = %s, updated_at = %s WHERE id = %s",
            (order_id, now, freeze_id),
        )
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
            VALUES (%s, %s, %s, %s, 'wealth_order', %s, 'freeze', %s, %s, %s, %s, 'api', 'wealth_purchase', %s, %s)
            """,
            (
                make_no("FOP"),
                freeze_id,
                account["id"],
                customer["id"],
                order_id,
                account["currency_code"],
                body.purchase_amount,
                account["frozen_amount"],
                after_frozen,
                now,
                now,
            ),
        )
        operation_id = int(cursor.lastrowid)
        cursor.execute(
            "UPDATE bank_account SET frozen_amount = %s, available_amount = %s, updated_at = %s WHERE id = %s",
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
                customer["id"],
                freeze_id,
                operation_id,
                account["currency_code"],
                str(body.purchase_amount),
                str(account["balance_amount"]),
                str(after_frozen),
                str(after_available),
                now,
            ),
        )
    data = {"order_no": order_no, "order_status": "submitted", "freeze_no": freeze_no}
    save_idempotent_result(
        ctx.channel_code, "wealth_purchase", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post("/wealth/orders/redeem", summary="发起理财赎回")
def create_redeem_order(
    body: Annotated[WealthRedeemRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "wealth_redeem", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    customer = ensure_customer_by_no(body.customer_no, ctx)
    account = ensure_account_by_no(body.account_no, ctx)
    position = _position_by_id(body.position_id, ctx)
    product = _wealth_product_by_id(int(position["product_id"]))
    channel = ensure_channel(ctx.channel_code)
    if (
        position["customer_id"] != customer["id"]
        or position["account_id"] != account["id"]
    ):
        raise forbidden("WEALTH_POSITION_SCOPE_FORBIDDEN", "持仓与客户或账户不一致")
    _ensure_open_period(product["id"], "redeem")
    if body.redeem_share > Decimal(str(position["available_share"])):
        raise conflict("INSUFFICIENT_AVAILABLE_SHARE", "持仓可用份额不足")
    arrival_date = _arrival_date(product["id"], local_now().date())
    now = local_now()
    order_no = make_no("WOR")
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO wealth_order (
                order_no,
                customer_id,
                account_id,
                product_id,
                channel_id,
                position_id,
                order_type,
                order_status,
                currency_code,
                order_share,
                submitted_at,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'redeem', 'submitted', %s, %s, %s, %s, %s)
            """,
            (
                order_no,
                customer["id"],
                account["id"],
                product["id"],
                channel["id"],
                position["id"],
                product["currency_code"],
                body.redeem_share,
                now,
                now,
                now,
            ),
        )
        cursor.execute(
            """
            UPDATE wealth_position
            SET available_share = available_share - %s,
                frozen_share = frozen_share + %s,
                updated_at = %s
            WHERE id = %s
            """,
            (body.redeem_share, body.redeem_share, now, position["id"]),
        )
    data = {
        "order_no": order_no,
        "order_status": "submitted",
        "expected_arrival_date": format_date(arrival_date),
    }
    save_idempotent_result(
        ctx.channel_code, "wealth_redeem", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post("/wealth/orders/{order_no}/confirm", summary="确认理财订单")
def confirm_wealth_order(
    order_no: Annotated[str, Path(description="理财订单号")],
    body: Annotated[WealthOrderConfirmRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "wealth_confirm", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    order = _wealth_order_by_no(order_no, ctx)
    if order["order_status"] != "submitted":
        raise conflict("WEALTH_ORDER_STATUS_FORBIDDEN", "理财订单状态不允许确认")
    account = ensure_account_by_no(_account_no_by_id(int(order["account_id"])), ctx)
    channel = ensure_channel(ctx.channel_code)
    now = local_now()
    with db_cursor() as (_, cursor):
        if order["order_type"] == "purchase":
            if body.confirmed_amount != Decimal(str(order["order_amount"])):
                raise bad_request(
                    "WEALTH_CONFIRM_AMOUNT_MISMATCH", "确认金额必须等于申购订单金额"
                )
            if order["freeze_id"] is None:
                raise conflict(
                    "WEALTH_ORDER_FREEZE_MISSING", "申购订单缺少资金冻结记录"
                )
            locked_account = fetch_account_for_update(cursor, int(account["id"]))
            release_fund_freeze(
                cursor,
                freeze_id=int(order["freeze_id"]),
                account=locked_account,
                amount=body.confirmed_amount,
                operation_type="release",
                reason="wealth_purchase_confirm",
                now=now,
            )
            account = fetch_account_for_update(cursor, int(account["id"]))
            tx = insert_success_transaction(
                cursor,
                account=account,
                channel=channel,
                request_no=body.request_no,
                transaction_type="wealth_purchase",
                amount=body.confirmed_amount,
                direction="debit",
                related_type="wealth_order",
                related_id=int(order["id"]),
                occurred_at=now,
            )
            cursor.execute(
                """
                INSERT INTO wealth_position (
                    customer_id,
                    account_id,
                    product_id,
                    currency_code,
                    holding_share,
                    available_share,
                    cost_amount,
                    market_value_amount,
                    last_nav,
                    last_valuation_date,
                    position_status,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, %s)
                ON DUPLICATE KEY UPDATE
                    holding_share = holding_share + VALUES(holding_share),
                    available_share = available_share + VALUES(available_share),
                    cost_amount = cost_amount + VALUES(cost_amount),
                    market_value_amount = market_value_amount + VALUES(market_value_amount),
                    last_nav = VALUES(last_nav),
                    last_valuation_date = VALUES(last_valuation_date),
                    updated_at = VALUES(updated_at)
                """,
                (
                    order["customer_id"],
                    order["account_id"],
                    order["product_id"],
                    order["currency_code"],
                    body.confirmed_share,
                    body.confirmed_share,
                    body.confirmed_amount,
                    body.confirmed_amount,
                    body.confirmed_nav,
                    body.confirmed_date,
                    now,
                    now,
                ),
            )
            cursor.execute(
                "SELECT id, position_status FROM wealth_position WHERE customer_id = %s AND account_id = %s AND product_id = %s",
                (order["customer_id"], order["account_id"], order["product_id"]),
            )
            position = cursor.fetchone()
        else:
            tx = insert_success_transaction(
                cursor,
                account=account,
                channel=channel,
                request_no=body.request_no,
                transaction_type="wealth_redeem",
                amount=body.confirmed_amount,
                direction="credit",
                related_type="wealth_order",
                related_id=int(order["id"]),
                occurred_at=now,
            )
            cursor.execute(
                """
                UPDATE wealth_position
                SET holding_share = holding_share - %s,
                    frozen_share = frozen_share - %s,
                    market_value_amount = GREATEST(market_value_amount - %s, 0),
                    updated_at = %s
                WHERE id = %s
                """,
                (
                    body.confirmed_share,
                    body.confirmed_share,
                    body.confirmed_amount,
                    now,
                    order["position_id"],
                ),
            )
            cursor.execute(
                "SELECT id, position_status FROM wealth_position WHERE id = %s",
                (order["position_id"],),
            )
            position = cursor.fetchone()
        cursor.execute(
            """
            UPDATE wealth_order
            SET order_status = 'confirmed',
                confirmed_amount = %s,
                confirmed_share = %s,
                confirmed_nav = %s,
                transaction_id = %s,
                position_id = %s,
                confirmed_at = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (
                body.confirmed_amount,
                body.confirmed_share,
                str(body.confirmed_nav),
                tx["transaction_id"],
                position["id"] if position else order["position_id"],
                now,
                now,
                order["id"],
            ),
        )
    data = {
        "order_no": order_no,
        "order_status": "confirmed",
        "position_status": position["position_status"] if position else "active",
        "transaction_no": tx["transaction_no"],
    }
    save_idempotent_result(
        ctx.channel_code, "wealth_confirm", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.post("/wealth/orders/{order_no}/cancel", summary="撤销理财订单")
def cancel_wealth_order(
    order_no: Annotated[str, Path(description="理财订单号")],
    body: Annotated[WealthOrderCancelRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "wealth_cancel", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    order = _wealth_order_by_no(order_no, ctx)
    if order["order_status"] != "submitted":
        raise conflict("WEALTH_ORDER_STATUS_FORBIDDEN", "理财订单状态不允许撤销")
    now = local_now()
    unfreeze_status = "not_required"
    with db_cursor() as (_, cursor):
        if order["order_type"] == "purchase" and order["freeze_id"]:
            locked_account = fetch_account_for_update(cursor, int(order["account_id"]))
            release_fund_freeze(
                cursor,
                freeze_id=int(order["freeze_id"]),
                account=locked_account,
                amount=Decimal(str(order["order_amount"])),
                operation_type="cancel",
                reason="wealth_purchase_cancel",
                now=now,
            )
            unfreeze_status = "released"
        if order["order_type"] == "redeem" and order["position_id"]:
            cursor.execute(
                """
                UPDATE wealth_position
                SET available_share = available_share + %s,
                    frozen_share = GREATEST(frozen_share - %s, 0),
                    updated_at = %s
                WHERE id = %s
                """,
                (order["order_share"], order["order_share"], now, order["position_id"]),
            )
            unfreeze_status = "released"
        cursor.execute(
            """
            UPDATE wealth_order
            SET order_status = 'cancelled',
                cancel_reason = %s,
                cancelled_at = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (body.cancel_reason, now, now, order["id"]),
        )
    data = {
        "order_no": order_no,
        "order_status": "cancelled",
        "unfreeze_status": unfreeze_status,
    }
    save_idempotent_result(
        ctx.channel_code, "wealth_cancel", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)


@router.get("/wealth/orders/{order_no}", summary="查询理财订单详情")
def get_wealth_order(
    order_no: Annotated[str, Path(description="理财订单号")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    order = _wealth_order_by_no(order_no, ctx)
    transaction = (
        fetch_one(
            "SELECT * FROM account_transaction WHERE id = %s",
            (order["transaction_id"],),
        )
        if order["transaction_id"]
        else None
    )
    reconcile = (
        fetch_one(
            "SELECT process_status FROM reconciliation_result WHERE transaction_id = %s ORDER BY id DESC LIMIT 1",
            (order["transaction_id"],),
        )
        if order["transaction_id"]
        else None
    )
    return ok(
        {
            "order_status": order["order_status"],
            "confirmed_share": str(order["confirmed_share"]),
            "transaction": serialize_row(transaction) if transaction else None,
            "reconcile_status": reconcile["process_status"] if reconcile else None,
        },
        ctx.request_id,
    )


@router.get("/customers/{customer_no}/wealth/positions", summary="查询客户理财持仓")
def list_wealth_positions(
    customer_no: Annotated[str, Path(description="客户号，对应 customer.customer_no")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    product_code: str | None = Query(description="产品编码", default=None),
) -> dict[str, object]:
    customer = ensure_customer_by_no(customer_no, ctx)
    where = ["position.customer_id = %s"]
    params: list[object] = [customer["id"]]
    if product_code:
        where.append("product.product_code = %s")
        params.append(product_code)
    rows = fetch_all(
        f"""
        SELECT
            position.*,
            product.product_code,
            product.product_name,
            COALESCE(SUM(income.income_amount), 0) AS income
        FROM wealth_position AS position
        JOIN wealth_product AS product ON product.id = position.product_id
        LEFT JOIN wealth_income AS income ON income.position_id = position.id
        WHERE {" AND ".join(where)}
        GROUP BY position.id, product.product_code, product.product_name
        ORDER BY position.updated_at DESC
        """,
        tuple(params),
    )
    return ok({"list": serialize_rows(rows)}, ctx.request_id)


@router.get("/customers/{customer_no}/wealth/incomes", summary="查询客户理财收益")
def list_wealth_incomes(
    customer_no: Annotated[str, Path(description="客户号，对应 customer.customer_no")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
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
    customer = ensure_customer_by_no(customer_no, ctx)
    where = ["income.customer_id = %s"]
    params: list[object] = [customer["id"]]
    if start_date:
        where.append("income.income_date >= %s")
        params.append(start_date)
    if end_date:
        where.append("income.income_date <= %s")
        params.append(end_date)
    offset, limit = offset_limit(page_no, page_size)
    rows = fetch_all(
        f"""
        SELECT
            income.income_no,
            income.income_date,
            product.product_code,
            product.product_name,
            income.income_amount,
            income.settled_flag
        FROM wealth_income AS income
        JOIN wealth_product AS product ON product.id = income.product_id
        WHERE {" AND ".join(where)}
        ORDER BY income.income_date DESC, income.id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )
    total = count_total(
        f"""
        SELECT COUNT(*) AS total
        FROM wealth_income AS income
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


@router.post("/wealth/incomes/{income_no}/settle", summary="结转理财收益")
def settle_wealth_income(
    income_no: Annotated[str, Path(description="理财收益编号")],
    body: Annotated[WealthIncomeSettleRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "wealth_income_settle", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)
    income = fetch_one("SELECT * FROM wealth_income WHERE income_no = %s", (income_no,))
    if income is None:
        raise not_found("WEALTH_INCOME_NOT_FOUND", "理财收益不存在")
    if income["settled_flag"]:
        raise conflict("WEALTH_INCOME_SETTLED", "理财收益已结转")
    if body.settle_amount != Decimal(str(income["income_amount"])):
        raise bad_request(
            "WEALTH_INCOME_AMOUNT_MISMATCH", "结转金额必须等于待结转收益金额"
        )
    account = ensure_account_by_no(_account_no_by_id(int(income["account_id"])), ctx)
    channel = ensure_channel(ctx.channel_code)
    now = local_now()
    with db_cursor() as (_, cursor):
        tx = insert_success_transaction(
            cursor,
            account=account,
            channel=channel,
            request_no=body.request_no,
            transaction_type="wealth_income_settle",
            amount=body.settle_amount,
            direction="credit",
            related_type="wealth_income",
            related_id=int(income["id"]),
            occurred_at=now,
        )
        cursor.execute(
            """
            UPDATE wealth_income
            SET settled_flag = 1,
                transaction_id = %s,
                ledger_id = %s,
                settled_at = %s
            WHERE id = %s
            """,
            (tx["transaction_id"], tx["ledger_id"], now, income["id"]),
        )
    data = {
        "income_no": income_no,
        "settled_flag": 1,
        "transaction_no": tx["transaction_no"],
    }
    save_idempotent_result(
        ctx.channel_code,
        "wealth_income_settle",
        body.request_no,
        body.model_dump(),
        data,
    )
    return ok(data, ctx.request_id)


def _wealth_product_by_code(product_code: str) -> dict[str, Any]:
    row = fetch_one(
        "SELECT * FROM wealth_product WHERE product_code = %s", (product_code,)
    )
    if row is None:
        raise not_found("WEALTH_PRODUCT_NOT_FOUND", "理财产品不存在")
    return row


def _wealth_product_by_id(product_id: int) -> dict[str, Any]:
    row = fetch_one("SELECT * FROM wealth_product WHERE id = %s", (product_id,))
    if row is None:
        raise not_found("WEALTH_PRODUCT_NOT_FOUND", "理财产品不存在")
    return row


def _wealth_order_by_no(order_no: str, ctx: RequestContext) -> dict[str, Any]:
    row = fetch_one("SELECT * FROM wealth_order WHERE order_no = %s", (order_no,))
    if row is None:
        raise not_found("WEALTH_ORDER_NOT_FOUND", "理财订单不存在")
    if ctx.auth_type == "customer":
        customer = fetch_one(
            "SELECT customer_no FROM customer WHERE id = %s", (row["customer_id"],)
        )
        if customer is None or customer["customer_no"] != ctx.principal_no:
            raise forbidden("CUSTOMER_SCOPE_FORBIDDEN", "客户只能访问本人业务对象")
    return row


def _position_by_id(position_id: int, ctx: RequestContext) -> dict[str, Any]:
    row = fetch_one("SELECT * FROM wealth_position WHERE id = %s", (position_id,))
    if row is None:
        raise not_found("WEALTH_POSITION_NOT_FOUND", "理财持仓不存在")
    if ctx.auth_type == "customer":
        customer = fetch_one(
            "SELECT customer_no FROM customer WHERE id = %s", (row["customer_id"],)
        )
        if customer is None or customer["customer_no"] != ctx.principal_no:
            raise forbidden("CUSTOMER_SCOPE_FORBIDDEN", "客户只能访问本人业务对象")
    return row


def _ensure_open_period(product_id: int, operation: str) -> None:
    now = local_now()
    if operation == "purchase":
        condition = "purchase_start_at <= %s AND purchase_end_at >= %s"
        params = (product_id, now, now)
    else:
        condition = "redeem_start_at <= %s AND redeem_end_at >= %s"
        params = (product_id, now, now)
    row = fetch_one(
        f"""
        SELECT id
        FROM wealth_open_period
        WHERE product_id = %s
          AND period_status = 'open'
          AND {condition}
        LIMIT 1
        """,
        params,
    )
    if row is None:
        raise conflict("WEALTH_OPEN_PERIOD_UNAVAILABLE", "产品当前不在可交易开放期")


def _arrival_date(product_id: int, trade_date: date) -> date:
    row = fetch_one(
        """
        SELECT redeem_arrival_date
        FROM wealth_trade_calendar
        WHERE product_id = %s AND calendar_date >= %s AND trade_flag = 1
        ORDER BY calendar_date
        LIMIT 1
        """,
        (product_id, trade_date),
    )
    return row["redeem_arrival_date"] if row else trade_date


def _account_no_by_id(account_id: int) -> str:
    row = fetch_one("SELECT account_no FROM bank_account WHERE id = %s", (account_id,))
    if row is None:
        raise not_found("ACCOUNT_NOT_FOUND", "账户不存在")
    return str(row["account_no"])
