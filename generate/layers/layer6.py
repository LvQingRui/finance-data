"""Layer6: repayment, overdue and fee reduction."""

from __future__ import annotations

from datetime import datetime, timedelta

from ..config import GENERATION_DEFAULTS, LAYERS
from ..db import db
from .base import BaseGenerator
from .common import clear_tables, code, dt, fetch_id_values, fetch_ids, max_id
from .fund_flows import (
    iter_account_ledgers,
    iter_account_transactions,
    iter_channel_transactions,
    iter_reconciliation_results,
)


class Layer6Generator(BaseGenerator):
    layer = 6

    def run(self) -> None:
        self.header()
        clear_tables(LAYERS[self.layer]["tables"])
        contracts = fetch_id_values("loan_contract", ["id", "application_id", "customer_id", "repayment_account_id", "currency_code", "principal_amount", "annual_interest_rate"])
        accounts = [
            {
                "id": contract["repayment_account_id"],
                "customer_id": contract["customer_id"],
                "currency_code": contract["currency_code"],
            }
            for contract in contracts
        ]
        channel_ids = fetch_ids("dim_channel", "id > 0")
        employee_ids = fetch_ids("dim_employee")
        tx_days = min(int(GENERATION_DEFAULTS["calendar_days"]), 730)
        periods = int(GENERATION_DEFAULTS["repayment_periods"])
        self._repayment_contracts = contracts
        self._repayment_periods = periods
        schedule_count = len(contracts) * periods
        repayment_count = int(schedule_count * 0.82)
        overdue_count = max(1, int(schedule_count * 0.08))
        reduction_count = max(1, overdue_count // 3)
        db.execute("DELETE FROM credit_limit_change_log WHERE change_type = 'release'")
        tx_start = max_id("account_transaction") + 1
        channel_tx_start = max_id("channel_transaction") + 1
        ledger_start = max_id("account_ledger") + 1
        result_start = max_id("reconciliation_result") + 1
        limit_log_start = max_id("credit_limit_change_log") + 1
        counts: dict[str, int] = {}
        counts["repayment_schedule"] = self.stream_rows("repayment_schedule", self.iter_schedules(contracts, periods), total_rows=schedule_count, build_step_name="build repayment_schedule")
        counts["repayment_bill"] = self.stream_rows("repayment_bill", self.iter_bills(contracts, periods), total_rows=schedule_count, build_step_name="build repayment_bill")
        counts["repayment_authorization"] = self.stream_rows("repayment_authorization", self.iter_authorizations(contracts), total_rows=len(contracts), build_step_name="build repayment_authorization")
        repayment_sources = db.fetch_all(
            """
            SELECT
                bill.id AS bill_id,
                bill.contract_id,
                bill.customer_id,
                bill.period_no,
                bill.currency_code,
                bill.principal_amount,
                bill.interest_amount,
                bill.fee_amount,
                bill.penalty_amount,
                bill.billed_at,
                bill.paid_at,
                contract.repayment_account_id AS account_id
            FROM repayment_bill bill
            JOIN loan_contract contract ON contract.id = bill.contract_id
            WHERE bill.bill_status = 'paid'
            ORDER BY bill.id
            LIMIT %s
            """,
            (repayment_count,),
        )
        repayment_count = len(repayment_sources)
        self._repayment_sources = repayment_sources
        accounts = [
            {
                "id": source["account_id"],
                "customer_id": source["customer_id"],
                "currency_code": source["currency_code"],
            }
            for source in repayment_sources
        ]
        counts["account_transaction"] = self.stream_rows(
            "account_transaction",
            iter_account_transactions(
                start_id=tx_start,
                total=repayment_count,
                accounts=accounts,
                channel_ids=channel_ids,
                tx_days=tx_days,
                related_type="repayment_bill",
                transaction_type="loan_repayment",
                prefix="RTX",
                amount_func=self.repayment_flow_amount,
                local_now=self.local_now,
                related_ids=[int(source["bill_id"]) for source in repayment_sources],
                amount_ids=list(range(1, repayment_count + 1)),
                time_func=self.repayment_flow_time,
            ),
            total_rows=repayment_count,
            build_step_name="build repayment account_transaction",
        )
        counts["channel_transaction"] = self.stream_rows(
            "channel_transaction",
            iter_channel_transactions(
                start_id=channel_tx_start,
                transaction_start_id=tx_start,
                total=repayment_count,
                accounts=accounts,
                channel_ids=channel_ids,
                tx_days=tx_days,
                prefix="RCH",
                amount_func=self.repayment_flow_amount,
                local_now=self.local_now,
                transaction_prefix="RTX",
                amount_ids=list(range(1, repayment_count + 1)),
                time_func=self.repayment_flow_time,
            ),
            total_rows=repayment_count,
            build_step_name="build repayment channel_transaction",
        )
        counts["account_ledger"] = self.stream_rows(
            "account_ledger",
            iter_account_ledgers(
                start_id=ledger_start,
                transaction_start_id=tx_start,
                total=repayment_count,
                accounts=accounts,
                tx_days=tx_days,
                prefix="RLD",
                amount_func=self.repayment_flow_amount,
                amount_ids=list(range(1, repayment_count + 1)),
                transaction_type="loan_repayment",
                time_func=self.repayment_flow_time,
            ),
            total_rows=repayment_count,
            build_step_name="build repayment account_ledger",
        )
        counts["reconciliation_result"] = self.stream_rows(
            "reconciliation_result",
            iter_reconciliation_results(
                start_id=result_start,
                transaction_start_id=tx_start,
                channel_transaction_start_id=channel_tx_start,
                total=repayment_count,
                channel_ids=channel_ids,
                tx_days=tx_days,
                prefix="RRC",
                local_now=self.local_now,
            ),
            total_rows=repayment_count,
            build_step_name="build repayment reconciliation_result",
        )
        counts["repayment_record"] = self.stream_rows("repayment_record", self.iter_repayments(repayment_sources, tx_start), total_rows=repayment_count, build_step_name="build repayment_record")
        counts["repayment_allocation"] = self.stream_rows("repayment_allocation", self.iter_allocations(repayment_sources), total_rows=repayment_count, build_step_name="build repayment_allocation")
        overdue_bills = fetch_id_values(
            "repayment_bill",
            [
                "id",
                "contract_id",
                "customer_id",
                "period_no",
                "due_date",
                "currency_code",
                "principal_amount",
                "interest_amount",
                "fee_amount",
                "penalty_amount",
                "outstanding_amount",
            ],
            "bill_status = 'overdue'",
            limit=overdue_count,
        )
        counts["overdue_record"] = self.stream_rows("overdue_record", self.iter_overdue(overdue_bills), total_rows=len(overdue_bills), build_step_name="build overdue_record")
        counts["fee_reduction"] = self.stream_rows("fee_reduction", self.iter_fee_reduction(reduction_count, overdue_bills, employee_ids), total_rows=reduction_count, build_step_name="build fee_reduction")
        counts["credit_limit_change_log"] = self.stream_rows("credit_limit_change_log", self.iter_limit_release_logs(limit_log_start, contracts), total_rows=len(contracts), build_step_name="build credit_limit_release_log")
        self.log_table_counts(counts)

    def period_amounts(self, contract: dict, periods: int) -> tuple[float, float, float]:
        principal = round(float(contract["principal_amount"]) / periods, 2)
        interest = round(float(contract["principal_amount"]) * float(contract["annual_interest_rate"]) / 12, 2)
        fee = 0.0
        return principal, interest, fee

    def repayment_flow_amount(self, row_id: int, account: dict) -> float:
        source = self._repayment_sources[row_id - 1]
        return (
            float(source["principal_amount"])
            + float(source["interest_amount"])
            + float(source["fee_amount"])
            + float(source["penalty_amount"])
        )

    def repayment_flow_time(self, row_id: int, account: dict):
        source = self._repayment_sources[row_id - 1]
        return source["paid_at"] or source["billed_at"] + timedelta(hours=1)

    def iter_limit_release_logs(self, start_id: int, contracts: list[dict]):
        for offset, contract in enumerate(contracts):
            row_id = start_id + offset
            contract_id = int(contract["id"])
            release_amount = round(float(contract["principal_amount"]) * 0.25, 2)
            used_amount = round(float(contract["principal_amount"]), 2)
            total_amount = round(max(100000 + contract_id % 50 * 5000, used_amount * 2), 2)
            yield {
                "id": row_id,
                "change_no": code("LCL", row_id, 10),
                "credit_limit_id": contract["application_id"],
                "change_seq": 4,
                "credit_application_id": None,
                "loan_application_id": contract["application_id"],
                "contract_id": contract_id,
                "repayment_id": contract_id,
                "change_type": "release",
                "currency_code": contract["currency_code"],
                "change_amount": release_amount,
                "before_total_amount": total_amount,
                "after_total_amount": total_amount,
                "before_used_amount": used_amount,
                "after_used_amount": max(0, used_amount - release_amount),
                "before_frozen_amount": 0,
                "after_frozen_amount": 0,
                "before_available_amount": max(0, total_amount - used_amount),
                "after_available_amount": max(0, total_amount - used_amount + release_amount),
                "changed_at": dt(contract_id % 365, 10),
                "created_at": dt(contract_id % 365, 10),
            }

    def iter_schedules(self, contracts: list[dict], periods: int):
        row_id = 1
        for contract in contracts:
            principal, interest, fee = self.period_amounts(contract, periods)
            for period in range(1, periods + 1):
                due_date = (dt(365 - period * 30).date() + timedelta(days=contract["id"] % 30))
                created_at = dt(720, 8)
                status = "paid" if row_id % 100 < 82 else "overdue"
                updated_at = datetime.combine(due_date, datetime.min.time()) if status == "overdue" else created_at
                yield {
                    "id": row_id,
                    "contract_id": contract["id"],
                    "customer_id": contract["customer_id"],
                    "schedule_version": 1,
                    "period_no": period,
                    "due_date": due_date,
                    "currency_code": contract["currency_code"],
                    "principal_amount": principal,
                    "interest_amount": interest,
                    "fee_amount": fee,
                    "total_amount": principal + interest + fee,
                    "schedule_status": status,
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
                row_id += 1

    def iter_bills(self, contracts: list[dict], periods: int):
        row_id = 1
        for contract in contracts:
            principal, interest, fee = self.period_amounts(contract, periods)
            total = principal + interest + fee
            for period in range(1, periods + 1):
                paid = total if row_id % 100 < 82 else 0
                penalty = round(total * 0.01, 2) if not paid else 0
                billed_at = dt(365 - period * 30, 8)
                paid_at = dt(365 - period * 30, 9) if paid else None
                yield {
                    "id": row_id,
                    "bill_no": code("BILL", row_id, 10),
                    "contract_id": contract["id"],
                    "schedule_id": row_id,
                    "customer_id": contract["customer_id"],
                    "period_no": period,
                    "due_date": (dt(365 - period * 30).date() + timedelta(days=contract["id"] % 30)),
                    "currency_code": contract["currency_code"],
                    "principal_amount": principal,
                    "interest_amount": interest,
                    "fee_amount": fee,
                    "penalty_amount": penalty,
                    "reduced_amount": 0,
                    "paid_amount": paid,
                    "written_off_amount": 0,
                    "restructured_amount": 0,
                    "outstanding_amount": 0 if paid else total + penalty,
                    "bill_status": "paid" if paid else "overdue",
                    "billed_at": billed_at,
                    "paid_at": paid_at,
                    "created_at": billed_at,
                    "updated_at": paid_at or billed_at,
                }
                row_id += 1

    def iter_authorizations(self, contracts: list[dict]):
        for row_id, contract in enumerate(contracts, start=1):
            signed_at = dt(row_id % 720, 16)
            yield {
                "id": row_id,
                "authorization_no": code("AUT", row_id, 10),
                "contract_id": contract["id"],
                "customer_id": contract["customer_id"],
                "account_id": contract["repayment_account_id"],
                "authorization_type": "auto_debit",
                "authorization_status": "active",
                "valid_from": signed_at.date(),
                "valid_to": (signed_at + timedelta(days=1095)).date(),
                "signed_at": signed_at,
                "created_at": signed_at,
                "updated_at": signed_at,
            }

    def iter_repayments(self, sources: list[dict], tx_start: int):
        for row_id, source in enumerate(sources, start=1):
            principal = float(source["principal_amount"])
            interest = float(source["interest_amount"])
            fee = float(source["fee_amount"])
            penalty = float(source["penalty_amount"])
            amount = principal + interest + fee + penalty
            repaid_at = source["paid_at"] or source["billed_at"] + timedelta(hours=1)
            yield {
                "id": row_id,
                "repayment_no": code("RPM", row_id, 10),
                "bill_id": source["bill_id"],
                "contract_id": source["contract_id"],
                "customer_id": source["customer_id"],
                "account_id": source["account_id"],
                "transaction_id": tx_start + row_id - 1,
                "authorization_id": source["contract_id"],
                "collection_case_id": None,
                "repayment_promise_id": None,
                "original_repayment_id": None,
                "repayment_type": "normal",
                "currency_code": source["currency_code"],
                "repayment_amount": amount,
                "principal_paid_amount": principal,
                "interest_paid_amount": interest,
                "fee_paid_amount": fee,
                "penalty_paid_amount": penalty,
                "repayment_status": "success",
                "repaid_at": repaid_at,
                "created_at": repaid_at,
                "updated_at": repaid_at,
            }

    def iter_allocations(self, sources: list[dict]):
        for row_id, source in enumerate(sources, start=1):
            principal = float(source["principal_amount"])
            interest = float(source["interest_amount"])
            fee = float(source["fee_amount"])
            penalty = float(source["penalty_amount"])
            created_at = source["paid_at"] or source["billed_at"] + timedelta(hours=1)
            yield {
                "id": row_id,
                "allocation_no": code("ALL", row_id, 10),
                "repayment_id": row_id,
                "bill_id": source["bill_id"],
                "contract_id": source["contract_id"],
                "period_no": source["period_no"],
                "currency_code": source["currency_code"],
                "principal_amount": principal,
                "interest_amount": interest,
                "fee_amount": fee,
                "penalty_amount": penalty,
                "allocated_amount": principal + interest + fee + penalty,
                "created_at": created_at,
            }

    def iter_overdue(self, bills: list[dict]):
        for row_id, bill in enumerate(bills, start=1):
            principal = float(bill["principal_amount"])
            interest = float(bill["interest_amount"])
            fee = float(bill["fee_amount"])
            penalty = float(bill["penalty_amount"])
            created_at = dt(row_id % 180, 8)
            yield {
                "id": row_id,
                "overdue_no": code("OVD", row_id, 10),
                "bill_id": bill["id"],
                "contract_id": bill["contract_id"],
                "customer_id": bill["customer_id"],
                "period_no": bill["period_no"],
                "overdue_start_date": bill["due_date"],
                "overdue_days": 1 + row_id % 120,
                "currency_code": bill["currency_code"],
                "overdue_principal_amount": principal,
                "overdue_interest_amount": interest,
                "overdue_fee_amount": fee,
                "penalty_amount": penalty,
                "overdue_total_amount": bill["outstanding_amount"],
                "paid_amount": 0,
                "reduced_amount": 0,
                "written_off_amount": 0,
                "restructured_amount": 0,
                "recovered_amount": 0,
                "outstanding_amount": bill["outstanding_amount"],
                "overdue_level": "M1" if row_id % 3 else "M2",
                "overdue_status": "active",
                "settled_at": None,
                "created_at": created_at,
                "updated_at": created_at,
            }

    def iter_fee_reduction(self, total: int, overdue_bills: list[dict], employee_ids: list[int]):
        for row_id in range(1, total + 1):
            bill = overdue_bills[(row_id - 1) % len(overdue_bills)]
            approved_at = dt(row_id % 180, 15)
            yield {
                "id": row_id,
                "reduction_no": code("RED", row_id, 10),
                "bill_id": bill["id"],
                "contract_id": bill["contract_id"],
                "customer_id": bill["customer_id"],
                "reduction_type": "penalty",
                "currency_code": bill["currency_code"],
                "apply_amount": 50,
                "approved_amount": 30,
                "approved_interest_amount": 0,
                "approved_fee_amount": 0,
                "approved_penalty_amount": 30,
                "reduction_status": "approved",
                "approved_by": employee_ids[(row_id - 1) % len(employee_ids)],
                "approval_comment": "费用减免审批通过",
                "approved_at": approved_at,
                "created_at": dt(row_id % 180, 14),
                "updated_at": approved_at,
            }
