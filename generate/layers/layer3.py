"""Layer3: accounts, ordinary transactions and reconciliation."""

from __future__ import annotations

from datetime import timedelta

from ..config import GENERATION_DEFAULTS, LAYERS
from .base import BaseGenerator
from .common import clear_tables, code, dt, fetch_id_values, fetch_ids


class Layer3Generator(BaseGenerator):
    layer = 3

    def run(self) -> None:
        self.header()
        clear_tables(LAYERS[self.layer]["tables"])
        customers = fetch_id_values(
            "customer",
            ["id", "branch_id", "register_channel_id", "customer_type"],
            "customer_status <> 'closed'",
        )
        account_products = fetch_id_values("account_product", ["id", "currency_code", "account_type"])
        channel_ids = fetch_ids("dim_channel", "id > 0")
        employee_ids = fetch_ids("dim_employee")
        tx_count = int(GENERATION_DEFAULTS["transactions"])
        tx_days = min(int(GENERATION_DEFAULTS["calendar_days"]), 730)
        batch_count = len(channel_ids) * tx_days
        account_count = max(len(customers), int(len(customers) * 1.4))
        freeze_count = max(10, account_count // 50)

        counts: dict[str, int] = {}
        counts["bank_account"] = self.stream_rows(
            "bank_account",
            self.iter_bank_accounts(account_count, customers, account_products),
            total_rows=account_count,
            build_step_name="build bank_account",
        )
        accounts = fetch_id_values(
            "bank_account",
            ["id", "customer_id", "branch_id", "open_channel_id", "currency_code"],
        )
        counts["bank_account_status_history"] = self.stream_rows(
            "bank_account_status_history",
            self.iter_account_status_history(accounts, employee_ids),
            total_rows=account_count,
            build_step_name="build bank_account_status_history",
        )
        customer_types = {
            int(customer["id"]): customer["customer_type"] for customer in customers
        }
        personal_accounts = [
            account
            for account in accounts
            if customer_types[int(account["customer_id"])] == "personal"
        ]
        card_count = int(len(personal_accounts) * 0.9)
        counts["bank_card"] = self.stream_rows(
            "bank_card",
            self.iter_bank_cards(personal_accounts, card_count),
            total_rows=card_count,
            build_step_name="build bank_card",
        )
        counts["account_transaction"] = self.stream_rows(
            "account_transaction",
            self.iter_account_transactions(tx_count, accounts, channel_ids, tx_days, card_count),
            total_rows=tx_count,
            build_step_name="build account_transaction",
        )
        counts["channel_transaction"] = self.stream_rows(
            "channel_transaction",
            self.iter_channel_transactions(tx_count, channel_ids, accounts, tx_days),
            total_rows=tx_count,
            build_step_name="build channel_transaction",
        )
        counts["reconciliation_batch"] = self.stream_rows(
            "reconciliation_batch",
            self.iter_reconciliation_batches(channel_ids, tx_days),
            total_rows=batch_count,
            build_step_name="build reconciliation_batch",
        )
        counts["reconciliation_result"] = self.stream_rows(
            "reconciliation_result",
            self.iter_reconciliation_results(tx_count, channel_ids, tx_days),
            total_rows=tx_count,
            build_step_name="build reconciliation_result",
        )
        adjustment_count = max(1, tx_count // 200)
        counts["reconciliation_adjustment"] = self.stream_rows(
            "reconciliation_adjustment",
            self.iter_reconciliation_adjustments(adjustment_count, employee_ids),
            total_rows=adjustment_count,
            build_step_name="build reconciliation_adjustment",
        )
        counts["fund_freeze"] = self.stream_rows(
            "fund_freeze",
            self.iter_fund_freezes(freeze_count, accounts),
            total_rows=freeze_count,
            build_step_name="build fund_freeze",
        )
        counts["fund_freeze_operation"] = self.stream_rows(
            "fund_freeze_operation",
            self.iter_fund_freeze_operations(freeze_count, accounts, employee_ids),
            total_rows=freeze_count,
            build_step_name="build fund_freeze_operation",
        )
        counts["account_ledger"] = self.stream_rows(
            "account_ledger",
            self.iter_account_ledgers(tx_count, accounts),
            total_rows=tx_count,
            build_step_name="build account_ledger",
        )
        self.log_table_counts(counts)

    def iter_bank_accounts(
        self,
        total: int,
        customers: list[dict],
        account_products: list[dict],
    ):
        for index in range(1, total + 1):
            customer = customers[(index - 1) % len(customers)]
            product = account_products[(index - 1) % len(account_products)]
            status = "closed" if index % 100 >= 98 else "normal"
            balance = 2000 + (index % 200) * 125
            frozen = 100 if index % 50 == 0 else 0
            opened_at = dt((index * 5) % 1095, 10)
            closed_at = min(opened_at + timedelta(days=500), dt(0, 17)) if status == "closed" else None
            yield {
                "id": index,
                "account_no": code("ACC", index, 10),
                "customer_id": customer["id"],
                "branch_id": customer["branch_id"],
                "open_channel_id": customer["register_channel_id"],
                "account_product_id": product["id"],
                "currency_code": product["currency_code"],
                "account_type": product["account_type"],
                "account_status": status,
                "balance_amount": balance,
                "frozen_amount": frozen,
                "available_amount": balance - frozen,
                "opened_at": opened_at,
                "closed_at": closed_at,
                "created_at": opened_at,
                "updated_at": closed_at or opened_at,
            }

    def iter_account_status_history(self, accounts: list[dict], employee_ids: list[int]):
        for index, account in enumerate(accounts, start=1):
            yield {
                "id": index,
                "account_id": index,
                "customer_id": account["customer_id"],
                "change_seq": 1,
                "from_status": "none",
                "to_status": "normal",
                "change_reason": "账户开户",
                "related_type": "none",
                "related_id": None,
                "operator_id": employee_ids[(index - 1) % len(employee_ids)],
                "changed_at": dt((index * 5) % 1095, 10),
                "created_at": dt((index * 5) % 1095, 10),
            }

    def iter_bank_cards(self, accounts: list[dict], total: int):
        row_id = 1
        for index, account in enumerate(accounts[:total], start=1):
            issued_at = dt((index * 5) % 1095, 11)
            yield {
                "id": row_id,
                "card_no": f"622200{row_id:013d}",
                "customer_id": account["customer_id"],
                "account_id": account["id"],
                "card_type": "debit",
                "card_level": "gold" if row_id % 10 == 0 else "standard",
                "card_status": "active",
                "issued_at": issued_at,
                "expired_at": issued_at + timedelta(days=3650),
                "created_at": issued_at,
                "updated_at": issued_at,
            }
            row_id += 1

    def transaction_type(self, tx_id: int) -> str:
        types = ["transfer", "consume", "deposit", "withdraw", "refund", "adjustment"]
        return types[(tx_id - 1) % len(types)]

    def target_account(self, accounts: list[dict], source_index: int) -> dict:
        source = accounts[source_index % len(accounts)]
        for step in range(1, len(accounts) + 1):
            target = accounts[(source_index + step) % len(accounts)]
            if target["currency_code"] == source["currency_code"]:
                return target
        return source

    def account_direction(
        self,
        tx_type: str,
        account: dict,
        target_account: dict,
    ) -> tuple[int | None, int | None]:
        if tx_type == "transfer":
            return int(account["id"]), int(target_account["id"])
        if tx_type in {"consume", "withdraw"}:
            return int(account["id"]), None
        if tx_type in {"deposit", "refund"}:
            return None, int(account["id"])
        return int(account["id"]), None

    def iter_account_transactions(
        self,
        total: int,
        accounts: list[dict],
        channel_ids: list[int],
        tx_days: int,
        card_count: int,
    ):
        for tx_id in range(1, total + 1):
            account = accounts[(tx_id - 1) % len(accounts)]
            target_account = self.target_account(accounts, tx_id - 1)
            tx_type = self.transaction_type(tx_id)
            from_account_id, to_account_id = self.account_direction(tx_type, account, target_account)
            status = "success" if tx_id % 100 < 95 else "failed"
            amount = 20 + (tx_id % 500) * 3
            transaction_at = dt(tx_id % tx_days, 9 + tx_id % 8)
            yield {
                "id": tx_id,
                "transaction_no": code("TXN", tx_id, 12),
                "customer_id": account["customer_id"],
                "from_account_id": from_account_id,
                "to_account_id": to_account_id,
                "card_id": account["id"] if int(account["id"]) <= card_count else None,
                "channel_id": channel_ids[(tx_id - 1) % len(channel_ids)],
                "original_transaction_id": None,
                "biz_order_no": code("BIZ", tx_id, 12),
                "external_order_no": code("EXT", tx_id, 12),
                "merchant_no": f"M{tx_id % 1000:06d}",
                "merchant_name": "中州合作商户",
                "counterparty_name": "交易对手",
                "counterparty_account_no": code("CP", tx_id, 12),
                "counterparty_bank_name": "中州银行",
                "transaction_type": tx_type,
                "transaction_status": status,
                "reconcile_status": "matched",
                "currency_code": account["currency_code"],
                "transaction_amount": amount,
                "fee_amount": 0 if tx_id % 5 else 1,
                "related_type": "none",
                "related_id": None,
                "transaction_at": transaction_at,
                "created_at": transaction_at,
                "updated_at": transaction_at,
            }

    def iter_channel_transactions(
        self,
        total: int,
        channel_ids: list[int],
        accounts: list[dict],
        tx_days: int,
    ):
        for tx_id in range(1, total + 1):
            account = accounts[(tx_id - 1) % len(accounts)]
            status = "success" if tx_id % 100 < 95 else "failed"
            requested_at = dt(tx_id % tx_days, 9 + tx_id % 8)
            callback_at = requested_at if status == "success" else None
            yield {
                "id": tx_id,
                "channel_txn_no": code("CHN", tx_id, 12),
                "channel_id": channel_ids[(tx_id - 1) % len(channel_ids)],
                "transaction_id": tx_id,
                "channel_order_no": code("EXT", tx_id, 12),
                "channel_trade_no": code("TRD", tx_id, 12),
                "request_no": code("REQ", tx_id, 12),
                "request_type": "payment",
                "request_status": status,
                "callback_status": "verified" if status == "success" else "none",
                "reconcile_status": "matched",
                "currency_code": account["currency_code"],
                "channel_amount": 20 + (tx_id % 500) * 3,
                "channel_fee_amount": 0 if tx_id % 5 else 1,
                "error_code": None if status == "success" else "E_TIMEOUT",
                "error_message": None if status == "success" else "渠道超时",
                "requested_at": requested_at,
                "responded_at": requested_at,
                "callback_at": callback_at,
                "created_at": requested_at,
                "updated_at": callback_at or requested_at,
            }

    def iter_reconciliation_batches(self, channel_ids: list[int], tx_days: int):
        row_id = 1
        for channel_id in channel_ids:
            for day_offset in range(tx_days):
                reconcile_date = dt(day_offset).date()
                completed_at = dt(day_offset, 2)
                yield {
                    "id": row_id,
                    "batch_no": code("RCB", row_id, 10),
                    "channel_id": channel_id,
                    "reconcile_date": reconcile_date,
                    "file_name": f"reconcile_{channel_id}_{reconcile_date}.csv",
                    "file_hash": f"hash-{row_id:012d}",
                    "batch_status": "completed",
                    "started_at": dt(day_offset, 1),
                    "completed_at": completed_at,
                    "created_at": dt(day_offset, 1),
                    "updated_at": completed_at,
                }
                row_id += 1

    def iter_reconciliation_results(self, total: int, channel_ids: list[int], tx_days: int):
        for tx_id in range(1, total + 1):
            channel_index = (tx_id - 1) % len(channel_ids)
            day_offset = tx_id % tx_days
            batch_id = channel_index * tx_days + day_offset + 1
            processed_at = dt(day_offset, 3)
            yield {
                "id": tx_id,
                "result_no": code("RCR", tx_id, 12),
                "batch_id": batch_id,
                "transaction_id": tx_id,
                "channel_transaction_id": tx_id,
                "result_type": "matched",
                "difference_amount": 0,
                "process_status": "closed",
                "process_comment": "自动对账完成",
                "created_at": processed_at,
                "updated_at": processed_at,
            }

    def iter_reconciliation_adjustments(self, total: int, employee_ids: list[int]):
        for row_id in range(1, total + 1):
            result_id = row_id * 200
            posted_at = dt(row_id % 30, 5)
            yield {
                "id": row_id,
                "adjustment_no": code("RCA", row_id, 10),
                "result_id": result_id,
                "transaction_id": result_id,
                "currency_code": "CNY",
                "adjustment_amount": 1,
                "adjustment_direction": "debit",
                "adjustment_status": "posted",
                "approved_by": employee_ids[(row_id - 1) % len(employee_ids)],
                "approved_at": dt(row_id % 30, 4),
                "posted_at": posted_at,
                "created_at": dt(row_id % 30, 4),
                "updated_at": posted_at,
            }

    def iter_fund_freezes(self, total: int, accounts: list[dict]):
        for row_id in range(1, total + 1):
            account = accounts[(row_id * 50 - 1) % len(accounts)]
            frozen_at = dt(row_id % 120, 8)
            yield {
                "id": row_id,
                "freeze_no": code("FRZ", row_id, 10),
                "account_id": account["id"],
                "customer_id": account["customer_id"],
                "freeze_type": "judicial",
                "related_type": "ordinary",
                "related_id": None,
                "judicial_instruction_no": code("JUD", row_id, 8),
                "currency_code": account["currency_code"],
                "freeze_amount": 100,
                "released_amount": 0,
                "freeze_status": "active",
                "frozen_at": frozen_at,
                "released_at": None,
                "created_at": frozen_at,
                "updated_at": frozen_at,
            }

    def iter_fund_freeze_operations(
        self,
        total: int,
        accounts: list[dict],
        employee_ids: list[int],
    ):
        for row_id in range(1, total + 1):
            account = accounts[(row_id * 50 - 1) % len(accounts)]
            yield {
                "id": row_id,
                "operation_no": code("FOP", row_id, 10),
                "freeze_id": row_id,
                "account_id": account["id"],
                "customer_id": account["customer_id"],
                "transaction_id": None,
                "related_type": "ordinary",
                "related_id": None,
                "judicial_instruction_no": code("JUD", row_id, 8),
                "operation_type": "freeze",
                "currency_code": account["currency_code"],
                "operation_amount": 100,
                "before_frozen_amount": 0,
                "after_frozen_amount": 100,
                "operation_source": "system",
                "operator_id": employee_ids[(row_id - 1) % len(employee_ids)],
                "operation_reason": "司法冻结",
                "operated_at": dt(row_id % 120, 8),
                "created_at": dt(row_id % 120, 8),
            }

    def iter_account_ledgers(self, total: int, accounts: list[dict]):
        row_id = 1
        for tx_id in range(1, total + 1):
            if tx_id % 100 >= 95:
                continue
            account = accounts[(tx_id - 1) % len(accounts)]
            tx_type = self.transaction_type(tx_id)
            if tx_type in {"deposit", "refund"}:
                ledger_account = account
                ledger_type = "credit"
                sign = 1
            else:
                ledger_account = account
                ledger_type = "debit" if tx_type != "adjustment" else "adjust"
                sign = -1
            amount = 20 + (tx_id % 500) * 3
            balance = 2000 + (int(ledger_account["id"]) % 200) * 125 + amount
            yield {
                "id": row_id,
                "ledger_no": code("LED", row_id, 12),
                "account_id": ledger_account["id"],
                "customer_id": ledger_account["customer_id"],
                "transaction_id": tx_id,
                "freeze_id": None,
                "freeze_operation_id": None,
                "ledger_type": ledger_type,
                "currency_code": ledger_account["currency_code"],
                "amount_delta": str(amount * sign),
                "frozen_delta": "0",
                "balance_after": str(balance),
                "frozen_after": "0",
                "available_after": str(balance),
                "created_at": dt(tx_id % int(GENERATION_DEFAULTS["calendar_days"]), 10),
            }
            row_id += 1
