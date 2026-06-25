"""Shared integration test fixtures."""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.database import db_cursor, fetch_all, fetch_one
from app.idempotency import _RECORDS
from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="session")
def seed() -> dict[str, Any]:
    return {
        "channel_code": require_seed(
            "SELECT channel_code FROM dim_channel WHERE channel_status = 'active' LIMIT 1"
        )["channel_code"],
        "employee_no": require_seed(
            "SELECT employee_no FROM dim_employee WHERE employee_status = 'active' LIMIT 1"
        )["employee_no"],
        "collector_no": require_seed(
            """
            SELECT employee_no
            FROM dim_employee
            WHERE employee_status = 'active' AND employee_role = 'collector'
            LIMIT 1
            """
        )["employee_no"],
        "branch_code": require_seed(
            "SELECT branch_code FROM dim_branch WHERE branch_status = 'active' LIMIT 1"
        )["branch_code"],
        "account_product": require_seed(
            """
            SELECT product_code, currency_code
            FROM account_product
            WHERE product_status = 'active' AND currency_code = 'CNY'
            LIMIT 1
            """
        ),
        "loan_product": require_seed(
            """
            SELECT product_code, min_amount, max_amount, min_term_months,
                   max_term_months, annual_interest_rate, repayment_method
            FROM loan_product
            WHERE product_status = 'active' AND currency_code = 'CNY'
            LIMIT 1
            """
        ),
        "wealth_product": require_seed(
            """
            SELECT id, product_code, min_purchase_amount
            FROM wealth_product
            WHERE product_status IN ('selling', 'active') AND currency_code = 'CNY'
            LIMIT 1
            """
        ),
        "risk_level_code": require_seed(
            """
            SELECT risk_level_code
            FROM dim_risk_level
            WHERE yn = 1 AND risk_level_type = 'event'
            ORDER BY sort_no
            LIMIT 1
            """
        )["risk_level_code"],
        "risk_event_type": require_seed(
            """
            SELECT applicable_event_type
            FROM risk_strategy
            WHERE strategy_status = 'active'
            LIMIT 1
            """
        )["applicable_event_type"],
    }


@pytest.fixture(autouse=True)
def isolated_database() -> Iterator[None]:
    before = table_max_ids()
    _RECORDS.clear()
    try:
        yield
    finally:
        _RECORDS.clear()
        delete_rows_after(before)


@pytest.fixture
def api(client: TestClient, seed: dict[str, Any]) -> ApiClient:
    return ApiClient(client, seed)


