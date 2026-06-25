"""Business flow integration tests."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from conftest import (
    ApiClient,
    create_account,
    create_customer,
    insert_collateral,
    insert_contract_document,
    make_first_bill_overdue,
    prepare_wealth_open_period,
    require_seed,
)
from fastapi.testclient import TestClient

from app.database import db_cursor


def test_foundation_catalog_endpoints(api: ApiClient) -> None:
    endpoints = [
        "/api/v1/branches",
        "/api/v1/channels",
        "/api/v1/currencies",
        "/api/v1/risk-levels",
        "/api/v1/account-products",
        "/api/v1/service-products",
        "/api/v1/employees",
    ]
    for endpoint in endpoints:
        data = api.get_ok(endpoint)
        assert "list" in data
        assert len(data["list"]) > 0


def test_customer_lifecycle_idempotency_scope_and_profile_tables(
    api: ApiClient, client: TestClient
) -> None:
    customer_no = create_customer(api)
    customer = require_seed("SELECT id FROM customer WHERE customer_no = %s", (customer_no,))

    replay_payload = {
        "request_no": api.next_no("CONTACT"),
        "contact_type": "mobile",
        "contact_value": api.next_no("138"),
        "is_primary": True,
        "contact_name": "接口测试",
    }
    first = api.post_ok(
        f"/api/v1/customers/{customer_no}/contacts",
        replay_payload,
        token=customer_no,
    )
    second = api.post_ok(
        f"/api/v1/customers/{customer_no}/contacts",
        replay_payload,
        token=customer_no,
    )
    assert second == first
    mismatch = client.post(
        f"/api/v1/customers/{customer_no}/contacts",
        headers=api.headers(token=customer_no),
        json={**replay_payload, "contact_value": api.next_no("139")},
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "IDEMPOTENCY_PAYLOAD_MISMATCH"

    api.patch_ok(
        f"/api/v1/customers/{customer_no}",
        {
            "request_no": api.next_no("UPD"),
            "customer_name": "接口测试客户已更新",
            "branch_code": api.seed["branch_code"],
        },
        token=customer_no,
    )
    api.post_ok(
        f"/api/v1/customers/{customer_no}/identities",
        {
            "request_no": api.next_no("ID"),
            "identity_type": "id_card",
            "identity_no": api.next_no("IDNO"),
            "legal_name": "接口测试客户已更新",
            "identity_valid_from": "2020-01-01",
            "identity_valid_to": "2030-01-01",
        },
        token=customer_no,
    )
    api.post_ok(
        f"/api/v1/customers/{customer_no}/devices",
        {
            "request_no": api.next_no("DEV"),
            "device_no": api.next_no("DEVICE"),
            "device_type": "ios",
            "device_fingerprint": api.next_no("FINGER"),
            "push_token": api.next_no("PUSH"),
            "device_name": "iPhone",
        },
        token=customer_no,
    )
    api.post_ok(
        f"/api/v1/customers/{customer_no}/kyc",
        {
            "request_no": api.next_no("KYC"),
            "occupation": "engineer",
            "industry": "software",
            "annual_income_amount": "300000.00",
            "income_currency_code": "CNY",
            "fund_source": "salary",
            "employment_status": "employed",
        },
        token=customer_no,
    )
    api.post_ok(
        f"/api/v1/customers/{customer_no}/risk-assessments",
        {
            "request_no": api.next_no("RISK"),
            "assessment_type": "standard",
            "assessment_score": 80,
            "valid_from": "2026-01-01",
            "valid_to": "2027-01-01",
        },
        token=customer_no,
    )
    api.post_ok(
        f"/api/v1/customers/{customer_no}/tags",
        {
            "request_no": api.next_no("TAG"),
            "tag_code": require_seed("SELECT tag_code FROM customer_tag WHERE yn = 1 LIMIT 1")["tag_code"],
            "source_type": "manual",
        },
        token=customer_no,
    )

    enterprise_no = create_customer(api, customer_type="enterprise")
    api.post_ok(
        f"/api/v1/customers/{enterprise_no}/beneficial-owners",
        {
            "request_no": api.next_no("BO"),
            "owner_type": "natural_person",
            "owner_name": "企业受益人",
            "identity_type": "id_card",
            "identity_no": api.next_no("BOID"),
            "ownership_ratio": "60.00",
            "control_description": "major shareholder",
            "authorization_valid_from": "2026-01-01",
            "authorization_valid_to": "2027-01-01",
        },
        token=enterprise_no,
    )

    profile = api.get_ok(f"/api/v1/customers/{customer_no}", token=customer_no)
    assert profile["customer_profile"]["customer_name"] == "接口测试客户已更新"
    history = api.get_ok(
        f"/api/v1/customers/{customer_no}/status-history",
        token=customer_no,
    )
    assert history["list"]

    other_customer_no = create_customer(api)
    forbidden = client.get(
        f"/api/v1/customers/{customer_no}",
        headers=api.headers(token=other_customer_no),
    )
    assert forbidden.status_code == 403
    assert require_seed("SELECT COUNT(*) AS total FROM customer_identity WHERE customer_id = %s", (customer["id"],))["total"] == 1
    assert require_seed("SELECT COUNT(*) AS total FROM customer_kyc WHERE customer_id = %s", (customer["id"],))["total"] == 1


def test_account_transaction_freeze_and_reconciliation_flow(api: ApiClient) -> None:
    customer_no = create_customer(api)
    account_no = create_account(api, customer_no, open_amount="10000.00")

    card = api.post_ok(
        f"/api/v1/accounts/{account_no}/cards",
        {"request_no": api.next_no("CARD"), "card_type": "debit", "card_level": "standard"},
        token=customer_no,
    )
    assert card["card_status"] == "active"
    assert api.get_ok(f"/api/v1/accounts/{account_no}", token=customer_no)["account_status"] == "active"
    assert api.get_ok(f"/api/v1/customers/{customer_no}/accounts", token=customer_no)["list"]

    status_account_no = create_account(api, customer_no, open_amount="100.00")
    status_change = api.post_ok(
        f"/api/v1/accounts/{status_account_no}/status-changes",
        {
            "request_no": api.next_no("AST"),
            "target_status": "frozen",
            "reason": "接口测试冻结状态",
        },
        token=customer_no,
    )
    assert status_change["current_status"] == "frozen"

    deposit = api.post_ok(
        "/api/v1/transactions",
        {
            "request_no": api.next_no("DEP"),
            "customer_no": customer_no,
            "account_no": account_no,
            "transaction_type": "deposit",
            "amount": "500.00",
            "currency_code": "CNY",
            "related_type": "none",
        },
        token=customer_no,
    )
    assert deposit["transaction_status"] == "success"
    withdrawal = api.post_ok(
        "/api/v1/transactions",
        {
            "request_no": api.next_no("PAY"),
            "customer_no": customer_no,
            "account_no": account_no,
            "transaction_type": "payment",
            "amount": "200.00",
            "currency_code": "CNY",
            "related_type": "none",
        },
        token=customer_no,
    )
    assert withdrawal["transaction_status"] == "success"
    failed = api.post_ok(
        "/api/v1/transactions",
        {
            "request_no": api.next_no("FAIL"),
            "customer_no": customer_no,
            "account_no": account_no,
            "transaction_type": "payment",
            "amount": "99999999.00",
            "currency_code": "CNY",
            "related_type": "none",
        },
        token=customer_no,
    )
    assert failed["transaction_status"] == "failed"

    detail = api.get_ok(f"/api/v1/transactions/{deposit['transaction_no']}", token=customer_no)
    assert detail["transaction_status"] == "success"
    assert detail["reconcile_status"] == "closed"
    assert api.get_ok(f"/api/v1/accounts/{account_no}/transactions", token=customer_no, params={"page_size": 5})["total_count"] >= 3
    assert api.get_ok(f"/api/v1/accounts/{account_no}/ledgers", token=customer_no, params={"page_size": 5})["total_count"] >= 2

    freeze = api.post_ok(
        "/api/v1/fund-freezes",
        {
            "request_no": api.next_no("FRZ"),
            "account_no": account_no,
            "freeze_amount": "100.00",
            "freeze_type": "business",
            "freeze_reason": "接口测试冻结",
            "related_type": "test",
        },
        token=customer_no,
    )
    operation = api.post_ok(
        f"/api/v1/fund-freezes/{freeze['freeze_no']}/operations",
        {
            "request_no": api.next_no("FOP"),
            "operation_type": "unfreeze",
            "amount": "100.00",
            "reason": "接口测试解冻",
        },
        token=customer_no,
    )
    assert operation["freeze_status"] == "released"

    batch = api.post_ok(
        "/api/v1/reconciliation/batches",
        {
            "request_no": api.next_no("BAT"),
            "channel_code": api.seed["channel_code"],
            "reconcile_date": str(date.today()),
        },
    )
    result = api.post_ok(
        "/api/v1/reconciliation/results",
        {
            "request_no": api.next_no("REC"),
            "batch_no": batch["batch_no"],
            "transaction_no": failed["transaction_no"],
            "result_type": "bank_only",
        },
    )
    adjustment = api.post_ok(
        "/api/v1/reconciliation/adjustments",
        {
            "request_no": api.next_no("ADJ"),
            "result_no": result["result_no"],
            "adjustment_amount": "10.00",
            "adjustment_reason": "接口测试调账",
            "adjustment_direction": "credit",
        },
    )
    approved = api.post_ok(
        f"/api/v1/reconciliation/adjustments/{adjustment['adjustment_no']}/approval",
        {
            "request_no": api.next_no("ADJA"),
            "approval_result": "approved",
            "approval_amount": "10.00",
            "approval_comment": "同意",
        },
    )
    assert approved["adjustment_status"] == "approved"
    posted = api.post_ok(
        f"/api/v1/reconciliation/adjustments/{adjustment['adjustment_no']}/post",
        {
            "request_no": api.next_no("ADJP"),
            "account_no": account_no,
            "post_amount": "10.00",
            "post_date": str(date.today()),
        },
        token=customer_no,
    )
    assert posted["adjustment_status"] == "posted"


def test_wealth_purchase_redeem_income_settlement_flow(api: ApiClient) -> None:
    customer_no = create_customer(api)
    account_no = create_account(api, customer_no, open_amount="50000.00")
    product = api.seed["wealth_product"]
    prepare_wealth_open_period(int(product["id"]))

    api.get_ok("/api/v1/wealth/products", params={"currency_code": "CNY"})
    api.get_ok(f"/api/v1/wealth/products/{product['product_code']}")
    api.get_ok(f"/api/v1/wealth/products/{product['product_code']}/navs", params={"page_size": 3})
    purchase_amount = max(Decimal(str(product["min_purchase_amount"])), Decimal("1000.00"))
    purchase = api.post_ok(
        "/api/v1/wealth/orders/purchase",
        {
            "request_no": api.next_no("WOP"),
            "customer_no": customer_no,
            "account_no": account_no,
            "product_code": product["product_code"],
            "purchase_amount": str(purchase_amount),
        },
        token=customer_no,
    )
    cancellable_purchase = api.post_ok(
        "/api/v1/wealth/orders/purchase",
        {
            "request_no": api.next_no("WXP"),
            "customer_no": customer_no,
            "account_no": account_no,
            "product_code": product["product_code"],
            "purchase_amount": "100.00",
        },
        token=customer_no,
    )
    cancelled = api.post_ok(
        f"/api/v1/wealth/orders/{cancellable_purchase['order_no']}/cancel",
        {
            "request_no": api.next_no("WCL"),
            "cancel_reason": "客户撤销",
        },
        token=customer_no,
    )
    assert cancelled["order_status"] == "cancelled"
    confirm = api.post_ok(
        f"/api/v1/wealth/orders/{purchase['order_no']}/confirm",
        {
            "request_no": api.next_no("WOC"),
            "confirmed_amount": str(purchase_amount),
            "confirmed_share": str(purchase_amount),
            "confirmed_nav": "1.000000",
            "confirmed_date": str(date.today()),
        },
        token=customer_no,
    )
    assert confirm["order_status"] == "confirmed"
    position = require_seed(
        """
        SELECT position.*
        FROM wealth_position AS position
        JOIN customer ON customer.id = position.customer_id
        WHERE customer.customer_no = %s
        ORDER BY position.id DESC
        LIMIT 1
        """,
        (customer_no,),
    )
    positions = api.get_ok(f"/api/v1/customers/{customer_no}/wealth/positions", token=customer_no)
    assert positions["list"]

    redeem = api.post_ok(
        "/api/v1/wealth/orders/redeem",
        {
            "request_no": api.next_no("WOR"),
            "customer_no": customer_no,
            "account_no": account_no,
            "position_id": position["id"],
            "redeem_share": "100.00",
        },
        token=customer_no,
    )
    redeem_confirm = api.post_ok(
        f"/api/v1/wealth/orders/{redeem['order_no']}/confirm",
        {
            "request_no": api.next_no("WRC"),
            "confirmed_amount": "100.00",
            "confirmed_share": "100.00",
            "confirmed_nav": "1.000000",
            "confirmed_date": str(date.today()),
        },
        token=customer_no,
    )
    assert redeem_confirm["order_status"] == "confirmed"
    api.get_ok(f"/api/v1/wealth/orders/{redeem['order_no']}", token=customer_no)

    income_no = api.next_no("WIN")
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO wealth_income (
                income_no,
                position_id,
                customer_id,
                account_id,
                product_id,
                income_date,
                currency_code,
                income_type,
                income_amount,
                settled_flag,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'CNY', 'daily_income', 12.34, 0, NOW())
            """,
            (
                income_no,
                position["id"],
                position["customer_id"],
                position["account_id"],
                position["product_id"],
                date.today(),
            ),
        )
    incomes = api.get_ok(f"/api/v1/customers/{customer_no}/wealth/incomes", token=customer_no)
    assert incomes["total_count"] >= 1
    settled = api.post_ok(
        f"/api/v1/wealth/incomes/{income_no}/settle",
        {
            "request_no": api.next_no("WIS"),
            "settle_amount": "12.34",
            "settle_date": str(date.today()),
        },
        token=customer_no,
    )
    assert settled["settled_flag"] == 1


