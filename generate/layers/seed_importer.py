"""Seed import helpers for Layer1."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from ..config import SEEDS_DIR
from ..db import db
from ..insert_support import insert_dict_rows

PERMISSIONS_BY_ROLE = {
    "relationship_manager": ["customer.read", "customer.manage", "loan.apply"],
    "loan_approver": ["loan.read", "loan.approve", "credit.approve"],
    "risk_officer": ["risk.read", "risk.review", "aml.review"],
    "collector": ["collection.read", "collection.action", "repayment.promise"],
    "operator": ["operation.read", "workflow.manage", "notification.manage"],
    "customer_service": ["ticket.read", "ticket.handle", "customer.read"],
}

ZERO_DEFAULT_COLUMNS = {"min_guarantee_ratio"}

NULLABLE_COLUMNS = {
    "parent_id",
    "closed_at",
    "resigned_at",
    "effective_to",
}


class SeedImporter:
    """Imports CSV seeds and applies documented derived fields."""

    def __init__(self, seeds_dir: Path | None = None) -> None:
        self.seeds_dir = seeds_dir or SEEDS_DIR

    def load_csv(self, relative_path: str) -> list[dict[str, Any]]:
        path = self.seeds_dir / relative_path
        if not path.exists():
            raise FileNotFoundError(f"missing seed file: {path}")

        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                rows.append({key: self.normalize_cell(key, value) for key, value in row.items()})
        if not rows:
            raise ValueError(f"seed file is empty: {path}")
        return rows

    def normalize_cell(self, column: str, value: str | None) -> Any:
        if value is None:
            return None
        if value == "NULL":
            return None
        if value == "" and column in ZERO_DEFAULT_COLUMNS:
            return 0
        if value == "" and column in NULLABLE_COLUMNS:
            return None
        return value

    def insert_rows(self, table_name: str, rows: list[dict[str, Any]]) -> int:
        return insert_dict_rows(table_name, rows)

    def import_simple_table(self, table_name: str, relative_path: str) -> int:
        return self.insert_rows(table_name, self.load_csv(relative_path))

    def import_dim_employee(self) -> int:
        rows: list[dict[str, Any]] = []
        for row in self.load_csv("1_foundation/dim_employee.csv"):
            role = str(row["employee_role"])
            row["permission_codes"] = json.dumps(
                PERMISSIONS_BY_ROLE.get(role, ["operation.read"]),
                ensure_ascii=False,
            )
            rows.append(row)
        return self.insert_rows("dim_employee", rows)

    def import_layer1_seeds(self) -> dict[str, int]:
        counts = {
            "dim_branch": self.import_simple_table(
                "dim_branch", "1_foundation/dim_branch.csv"
            ),
            "dim_channel": self.import_simple_table(
                "dim_channel", "1_foundation/dim_channel.csv"
            ),
            "dim_currency": self.import_simple_table(
                "dim_currency", "1_foundation/dim_currency.csv"
            ),
            "dim_risk_level": self.import_simple_table(
                "dim_risk_level", "1_foundation/dim_risk_level.csv"
            ),
            "dim_employee": self.import_dim_employee(),
            "dim_product_category": self.import_simple_table(
                "dim_product_category", "1_foundation/dim_product_category.csv"
            ),
            "account_product": self.import_simple_table(
                "account_product", "2_product/account_product.csv"
            ),
            "service_product": self.import_simple_table(
                "service_product", "2_product/service_product.csv"
            ),
            "loan_product": self.import_simple_table(
                "loan_product", "2_product/loan_product.csv"
            ),
            "loan_product_eligibility_rule": self.import_simple_table(
                "loan_product_eligibility_rule",
                "2_product/loan_product_eligibility_rule.csv",
            ),
            "loan_product_rate_tier": self.import_simple_table(
                "loan_product_rate_tier", "2_product/loan_product_rate_tier.csv"
            ),
            "loan_product_required_material": self.import_simple_table(
                "loan_product_required_material",
                "2_product/loan_product_required_material.csv",
            ),
            "wealth_product": self.import_simple_table(
                "wealth_product", "2_product/wealth_product.csv"
            ),
            "wealth_settlement_rule": self.import_simple_table(
                "wealth_settlement_rule", "2_product/wealth_settlement_rule.csv"
            ),
            "risk_rule": self.import_simple_table("risk_rule", "3_rule/risk_rule.csv"),
            "risk_strategy": self.import_simple_table(
                "risk_strategy", "3_rule/risk_strategy.csv"
            ),
            "risk_strategy_rule_rel": self.import_simple_table(
                "risk_strategy_rule_rel", "3_rule/risk_strategy_rule_rel.csv"
            ),
            "business_metric_dict": self.import_simple_table(
                "business_metric_dict", "3_rule/business_metric_dict.csv"
            ),
        }
        db.execute("ALTER TABLE dim_branch AUTO_INCREMENT = 100000")
        db.execute("ALTER TABLE dim_product_category AUTO_INCREMENT = 100000")
        return counts
