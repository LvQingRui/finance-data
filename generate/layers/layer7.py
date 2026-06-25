"""Layer7: risk, AML and collection disposal."""

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


class Layer7Generator(BaseGenerator):
    layer = 7

    def run(self) -> None:
        self.header()
        clear_tables(LAYERS[self.layer]["tables"])
        customers = fetch_id_values(
            "customer",
            ["id", "customer_no", "branch_id"],
            "customer_status <> 'closed'",
        )
        transactions = fetch_id_values(
            "account_transaction",
            ["id", "customer_id", "currency_code", "transaction_amount", "transaction_at"],
        )
        loan_applications = fetch_id_values("loan_application", ["id", "customer_id", "submitted_at"])
        overdue = fetch_id_values(
            "overdue_record",
            [
                "id",
                "contract_id",
                "customer_id",
                "currency_code",
                "overdue_start_date",
                "overdue_total_amount",
                "outstanding_amount",
            ],
        )
        collaterals = fetch_id_values(
            "collateral_asset",
            ["id", "contract_id", "customer_id", "currency_code", "secured_amount"],
        )
        contracts = fetch_id_values(
            "loan_contract",
            ["id", "repayment_account_id", "currency_code"],
        )
        ledgers = fetch_id_values("account_ledger", ["id"])
        channel_ids = fetch_ids("dim_channel", "id > 0")
        strategy_ids = fetch_ids("risk_strategy")
        rule_ids = fetch_ids("risk_rule")
        risk_level_ids = fetch_ids("dim_risk_level", "risk_level_type = 'event'")
        employee_ids = fetch_ids("dim_employee")
        collector_ids = fetch_ids("dim_employee", "employee_role = 'collector'")
        risk_employee_ids = fetch_ids("dim_employee", "employee_role = 'risk_officer'")
        risk_count = min(int(GENERATION_DEFAULTS["risk_events"]), len(customers))
        aml_case_count = max(1, risk_count // 5)
        blacklist_count = max(1, risk_count // 8)
        review_count = max(1, risk_count // 2)
        case_count = min(len(overdue), max(1, risk_count // 2))
        action_count = case_count * 4
        promise_count = max(1, case_count // 2)
        legal_count = max(1, case_count // 12)
        write_off_count = max(1, case_count // 15)
        restructure_count = max(1, case_count // 14)
        disposal_count = min(len(collaterals), max(1, case_count // 18))
        perf_days = min(int(GENERATION_DEFAULTS["stat_days"]), 90)
        tx_days = min(int(GENERATION_DEFAULTS["calendar_days"]), 730)
        risk_sources = self.risk_event_sources(risk_count, transactions, loan_applications)
        aml_sources = self.aml_sources(aml_case_count, risk_sources, transactions)

        counts: dict[str, int] = {}
        counts["risk_event"] = self.stream_rows(
            "risk_event",
            self.iter_risk_events(risk_sources, strategy_ids, risk_level_ids),
            total_rows=risk_count,
            build_step_name="build risk_event",
        )
        counts["risk_hit_record"] = self.stream_rows(
            "risk_hit_record",
            self.iter_risk_hits(risk_sources, rule_ids),
            total_rows=risk_count,
            build_step_name="build risk_hit_record",
        )
        counts["blacklist_record"] = self.stream_rows(
            "blacklist_record",
            self.iter_blacklists(blacklist_count, customers, risk_level_ids, risk_employee_ids),
            total_rows=blacklist_count,
            build_step_name="build blacklist_record",
        )
        counts["aml_case"] = self.stream_rows(
            "aml_case",
            self.iter_aml_cases(aml_sources, risk_level_ids),
            total_rows=aml_case_count,
            build_step_name="build aml_case",
        )
        counts["aml_case_transaction"] = self.stream_rows(
            "aml_case_transaction",
            self.iter_aml_case_transactions(aml_sources),
            total_rows=aml_case_count * 3,
            build_step_name="build aml_case_transaction",
        )
        counts["suspicious_transaction_report"] = self.stream_rows(
            "suspicious_transaction_report",
            self.iter_suspicious_reports(aml_sources),
            total_rows=aml_case_count,
            build_step_name="build suspicious_transaction_report",
        )
        counts["aml_review_result"] = self.stream_rows(
            "aml_review_result",
            self.iter_aml_reviews(aml_sources, risk_employee_ids or employee_ids),
            total_rows=aml_case_count,
            build_step_name="build aml_review_result",
        )
        counts["manual_review_task"] = self.stream_rows(
            "manual_review_task",
            self.iter_manual_tasks(review_count, risk_sources, risk_employee_ids or employee_ids),
            total_rows=review_count,
            build_step_name="build manual_review_task",
        )
        counts["collection_case"] = self.stream_rows(
            "collection_case",
            self.iter_collection_cases(case_count, overdue, collector_ids or employee_ids),
            total_rows=case_count,
            build_step_name="build collection_case",
        )
        cases = fetch_id_values(
            "collection_case",
            ["id", "contract_id", "customer_id", "collector_id", "collection_stage", "case_amount", "assigned_at"],
        )
        disposal_sources = self.collateral_disposal_sources(disposal_count, cases, collaterals)
        disposal_count = len(disposal_sources)
        contract_accounts = self.case_accounts(cases, contracts)
        self._collection_repayment_cases = cases
        collection_related_ids = [int(cases[offset % len(cases)]["contract_id"]) for offset in range(promise_count)]
        collection_amount_ids = list(range(1, promise_count + 1))
        tx_start = max_id("account_transaction") + 1
        channel_tx_start = max_id("channel_transaction") + 1
        ledger_start = max_id("account_ledger") + 1
        result_start = max_id("reconciliation_result") + 1
        repayment_start = max_id("repayment_record") + 1
        allocation_start = max_id("repayment_allocation") + 1
        counts["collection_action"] = self.stream_rows(
            "collection_action",
            self.iter_collection_actions(action_count, cases),
            total_rows=action_count,
            build_step_name="build collection_action",
        )
        counts["collection_contact_record"] = self.stream_rows(
            "collection_contact_record",
            self.iter_collection_contacts(action_count, cases, collector_ids or employee_ids),
            total_rows=action_count,
            build_step_name="build collection_contact_record",
        )
        counts["account_transaction"] = self.stream_rows(
            "account_transaction",
            iter_account_transactions(
                start_id=tx_start,
                total=promise_count,
                accounts=contract_accounts,
                channel_ids=channel_ids,
                tx_days=tx_days,
                related_type="loan_contract",
                transaction_type="loan_repayment",
                prefix="CTX",
                amount_func=self.collection_repayment_amount,
                local_now=self.local_now,
                related_ids=collection_related_ids,
                amount_ids=collection_amount_ids,
                time_func=self.collection_repayment_time,
            ),
            total_rows=promise_count,
            build_step_name="build collection account_transaction",
        )
        counts["channel_transaction"] = self.stream_rows(
            "channel_transaction",
            iter_channel_transactions(
                start_id=channel_tx_start,
                transaction_start_id=tx_start,
                total=promise_count,
                accounts=contract_accounts,
                channel_ids=channel_ids,
                tx_days=tx_days,
                prefix="CCH",
                amount_func=self.collection_repayment_amount,
                local_now=self.local_now,
                transaction_prefix="CTX",
                amount_ids=collection_amount_ids,
                time_func=self.collection_repayment_time,
            ),
            total_rows=promise_count,
            build_step_name="build collection channel_transaction",
        )
        counts["account_ledger"] = self.stream_rows(
            "account_ledger",
            iter_account_ledgers(
                start_id=ledger_start,
                transaction_start_id=tx_start,
                total=promise_count,
                accounts=contract_accounts,
                tx_days=tx_days,
                prefix="CLD",
                amount_func=self.collection_repayment_amount,
                amount_ids=collection_amount_ids,
                transaction_type="loan_repayment",
                time_func=self.collection_repayment_time,
            ),
            total_rows=promise_count,
            build_step_name="build collection account_ledger",
        )
        counts["reconciliation_result"] = self.stream_rows(
            "reconciliation_result",
            iter_reconciliation_results(
                start_id=result_start,
                transaction_start_id=tx_start,
                channel_transaction_start_id=channel_tx_start,
                total=promise_count,
                channel_ids=channel_ids,
                tx_days=tx_days,
                prefix="CRC",
                local_now=self.local_now,
            ),
            total_rows=promise_count,
            build_step_name="build collection reconciliation_result",
        )
        counts["repayment_record"] = self.stream_rows(
            "repayment_record",
            self.iter_collection_repayments(repayment_start, promise_count, cases, contract_accounts, tx_start),
            total_rows=promise_count,
            build_step_name="build collection repayment_record",
        )
        counts["repayment_allocation"] = self.stream_rows(
            "repayment_allocation",
            self.iter_collection_allocations(allocation_start, repayment_start, promise_count, cases),
            total_rows=promise_count,
            build_step_name="build collection repayment_allocation",
        )
        counts["repayment_promise"] = self.stream_rows(
            "repayment_promise",
            self.iter_promises(promise_count, cases, repayment_start),
            total_rows=promise_count,
            build_step_name="build repayment_promise",
        )
        counts["legal_case"] = self.stream_rows(
            "legal_case",
            self.iter_legal_cases(legal_count, cases),
            total_rows=legal_count,
            build_step_name="build legal_case",
        )
        counts["loan_write_off"] = self.stream_rows(
            "loan_write_off",
            self.iter_write_offs(write_off_count, cases, employee_ids),
            total_rows=write_off_count,
            build_step_name="build loan_write_off",
        )
        counts["loan_restructure"] = self.stream_rows(
            "loan_restructure",
            self.iter_restructures(restructure_count, cases, employee_ids),
            total_rows=restructure_count,
            build_step_name="build loan_restructure",
        )
        counts["collateral_disposal"] = self.stream_rows(
            "collateral_disposal",
            self.iter_collateral_disposals(
                disposal_sources,
                max_id("repayment_record"),
                max_id("account_transaction"),
                ledgers,
            ),
            total_rows=disposal_count,
            build_step_name="build collateral_disposal",
        )
        counts["collection_performance_daily"] = self.stream_rows(
            "collection_performance_daily",
            self.iter_collection_performance(perf_days),
            total_rows=self.collection_performance_count(perf_days),
            build_step_name="build collection_performance_daily",
        )
        self.log_table_counts(counts)

    def case_accounts(self, cases: list[dict], contracts: list[dict]) -> list[dict]:
        contract_map = {int(contract["id"]): contract for contract in contracts}
        accounts: list[dict] = []
        for case in cases:
            contract = contract_map[int(case["contract_id"])]
            accounts.append(
                {
                    "id": contract["repayment_account_id"],
                    "customer_id": case["customer_id"],
                    "currency_code": contract["currency_code"],
                }
            )
        return accounts

    def collection_repayment_amount(self, row_id: int, account: dict) -> float:
        return round(1000 + row_id % 100 * 25, 2)

    def collection_repayment_time(self, row_id: int, account: dict):
        case = self._collection_repayment_cases[(row_id - 1) % len(self._collection_repayment_cases)]
        return case["assigned_at"] + timedelta(hours=4)

    def risk_event_sources(
        self,
        total: int,
        transactions: list[dict],
        loan_applications: list[dict],
    ) -> list[dict]:
        sources = []
        for row_id in range(1, total + 1):
            if row_id % 2 or not loan_applications:
                tx = transactions[(row_id - 1) % len(transactions)]
                created_at = tx["transaction_at"] + timedelta(minutes=5)
                sources.append(
                    {
                        "id": row_id,
                        "customer_id": tx["customer_id"],
                        "related_type": "account_transaction",
                        "related_id": tx["id"],
                        "event_type": "transaction",
                        "created_at": created_at,
                    }
                )
            else:
                application = loan_applications[(row_id - 1) % len(loan_applications)]
                created_at = application["submitted_at"] + timedelta(hours=2)
                sources.append(
                    {
                        "id": row_id,
                        "customer_id": application["customer_id"],
                        "related_type": "loan_application",
                        "related_id": application["id"],
                        "event_type": "credit_apply",
                        "created_at": created_at,
                    }
                )
        return sources

    def aml_sources(
        self,
        total: int,
        risk_sources: list[dict],
        transactions: list[dict],
    ) -> list[dict]:
        transactions_by_id = {int(tx["id"]): tx for tx in transactions}
        grouped: dict[tuple[int, str], list[dict]] = {}
        for tx in transactions:
            key = (int(tx["customer_id"]), str(tx["currency_code"]))
            if len(grouped.setdefault(key, [])) < 3:
                grouped[key].append(tx)
        account_sources = [
            source for source in risk_sources
            if source["related_type"] == "account_transaction"
        ]
        sources = []
        for index in range(total):
            risk_source = account_sources[index % len(account_sources)]
            primary_tx = transactions_by_id[int(risk_source["related_id"])]
            key = (int(primary_tx["customer_id"]), str(primary_tx["currency_code"]))
            case_transactions = grouped[key]
            if len(case_transactions) < 3:
                raise RuntimeError("AML case source customer has fewer than 3 transactions")
            latest_transaction_at = max(tx["transaction_at"] for tx in case_transactions)
            created_at = max(risk_source["created_at"], latest_transaction_at) + timedelta(minutes=30)
            sources.append(
                {
                    "risk_event_id": risk_source["id"],
                    "customer_id": primary_tx["customer_id"],
                    "primary_transaction_id": primary_tx["id"],
                    "currency_code": primary_tx["currency_code"],
                    "transactions": case_transactions,
                    "total_transaction_amount": sum(
                        float(tx["transaction_amount"]) for tx in case_transactions
                    ),
                    "created_at": created_at,
                }
            )
        return sources

    def iter_risk_events(
        self,
        sources: list[dict],
        strategy_ids: list[int],
        risk_level_ids: list[int],
    ):
        actions = ("pass", "review", "reject", "block")
        for source in sources:
            row_id = int(source["id"])
            score = 10 + row_id % 91
            hit = 1 if score >= 35 else 0
            created_at = source["created_at"]
            yield {
                "id": row_id,
                "event_no": code("REV", row_id, 10),
                "customer_id": source["customer_id"],
                "event_type": source["event_type"],
                "related_type": source["related_type"],
                "related_id": source["related_id"],
                "strategy_id": strategy_ids[(row_id - 1) % len(strategy_ids)],
                "risk_level_id": risk_level_ids[min(len(risk_level_ids) - 1, score // 20)],
                "risk_score": score,
                "decision_action": actions[min(len(actions) - 1, score // 30)],
                "hit_flag": hit,
                "no_hit_reason": None if hit else "below_threshold",
                "decision_reason": "规则评分触发" if hit else "未达到命中阈值",
                "event_status": "closed" if row_id % 5 else "reviewing",
                "created_at": created_at,
                "updated_at": created_at,
            }

    def iter_risk_hits(self, sources: list[dict], rule_ids: list[int]):
        for row_id, source in enumerate(sources, start=1):
            created_at = source["created_at"] + timedelta(minutes=1)
            yield {
                "id": row_id,
                "event_id": source["id"],
                "rule_id": rule_ids[(row_id - 1) % len(rule_ids)],
                "hit_score": 10 + row_id % 80,
                "hit_detail": f"风险规则命中明细 {row_id}",
                "decision_action": "review" if row_id % 4 else "block",
                "created_at": created_at,
            }

    def iter_blacklists(
        self,
        total: int,
        customers: list[dict],
        risk_level_ids: list[int],
        employee_ids: list[int],
    ):
        for row_id in range(1, total + 1):
            customer = customers[(row_id - 1) % len(customers)]
            active = row_id % 6 != 0
            removed_at = None if active else dt(row_id % 120, 16)
            created_at = dt(row_id % 365, 9)
            yield {
                "id": row_id,
                "blacklist_no": code("BLK", row_id, 10),
                "subject_type": "customer",
                "subject_value": customer["customer_no"],
                "risk_level_id": risk_level_ids[-1],
                "blacklist_reason": "严重逾期或疑似欺诈",
                "blacklist_status": "active" if active else "removed",
                "effective_from": dt(row_id % 365).date(),
                "effective_to": None if active else dt(row_id % 120).date(),
                "removed_reason": None if active else "风险解除",
                "removed_by": None if active else employee_ids[(row_id - 1) % len(employee_ids)],
                "removed_at": removed_at,
                "approval_ref": code("APR", row_id, 10),
                "created_at": created_at,
                "updated_at": removed_at or created_at,
            }

    def iter_aml_cases(self, sources: list[dict], risk_level_ids: list[int]):
        for row_id, source in enumerate(sources, start=1):
            closed = row_id % 4 != 0
            opened_at = source["created_at"]
            closed_at = opened_at + timedelta(days=1, hours=6) if closed else None
            yield {
                "id": row_id,
                "case_no": code("AML", row_id, 10),
                "risk_event_id": source["risk_event_id"],
                "customer_id": source["customer_id"],
                "primary_transaction_id": source["primary_transaction_id"],
                "transaction_count": 3,
                "total_transaction_amount": source["total_transaction_amount"],
                "currency_code": source["currency_code"],
                "case_type": "suspicious_transfer",
                "case_status": "closed" if closed else "investigating",
                "risk_level_id": risk_level_ids[min(len(risk_level_ids) - 1, row_id % 5)],
                "case_summary": "可疑交易监测案件",
                "opened_at": opened_at,
                "closed_at": closed_at,
                "created_at": opened_at,
                "updated_at": closed_at or opened_at,
            }

    def iter_aml_case_transactions(self, sources: list[dict]):
        row_id = 1
        for case_id, source in enumerate(sources, start=1):
            for tx in source["transactions"]:
                yield {
                    "id": row_id,
                    "aml_case_id": case_id,
                    "transaction_id": tx["id"],
                    "customer_id": tx["customer_id"],
                    "currency_code": tx["currency_code"],
                    "transaction_amount": tx["transaction_amount"],
                    "included_flag": 1,
                    "include_reason": "纳入可疑交易分析范围",
                    "created_at": source["created_at"],
                }
                row_id += 1

    def iter_suspicious_reports(self, sources: list[dict]):
        for row_id, source in enumerate(sources, start=1):
            reported_at = source["created_at"] + timedelta(hours=1)
            accepted_at = reported_at + timedelta(hours=2) if row_id % 5 else None
            yield {
                "id": row_id,
                "report_no": code("STR", row_id, 10),
                "aml_case_id": row_id,
                "customer_id": source["customer_id"],
                "transaction_count": 3,
                "total_transaction_amount": source["total_transaction_amount"],
                "currency_code": source["currency_code"],
                "report_period_start": (reported_at - timedelta(days=30)).date(),
                "report_period_end": reported_at.date(),
                "report_type": "initial",
                "report_status": "accepted" if row_id % 5 else "submitted",
                "reported_at": reported_at,
                "accepted_at": accepted_at,
                "report_content": "可疑交易报告内容",
                "created_at": reported_at,
                "updated_at": accepted_at or reported_at,
            }

    def iter_aml_reviews(self, sources: list[dict], employee_ids: list[int]):
        for row_id, source in enumerate(sources, start=1):
            reviewed_at = source["created_at"] + timedelta(hours=2)
            yield {
                "id": row_id,
                "review_no": code("AMR", row_id, 10),
                "aml_case_id": row_id,
                "risk_event_id": source["risk_event_id"],
                "reviewer_id": employee_ids[(row_id - 1) % len(employee_ids)],
                "review_result": "confirmed" if row_id % 5 else "monitor",
                "review_comment": "AML复核完成",
                "reviewed_at": reviewed_at,
                "created_at": reviewed_at,
            }

    def iter_manual_tasks(self, total: int, risk_sources: list[dict], employee_ids: list[int]):
        for row_id in range(1, total + 1):
            source = risk_sources[(row_id - 1) % len(risk_sources)]
            done = row_id % 6 != 0
            assigned_at = source["created_at"] + timedelta(hours=1)
            completed_at = assigned_at + timedelta(hours=2) if done else None
            yield {
                "id": row_id,
                "task_no": code("MRT", row_id, 10),
                "customer_id": source["customer_id"],
                "risk_event_id": source["id"],
                "related_type": "risk_event",
                "related_id": source["id"],
                "assignee_id": employee_ids[(row_id - 1) % len(employee_ids)],
                "task_type": "risk_review",
                "task_status": "approved" if done else "processing",
                "review_result": "approved" if done else None,
                "review_comment": "人工复核通过" if done else None,
                "assigned_at": assigned_at,
                "completed_at": completed_at,
                "created_at": assigned_at,
                "updated_at": completed_at or assigned_at,
            }

    def iter_collection_cases(self, total: int, overdue: list[dict], collector_ids: list[int]):
        for row_id in range(1, total + 1):
            item = overdue[row_id - 1]
            closed = row_id % 5 == 0
            overdue_start_at = datetime.combine(item["overdue_start_date"], datetime.min.time()) + timedelta(hours=9)
            assigned_at = max(dt(row_id % 120, 9), overdue_start_at)
            closed_at = assigned_at + timedelta(days=7, hours=8) if closed else None
            yield {
                "id": row_id,
                "case_no": code("CLC", row_id, 10),
                "overdue_id": item["id"],
                "contract_id": item["contract_id"],
                "customer_id": item["customer_id"],
                "collector_id": collector_ids[(row_id - 1) % len(collector_ids)],
                "collection_stage": "M1" if row_id % 3 else "M2",
                "case_status": "closed" if closed else "active",
                "case_amount": item["outstanding_amount"],
                "assigned_at": assigned_at,
                "closed_at": closed_at,
                "created_at": assigned_at,
                "updated_at": closed_at or assigned_at,
            }

    def iter_collection_actions(self, total: int, cases: list[dict]):
        action_types = ("phone_call", "sms", "repayment_plan", "legal_notice")
        for row_id in range(1, total + 1):
            case = cases[(row_id - 1) // 4]
            action_type = action_types[(row_id - 1) % len(action_types)]
            action_at = dt(row_id % 120, 10)
            yield {
                "id": row_id,
                "action_no": code("CLA", row_id, 10),
                "case_id": case["id"],
                "customer_id": case["customer_id"],
                "contract_id": case["contract_id"],
                "action_type": action_type,
                "action_status": "completed",
                "action_result": f"{action_type}处置完成",
                "operator_id": case["collector_id"],
                "action_at": action_at,
                "created_at": action_at,
                "updated_at": action_at,
            }

    def iter_collection_contacts(
        self,
        total: int,
        cases: list[dict],
        collector_ids: list[int],
    ):
        methods = ("phone", "sms", "app", "letter")
        for row_id in range(1, total + 1):
            case = cases[(row_id - 1) // 4]
            yield {
                "id": row_id,
                "case_id": case["id"],
                "collector_id": case["collector_id"],
                "assistant_collector_id": collector_ids[row_id % len(collector_ids)],
                "contact_method": methods[(row_id - 1) % len(methods)],
                "contact_result": "connected" if row_id % 4 else "unreachable",
                "contact_content": "催收联系记录",
                "next_contact_at": dt(row_id % 60, 10) + timedelta(days=3),
                "contacted_at": dt(row_id % 120, 10),
                "created_at": dt(row_id % 120, 10),
            }

    def iter_collection_repayments(
        self,
        start_id: int,
        total: int,
        cases: list[dict],
        accounts: list[dict],
        tx_start: int,
    ):
        for offset in range(total):
            row_id = start_id + offset
            promise_id = offset + 1
            case = cases[offset % len(cases)]
            account = accounts[offset % len(accounts)]
            amount = self.collection_repayment_amount(promise_id, account)
            repaid_at = case["assigned_at"] + timedelta(hours=4)
            yield {
                "id": row_id,
                "repayment_no": code("CRP", row_id, 10),
                "bill_id": None,
                "contract_id": case["contract_id"],
                "customer_id": case["customer_id"],
                "account_id": account["id"],
                "transaction_id": tx_start + offset,
                "authorization_id": None,
                "collection_case_id": case["id"],
                "repayment_promise_id": None,
                "original_repayment_id": None,
                "repayment_type": "collection",
                "currency_code": account["currency_code"],
                "repayment_amount": amount,
                "principal_paid_amount": round(amount * 0.82, 2),
                "interest_paid_amount": round(amount * 0.12, 2),
                "fee_paid_amount": 0,
                "penalty_paid_amount": round(amount * 0.06, 2),
                "repayment_status": "success",
                "repaid_at": repaid_at,
                "created_at": repaid_at,
                "updated_at": repaid_at,
            }

    def iter_collection_allocations(
        self,
        start_id: int,
        repayment_start: int,
        total: int,
        cases: list[dict],
    ):
        for offset in range(total):
            row_id = start_id + offset
            case = cases[offset % len(cases)]
            amount = self.collection_repayment_amount(offset + 1, {})
            yield {
                "id": row_id,
                "allocation_no": code("CAL", row_id, 10),
                "repayment_id": repayment_start + offset,
                "bill_id": None,
                "contract_id": case["contract_id"],
                "period_no": 0,
                "currency_code": "CNY",
                "principal_amount": round(amount * 0.82, 2),
                "interest_amount": round(amount * 0.12, 2),
                "fee_amount": 0,
                "penalty_amount": round(amount * 0.06, 2),
                "allocated_amount": amount,
                "created_at": dt((offset + 1) % 90, 15),
            }

    def iter_promises(self, total: int, cases: list[dict], repayment_start: int):
        for row_id in range(1, total + 1):
            case = cases[(row_id - 1) % len(cases)]
            fulfilled = row_id % 3 != 0
            amount = min(float(case["case_amount"]), 1000 + row_id * 20)
            fulfilled_at = dt(row_id % 60, 15) if fulfilled else None
            created_at = dt(row_id % 120, 10)
            yield {
                "id": row_id,
                "promise_no": code("RPP", row_id, 10),
                "case_id": case["id"],
                "customer_id": case["customer_id"],
                "currency_code": "CNY",
                "promise_amount": amount,
                "promise_date": (dt(row_id % 90).date() + timedelta(days=7)),
                "promise_status": "fulfilled" if fulfilled else "broken",
                "fulfilled_amount": amount if fulfilled else 0,
                "fulfilled_repayment_id": repayment_start + row_id - 1 if fulfilled else None,
                "fulfilled_at": fulfilled_at,
                "created_at": created_at,
                "updated_at": fulfilled_at or created_at,
            }

    def iter_legal_cases(self, total: int, cases: list[dict]):
        for row_id in range(1, total + 1):
            case = cases[(row_id - 1) % len(cases)]
            action_id = (int(case["id"]) - 1) * 4 + 4
            closed = row_id % 4 == 0
            accepted_at = dt(row_id % 90, 9)
            closed_at = dt(row_id % 45, 17) if closed else None
            yield {
                "id": row_id,
                "legal_case_no": code("LGC", row_id, 10),
                "action_id": action_id,
                "case_id": case["id"],
                "contract_id": case["contract_id"],
                "customer_id": case["customer_id"],
                "legal_type": "litigation",
                "legal_status": "closed" if closed else "accepted",
                "claim_amount": case["case_amount"],
                "accepted_at": accepted_at,
                "closed_at": closed_at,
                "created_at": accepted_at,
                "updated_at": closed_at or accepted_at,
            }

    def iter_write_offs(self, total: int, cases: list[dict], employee_ids: list[int]):
        for row_id in range(1, total + 1):
            case = cases[(row_id + total - 1) % len(cases)]
            amount = round(float(case["case_amount"]) * 0.6, 2)
            approved_at = dt(row_id % 90, 15)
            posted_at = dt(row_id % 60, 16) if row_id % 4 else None
            yield {
                "id": row_id,
                "write_off_no": code("WOF", row_id, 10),
                "action_id": (int(case["id"]) - 1) * 4 + 4,
                "case_id": case["id"],
                "contract_id": case["contract_id"],
                "customer_id": case["customer_id"],
                "currency_code": "CNY",
                "apply_amount": amount,
                "approved_amount": amount,
                "approved_principal_amount": round(amount * 0.8, 2),
                "approved_interest_amount": round(amount * 0.15, 2),
                "approved_fee_amount": 0,
                "approved_penalty_amount": round(amount * 0.05, 2),
                "write_off_status": "posted" if row_id % 4 else "approved",
                "approved_by": employee_ids[(row_id - 1) % len(employee_ids)],
                "approval_comment": "核销审批通过",
                "approved_at": approved_at,
                "posted_at": posted_at,
                "created_at": dt(row_id % 90, 14),
                "updated_at": posted_at or approved_at,
            }

    def iter_restructures(self, total: int, cases: list[dict], employee_ids: list[int]):
        for row_id in range(1, total + 1):
            case = cases[(row_id + total * 2 - 1) % len(cases)]
            before = float(case["case_amount"])
            reduced = round(before * 0.08, 2)
            capitalized = round(before * 0.03, 2)
            approved_at = dt(row_id % 90, 16)
            effective_at = dt(row_id % 60, 9)
            yield {
                "id": row_id,
                "restructure_no": code("RST", row_id, 10),
                "action_id": (int(case["id"]) - 1) * 4 + 4,
                "case_id": case["id"],
                "contract_id": case["contract_id"],
                "customer_id": case["customer_id"],
                "before_outstanding_principal_amount": before,
                "capitalized_amount": capitalized,
                "reduced_amount": reduced,
                "after_outstanding_principal_amount": before + capitalized - reduced,
                "original_schedule_version": 1,
                "new_schedule_version": 2,
                "restructure_type": "extension",
                "new_term_months": 24,
                "new_interest_rate": 0.052,
                "restructure_status": "effective",
                "approved_by": employee_ids[(row_id - 1) % len(employee_ids)],
                "approved_at": approved_at,
                "effective_at": effective_at,
                "created_at": dt(row_id % 90, 15),
                "updated_at": effective_at,
            }

    def iter_collateral_disposals(
        self,
        sources: list[dict],
        repayment_count: int,
        transaction_count: int,
        ledgers: list[dict],
    ):
        for row_id, source in enumerate(sources, start=1):
            case = source["case"]
            collateral = source["collateral"]
            amount = round(float(collateral["secured_amount"]) * 0.7, 2)
            completed_at = dt(row_id % 60, 16)
            yield {
                "id": row_id,
                "disposal_no": code("DSP", row_id, 10),
                "action_id": (int(case["id"]) - 1) * 4 + 4,
                "case_id": case["id"],
                "collateral_id": collateral["id"],
                "contract_id": collateral["contract_id"],
                "customer_id": collateral["customer_id"],
                "repayment_id": row_id if row_id <= repayment_count else None,
                "transaction_id": row_id if row_id <= transaction_count else None,
                "ledger_id": ledgers[(row_id - 1) % len(ledgers)]["id"] if ledgers else None,
                "currency_code": collateral["currency_code"],
                "disposal_method": "auction",
                "disposal_amount": amount,
                "received_amount": round(amount * 0.95, 2),
                "disposal_status": "completed",
                "completed_at": completed_at,
                "created_at": dt(row_id % 90, 11),
                "updated_at": completed_at,
            }

    def collateral_disposal_sources(
        self,
        total: int,
        cases: list[dict],
        collaterals: list[dict],
    ) -> list[dict]:
        collaterals_by_contract: dict[int, list[dict]] = {}
        for collateral in collaterals:
            collaterals_by_contract.setdefault(int(collateral["contract_id"]), []).append(collateral)
        matched = [
            {
                "case": case,
                "collateral": collaterals_by_contract[int(case["contract_id"])][0],
            }
            for case in cases
            if int(case["contract_id"]) in collaterals_by_contract
        ]
        if not matched:
            raise RuntimeError("no collection case can be matched to collateral asset")
        return [matched[index % len(matched)] for index in range(total)]

    def collection_performance_count(self, days: int) -> int:
        return len(self.collection_performance_rows(days))

    def iter_collection_performance(self, days: int):
        for row in self.collection_performance_rows(days):
            yield row

    def collection_performance_rows(self, days: int) -> list[dict]:
        start_date = dt(days - 1).date()
        metrics: dict[tuple, dict] = {}

        def bucket(stat_date, collector_id, branch_id, stage, currency_code="CNY") -> dict:
            key = (stat_date, int(collector_id), int(branch_id), stage, currency_code)
            if key not in metrics:
                metrics[key] = {
                    "stat_date": stat_date,
                    "collector_id": int(collector_id),
                    "branch_id": int(branch_id),
                    "collection_stage": stage,
                    "assigned_case_count": 0,
                    "active_case_count": 0,
                    "contact_attempt_count": 0,
                    "connected_count": 0,
                    "promise_count": 0,
                    "currency_code": currency_code,
                    "assigned_amount": 0,
                    "promised_amount": 0,
                    "recovered_amount": 0,
                    "settled_case_count": 0,
                    "broken_promise_count": 0,
                }
            return metrics[key]

        for row in db.fetch_all(
            """
            SELECT
                DATE(collection_case.created_at) AS stat_date,
                collection_case.collector_id,
                employee.branch_id,
                collection_case.collection_stage,
                overdue.currency_code,
                collection_case.case_status,
                COUNT(*) AS assigned_case_count,
                SUM(collection_case.case_amount) AS assigned_amount
            FROM collection_case
            JOIN overdue_record overdue ON overdue.id = collection_case.overdue_id
            JOIN dim_employee employee ON employee.id = collection_case.collector_id
            WHERE DATE(collection_case.created_at) >= %s
            GROUP BY
                DATE(collection_case.created_at),
                collection_case.collector_id,
                employee.branch_id,
                collection_case.collection_stage,
                overdue.currency_code,
                collection_case.case_status
            """,
            (start_date,),
        ):
            item = bucket(
                row["stat_date"],
                row["collector_id"],
                row["branch_id"],
                row["collection_stage"],
                row["currency_code"],
            )
            item["assigned_case_count"] += int(row["assigned_case_count"])
            item["assigned_amount"] += float(row["assigned_amount"] or 0)
            if row["case_status"] == "active":
                item["active_case_count"] += int(row["assigned_case_count"])
            if row["case_status"] == "closed":
                item["settled_case_count"] += int(row["assigned_case_count"])

        for row in db.fetch_all(
            """
            SELECT
                DATE(contact.contacted_at) AS stat_date,
                collection_case.collector_id,
                employee.branch_id,
                collection_case.collection_stage,
                contact.contact_result,
                COUNT(*) AS contact_count
            FROM collection_contact_record contact
            JOIN collection_case ON collection_case.id = contact.case_id
            JOIN dim_employee employee ON employee.id = collection_case.collector_id
            WHERE DATE(contact.contacted_at) >= %s
            GROUP BY
                DATE(contact.contacted_at),
                collection_case.collector_id,
                employee.branch_id,
                collection_case.collection_stage,
                contact.contact_result
            """,
            (start_date,),
        ):
            item = bucket(
                row["stat_date"],
                row["collector_id"],
                row["branch_id"],
                row["collection_stage"],
            )
            item["contact_attempt_count"] += int(row["contact_count"])
            if row["contact_result"] == "connected":
                item["connected_count"] += int(row["contact_count"])

        for row in db.fetch_all(
            """
            SELECT
                DATE(promise.created_at) AS stat_date,
                collection_case.collector_id,
                employee.branch_id,
                collection_case.collection_stage,
                promise.promise_status,
                COUNT(*) AS promise_count,
                SUM(promise.promise_amount) AS promised_amount
            FROM repayment_promise promise
            JOIN collection_case ON collection_case.id = promise.case_id
            JOIN dim_employee employee ON employee.id = collection_case.collector_id
            WHERE DATE(promise.created_at) >= %s
            GROUP BY
                DATE(promise.created_at),
                collection_case.collector_id,
                employee.branch_id,
                collection_case.collection_stage,
                promise.promise_status
            """,
            (start_date,),
        ):
            item = bucket(
                row["stat_date"],
                row["collector_id"],
                row["branch_id"],
                row["collection_stage"],
            )
            item["promise_count"] += int(row["promise_count"])
            item["promised_amount"] += float(row["promised_amount"] or 0)
            if row["promise_status"] == "broken":
                item["broken_promise_count"] += int(row["promise_count"])

        for row in db.fetch_all(
            """
            SELECT
                DATE(repayment.repaid_at) AS stat_date,
                collection_case.collector_id,
                employee.branch_id,
                collection_case.collection_stage,
                repayment.currency_code,
                SUM(repayment.repayment_amount) AS recovered_amount
            FROM repayment_record repayment
            JOIN collection_case ON collection_case.id = repayment.collection_case_id
            JOIN dim_employee employee ON employee.id = collection_case.collector_id
            WHERE repayment.repayment_type = 'collection'
              AND repayment.repayment_status = 'success'
              AND DATE(repayment.repaid_at) >= %s
            GROUP BY
                DATE(repayment.repaid_at),
                collection_case.collector_id,
                employee.branch_id,
                collection_case.collection_stage,
                repayment.currency_code
            """,
            (start_date,),
        ):
            item = bucket(
                row["stat_date"],
                row["collector_id"],
                row["branch_id"],
                row["collection_stage"],
                row["currency_code"],
            )
            item["recovered_amount"] += float(row["recovered_amount"] or 0)

        rows = []
        row_id = 1
        for key in sorted(metrics):
            item = metrics[key]
            assigned_amount = item["assigned_amount"]
            recovered_amount = item["recovered_amount"]
            rows.append(
                {
                    "id": row_id,
                    "stat_date": item["stat_date"],
                    "collector_id": item["collector_id"],
                    "branch_id": item["branch_id"],
                    "collection_stage": item["collection_stage"],
                    "assigned_case_count": item["assigned_case_count"],
                    "active_case_count": item["active_case_count"],
                    "contact_attempt_count": item["contact_attempt_count"],
                    "connected_count": item["connected_count"],
                    "promise_count": item["promise_count"],
                    "currency_code": item["currency_code"],
                    "assigned_amount": round(assigned_amount, 2),
                    "promised_amount": round(item["promised_amount"], 2),
                    "recovered_amount": round(recovered_amount, 2),
                    "settled_case_count": item["settled_case_count"],
                    "broken_promise_count": item["broken_promise_count"],
                    "recovery_rate": round(recovered_amount / assigned_amount, 6) if assigned_amount else 0,
                    "created_at": dt(0, 23),
                }
            )
            row_id += 1
        return rows