def _run_credit_loan_repayment_overdue_and_fee_reduction_flow(api: ApiClient) -> dict[str, Any]:
    customer_no = create_customer(api)
    account_no = create_account(api, customer_no, open_amount="20000.00")
    loan_product = api.seed["loan_product"]

    api.get_ok("/api/v1/loan/products", params={"currency_code": "CNY"})
    api.get_ok(f"/api/v1/loan/products/{loan_product['product_code']}")
    credit = api.post_ok(
        "/api/v1/credit/applications",
        {
            "request_no": api.next_no("CRA"),
            "customer_no": customer_no,
            "product_code": loan_product["product_code"],
            "apply_limit_amount": "50000.00",
            "materials": [
                {
                    "material_type": "identity",
                    "material_name": "身份证",
                    "file_url": "https://files.example/identity.pdf",
                    "file_hash": api.next_no("HASH"),
                }
            ],
        },
        token=customer_no,
    )
    api.get_ok(f"/api/v1/credit/applications/{credit['credit_application_no']}", token=customer_no)
    approval = api.post_ok(
        f"/api/v1/credit/applications/{credit['credit_application_no']}/approval-records",
        {
            "request_no": api.next_no("CAP"),
            "approval_node": "final",
            "approval_result": "approved",
            "approved_limit_amount": "50000.00",
            "approval_comment": "通过",
        },
    )
    assert approval["application_status"] == "approved"
    limits = api.get_ok(f"/api/v1/customers/{customer_no}/credit-limits", token=customer_no)
    limit_no = limits["list"][0]["limit_no"]

    loan = api.post_ok(
        "/api/v1/loan/applications",
        {
            "request_no": api.next_no("LAP"),
            "customer_no": customer_no,
            "limit_no": limit_no,
            "apply_amount": "12000.00",
            "apply_term_months": 3,
            "repayment_method": loan_product["repayment_method"],
            "loan_purpose": "consume",
            "materials": [
                {
                    "material_type": "income",
                    "material_name": "收入证明",
                    "file_url": "https://files.example/income.pdf",
                    "file_hash": api.next_no("HASH"),
                }
            ],
        },
        token=customer_no,
    )
    api.get_ok(f"/api/v1/loan/applications/{loan['application_no']}", token=customer_no)
    cancellable_loan = api.post_ok(
        "/api/v1/loan/applications",
        {
            "request_no": api.next_no("LAC"),
            "customer_no": customer_no,
            "limit_no": limit_no,
            "apply_amount": str(loan_product["min_amount"]),
            "apply_term_months": 3,
            "repayment_method": loan_product["repayment_method"],
            "loan_purpose": "consume",
            "materials": [],
        },
        token=customer_no,
    )
    cancelled = api.post_ok(
        f"/api/v1/loan/applications/{cancellable_loan['application_no']}/status-changes",
        {
            "request_no": api.next_no("LCS"),
            "target_status": "cancelled",
            "reason": "客户取消",
        },
        token=customer_no,
    )
    assert cancelled["application_status"] == "cancelled"
    loan_approval = api.post_ok(
        f"/api/v1/loan/applications/{loan['application_no']}/approval-records",
        {
            "request_no": api.next_no("LAA"),
            "approval_node": "final",
            "approval_result": "approved",
            "approved_amount": "12000.00",
            "approved_rate": str(loan_product["annual_interest_rate"]),
            "approved_term_months": 3,
            "approval_comment": "同意",
        },
    )
    assert loan_approval["application_status"] == "approved"
    contract_no = str(
        require_seed(
            """
            SELECT contract.contract_no
            FROM loan_contract AS contract
            JOIN loan_application AS application ON application.id = contract.application_id
            WHERE application.application_no = %s
            """,
            (loan["application_no"],),
        )["contract_no"]
    )
    document_no = insert_contract_document(contract_no)
    sign = api.post_ok(
        f"/api/v1/loan/contracts/{contract_no}/sign-records",
        {
            "request_no": api.next_no("SGN"),
            "document_no": document_no,
            "signer_type": "customer",
            "signer_name": "接口测试客户",
            "sign_method": "sms",
            "sign_result": "signed",
        },
        token=customer_no,
    )
    assert sign["contract_status"] == "signed"
    disbursement = api.post_ok(
        f"/api/v1/loan/contracts/{contract_no}/disbursements",
        {
            "request_no": api.next_no("DSB"),
            "account_no": account_no,
            "disbursement_amount": "12000.00",
        },
        token=customer_no,
    )
    assert disbursement["disbursement_status"] == "success"
    schedules = api.get_ok(f"/api/v1/loan/contracts/{contract_no}/repayment-schedules", token=customer_no)
    assert len(schedules["list"]) == 3
    generated = api.post_ok(
        "/api/v1/repayment/bills/generate",
        {
            "request_no": api.next_no("BIL"),
            "contract_no": contract_no,
            "bill_date": str(date.today()),
            "period_start": 1,
            "period_end": 2,
        },
        token=customer_no,
    )
    assert generated["bill_count"] == 2
    bill_no = make_first_bill_overdue(contract_no)
    api.get_ok("/api/v1/repayment/bills", token=customer_no, params={"contract_no": contract_no})
    auth = api.post_ok(
        "/api/v1/repayment/authorizations",
        {
            "request_no": api.next_no("AUT"),
            "customer_no": customer_no,
            "contract_no": contract_no,
            "account_no": account_no,
            "authorization_type": "auto_debit",
            "valid_from": str(date.today()),
            "valid_to": str(date.today() + timedelta(days=365)),
        },
        token=customer_no,
    )
    assert auth["authorization_status"] == "active"
    overdue_refresh = api.post_ok(
        "/api/v1/overdues/refresh",
        {
            "request_no": api.next_no("OVR"),
            "contract_no": contract_no,
            "overdue_date": str(date.today()),
        },
        token=customer_no,
    )
    assert overdue_refresh["overdue_count"] >= 1
    overdues = api.get_ok("/api/v1/overdues", token=customer_no, params={"contract_no": contract_no})
    overdue_no = overdues["list"][0]["overdue_no"]
    reduction = api.post_ok(
        "/api/v1/fee-reductions",
        {
            "request_no": api.next_no("RED"),
            "bill_no": bill_no,
            "reduction_type": "fee",
            "apply_amount": "10.00",
            "reason": "接口测试减免",
        },
        token=customer_no,
    )
    reduction_approval = api.post_ok(
        f"/api/v1/fee-reductions/{reduction['reduction_no']}/approval",
        {
            "request_no": api.next_no("RAP"),
            "approval_result": "approved",
            "approved_amount": "10.00",
            "reason": "同意",
        },
    )
    assert reduction_approval["reduction_status"] == "approved"
    repayment = api.post_ok(
        "/api/v1/repayments",
        {
            "request_no": api.next_no("RPM"),
            "bill_no": bill_no,
            "account_no": account_no,
            "repayment_amount": "100.00",
            "repayment_type": "normal",
        },
        token=customer_no,
    )
    assert repayment["repayment_status"] == "success"
    api.get_ok(f"/api/v1/repayments/{repayment['repayment_no']}", token=customer_no)
    api.get_ok(f"/api/v1/loan/contracts/{contract_no}", token=customer_no)
    return {
        "customer_no": customer_no,
        "account_no": account_no,
        "contract_no": contract_no,
        "application_no": loan["application_no"],
        "overdue_no": overdue_no,
        "bill_no": bill_no,
    }


