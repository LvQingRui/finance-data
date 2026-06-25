"""Layer4: wealth business cycle."""

from __future__ import annotations

from datetime import timedelta

from ..config import GENERATION_DEFAULTS, LAYERS
from .base import BaseGenerator
from .common import clear_tables, code, dt, fetch_id_values, fetch_ids, max_id
from .fund_flows import (
    iter_account_ledgers,
    iter_account_transactions,
    iter_channel_transactions,
    iter_reconciliation_results,
)


class Layer4Generator(BaseGenerator):
    layer = 4

    def run(self) -> None:
        self.header()
        clear_tables(LAYERS[self.layer]["tables"])
        source_accounts = fetch_id_values("bank_account", ["id", "customer_id", "currency_code"], "account_status = 'normal'")
        products = fetch_id_values("wealth_product", ["id", "currency_code", "min_purchase_amount"], "product_status = 'selling'")
        products = self.products_with_accounts(products, source_accounts)
        self._wealth_products = products
        assessments = fetch_id_values("customer_risk_assessment", ["id", "customer_id"])
        channel_ids = fetch_ids("dim_channel", "id > 0")
        tx_days = min(int(GENERATION_DEFAULTS["calendar_days"]), 730)
        order_count = min(int(GENERATION_DEFAULTS["wealth_orders"]), len(source_accounts))
        position_count = max(1, min(order_count // 3, 25000))
        accounts = self.accounts_for_products(order_count, source_accounts, products)
        position_accounts = self.accounts_for_products(position_count, source_accounts, products)
        income_count = position_count * 2
        funded_order_ids = [order_id for order_id in range(1, order_count + 1) if order_id % 20]
        funded_order_accounts = [accounts[order_id - 1] for order_id in funded_order_ids]
        self._wealth_order_tx_ids = {
            order_id: tx_index
            for tx_index, order_id in enumerate(funded_order_ids, start=max_id("account_transaction") + 1)
        }
        tx_start = max_id("account_transaction") + 1
        channel_tx_start = max_id("channel_transaction") + 1
        ledger_start = max_id("account_ledger") + 1
        result_start = max_id("reconciliation_result") + 1
        freeze_start = max_id("fund_freeze") + 1
        freeze_operation_start = max_id("fund_freeze_operation") + 1

        counts: dict[str, int] = {}
        counts["wealth_position"] = self.stream_rows(
            "wealth_position",
            self.iter_positions(position_count, position_accounts, products),
            total_rows=position_count,
            build_step_name="build wealth_position",
        )
        counts["account_transaction"] = self.stream_rows(
            "account_transaction",
            iter_account_transactions(
                start_id=tx_start,
                total=len(funded_order_ids),
                accounts=funded_order_accounts,
                channel_ids=channel_ids,
                tx_days=tx_days,
                related_type="wealth_order",
                transaction_type=self.order_transaction_type,
                prefix="WTX",
                amount_func=self.order_amount,
                local_now=self.local_now,
                related_ids=funded_order_ids,
            ),
            total_rows=len(funded_order_ids),
            build_step_name="build wealth account_transaction",
        )
        counts["channel_transaction"] = self.stream_rows(
            "channel_transaction",
            iter_channel_transactions(
                start_id=channel_tx_start,
                transaction_start_id=tx_start,
                total=len(funded_order_ids),
                accounts=funded_order_accounts,
                channel_ids=channel_ids,
                tx_days=tx_days,
                prefix="WCH",
                amount_func=self.order_amount,
                local_now=self.local_now,
                related_ids=funded_order_ids,
                transaction_prefix="WTX",
            ),
            total_rows=len(funded_order_ids),
            build_step_name="build wealth channel_transaction",
        )
        counts["account_ledger"] = self.stream_rows(
            "account_ledger",
            iter_account_ledgers(
                start_id=ledger_start,
                transaction_start_id=tx_start,
                total=len(funded_order_ids),
                accounts=funded_order_accounts,
                tx_days=tx_days,
                prefix="WLD",
                amount_func=self.order_amount,
                related_ids=funded_order_ids,
                transaction_type=self.order_transaction_type,
            ),
            total_rows=len(funded_order_ids),
            build_step_name="build wealth account_ledger",
        )
        counts["reconciliation_result"] = self.stream_rows(
            "reconciliation_result",
            iter_reconciliation_results(
                start_id=result_start,
                transaction_start_id=tx_start,
                channel_transaction_start_id=channel_tx_start,
                total=len(funded_order_ids),
                channel_ids=channel_ids,
                tx_days=tx_days,
                prefix="WRC",
                local_now=self.local_now,
            ),
            total_rows=len(funded_order_ids),
            build_step_name="build wealth reconciliation_result",
        )
        counts["fund_freeze"] = self.stream_rows(
            "fund_freeze",
            self.iter_order_freezes(freeze_start, order_count, accounts, products),
            total_rows=order_count,
            build_step_name="build wealth fund_freeze",
        )
        counts["fund_freeze_operation"] = self.stream_rows(
            "fund_freeze_operation",
            self.iter_order_freeze_operations(
                freeze_operation_start,
                freeze_start,
                order_count,
                accounts,
                products,
                self._wealth_order_tx_ids,
            ),
            total_rows=order_count,
            build_step_name="build wealth fund_freeze_operation",
        )
        counts["wealth_order"] = self.stream_rows(
            "wealth_order",
            self.iter_orders(
                order_count,
                accounts,
                products,
                self.assessment_by_customer(assessments),
                channel_ids,
                self._wealth_order_tx_ids,
                freeze_start,
                position_count,
            ),
            total_rows=order_count,
            build_step_name="build wealth_order",
        )
        positions = fetch_id_values(
            "wealth_position",
            ["id", "customer_id", "account_id", "product_id", "currency_code", "created_at"],
        )
        settled_income_ids = [income_id for income_id in range(1, income_count + 1) if income_id % 3 == 0]
        settled_income_accounts = [
            {
                "id": positions[(income_id - 1) % len(positions)]["account_id"],
                "customer_id": positions[(income_id - 1) % len(positions)]["customer_id"],
                "currency_code": positions[(income_id - 1) % len(positions)]["currency_code"],
            }
            for income_id in settled_income_ids
        ]
        income_tx_start = tx_start + len(funded_order_ids)
        income_channel_tx_start = channel_tx_start + len(funded_order_ids)
        income_ledger_start = ledger_start + len(funded_order_ids)
        income_result_start = result_start + len(funded_order_ids)
        self._wealth_income_tx_ids = {
            income_id: tx_index
            for tx_index, income_id in enumerate(settled_income_ids, start=income_tx_start)
        }
        self._wealth_income_ledger_ids = {
            income_id: ledger_id
            for ledger_id, income_id in enumerate(settled_income_ids, start=income_ledger_start)
        }
        self._wealth_income_times = {
            income_id: self.income_time(income_id, positions)
            for income_id in settled_income_ids
        }
        counts["wealth_income_account_transaction"] = self.stream_rows(
            "account_transaction",
            iter_account_transactions(
                start_id=income_tx_start,
                total=len(settled_income_ids),
                accounts=settled_income_accounts,
                channel_ids=channel_ids,
                tx_days=tx_days,
                related_type="wealth_income",
                transaction_type="wealth_income",
                prefix="ITX",
                amount_func=self.income_amount,
                local_now=self.local_now,
                related_ids=settled_income_ids,
                time_func=lambda income_id, _account: self._wealth_income_times[income_id],
            ),
            total_rows=len(settled_income_ids),
            build_step_name="build wealth_income account_transaction",
        )
        counts["wealth_income_channel_transaction"] = self.stream_rows(
            "channel_transaction",
            iter_channel_transactions(
                start_id=income_channel_tx_start,
                transaction_start_id=income_tx_start,
                total=len(settled_income_ids),
                accounts=settled_income_accounts,
                channel_ids=channel_ids,
                tx_days=tx_days,
                prefix="ICH",
                amount_func=self.income_amount,
                local_now=self.local_now,
                related_ids=settled_income_ids,
                transaction_prefix="ITX",
                time_func=lambda income_id, _account: self._wealth_income_times[income_id],
            ),
            total_rows=len(settled_income_ids),
            build_step_name="build wealth_income channel_transaction",
        )
        counts["wealth_income_account_ledger"] = self.stream_rows(
            "account_ledger",
            iter_account_ledgers(
                start_id=income_ledger_start,
                transaction_start_id=income_tx_start,
                total=len(settled_income_ids),
                accounts=settled_income_accounts,
                tx_days=tx_days,
                prefix="ILD",
                amount_func=self.income_amount,
                related_ids=settled_income_ids,
                transaction_type="wealth_income",
                time_func=lambda income_id, _account: self._wealth_income_times[income_id],
            ),
            total_rows=len(settled_income_ids),
            build_step_name="build wealth_income account_ledger",
        )
        counts["wealth_income_reconciliation_result"] = self.stream_rows(
            "reconciliation_result",
            iter_reconciliation_results(
                start_id=income_result_start,
                transaction_start_id=income_tx_start,
                channel_transaction_start_id=income_channel_tx_start,
                total=len(settled_income_ids),
                channel_ids=channel_ids,
                tx_days=tx_days,
                prefix="IRC",
                local_now=self.local_now,
            ),
            total_rows=len(settled_income_ids),
            build_step_name="build wealth_income reconciliation_result",
        )
        counts["wealth_income"] = self.stream_rows(
            "wealth_income",
            self.iter_income(income_count, positions),
            total_rows=income_count,
            build_step_name="build wealth_income",
        )
        self.log_table_counts(counts)

    def products_with_accounts(self, products: list[dict], accounts: list[dict]) -> list[dict]:
        account_currencies = {account["currency_code"] for account in accounts}
        available_products = [
            product for product in products
            if product["currency_code"] in account_currencies
        ]
        if not available_products:
            raise RuntimeError("no wealth product has matching account currency")
        return available_products

    def accounts_for_products(
        self,
        total: int,
        accounts: list[dict],
        products: list[dict],
    ) -> list[dict]:
        accounts_by_currency: dict[str, list[dict]] = {}
        for account in accounts:
            accounts_by_currency.setdefault(str(account["currency_code"]), []).append(account)
        result = []
        for offset in range(total):
            product = products[offset % len(products)]
            currency_accounts = accounts_by_currency[str(product["currency_code"])]
            result.append(currency_accounts[offset % len(currency_accounts)])
        return result

    def order_amount(self, row_id: int, account: dict) -> float:
        product = self._wealth_products[(row_id - 1) % len(self._wealth_products)]
        return round(max(float(product["min_purchase_amount"]), 1000 + row_id % 1000), 2)

    def order_transaction_type(self, row_id: int) -> str:
        return "wealth_redeem" if row_id % 5 == 0 else "wealth_purchase"

    def income_amount(self, row_id: int, account: dict) -> float:
        return round(1 + row_id % 20 * 0.1, 2)

    def income_time(self, row_id: int, positions: list[dict]):
        position = positions[(row_id - 1) % len(positions)]
        return position["created_at"] + timedelta(days=(row_id - 1) // len(positions) + 1, hours=6)

    def assessment_by_customer(self, assessments: list[dict]) -> dict[int, int]:
        return {int(assessment["customer_id"]): int(assessment["id"]) for assessment in assessments}

    def iter_positions(self, total: int, accounts: list[dict], products: list[dict]):
        for row_id in range(1, total + 1):
            account = accounts[(row_id - 1) % len(accounts)]
            product = products[(row_id - 1) % len(products)]
            share = 1000 + row_id % 500
            nav = 1.02
            valuation_at = dt(row_id % 365, 17)
            yield {
                "id": row_id,
                "customer_id": account["customer_id"],
                "account_id": account["id"],
                "product_id": product["id"],
                "currency_code": product["currency_code"],
                "holding_share": share,
                "available_share": share,
                "frozen_share": 0,
                "cost_amount": round(share * nav, 2),
                "market_value_amount": round(share * nav * 1.01, 2),
                "accumulated_income_amount": round(share * 0.01, 2),
                "last_nav": nav,
                "last_valuation_date": valuation_at.date(),
                "position_status": "active",
                "created_at": dt(row_id % 365, 10),
                "updated_at": valuation_at,
            }

    def iter_orders(
        self,
        total: int,
        accounts: list[dict],
        products: list[dict],
        assessments: dict[int, int],
        channel_ids: list[int],
        order_tx_ids: dict[int, int],
        freeze_start: int,
        position_count: int,
    ):
        for row_id in range(1, total + 1):
            account = accounts[(row_id - 1) % len(accounts)]
            product = products[(row_id - 1) % len(products)]
            amount = self.order_amount(row_id, account)
            order_type = "purchase" if row_id % 5 else "redeem"
            status = "confirmed" if row_id % 20 else "cancelled"
            submitted_at = dt(row_id % 365, 10)
            confirmed_at = dt(row_id % 365, 11) if status == "confirmed" else None
            cancelled_at = dt(row_id % 365, 11) if status == "cancelled" else None
            yield {
                "id": row_id,
                "order_no": code("WMO", row_id, 10),
                "customer_id": account["customer_id"],
                "account_id": account["id"],
                "product_id": product["id"],
                "channel_id": channel_ids[(row_id - 1) % len(channel_ids)],
                "risk_assessment_id": assessments[int(account["customer_id"])],
                "original_order_id": None,
                "transaction_id": order_tx_ids.get(row_id),
                "freeze_id": freeze_start + row_id - 1,
                "position_id": row_id % position_count + 1,
                "order_type": order_type,
                "order_status": status,
                "currency_code": product["currency_code"],
                "order_amount": amount,
                "order_share": round(amount / 1.02, 6),
                "confirmed_amount": amount if status == "confirmed" else 0,
                "confirmed_share": round(amount / 1.02, 6) if status == "confirmed" else 0,
                "confirmed_nav": "1.020000",
                "fee_amount": 0,
                "cancel_reason": "客户撤单" if status == "cancelled" else None,
                "submitted_at": submitted_at,
                "confirmed_at": confirmed_at,
                "cancelled_at": cancelled_at,
                "created_at": submitted_at,
                "updated_at": confirmed_at or cancelled_at or submitted_at,
            }

    def iter_income(
        self,
        total: int,
        positions: list[dict],
    ):
        for row_id in range(1, total + 1):
            position = positions[(row_id - 1) % len(positions)]
            settled = 1 if row_id % 3 == 0 else 0
            income_at = self.income_time(row_id, positions)
            yield {
                "id": row_id,
                "income_no": code("WIN", row_id, 10),
                "customer_id": position["customer_id"],
                "account_id": position["account_id"],
                "position_id": position["id"],
                "product_id": position["product_id"],
                "transaction_id": self._wealth_income_tx_ids.get(row_id) if settled else None,
                "ledger_id": self._wealth_income_ledger_ids.get(row_id) if settled else None,
                "income_date": income_at.date(),
                "income_type": "daily_income",
                "currency_code": position["currency_code"],
                "income_amount": self.income_amount(row_id, position),
                "settled_flag": settled,
                "settled_at": income_at if settled else None,
                "created_at": income_at,
            }

    def iter_order_freezes(
        self,
        start_id: int,
        total: int,
        accounts: list[dict],
        products: list[dict],
    ):
        for offset in range(total):
            row_id = start_id + offset
            order_id = offset + 1
            account = accounts[offset % len(accounts)]
            product = products[offset % len(products)]
            amount = self.order_amount(order_id, account)
            frozen_at = dt(order_id % 120, 10)
            released_at = dt(order_id % 120, 11)
            yield {
                "id": row_id,
                "freeze_no": code("WFR", row_id, 10),
                "account_id": account["id"],
                "customer_id": account["customer_id"],
                "freeze_type": self.order_transaction_type(order_id),
                "related_type": "wealth_order",
                "related_id": order_id,
                "judicial_instruction_no": None,
                "currency_code": product["currency_code"],
                "freeze_amount": amount,
                "released_amount": amount,
                "freeze_status": "released",
                "frozen_at": frozen_at,
                "released_at": released_at,
                "created_at": frozen_at,
                "updated_at": released_at,
            }

    def iter_order_freeze_operations(
        self,
        start_id: int,
        freeze_start: int,
        total: int,
        accounts: list[dict],
        products: list[dict],
        order_tx_ids: dict[int, int],
    ):
        for offset in range(total):
            row_id = start_id + offset
            order_id = offset + 1
            account = accounts[offset % len(accounts)]
            product = products[offset % len(products)]
            amount = self.order_amount(order_id, account)
            yield {
                "id": row_id,
                "operation_no": code("WFO", row_id, 10),
                "freeze_id": freeze_start + offset,
                "account_id": account["id"],
                "customer_id": account["customer_id"],
                "transaction_id": order_tx_ids.get(order_id),
                "related_type": "wealth_order",
                "related_id": order_id,
                "judicial_instruction_no": None,
                "operation_type": "release",
                "currency_code": product["currency_code"],
                "operation_amount": amount,
                "before_frozen_amount": amount,
                "after_frozen_amount": 0,
                "operation_source": "system",
                "operator_id": None,
                "operation_reason": "理财确认释放冻结",
                "operated_at": dt(order_id % 120, 11),
                "created_at": dt(order_id % 120, 11),
            }
