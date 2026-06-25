"""Layer1: foundation, products, rules and wealth derived data."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Iterable

from ..config import GENERATION_DEFAULTS, LAYERS
from ..db import db
from .base import BaseGenerator
from .seed_importer import SeedImporter


class Layer1Generator(BaseGenerator):
    layer = 1
    layer_name = "基础配置与产品主数据"

    def __init__(self) -> None:
        self.today = date.today()

    def run(self) -> None:
        self.header()
        self.clear_layer_tables()

        counts = {table: 0 for table in LAYERS[self.layer]["tables"]}
        counts.update(SeedImporter().import_layer1_seeds())

        products = self.fetch_wealth_products()
        settlement_rules = self.fetch_wealth_settlement_rules()
        counts["wealth_open_period"] = self.generate_wealth_open_periods(products)
        counts["wealth_trade_calendar"] = self.generate_wealth_trade_calendar(
            products,
            settlement_rules,
        )
        counts["wealth_nav"] = self.generate_wealth_nav(products)
        counts["wealth_product_notice"] = self.generate_wealth_product_notices(products)

        self.validate(counts)
        self.log_table_counts(counts)

    def clear_layer_tables(self) -> None:
        db.execute("SET FOREIGN_KEY_CHECKS = 0")
        try:
            for table in reversed(LAYERS[self.layer]["tables"]):
                db.execute(f"TRUNCATE TABLE `{table}`")
        finally:
            db.execute("SET FOREIGN_KEY_CHECKS = 1")

    def fetch_wealth_products(self) -> list[dict[str, Any]]:
        return db.fetch_all(
            """
            SELECT
                id,
                product_code,
                product_name,
                product_type,
                operation_mode,
                expected_yield_rate,
                nav_based_flag,
                sale_start_at,
                sale_end_at
            FROM wealth_product
            ORDER BY id
            """
        )

    def fetch_wealth_settlement_rules(self) -> dict[int, dict[str, Any]]:
        rows = db.fetch_all(
            """
            SELECT
                product_id,
                purchase_confirm_days,
                redeem_confirm_days,
                redeem_arrival_days
            FROM wealth_settlement_rule
            """
        )
        return {int(row["product_id"]): row for row in rows}

    def generate_wealth_open_periods(self, products: list[dict[str, Any]]) -> int:
        months = max(4, int(GENERATION_DEFAULTS["calendar_days"]) // 30)
        open_products = [
            product
            for product in products
            if product["operation_mode"] in {"open", "periodic_open"}
        ]
        total_rows = len(open_products) * months
        return self.stream_rows(
            "wealth_open_period",
            self.iter_wealth_open_periods(open_products, months),
            total_rows=total_rows,
            build_step_name="build wealth_open_period",
        )

    def iter_wealth_open_periods(
        self,
        products: list[dict[str, Any]],
        months: int,
    ) -> Iterable[dict[str, Any]]:
        row_id = 1
        first_month = date(self.today.year, self.today.month, 1)
        start_month = self.add_months(first_month, -(months - 1))
        for product in products:
            for period_no in range(1, months + 1):
                month_start = self.add_months(start_month, period_no - 1)
                purchase_start = datetime.combine(month_start, time(9, 0, 0))
                purchase_end = datetime.combine(
                    min(self.add_days(month_start, 9), self.month_end(month_start)),
                    time(15, 0, 0),
                )
                status = "closed" if purchase_end.date() < self.today else "planned"
                created_at = purchase_start
                updated_at = purchase_end if status == "closed" else created_at
                yield {
                    "id": row_id,
                    "product_id": product["id"],
                    "period_no": period_no,
                    "purchase_start_at": purchase_start,
                    "purchase_end_at": purchase_end,
                    "redeem_start_at": purchase_start,
                    "redeem_end_at": purchase_end,
                    "period_status": status,
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
                row_id += 1

    def generate_wealth_trade_calendar(
        self,
        products: list[dict[str, Any]],
        settlement_rules: dict[int, dict[str, Any]],
    ) -> int:
        days = int(GENERATION_DEFAULTS["calendar_days"])
        total_rows = len(products) * days
        return self.stream_rows(
            "wealth_trade_calendar",
            self.iter_wealth_trade_calendar(products, settlement_rules, days),
            total_rows=total_rows,
            build_step_name="build wealth_trade_calendar",
        )

    def iter_wealth_trade_calendar(
        self,
        products: list[dict[str, Any]],
        settlement_rules: dict[int, dict[str, Any]],
        days: int,
    ) -> Iterable[dict[str, Any]]:
        row_id = 1
        start_date = self.today - timedelta(days=days - 1)
        for product in products:
            rule = settlement_rules[int(product["id"])]
            for offset in range(days):
                calendar_date = start_date + timedelta(days=offset)
                trade_flag = 1 if self.is_business_day(calendar_date) else 0
                purchase_confirm_date = self.add_business_days(
                    calendar_date,
                    int(rule["purchase_confirm_days"]),
                )
                redeem_confirm_date = self.add_business_days(
                    calendar_date,
                    int(rule["redeem_confirm_days"]),
                )
                redeem_arrival_date = self.add_business_days(
                    redeem_confirm_date,
                    int(rule["redeem_arrival_days"]),
                )
                created_at = datetime.combine(calendar_date, time(0, 0, 0))
                yield {
                    "id": row_id,
                    "product_id": product["id"],
                    "calendar_date": calendar_date,
                    "trade_flag": trade_flag,
                    "purchase_confirm_date": purchase_confirm_date,
                    "redeem_confirm_date": redeem_confirm_date,
                    "redeem_arrival_date": redeem_arrival_date,
                    "created_at": created_at,
                }
                row_id += 1

    def generate_wealth_nav(self, products: list[dict[str, Any]]) -> int:
        days = int(GENERATION_DEFAULTS["nav_days"])
        business_day_count = sum(
            1
            for offset in range(days)
            if self.is_business_day(self.today - timedelta(days=days - 1 - offset))
        )
        total_rows = len(products) * business_day_count
        return self.stream_rows(
            "wealth_nav",
            self.iter_wealth_nav(products, days),
            total_rows=total_rows,
            build_step_name="build wealth_nav",
        )

    def iter_wealth_nav(
        self,
        products: list[dict[str, Any]],
        days: int,
    ) -> Iterable[dict[str, Any]]:
        row_id = 1
        start_date = self.today - timedelta(days=days - 1)
        for product in products:
            accumulated_nav = Decimal("1.000000")
            for offset in range(days):
                nav_date = start_date + timedelta(days=offset)
                if not self.is_business_day(nav_date):
                    continue
                expected_yield = Decimal(str(product["expected_yield_rate"] or "0"))
                daily_yield = (
                    expected_yield / Decimal("252")
                    + Decimal(((int(product["id"]) + offset) % 7) - 3) / Decimal("1000000")
                )
                accumulated_nav = max(
                    Decimal("0.800000"),
                    accumulated_nav * (Decimal("1") + daily_yield),
                )
                unit_nav = accumulated_nav.quantize(Decimal("0.000001"))
                created_at = datetime.combine(nav_date, time(17, 0, 0))
                yield {
                    "id": row_id,
                    "product_id": product["id"],
                    "nav_date": nav_date,
                    "unit_nav": unit_nav,
                    "accumulated_nav": unit_nav,
                    "daily_yield_rate": daily_yield.quantize(Decimal("0.000001")),
                    "annualized_yield_rate": expected_yield.quantize(Decimal("0.000001")),
                    "created_at": created_at,
                }
                row_id += 1

    def generate_wealth_product_notices(self, products: list[dict[str, Any]]) -> int:
        notice_types = (
            ("product_intro", "产品说明"),
            ("open_period", "开放期公告"),
            ("risk_tip", "风险提示"),
        )
        total_rows = len(products) * len(notice_types)
        return self.stream_rows(
            "wealth_product_notice",
            self.iter_wealth_product_notices(products, notice_types),
            total_rows=total_rows,
            build_step_name="build wealth_product_notice",
        )

    def iter_wealth_product_notices(
        self,
        products: list[dict[str, Any]],
        notice_types: tuple[tuple[str, str], ...],
    ) -> Iterable[dict[str, Any]]:
        row_id = 1
        for product in products:
            for notice_type, notice_name in notice_types:
                published_at = datetime.combine(
                    self.today - timedelta(days=row_id % 90),
                    time(9, 0, 0),
                )
                yield {
                    "id": row_id,
                    "notice_no": f"NTC{row_id:08d}",
                    "product_id": product["id"],
                    "notice_type": notice_type,
                    "notice_title": f"{product['product_name']}{notice_name}",
                    "notice_content": (
                        f"{product['product_name']}的{notice_name}，"
                        "包括产品要素、交易安排、收益风险和投资者适当性提示"
                    ),
                    "published_at": published_at,
                    "notice_status": "published",
                    "created_at": published_at,
                    "updated_at": published_at,
                }
                row_id += 1

    def validate(self, counts: dict[str, int]) -> None:
        minimums = {
            "dim_branch": 50,
            "dim_employee": 300,
            "account_product": 10,
            "service_product": 12,
            "loan_product": 24,
            "wealth_product": 80,
            "risk_rule": 10,
            "business_metric_dict": 12,
        }
        for table, minimum in minimums.items():
            if counts.get(table, 0) < minimum:
                raise ValueError(f"{table} below required minimum {minimum}")

        required_child_counts = {
            "loan_product_eligibility_rule": "loan_product",
            "loan_product_rate_tier": "loan_product",
            "loan_product_required_material": "loan_product",
            "wealth_settlement_rule": "wealth_product",
        }
        for child_table, parent_table in required_child_counts.items():
            child_count = counts.get(child_table, 0)
            parent_count = counts.get(parent_table, 0)
            if child_count < parent_count:
                raise ValueError(f"{child_table} does not cover {parent_table}")

        invalid_strategy_rel = db.fetch_one(
            """
            SELECT COUNT(*) AS cnt
            FROM risk_strategy_rule_rel AS rel
            LEFT JOIN risk_strategy AS strategy ON strategy.id = rel.strategy_id
            LEFT JOIN risk_rule AS rule ON rule.id = rel.rule_id
            WHERE strategy.id IS NULL OR rule.id IS NULL
            """
        )
        if invalid_strategy_rel and int(invalid_strategy_rel["cnt"]) > 0:
            raise ValueError("risk_strategy_rule_rel has invalid references")

    def is_business_day(self, value: date) -> bool:
        return value.weekday() < 5

    def add_business_days(self, value: date, days: int) -> date:
        current = value
        remaining = max(days, 0)
        while remaining > 0 or not self.is_business_day(current):
            current += timedelta(days=1)
            if self.is_business_day(current):
                remaining -= 1
        return current

    def add_months(self, value: date, months: int) -> date:
        month = value.month - 1 + months
        year = value.year + month // 12
        month = month % 12 + 1
        day = min(value.day, self.month_end(date(year, month, 1)).day)
        return date(year, month, day)

    def add_days(self, value: date, days: int) -> date:
        return value + timedelta(days=days)

    def month_end(self, value: date) -> date:
        if value.month == 12:
            next_month = date(value.year + 1, 1, 1)
        else:
            next_month = date(value.year, value.month + 1, 1)
        return next_month - timedelta(days=1)