def test_credit_loan_repayment_overdue_and_fee_reduction_flow(api: ApiClient) -> None:
    context = _run_credit_loan_repayment_overdue_and_fee_reduction_flow(api)
    assert context["contract_no"]


def test_risk_aml_and_manual_review_flow(api: ApiClient) -> None:
    customer_no = create_customer(api)
    account_no = create_account(api, customer_no, open_amount="10000.00")
    transaction = api.post_ok(
        "/api/v1/transactions",
        {
            "request_no": api.next_no("TXN"),
            "customer_no": customer_no,
            "account_no": account_no,
            "transaction_type": "deposit",
            "amount": "800.00",
            "currency_code": "CNY",
            "related_type": "none",
        },
        token=customer_no,
    )
    event = api.post_ok(
        "/api/v1/risk/events",
        {
            "request_no": api.next_no("RKE"),
            "customer_no": customer_no,
            "related_type": "account_transaction",
            "related_id": require_seed(
                "SELECT id FROM account_transaction WHERE transaction_no = %s",
                (transaction["transaction_no"],),
            )["id"],
            "event_type": api.seed["risk_event_type"],
            "risk_score": 90,
        },
        token=customer_no,
    )
    event_detail = api.get_ok(f"/api/v1/risk/events/{event['event_no']}", token=customer_no)
    task = event_detail["manual_review_task"]
    if task is not None:
        review = api.post_ok(
            f"/api/v1/manual-review/tasks/{task['task_no']}/complete",
            {
                "request_no": api.next_no("MRT"),
                "review_result": "approved",
                "review_comment": "人工复核通过",
            },
        )
        assert review["task_status"] == "approved"

    blacklist = api.post_ok(
        "/api/v1/blacklists",
        {
            "request_no": api.next_no("BLK"),
            "subject_type": "customer",
            "subject_value": customer_no,
            "risk_level_code": api.seed["risk_level_code"],
            "reason": "接口测试黑名单",
            "effective_from": str(date.today()),
            "effective_to": str(date.today() + timedelta(days=30)),
        },
    )
    assert blacklist["blacklist_status"] == "active"
    assert api.get_ok("/api/v1/blacklists", params={"customer_no": customer_no})["total_count"] >= 1

    aml = api.post_ok(
        "/api/v1/aml/cases",
        {
            "request_no": api.next_no("AML"),
            "customer_no": customer_no,
            "risk_event_no": event["event_no"],
            "case_type": "suspicious_transaction",
            "suspicious_reason": "接口测试可疑交易",
            "transactions": [
                {
                    "transaction_no": transaction["transaction_no"],
                    "included_flag": 1,
                    "include_reason": "可疑交易明细",
                }
            ],
        },
        token=customer_no,
    )
    report = api.post_ok(
        f"/api/v1/aml/cases/{aml['case_no']}/review-results",
        {
            "request_no": api.next_no("AMR"),
            "review_result": "confirmed",
            "report_flag": True,
            "review_comment": "确认报送",
        },
    )
    assert report["report_no"]
    api.get_ok(f"/api/v1/aml/reports/{report['report_no']}")


