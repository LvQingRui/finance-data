"""Layer5: credit, loan approval, contract and disbursement."""

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


class Layer5Generator(BaseGenerator):
    layer = 5

    def run(self) -> None:
        self.header()
        clear_tables(LAYERS[self.layer]["tables"])
        customers = fetch_id_values("customer", ["id"], "customer_status <> 'closed'")
        products = fetch_id_values("loan_product", ["id", "currency_code", "min_amount", "max_amount", "annual_interest_rate", "min_term_months", "max_term_months", "repayment_method", "collateral_required_flag", "guarantee_required_flag"])
        self._loan_products = products
        accounts = fetch_id_values("bank_account", ["id", "customer_id", "currency_code"], "account_status = 'normal'")
        channel_ids = fetch_ids("dim_channel", "id > 0")
        employee_ids = fetch_ids("dim_employee")
        risk_ids = fetch_ids("dim_risk_level", "risk_level_type = 'event'")
        tx_days = min(int(GENERATION_DEFAULTS["calendar_days"]), 730)

        credit_count = min(int(GENERATION_DEFAULTS["credit_applications"]), len(customers))
        loan_app_count = min(int(GENERATION_DEFAULTS["loan_applications"]), credit_count)
        approved_application_ids = [
            app_id for app_id in range(1, loan_app_count + 1) if self.is_approved(app_id)
        ]
        contract_count = min(int(GENERATION_DEFAULTS["loan_contracts"]), len(approved_application_ids))
        tx_start = max_id("account_transaction") + 1
        channel_tx_start = max_id("channel_transaction") + 1
        ledger_start = max_id("account_ledger") + 1
        result_start = max_id("reconciliation_result") + 1
        counts: dict[str, int] = {}
        counts["credit_application"] = self.stream_rows("credit_application", self.iter_credit_applications(credit_count, customers, products, channel_ids), total_rows=credit_count, build_step_name="build credit_application")
        counts["credit_application_material"] = self.stream_rows("credit_application_material", self.iter_credit_materials(credit_count, customers, employee_ids), total_rows=credit_count * 3, build_step_name="build credit_application_material")
        counts["credit_approval_record"] = self.stream_rows("credit_approval_record", self.iter_credit_approvals(credit_count, employee_ids), total_rows=credit_count, build_step_name="build credit_approval_record")
        counts["credit_limit"] = self.stream_rows("credit_limit", self.iter_credit_limits(credit_count, customers, products), total_rows=credit_count, build_step_name="build credit_limit")
        counts["loan_application"] = self.stream_rows("loan_application", self.iter_loan_applications(loan_app_count, customers, products, channel_ids), total_rows=loan_app_count, build_step_name="build loan_application")
        counts["loan_application_material"] = self.stream_rows("loan_application_material", self.iter_loan_materials(loan_app_count, customers, employee_ids), total_rows=loan_app_count * 3, build_step_name="build loan_application_material")
        counts["credit_assessment"] = self.stream_rows("credit_assessment", self.iter_credit_assessments(loan_app_count, customers, risk_ids), total_rows=loan_app_count, build_step_name="build credit_assessment")
        counts["loan_approval_record"] = self.stream_rows("loan_approval_record", self.iter_loan_approvals(loan_app_count, products, employee_ids), total_rows=loan_app_count, build_step_name="build loan_approval_record")
        counts["loan_contract"] = self.stream_rows("loan_contract", self.iter_contracts(approved_application_ids[:contract_count], customers, products, accounts), total_rows=contract_count, build_step_name="build loan_contract")
        counts["loan_contract_document"] = self.stream_rows("loan_contract_document", self.iter_contract_documents(contract_count), total_rows=contract_count, build_step_name="build loan_contract_document")
        counts["contract_sign_record"] = self.stream_rows("contract_sign_record", self.iter_sign_records(contract_count, customers, channel_ids), total_rows=contract_count, build_step_name="build contract_sign_record")
        contracts = fetch_id_values(
            "loan_contract",
            [
                "id",
                "application_id",
                "customer_id",
                "repayment_account_id",
                "currency_code",
                "principal_amount",
                "disbursed_at",
            ],
        )
        self._loan_contracts = contracts
        contract_accounts = [
            {
                "id": contract["repayment_account_id"],
                "customer_id": contract["customer_id"],
                "currency_code": contract["currency_code"],
            }
            for contract in contracts
        ]
        collateral_count = max(1, contract_count // 5)
        guarantee_count = max(1, contract_count // 4)
        counts["collateral_asset"] = self.stream_rows("collateral_asset", self.iter_collateral(collateral_count, contracts), total_rows=collateral_count, build_step_name="build collateral_asset")
        counts["guarantee_record"] = self.stream_rows("guarantee_record", self.iter_guarantee(guarantee_count, contracts, customers), total_rows=guarantee_count, build_step_name="build guarantee_record")
        counts["account_transaction"] = self.stream_rows(
            "account_transaction",
            iter_account_transactions(
                start_id=tx_start,
                total=contract_count,
                accounts=contract_accounts,
                channel_ids=channel_ids,
                tx_days=tx_days,
                related_type="loan_contract",
                transaction_type="loan_disbursement",
                prefix="LTX",
                amount_func=self.loan_flow_amount,
                local_now=self.local_now,
                related_ids=[int(contract["id"]) for contract in contracts],
                time_func=self.loan_flow_time,
            ),
            total_rows=contract_count,
            build_step_name="build loan account_transaction",
        )
        counts["channel_transaction"] = self.stream_rows(
            "channel_transaction",
            iter_channel_transactions(
                start_id=channel_tx_start,
                transaction_start_id=tx_start,
                total=contract_count,
                accounts=contract_accounts,
                channel_ids=channel_ids,
                tx_days=tx_days,
                prefix="LCH",
                amount_func=self.loan_flow_amount,
                local_now=self.local_now,
                transaction_prefix="LTX",
                time_func=self.loan_flow_time,
            ),
            total_rows=contract_count,
            build_step_name="build loan channel_transaction",
        )
        counts["account_ledger"] = self.stream_rows(
            "account_ledger",
            iter_account_ledgers(
                start_id=ledger_start,
                transaction_start_id=tx_start,
                total=contract_count,
                accounts=contract_accounts,
                tx_days=tx_days,
                prefix="LLD",
                amount_func=self.loan_flow_amount,
                transaction_type="loan_disbursement",
                time_func=self.loan_flow_time,
            ),
            total_rows=contract_count,
            build_step_name="build loan account_ledger",
        )
        counts["reconciliation_result"] = self.stream_rows(
            "reconciliation_result",
            iter_reconciliation_results(
                start_id=result_start,
                transaction_start_id=tx_start,
                channel_transaction_start_id=channel_tx_start,
                total=contract_count,
                channel_ids=channel_ids,
                tx_days=tx_days,
                prefix="LRC",
                local_now=self.local_now,
            ),
            total_rows=contract_count,
            build_step_name="build loan reconciliation_result",
        )
        counts["loan_disbursement"] = self.stream_rows("loan_disbursement", self.iter_disbursements(contracts, tx_start), total_rows=contract_count, build_step_name="build loan_disbursement")
        counts["credit_limit_change_log"] = self.stream_rows("credit_limit_change_log", self.iter_limit_logs(credit_count, loan_app_count, approved_application_ids[:contract_count], products), total_rows=credit_count + loan_app_count + contract_count, build_step_name="build credit_limit_change_log")
        self.log_table_counts(counts)

    def is_approved(self, row_id: int) -> bool:
        return row_id % 10 < 7

    def amount_for_product(self, product: dict, row_id: int) -> float:
        min_amount = float(product["min_amount"])
        max_amount = float(product["max_amount"])
        return round(min(max_amount, min_amount + (row_id % 20 + 1) * 5000), 2)

    def limit_amount_for_product(self, product: dict, row_id: int) -> float:
        base_amount = 100000 + row_id % 50 * 5000
        return round(max(base_amount, self.amount_for_product(product, row_id) * 2), 2)

    def loan_flow_amount(self, row_id: int, account: dict) -> float:
        return float(self._loan_contracts[row_id - 1]["principal_amount"])

    def loan_flow_time(self, row_id: int, account: dict):
        return self._loan_contracts[row_id - 1]["disbursed_at"]

    def iter_credit_applications(self, total: int, customers: list[dict], products: list[dict], channel_ids: list[int]):
        for row_id in range(1, total + 1):
            customer = customers[(row_id - 1) % len(customers)]
            product = products[(row_id - 1) % len(products)]
            approved = self.is_approved(row_id)
            submitted_at = dt(row_id % 720, 10)
            decision_at = dt(row_id % 720, 12)
            yield {
                "id": row_id,
                "credit_application_no": code("CRA", row_id, 10),
                "customer_id": customer["id"],
                "product_id": product["id"],
                "channel_id": channel_ids[(row_id - 1) % len(channel_ids)],
                "apply_limit_amount": self.amount_for_product(product, row_id) * 2,
                "currency_code": product["currency_code"],
                "application_status": "approved" if approved else "rejected",
                "submitted_at": submitted_at,
                "approved_at": decision_at if approved else None,
                "rejected_at": decision_at if not approved else None,
                "created_at": submitted_at,
                "updated_at": decision_at,
            }

    def iter_credit_materials(self, total: int, customers: list[dict], employee_ids: list[int]):
        row_id = 1
        for app_id in range(1, total + 1):
            for material_type in ("identity", "income", "credit_authorization"):
                verified_at = dt(app_id % 720, 11)
                yield {
                    "id": row_id,
                    "material_no": code("CAM", row_id, 10),
                    "credit_application_id": app_id,
                    "customer_id": customers[(app_id - 1) % len(customers)]["id"],
                    "material_type": material_type,
                    "material_name": f"{material_type}材料",
                    "file_url": f"https://files.example/{row_id}.pdf",
                    "file_hash": f"hash-{row_id:012d}",
                    "submitted_by": "customer",
                    "verification_status": "verified",
                    "verified_by": employee_ids[(row_id - 1) % len(employee_ids)],
                    "verified_at": verified_at,
                    "submitted_at": dt(app_id % 720, 10),
                    "created_at": dt(app_id % 720, 10),
                    "updated_at": verified_at,
                }
                row_id += 1

    def iter_credit_approvals(self, total: int, employee_ids: list[int]):
        for row_id in range(1, total + 1):
            approved = self.is_approved(row_id)
            yield {
                "id": row_id,
                "credit_application_id": row_id,
                "approval_node": "credit_approval",
                "approval_round": 1,
                "approver_id": employee_ids[(row_id - 1) % len(employee_ids)],
                "approval_result": "approved" if approved else "rejected",
                "approved_limit_amount": 100000 + row_id % 50 * 5000 if approved else 0,
                "approval_comment": "审批完成",
                "approved_at": dt(row_id % 720, 12),
                "created_at": dt(row_id % 720, 12),
            }

    def iter_credit_limits(self, total: int, customers: list[dict], products: list[dict]):
        for row_id in range(1, total + 1):
            customer = customers[(row_id - 1) % len(customers)]
            product = products[(row_id - 1) % len(products)]
            amount = self.limit_amount_for_product(product, row_id)
            created_at = dt(row_id % 720, 12)
            yield {
                "id": row_id,
                "limit_no": code("LMT", row_id, 10),
                "credit_application_id": row_id,
                "customer_id": customer["id"],
                "product_id": product["id"],
                "currency_code": product["currency_code"],
                "total_limit_amount": amount,
                "used_limit_amount": 0,
                "frozen_limit_amount": 0,
                "available_limit_amount": amount,
                "limit_status": "active",
                "valid_from": dt(row_id % 720).date(),
                "valid_to": (dt(row_id % 720) + timedelta(days=365)).date(),
                "created_at": created_at,
                "updated_at": created_at,
            }

    def iter_loan_applications(self, total: int, customers: list[dict], products: list[dict], channel_ids: list[int]):
        for row_id in range(1, total + 1):
            customer = customers[(row_id - 1) % len(customers)]
            product = products[(row_id - 1) % len(products)]
            approved = self.is_approved(row_id)
            submitted_at = dt(row_id % 720, 13)
            decision_at = dt(row_id % 720, 15)
            yield {
                "id": row_id,
                "application_no": code("LAP", row_id, 10),
                "customer_id": customer["id"],
                "product_id": product["id"],
                "credit_limit_id": row_id,
                "channel_id": channel_ids[(row_id - 1) % len(channel_ids)],
                "apply_amount": self.amount_for_product(product, row_id),
                "apply_term_months": min(int(product["max_term_months"]), max(int(product["min_term_months"]), 12)),
                "loan_purpose": "consumer" if row_id % 3 else "business",
                "application_status": "approved" if approved else "rejected",
                "risk_decision": "pass" if approved else "reject",
                "submitted_at": submitted_at,
                "approved_at": decision_at if approved else None,
                "rejected_at": decision_at if not approved else None,
                "expired_at": submitted_at + timedelta(days=30),
                "created_at": submitted_at,
                "updated_at": decision_at,
            }

    def iter_loan_materials(self, total: int, customers: list[dict], employee_ids: list[int]):
        row_id = 1
        for app_id in range(1, total + 1):
            for material_type in ("identity", "income", "bank_statement"):
                verified_at = dt(app_id % 720, 14)
                yield {
                    "id": row_id,
                    "material_no": code("LAM", row_id, 10),
                    "application_id": app_id,
                    "customer_id": customers[(app_id - 1) % len(customers)]["id"],
                    "material_type": material_type,
                    "material_name": f"{material_type}材料",
                    "file_url": f"https://files.example/loan/{row_id}.pdf",
                    "file_hash": f"hash-loan-{row_id:012d}",
                    "submitted_by": "customer",
                    "verification_status": "verified",
                    "verified_by": employee_ids[(row_id - 1) % len(employee_ids)],
                    "verified_at": verified_at,
                    "submitted_at": dt(app_id % 720, 13),
                    "created_at": dt(app_id % 720, 13),
                    "updated_at": verified_at,
                }
                row_id += 1

    def iter_credit_assessments(self, total: int, customers: list[dict], risk_ids: list[int]):
        for row_id in range(1, total + 1):
            customer = customers[(row_id - 1) % len(customers)]
            assessed_at = dt(row_id % 720, 14)
            yield {
                "id": row_id,
                "assessment_no": code("CAS", row_id, 10),
                "credit_application_id": row_id,
                "application_id": row_id,
                "customer_id": customer["id"],
                "credit_report_no": code("CRP", row_id, 10),
                "credit_score": 620 + row_id % 260,
                "internal_score": 650 + row_id % 220,
                "debt_income_ratio": 0.25 + (row_id % 20) / 100,
                "monthly_income_amount": 8000 + row_id % 100 * 200,
                "monthly_debt_amount": 1000 + row_id % 50 * 100,
                "existing_loan_count": row_id % 3,
                "existing_credit_card_count": row_id % 4,
                "overdue_count_24m": row_id % 5,
                "max_overdue_days_24m": row_id % 30,
                "query_count_6m": row_id % 8,
                "risk_level_id": risk_ids[(row_id - 1) % len(risk_ids)],
                "assessment_result": "pass" if self.is_approved(row_id) else "reject",
                "assessment_summary": "征信评估完成",
                "assessed_at": assessed_at,
                "created_at": assessed_at,
                "updated_at": assessed_at,
            }

    def iter_loan_approvals(self, total: int, products: list[dict], employee_ids: list[int]):
        for row_id in range(1, total + 1):
            product = products[(row_id - 1) % len(products)]
            approved = self.is_approved(row_id)
            amount = self.amount_for_product(product, row_id)
            yield {
                "id": row_id,
                "application_id": row_id,
                "approval_node": "final_approval",
                "approver_id": employee_ids[(row_id - 1) % len(employee_ids)],
                "approval_round": 1,
                "sequence_no": 1,
                "approval_result": "approved" if approved else "rejected",
                "approval_comment": "贷款审批完成",
                "approved_amount": amount if approved else 0,
                "approved_term_months": min(int(product["max_term_months"]), max(int(product["min_term_months"]), 12)) if approved else 0,
                "approved_rate": product["annual_interest_rate"] if approved else 0,
                "approved_at": dt(row_id % 720, 15),
                "created_at": dt(row_id % 720, 15),
            }

    def accounts_by_customer(self, accounts: list[dict]) -> dict[int, list[dict]]:
        result: dict[int, list[dict]] = {}
        for account in accounts:
            result.setdefault(int(account["customer_id"]), []).append(account)
        return result

    def iter_contracts(self, application_ids: list[int], customers: list[dict], products: list[dict], accounts: list[dict]):
        accounts_by_customer = self.accounts_by_customer(accounts)
        for row_id, application_id in enumerate(application_ids, start=1):
            customer = customers[(application_id - 1) % len(customers)]
            product = products[(application_id - 1) % len(products)]
            customer_accounts = accounts_by_customer[int(customer["id"])]
            account = next(
                (
                    item for item in customer_accounts
                    if item["currency_code"] == product["currency_code"]
                ),
                customer_accounts[0],
            )
            amount = self.amount_for_product(product, application_id)
            term = min(int(product["max_term_months"]), max(int(product["min_term_months"]), 12))
            signed_at = dt(row_id % 720, 16)
            disbursed_at = dt(row_id % 720, 17)
            yield {
                "id": row_id,
                "contract_no": code("LCT", row_id, 10),
                "loan_no": code("LOAN", row_id, 10),
                "application_id": application_id,
                "customer_id": customer["id"],
                "product_id": product["id"],
                "repayment_account_id": account["id"],
                "currency_code": account["currency_code"],
                "principal_amount": amount,
                "disbursed_principal_amount": amount,
                "undisbursed_principal_amount": 0,
                "written_off_principal_amount": 0,
                "restructured_principal_amount": 0,
                "outstanding_principal_amount": round(amount * 0.75, 2),
                "annual_interest_rate": product["annual_interest_rate"],
                "term_months": term,
                "repayment_method": product["repayment_method"],
                "contract_status": "repaying",
                "signed_at": signed_at,
                "disbursed_at": disbursed_at,
                "settled_at": None,
                "created_at": signed_at,
                "updated_at": disbursed_at,
            }

    def iter_contract_documents(self, total: int):
        for row_id in range(1, total + 1):
            created_at = dt(row_id % 720, 16)
            yield {
                "id": row_id,
                "document_no": code("LCD", row_id, 10),
                "contract_id": row_id,
                "document_type": "loan_contract",
                "document_version": 1,
                "file_url": f"https://files.example/contract/{row_id}.pdf",
                "file_hash": f"hash-contract-{row_id:012d}",
                "sign_status": "signed",
                "created_at": created_at,
                "updated_at": created_at,
            }

    def iter_sign_records(self, total: int, customers: list[dict], channel_ids: list[int]):
        for row_id in range(1, total + 1):
            customer = customers[(row_id - 1) % len(customers)]
            signed_at = dt(row_id % 720, 16)
            yield {
                "id": row_id,
                "sign_no": code("SGN", row_id, 10),
                "contract_id": row_id,
                "document_id": row_id,
                "signer_type": "customer",
                "signer_name": f"客户{customer['id']:08d}",
                "sign_channel_id": channel_ids[(row_id - 1) % len(channel_ids)],
                "sign_method": "electronic",
                "seal_no": None,
                "sign_status": "signed",
                "signed_at": signed_at,
                "created_at": signed_at,
                "updated_at": signed_at,
            }

    def iter_collateral(self, total: int, contracts: list[dict]):
        for row_id in range(1, total + 1):
            contract = contracts[(row_id - 1) % len(contracts)]
            appraised_at = dt(row_id % 720, 14)
            yield {
                "id": row_id,
                "collateral_no": code("COL", row_id, 10),
                "application_id": contract["application_id"],
                "contract_id": contract["id"],
                "customer_id": contract["customer_id"],
                "asset_type": "property",
                "asset_name": f"抵押资产{row_id:06d}",
                "asset_owner_name": f"客户{int(contract['customer_id']):08d}",
                "ownership_certificate_no": code("CERT", row_id, 10),
                "currency_code": contract["currency_code"],
                "appraised_value_amount": 300000 + row_id * 1000,
                "pledge_rate": 0.7,
                "secured_amount": 200000 + row_id * 500,
                "appraisal_org": "中州评估",
                "appraised_at": appraised_at,
                "registration_status": "registered",
                "pledge_rank": 1,
                "priority_rule": "first",
                "collateral_status": "pledged",
                "created_at": appraised_at,
                "updated_at": appraised_at,
            }

    def iter_guarantee(self, total: int, contracts: list[dict], customers: list[dict]):
        for row_id in range(1, total + 1):
            contract = contracts[(row_id - 1) % len(contracts)]
            guarantor = customers[row_id % len(customers)]
            guarantee_start_at = dt(row_id % 720, 16)
            yield {
                "id": row_id,
                "guarantee_no": code("GUA", row_id, 10),
                "application_id": contract["application_id"],
                "contract_id": contract["id"],
                "customer_id": contract["customer_id"],
                "guarantor_customer_id": guarantor["id"],
                "guarantor_name": f"保证人{guarantor['id']:08d}",
                "guarantor_identity_type": "id_card",
                "guarantor_identity_no": f"3101011980{row_id:08d}",
                "guarantee_type": "joint",
                "currency_code": contract["currency_code"],
                "guarantee_amount": 100000 + row_id * 1000,
                "guarantee_start_at": guarantee_start_at,
                "guarantee_end_at": guarantee_start_at + timedelta(days=730),
                "guarantee_status": "active",
                "created_at": guarantee_start_at,
                "updated_at": guarantee_start_at,
            }

    def iter_disbursements(self, contracts: list[dict], tx_start: int):
        for row_id, contract in enumerate(contracts, start=1):
            disbursed_at = contract["disbursed_at"]
            yield {
                "id": row_id,
                "disbursement_no": code("DSB", row_id, 10),
                "contract_id": row_id,
                "customer_id": contract["customer_id"],
                "account_id": contract["repayment_account_id"],
                "transaction_id": tx_start + row_id - 1,
                "original_disbursement_id": None,
                "currency_code": contract["currency_code"],
                "disbursement_amount": contract["principal_amount"],
                "disbursement_status": "success",
                "disbursed_at": disbursed_at,
                "created_at": disbursed_at,
                "updated_at": disbursed_at,
            }

    def iter_limit_logs(self, credit_count: int, loan_app_count: int, contract_application_ids: list[int], products: list[dict]):
        row_id = 1
        for limit_id in range(1, credit_count + 1):
            product = products[(limit_id - 1) % len(products)]
            amount = self.limit_amount_for_product(product, limit_id)
            yield {
                "id": row_id,
                "change_no": code("LCL", row_id, 10),
                "credit_limit_id": limit_id,
                "change_seq": 1,
                "credit_application_id": limit_id,
                "loan_application_id": None,
                "contract_id": None,
                "repayment_id": None,
                "change_type": "grant",
                "currency_code": product["currency_code"],
                "change_amount": amount,
                "before_total_amount": 0,
                "after_total_amount": amount,
                "before_used_amount": 0,
                "after_used_amount": 0,
                "before_frozen_amount": 0,
                "after_frozen_amount": 0,
                "before_available_amount": 0,
                "after_available_amount": amount,
                "changed_at": dt(limit_id % 720, 12),
                "created_at": dt(limit_id % 720, 12),
            }
            row_id += 1
        for application_id in range(1, loan_app_count + 1):
            product = products[(application_id - 1) % len(products)]
            total_amount = self.limit_amount_for_product(product, application_id)
            amount = self.amount_for_product(product, application_id)
            yield {
                "id": row_id,
                "change_no": code("LCL", row_id, 10),
                "credit_limit_id": application_id,
                "change_seq": 2,
                "credit_application_id": None,
                "loan_application_id": application_id,
                "contract_id": None,
                "repayment_id": None,
                "change_type": "freeze",
                "currency_code": product["currency_code"],
                "change_amount": amount,
                "before_total_amount": total_amount,
                "after_total_amount": total_amount,
                "before_used_amount": 0,
                "after_used_amount": 0,
                "before_frozen_amount": 0,
                "after_frozen_amount": amount,
                "before_available_amount": total_amount,
                "after_available_amount": max(0, total_amount - amount),
                "changed_at": dt(application_id % 720, 15),
                "created_at": dt(application_id % 720, 15),
            }
            row_id += 1
        for contract_id, application_id in enumerate(contract_application_ids, start=1):
            product = products[(application_id - 1) % len(products)]
            total_amount = self.limit_amount_for_product(product, application_id)
            amount = self.amount_for_product(product, application_id)
            yield {
                "id": row_id,
                "change_no": code("LCL", row_id, 10),
                "credit_limit_id": application_id,
                "change_seq": 3,
                "credit_application_id": None,
                "loan_application_id": application_id,
                "contract_id": contract_id,
                "repayment_id": None,
                "change_type": "use",
                "currency_code": product["currency_code"],
                "change_amount": amount,
                "before_total_amount": total_amount,
                "after_total_amount": total_amount,
                "before_used_amount": 0,
                "after_used_amount": amount,
                "before_frozen_amount": amount,
                "after_frozen_amount": 0,
                "before_available_amount": max(0, total_amount - amount),
                "after_available_amount": max(0, total_amount - amount),
                "changed_at": dt(contract_id % 720, 17),
                "created_at": dt(contract_id % 720, 17),
            }
            row_id += 1
