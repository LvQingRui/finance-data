"""Generation configuration."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
SEEDS_DIR = ROOT_DIR / "seeds"

load_dotenv(ROOT_DIR / ".env")

DB_CONFIG = {
    "host": os.environ["DB_HOST"],
    "port": int(os.environ["DB_PORT"]),
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
    "database": os.environ["DB_NAME"],
    "charset": "utf8mb4",
    "autocommit": False,
}

LAYERS = {
    1: {
        "name": "基础配置与产品主数据",
        "tables": [
            "dim_branch",
            "dim_channel",
            "dim_currency",
            "dim_risk_level",
            "dim_employee",
            "dim_product_category",
            "account_product",
            "service_product",
            "loan_product",
            "loan_product_eligibility_rule",
            "loan_product_rate_tier",
            "loan_product_required_material",
            "wealth_product",
            "wealth_settlement_rule",
            "wealth_open_period",
            "wealth_trade_calendar",
            "wealth_nav",
            "wealth_product_notice",
            "risk_rule",
            "risk_strategy",
            "risk_strategy_rule_rel",
            "business_metric_dict",
        ],
    },
    2: {
        "name": "客户主数据",
        "tables": [
            "customer",
            "customer_status_history",
            "customer_identity",
            "customer_contact",
            "customer_device",
            "customer_kyc",
            "enterprise_profile",
            "beneficial_owner",
            "customer_risk_assessment",
            "customer_tag",
            "customer_tag_rel",
        ],
    },
    3: {
        "name": "账户、普通交易与对账",
        "tables": [
            "bank_account",
            "bank_account_status_history",
            "bank_card",
            "account_transaction",
            "channel_transaction",
            "account_ledger",
            "fund_freeze",
            "fund_freeze_operation",
            "reconciliation_batch",
            "reconciliation_result",
            "reconciliation_adjustment",
        ],
    },
    4: {
        "name": "理财业务闭环",
        "tables": [
            "wealth_position",
            "wealth_order",
            "wealth_income",
        ],
    },
    5: {
        "name": "信贷授信与放款",
        "tables": [
            "credit_application",
            "credit_application_material",
            "credit_approval_record",
            "credit_limit",
            "credit_limit_change_log",
            "loan_application",
            "loan_application_material",
            "credit_assessment",
            "loan_approval_record",
            "loan_contract",
            "loan_contract_document",
            "contract_sign_record",
            "collateral_asset",
            "guarantee_record",
            "loan_disbursement",
        ],
    },
    6: {
        "name": "正常还款、逾期与费用减免",
        "tables": [
            "repayment_schedule",
            "repayment_bill",
            "repayment_authorization",
            "repayment_record",
            "repayment_allocation",
            "overdue_record",
            "fee_reduction",
        ],
    },
    7: {
        "name": "风控、反洗钱与催收处置",
        "tables": [
            "risk_event",
            "risk_hit_record",
            "blacklist_record",
            "aml_case",
            "aml_case_transaction",
            "suspicious_transaction_report",
            "aml_review_result",
            "manual_review_task",
            "collection_case",
            "collection_action",
            "collection_contact_record",
            "repayment_promise",
            "legal_case",
            "loan_write_off",
            "loan_restructure",
            "collateral_disposal",
            "collection_performance_daily",
        ],
    },
    8: {
        "name": "运营支撑与日统计",
        "tables": [
            "notification_message",
            "support_ticket",
            "support_ticket_feedback",
            "workflow_instance",
            "workflow_task",
            "business_stat_daily",
        ],
    },
    9: {"name": "最终验收", "tables": []},
}

GENERATION_PROFILES = {
    "smoke": {
        "seed": 42,
        "batch_size": 2000,
        "calendar_days": 120,
        "nav_days": 120,
        "customers": 1200,
        "enterprise_ratio": 0.08,
        "accounts_per_customer": 1,
        "transactions": 6000,
        "wealth_orders": 900,
        "credit_applications": 700,
        "loan_applications": 520,
        "loan_contracts": 300,
        "repayment_periods": 6,
        "risk_events": 260,
        "support_tickets": 160,
        "stat_days": 30,
    },
    "full": {
        "seed": 42,
        "batch_size": 20000,
        "calendar_days": 365,
        "nav_days": 365,
        "customers": 50000,
        "enterprise_ratio": 0.08,
        "accounts_per_customer": 1,
        "transactions": 1000000,
        "wealth_orders": 30000,
        "credit_applications": 20000,
        "loan_applications": 15000,
        "loan_contracts": 8000,
        "repayment_periods": 12,
        "risk_events": 6000,
        "support_tickets": 800,
        "stat_days": 90,
    },
}

GENERATION_DEFAULTS = dict(GENERATION_PROFILES["full"])


@contextmanager
def generation_profile(profile: str):
    original = dict(GENERATION_DEFAULTS)
    GENERATION_DEFAULTS.clear()
    GENERATION_DEFAULTS.update(GENERATION_PROFILES[profile])
    try:
        yield GENERATION_DEFAULTS
    finally:
        GENERATION_DEFAULTS.clear()
        GENERATION_DEFAULTS.update(original)