def test_collection_disposal_flow(api: ApiClient) -> None:
    context = _run_credit_loan_repayment_overdue_and_fee_reduction_flow(api)
    collateral_no = insert_collateral(str(context["application_no"]), str(context["contract_no"]))
    case = api.post_ok(
        "/api/v1/collection/cases",
        {
            "request_no": api.next_no("COL"),
            "overdue_no": context["overdue_no"],
            "collector_no": api.seed["collector_no"],
            "collection_stage": "early",
        },
    )
    case_no = case["case_no"]
    api.get_ok(f"/api/v1/collection/cases/{case_no}")
    action = api.post_ok(
        f"/api/v1/collection/cases/{case_no}/actions",
        {"request_no": api.next_no("ACT"), "action_type": "phone_call", "action_result": "connected"},
    )
    assert action["action_status"] == "completed"
    contact = api.post_ok(
        f"/api/v1/collection/cases/{case_no}/contacts",
        {
            "request_no": api.next_no("CCR"),
            "contact_method": "phone",
            "contact_result": "promise",
            "contact_content": "客户承诺还款",
        },
    )
    assert contact["contact_result"] == "promise"
    promise = api.post_ok(
        f"/api/v1/collection/cases/{case_no}/promises",
        {
            "request_no": api.next_no("PRM"),
            "promise_amount": "100.00",
            "promise_date": str(date.today() + timedelta(days=3)),
        },
    )
    assert promise["promise_status"] == "active"
    repayment = api.post_ok(
        f"/api/v1/collection/cases/{case_no}/repayments",
        {
            "request_no": api.next_no("CRP"),
            "bill_no": context["bill_no"],
            "account_no": context["account_no"],
            "repayment_amount": "50.00",
            "promise_no": promise["promise_no"],
        },
        token=context["customer_no"],
    )
    assert repayment["repayment_status"] == "success"
    legal = api.post_ok(
        f"/api/v1/collection/cases/{case_no}/legal-cases",
        {"request_no": api.next_no("LEG"), "legal_type": "civil", "claim_amount": "1000.00"},
    )
    assert legal["legal_status"] == "submitted"
    write_off = api.post_ok(
        f"/api/v1/collection/cases/{case_no}/write-offs",
        {"request_no": api.next_no("WOF"), "apply_amount": "100.00"},
    )
    api.post_ok(
        f"/api/v1/collection/write-offs/{write_off['write_off_no']}/approval",
        {
            "request_no": api.next_no("WOA"),
            "approval_result": "approved",
            "approved_amount": "100.00",
            "approval_comment": "同意",
        },
    )
    posted = api.post_ok(
        f"/api/v1/collection/write-offs/{write_off['write_off_no']}/post",
        {"request_no": api.next_no("WOP"), "post_date": str(date.today())},
    )
    assert posted["write_off_status"] == "posted"
    restructure = api.post_ok(
        f"/api/v1/collection/cases/{case_no}/restructures",
        {
            "request_no": api.next_no("RST"),
            "restructure_principal_amount": "500.00",
            "new_term_months": 6,
            "new_interest_rate": "0.050000",
            "restructure_type": "extension",
        },
    )
    api.post_ok(
        f"/api/v1/collection/restructures/{restructure['restructure_no']}/approval",
        {
            "request_no": api.next_no("RSA"),
            "approval_result": "approved",
            "approval_comment": "同意",
        },
    )
    effective = api.post_ok(
        f"/api/v1/collection/restructures/{restructure['restructure_no']}/effective",
        {"request_no": api.next_no("RSE"), "effective_date": str(date.today())},
    )
    assert effective["restructure_status"] == "effective"
    disposal = api.post_ok(
        f"/api/v1/collection/cases/{case_no}/collateral-disposals",
        {
            "request_no": api.next_no("DSP"),
            "collateral_no": collateral_no,
            "disposal_amount": "1000.00",
            "received_amount": "800.00",
            "account_no": context["account_no"],
            "disposal_method": "auction",
        },
        token=context["customer_no"],
    )
    assert disposal["collateral_status"] == "disposed"
    api.get_ok("/api/v1/collection/performance-daily", params={"page_size": 2})