class ApiClient:
    def __init__(self, client: TestClient, seed: dict[str, Any]) -> None:
        self.client = client
        self.seed = seed
        self._request_seq = itertools.count(1)

    def headers(
        self,
        *,
        token: str | None = None,
        request_id: str | None = None,
        operator_no: str | None = None,
    ) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token or self.seed['employee_no']}",
            "X-Request-Id": request_id or self.next_no("REQ"),
            "X-Channel-Code": self.seed["channel_code"],
            "X-Operator-No": operator_no or self.seed["employee_no"],
        }

    def get_ok(
        self,
        path: str,
        *,
        token: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = self.client.get(path, headers=self.headers(token=token), params=params)
        return self.assert_ok(response)

    def post_ok(
        self,
        path: str,
        json: dict[str, Any],
        *,
        token: str | None = None,
    ) -> dict[str, Any]:
        response = self.client.post(path, headers=self.headers(token=token), json=json)
        return self.assert_ok(response)

    def patch_ok(
        self,
        path: str,
        json: dict[str, Any],
        *,
        token: str | None = None,
    ) -> dict[str, Any]:
        response = self.client.patch(path, headers=self.headers(token=token), json=json)
        return self.assert_ok(response)

    def assert_ok(self, response: Any) -> dict[str, Any]:
        body = response.json()
        assert response.status_code == 200, body
        assert body["code"] == 0, body
        assert body["data"] is not None
        return body["data"]

    def next_no(self, prefix: str) -> str:
        return f"IT{prefix}{next(self._request_seq):08d}"


def require_seed(sql: str, params: tuple[Any, ...] | None = None) -> dict[str, Any]:
    row = fetch_one(sql, params)
    assert row is not None, sql
    return row


def table_max_ids() -> dict[str, int]:
    rows = fetch_all("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
    tables = [next(iter(row.values())) for row in rows]
    max_ids: dict[str, int] = {}
    for table in tables:
        column = fetch_one(f"SHOW COLUMNS FROM `{table}` LIKE 'id'")
        if column is None:
            continue
        row = fetch_one(f"SELECT COALESCE(MAX(id), 0) AS max_id FROM `{table}`")
        max_ids[str(table)] = int(row["max_id"] if row else 0)
    return max_ids


def delete_rows_after(before: dict[str, int]) -> None:
    with db_cursor() as (_, cursor):
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        for table, max_id in sorted(before.items()):
            cursor.execute(f"DELETE FROM `{table}` WHERE id > %s", (max_id,))
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")


def create_customer(api: ApiClient, *, customer_type: str = "personal") -> str:
    payload: dict[str, Any] = {
        "request_no": api.next_no("CUST"),
        "customer_type": customer_type,
        "customer_name": f"接口测试客户{api.next_no('NM')}",
        "branch_code": api.seed["branch_code"],
        "channel_code": api.seed["channel_code"],
    }
    if customer_type == "enterprise":
        payload.update(
            {
                "company_name": f"接口测试企业{api.next_no('CO')}",
                "uniform_social_credit_code": api.next_no("USC"),
                "registered_capital_amount": "1000000.00",
                "registered_capital_currency_code": "CNY",
                "established_date": "2020-01-01",
                "registered_address": "测试地址",
                "business_scope": "金融数据测试",
                "industry": "software",
            }
        )
    data = api.post_ok("/api/v1/customers", payload)
    return str(data["customer_no"])


def create_account(api: ApiClient, customer_no: str, *, open_amount: str = "10000.00") -> str:
    data = api.post_ok(
        "/api/v1/accounts",
        {
            "request_no": api.next_no("ACC"),
            "customer_no": customer_no,
            "product_code": api.seed["account_product"]["product_code"],
            "currency_code": "CNY",
            "branch_code": api.seed["branch_code"],
            "channel_code": api.seed["channel_code"],
            "open_amount": open_amount,
        },
        token=customer_no,
    )
    return str(data["account_no"])


def prepare_wealth_open_period(product_id: int) -> None:
    now = datetime.now()
    start = now - timedelta(days=1)
    end = now + timedelta(days=1)
    period_no = int(
        require_seed(
            "SELECT COALESCE(MAX(period_no), 0) + 1 AS period_no FROM wealth_open_period WHERE product_id = %s",
            (product_id,),
        )["period_no"]
    )
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO wealth_open_period (
                product_id,
                period_no,
                purchase_start_at,
                purchase_end_at,
                redeem_start_at,
                redeem_end_at,
                period_status,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'open', %s, %s)
            """,
            (product_id, period_no, start, end, start, end, now, now),
        )


def insert_contract_document(contract_no: str) -> str:
    contract = require_seed("SELECT id FROM loan_contract WHERE contract_no = %s", (contract_no,))
    document_no = f"ITDOC{contract['id']:08d}"
    now = datetime.now()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO loan_contract_document (
                document_no,
                contract_id,
                document_type,
                document_version,
                file_url,
                file_hash,
                sign_status,
                created_at,
                updated_at
            )
            VALUES (%s, %s, 'loan_contract', 1, %s, %s, 'pending', %s, %s)
            """,
            (
                document_no,
                contract["id"],
                f"https://files.example/{document_no}.pdf",
                document_no.lower(),
                now,
                now,
            ),
        )
    return document_no


def insert_collateral(application_no: str, contract_no: str) -> str:
    application = require_seed("SELECT id, customer_id FROM loan_application WHERE application_no = %s", (application_no,))
    contract = require_seed("SELECT id FROM loan_contract WHERE contract_no = %s", (contract_no,))
    collateral_no = f"ITCOL{application['id']:08d}"
    now = datetime.now()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO collateral_asset (
                collateral_no,
                application_id,
                contract_id,
                customer_id,
                asset_type,
                asset_name,
                asset_owner_name,
                ownership_certificate_no,
                currency_code,
                appraised_value_amount,
                pledge_rate,
                secured_amount,
                appraisal_org,
                appraised_at,
                registration_status,
                pledge_rank,
                priority_rule,
                collateral_status,
                created_at,
                updated_at
            )
            VALUES (
                %s, %s, %s, %s, 'vehicle', '测试车辆', '接口测试客户', %s,
                'CNY', 100000.00, 0.500000, 50000.00, '测试评估机构', %s,
                'registered', 1, 'first', 'active', %s, %s
            )
            """,
            (
                collateral_no,
                application["id"],
                contract["id"],
                application["customer_id"],
                collateral_no,
                now,
                now,
                now,
            ),
        )
    return collateral_no


def make_first_bill_overdue(contract_no: str) -> str:
    contract = require_seed("SELECT id FROM loan_contract WHERE contract_no = %s", (contract_no,))
    bill = require_seed(
        """
        SELECT bill_no, id
        FROM repayment_bill
        WHERE contract_id = %s
        ORDER BY period_no
        LIMIT 1
        """,
        (contract["id"],),
    )
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            UPDATE repayment_bill
            SET due_date = %s,
                bill_status = 'billed',
                outstanding_amount = principal_amount + interest_amount + fee_amount,
                paid_amount = 0,
                reduced_amount = 0
            WHERE id = %s
            """,
            (date.today() - timedelta(days=40), bill["id"]),
        )
    return str(bill["bill_no"])