def test_operations_workflow_notification_support_and_metrics_flow(api: ApiClient) -> None:
    customer_no = create_customer(api)
    notification = api.post_ok(
        "/api/v1/notifications",
        {
            "request_no": api.next_no("MSG"),
            "customer_no": customer_no,
            "message_type": "service",
            "send_channel": "site_message",
            "related_type": "none",
            "message_title": "接口测试通知",
            "message_content": "通知内容",
        },
        token=customer_no,
    )
    assert notification["send_status"] == "success"
    assert api.get_ok(f"/api/v1/customers/{customer_no}/notifications", token=customer_no)["total_count"] >= 1

    ticket = api.post_ok(
        "/api/v1/support/tickets",
        {
            "request_no": api.next_no("TKT"),
            "customer_no": customer_no,
            "ticket_type": "consult",
            "ticket_title": "接口测试工单",
            "ticket_content": "工单内容",
            "related_type": "none",
        },
        token=customer_no,
    )
    ticket_row = require_seed("SELECT id FROM support_ticket WHERE ticket_no = %s", (ticket["ticket_no"],))
    api.get_ok(f"/api/v1/support/tickets/{ticket['ticket_no']}", token=customer_no)
    feedback = api.post_ok(
        f"/api/v1/support/tickets/{ticket['ticket_no']}/feedback",
        {
            "request_no": api.next_no("FBK"),
            "confirm_status": "confirmed",
            "satisfaction_score": 5,
            "feedback_content": "已解决",
        },
        token=customer_no,
    )
    assert feedback["confirm_status"] == "confirmed"

    workflow = api.post_ok(
        "/api/v1/workflow/instances",
        {
            "request_no": api.next_no("WFI"),
            "workflow_type": "support_ticket",
            "related_type": "support_ticket",
            "related_id": ticket_row["id"],
            "initiator_type": "customer",
            "initiator_no": customer_no,
        },
    )
    detail = api.get_ok(f"/api/v1/workflow/instances/{workflow['instance_no']}")
    assert detail["tasks"]
    completed = api.post_ok(
        f"/api/v1/workflow/tasks/{detail['tasks'][0]['task_no']}/complete",
        {
            "request_no": api.next_no("WFT"),
            "task_result": "approved",
            "task_comment": "处理完成",
        },
    )
    assert completed["instance_status"] == "approved"
    metrics = api.get_ok("/api/v1/metrics/daily", params={"page_size": 2})
    assert "list" in metrics


def test_readme_route_set_has_business_flow_coverage() -> None:
    exercised_paths = {
        "/api/v1/branches",
        "/api/v1/channels",
        "/api/v1/currencies",
        "/api/v1/risk-levels",
        "/api/v1/account-products",
        "/api/v1/service-products",
        "/api/v1/employees",
        "/api/v1/customers",
        "/api/v1/customers/{customer_no}",
        "/api/v1/customers/{customer_no}/identities",
        "/api/v1/customers/{customer_no}/contacts",
        "/api/v1/customers/{customer_no}/devices",
        "/api/v1/customers/{customer_no}/kyc",
        "/api/v1/customers/{customer_no}/beneficial-owners",
        "/api/v1/customers/{customer_no}/risk-assessments",
        "/api/v1/customers/{customer_no}/tags",
        "/api/v1/customers/{customer_no}/status-history",
        "/api/v1/accounts",
        "/api/v1/accounts/{account_no}",
        "/api/v1/customers/{customer_no}/accounts",
        "/api/v1/accounts/{account_no}/cards",
        "/api/v1/accounts/{account_no}/status-changes",
        "/api/v1/transactions",
        "/api/v1/transactions/{transaction_no}",
        "/api/v1/accounts/{account_no}/transactions",
        "/api/v1/accounts/{account_no}/ledgers",
        "/api/v1/fund-freezes",
        "/api/v1/fund-freezes/{freeze_no}/operations",
        "/api/v1/reconciliation/batches",
        "/api/v1/reconciliation/results",
        "/api/v1/reconciliation/adjustments",
        "/api/v1/reconciliation/adjustments/{adjustment_no}/approval",
        "/api/v1/reconciliation/adjustments/{adjustment_no}/post",
        "/api/v1/wealth/products",
        "/api/v1/wealth/products/{product_code}",
        "/api/v1/wealth/products/{product_code}/navs",
        "/api/v1/wealth/orders/purchase",
        "/api/v1/wealth/orders/redeem",
        "/api/v1/wealth/orders/{order_no}/confirm",
        "/api/v1/wealth/orders/{order_no}/cancel",
        "/api/v1/wealth/orders/{order_no}",
        "/api/v1/customers/{customer_no}/wealth/positions",
        "/api/v1/customers/{customer_no}/wealth/incomes",
        "/api/v1/wealth/incomes/{income_no}/settle",
        "/api/v1/loan/products",
        "/api/v1/loan/products/{product_code}",
        "/api/v1/credit/applications",
        "/api/v1/credit/applications/{credit_application_no}",
        "/api/v1/credit/applications/{credit_application_no}/approval-records",
        "/api/v1/customers/{customer_no}/credit-limits",
        "/api/v1/loan/applications",
        "/api/v1/loan/applications/{application_no}",
        "/api/v1/loan/applications/{application_no}/status-changes",
        "/api/v1/loan/applications/{application_no}/approval-records",
        "/api/v1/loan/contracts/{contract_no}/sign-records",
        "/api/v1/loan/contracts/{contract_no}/disbursements",
        "/api/v1/loan/contracts/{contract_no}",
        "/api/v1/loan/contracts/{contract_no}/repayment-schedules",
        "/api/v1/repayment/bills/generate",
        "/api/v1/repayment/bills",
        "/api/v1/repayment/authorizations",
        "/api/v1/repayments",
        "/api/v1/repayments/{repayment_no}",
        "/api/v1/overdues",
        "/api/v1/overdues/refresh",
        "/api/v1/fee-reductions",
        "/api/v1/fee-reductions/{reduction_no}/approval",
        "/api/v1/risk/events",
        "/api/v1/risk/events/{event_no}",
        "/api/v1/manual-review/tasks/{task_no}/complete",
        "/api/v1/blacklists",
        "/api/v1/aml/cases",
        "/api/v1/aml/cases/{case_no}/review-results",
        "/api/v1/aml/reports/{report_no}",
        "/api/v1/collection/cases",
        "/api/v1/collection/cases/{case_no}",
        "/api/v1/collection/cases/{case_no}/actions",
        "/api/v1/collection/cases/{case_no}/contacts",
        "/api/v1/collection/cases/{case_no}/promises",
        "/api/v1/collection/cases/{case_no}/repayments",
        "/api/v1/collection/cases/{case_no}/legal-cases",
        "/api/v1/collection/cases/{case_no}/write-offs",
        "/api/v1/collection/write-offs/{write_off_no}/approval",
        "/api/v1/collection/write-offs/{write_off_no}/post",
        "/api/v1/collection/cases/{case_no}/restructures",
        "/api/v1/collection/restructures/{restructure_no}/approval",
        "/api/v1/collection/restructures/{restructure_no}/effective",
        "/api/v1/collection/cases/{case_no}/collateral-disposals",
        "/api/v1/collection/performance-daily",
        "/api/v1/workflow/instances",
        "/api/v1/workflow/instances/{instance_no}",
        "/api/v1/workflow/tasks/{task_no}/complete",
        "/api/v1/notifications",
        "/api/v1/customers/{customer_no}/notifications",
        "/api/v1/support/tickets",
        "/api/v1/support/tickets/{ticket_no}",
        "/api/v1/support/tickets/{ticket_no}/feedback",
        "/api/v1/metrics/daily",
    }
    from tests.test_api_route_coverage import IMPLEMENTED_ROUTES

    missing = {path for _, path in IMPLEMENTED_ROUTES} - exercised_paths
    assert missing == set()
