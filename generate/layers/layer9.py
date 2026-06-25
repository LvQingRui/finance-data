"""Layer9: final validation."""

from __future__ import annotations

from ..config import GENERATION_DEFAULTS, LAYERS
from ..db import db
from .base import BaseGenerator
from .common import table_count


class Layer9Generator(BaseGenerator):
    layer = 9

    def run(self) -> None:
        self.header()
        required_tables = [
            table
            for layer_no, layer in LAYERS.items()
            if layer_no != self.layer
            for table in layer["tables"]
        ]
        empty_tables = [table for table in required_tables if table_count(table) == 0]
        if empty_tables:
            raise RuntimeError(f"empty generated tables: {', '.join(empty_tables)}")

        broken_refs = self.find_broken_references()
        if broken_refs:
            details = ", ".join(
                f"{item['table_name']}.{item['constraint_name']}"
                for item in broken_refs
            )
            raise RuntimeError(f"broken generated references: {details}")

        self.validate_scale_targets()
        self.validate_field_distribution()
        self.validate_business_unique_keys()
        self.validate_subject_consistency()
        self.validate_aml_consistency()
        self.validate_collection_consistency()
        self.validate_workflow_consistency()
        self.validate_cross_layer_append_consistency()
        self.validate_global_time_order()
        self.validate_amount_closure()
        self.validate_status_flow()
        self.validate_business_stats_traceability()
        self.validate_recent_indicators()

        counts = {table: table_count(table) for table in required_tables}
        self.log_table_counts(counts)
        self.log("  [OK] generated data validation passed")

    def expect_zero(self, sql: str, message: str, params: tuple | None = None) -> None:
        row = db.fetch_one(sql, params)
        count = int(row["cnt"]) if row else 0
        if count:
            raise RuntimeError(f"{message}: {count}")

    def expect_min_count(self, table: str, expected: int, message: str) -> None:
        actual = table_count(table)
        if actual < expected:
            raise RuntimeError(f"{message}: expected >= {expected}, actual {actual}")

    def validate_scale_targets(self) -> None:
        customers = int(GENERATION_DEFAULTS["customers"])
        transactions = int(GENERATION_DEFAULTS["transactions"])
        wealth_orders = int(GENERATION_DEFAULTS["wealth_orders"])
        credit_applications = int(GENERATION_DEFAULTS["credit_applications"])
        loan_applications = int(GENERATION_DEFAULTS["loan_applications"])
        loan_contracts = int(GENERATION_DEFAULTS["loan_contracts"])
        support_tickets = int(GENERATION_DEFAULTS["support_tickets"])
        stat_days = int(GENERATION_DEFAULTS["stat_days"])
        branch_count = self.scalar_count("dim_branch", "id >= 0")
        channel_count = self.scalar_count("dim_channel", "id >= 0")
        metric_count = table_count("business_metric_dict")

        self.expect_min_count("customer", customers, "customer scale target not reached")
        self.expect_min_count("account_transaction", transactions, "transaction scale target not reached")
        self.expect_min_count("wealth_order", wealth_orders, "wealth order scale target not reached")
        self.expect_min_count("credit_application", credit_applications, "credit application scale target not reached")
        self.expect_min_count("loan_application", loan_applications, "loan application scale target not reached")
        self.expect_min_count("loan_contract", loan_contracts, "loan contract scale target not reached")
        self.expect_min_count("support_ticket", support_tickets, "support ticket scale target not reached")
        self.expect_min_count(
            "business_stat_daily",
            stat_days * branch_count * channel_count * metric_count,
            "business stat scale target not reached",
        )

    def scalar_count(self, table: str, where: str) -> int:
        row = db.fetch_one(f"SELECT COUNT(*) AS cnt FROM `{table}` WHERE {where}")
        return int(row["cnt"]) if row else 0

    def validate_field_distribution(self) -> None:
        checks = [
            ("customer", "customer_type", 2),
            ("customer", "customer_status", 3),
            ("account_transaction", "transaction_type", 6),
            ("wealth_order", "order_type", 2),
            ("loan_application", "application_status", 2),
            ("repayment_bill", "bill_status", 2),
            ("collection_case", "collection_stage", 2),
            ("support_ticket", "ticket_status", 2),
        ]
        for table, column, expected in checks:
            row = db.fetch_one(f"SELECT COUNT(DISTINCT `{column}`) AS cnt FROM `{table}`")
            actual = int(row["cnt"]) if row else 0
            if actual < expected:
                raise RuntimeError(
                    f"{table}.{column} distribution too narrow: expected >= {expected}, actual {actual}"
                )

    def validate_business_unique_keys(self) -> None:
        checks = [
            ("customer", "customer_no"),
            ("bank_account", "account_no"),
            ("account_transaction", "transaction_no"),
            ("channel_transaction", "channel_txn_no"),
            ("wealth_order", "order_no"),
            ("credit_application", "credit_application_no"),
            ("loan_application", "application_no"),
            ("loan_contract", "contract_no"),
            ("repayment_bill", "bill_no"),
            ("repayment_record", "repayment_no"),
            ("collection_case", "case_no"),
            ("support_ticket", "ticket_no"),
        ]
        for table, column in checks:
            self.expect_zero(
                f"""
                SELECT COUNT(*) AS cnt
                FROM (
                    SELECT `{column}`
                    FROM `{table}`
                    GROUP BY `{column}`
                    HAVING COUNT(*) > 1
                ) duplicated
                """,
                f"{table}.{column} has duplicate business keys",
            )

    def validate_subject_consistency(self) -> None:
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM wealth_order wo
            JOIN bank_account acct ON acct.id = wo.account_id
            JOIN customer_risk_assessment assessment
                ON assessment.id = wo.risk_assessment_id
            WHERE wo.customer_id <> acct.customer_id
               OR wo.customer_id <> assessment.customer_id
            """,
            "wealth order customer, account or assessment mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM loan_contract contract
            JOIN loan_application application
                ON application.id = contract.application_id
            JOIN loan_disbursement disbursement
                ON disbursement.contract_id = contract.id
            JOIN bank_account account
                ON account.id = contract.repayment_account_id
            WHERE contract.customer_id <> application.customer_id
               OR contract.customer_id <> disbursement.customer_id
               OR contract.customer_id <> account.customer_id
               OR contract.currency_code <> disbursement.currency_code
               OR contract.currency_code <> account.currency_code
            """,
            "loan contract, application, disbursement or repayment account customer mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM repayment_record repayment
            JOIN loan_contract contract
                ON contract.id = repayment.contract_id
            LEFT JOIN bank_account account
                ON account.id = repayment.account_id
            WHERE repayment.customer_id <> contract.customer_id
               OR (
                   account.id IS NOT NULL
                   AND repayment.customer_id <> account.customer_id
               )
               OR (
                   account.id IS NOT NULL
                   AND repayment.currency_code <> account.currency_code
               )
            """,
            "repayment customer, contract or account mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM credit_application_material material
            JOIN credit_application application
                ON application.id = material.credit_application_id
            WHERE material.customer_id <> application.customer_id
            """,
            "credit application material customer mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM loan_application_material material
            JOIN loan_application application
                ON application.id = material.application_id
            WHERE material.customer_id <> application.customer_id
            """,
            "loan application material customer mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM collateral_asset collateral
            JOIN loan_contract contract ON contract.id = collateral.contract_id
            WHERE collateral.customer_id <> contract.customer_id
               OR collateral.application_id <> contract.application_id
            """,
            "collateral customer or application mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM guarantee_record guarantee_record
            JOIN loan_contract contract ON contract.id = guarantee_record.contract_id
            WHERE guarantee_record.customer_id <> contract.customer_id
               OR guarantee_record.application_id <> contract.application_id
            """,
            "guarantee customer or application mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM risk_event event
            LEFT JOIN account_transaction tx
                ON event.related_type = 'account_transaction'
                AND tx.id = event.related_id
            LEFT JOIN loan_application application
                ON event.related_type = 'loan_application'
                AND application.id = event.related_id
            WHERE (
                    event.related_type = 'account_transaction'
                    AND (
                        tx.id IS NULL
                        OR tx.customer_id <> event.customer_id
                        OR event.created_at < tx.transaction_at
                    )
                )
               OR (
                    event.related_type = 'loan_application'
                    AND (
                        application.id IS NULL
                        OR application.customer_id <> event.customer_id
                        OR event.created_at < application.submitted_at
                    )
                )
            """,
            "risk event related subject mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM manual_review_task task
            JOIN risk_event event ON event.id = task.risk_event_id
            WHERE task.risk_event_id IS NOT NULL
              AND task.task_type = 'risk_review'
              AND (
                  task.customer_id <> event.customer_id
                  OR task.related_type <> 'risk_event'
                  OR task.related_id <> event.id
                  OR task.assigned_at < event.created_at
                  OR task.created_at < event.created_at
              )
            """,
            "manual review task subject mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM manual_review_task task
            WHERE (
                    task.task_status IN ('approved', 'rejected')
                    AND (
                        task.completed_at IS NULL
                        OR task.review_result IS NULL
                    )
                )
               OR (
                    task.task_status = 'pending'
                    AND task.completed_at IS NOT NULL
                )
               OR (
                    task.task_type IN ('risk_review', 'aml_review')
                    AND task.risk_event_id IS NULL
                )
               OR (
                    task.task_type = 'loan_review'
                    AND task.related_type NOT IN ('credit_application', 'loan_application')
                )
               OR (
                    task.task_type = 'wealth_review'
                    AND task.related_type <> 'wealth_order'
                )
               OR (
                    task.task_type = 'fee_reduction_review'
                    AND task.related_type <> 'fee_reduction'
                )
            """,
            "manual review task status mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM notification_message message
            LEFT JOIN account_transaction tx
                ON message.related_type = 'account_transaction'
                AND tx.id = message.related_id
            LEFT JOIN repayment_bill bill
                ON message.related_type = 'repayment_bill'
                AND bill.id = message.related_id
            LEFT JOIN wealth_order wo
                ON message.related_type = 'wealth_order'
                AND wo.id = message.related_id
            LEFT JOIN loan_contract contract
                ON message.related_type = 'loan_contract'
                AND contract.id = message.related_id
            LEFT JOIN collection_case collection
                ON message.related_type = 'collection_case'
                AND collection.id = message.related_id
            LEFT JOIN support_ticket ticket
                ON message.related_type = 'support_ticket'
                AND ticket.id = message.related_id
            WHERE (
                    message.related_type = 'account_transaction'
                    AND (
                        tx.id IS NULL
                        OR tx.customer_id <> message.customer_id
                        OR message.created_at < tx.transaction_at
                        OR (
                            message.sent_at IS NOT NULL
                            AND message.sent_at < tx.transaction_at
                        )
                    )
                )
               OR (
                    message.related_type = 'repayment_bill'
                    AND (
                        bill.id IS NULL
                        OR bill.customer_id <> message.customer_id
                        OR message.created_at < bill.created_at
                        OR (
                            message.sent_at IS NOT NULL
                            AND message.sent_at < bill.created_at
                        )
                    )
                )
               OR (
                    message.related_type = 'wealth_order'
                    AND (
                        wo.id IS NULL
                        OR wo.customer_id <> message.customer_id
                        OR message.created_at < wo.submitted_at
                    )
                )
               OR (
                    message.related_type = 'loan_contract'
                    AND (
                        contract.id IS NULL
                        OR contract.customer_id <> message.customer_id
                        OR message.created_at < contract.signed_at
                    )
                )
               OR (
                    message.related_type = 'collection_case'
                    AND (
                        collection.id IS NULL
                        OR collection.customer_id <> message.customer_id
                        OR message.created_at < collection.assigned_at
                    )
                )
               OR (
                    message.related_type = 'support_ticket'
                    AND (
                        ticket.id IS NULL
                        OR ticket.customer_id <> message.customer_id
                        OR message.created_at < ticket.created_at
                    )
                )
               OR (
                    message.related_type = 'none'
                    AND message.related_id IS NOT NULL
                )
            """,
            "notification related subject mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM notification_message message
            WHERE (
                    message.send_channel = 'app_push'
                    AND NOT EXISTS (
                        SELECT 1
                        FROM customer_device device
                        WHERE device.customer_id = message.customer_id
                          AND device.device_type IN ('ios', 'android')
                          AND device.push_token IS NOT NULL
                          AND device.risk_status <> 'blacklisted'
                    )
                )
               OR (
                    message.send_channel = 'sms'
                    AND NOT EXISTS (
                        SELECT 1
                        FROM customer_contact contact
                        WHERE contact.customer_id = message.customer_id
                          AND contact.contact_type = 'mobile'
                          AND contact.verified_flag = 1
                    )
                )
               OR (
                    message.send_channel = 'email'
                    AND NOT EXISTS (
                        SELECT 1
                        FROM customer_contact contact
                        WHERE contact.customer_id = message.customer_id
                          AND contact.contact_type = 'email'
                          AND contact.verified_flag = 1
                    )
                )
               OR message.send_channel NOT IN (
                    'sms',
                    'email',
                    'app_push',
                    'site_message'
                )
               OR message.message_type NOT IN (
                    'account',
                    'transaction',
                    'wealth',
                    'loan',
                    'repayment',
                    'collection',
                    'system'
                )
            """,
            "notification channel reachability mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM support_ticket ticket
            LEFT JOIN account_transaction tx
                ON ticket.related_type = 'account_transaction'
                AND tx.id = ticket.related_id
            LEFT JOIN repayment_bill bill
                ON ticket.related_type = 'repayment_bill'
                AND bill.id = ticket.related_id
            WHERE (
                    ticket.related_type = 'account_transaction'
                    AND (
                        tx.id IS NULL
                        OR tx.customer_id <> ticket.customer_id
                        OR ticket.submitted_at < tx.transaction_at
                    )
                )
               OR (
                    ticket.related_type = 'repayment_bill'
                    AND (
                        bill.id IS NULL
                        OR bill.customer_id <> ticket.customer_id
                        OR ticket.submitted_at < bill.created_at
                    )
                )
            """,
            "support ticket related subject or time mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM support_ticket_feedback feedback
            JOIN support_ticket ticket ON ticket.id = feedback.ticket_id
            WHERE feedback.customer_id <> ticket.customer_id
               OR ticket.ticket_status NOT IN ('closed', 'resolved')
               OR feedback.confirm_status NOT IN ('confirmed', 'not_confirmed', 'disputed')
               OR (
                    feedback.satisfaction_score IS NOT NULL
                    AND (
                        feedback.satisfaction_score < 1
                        OR feedback.satisfaction_score > 5
                    )
                )
               OR feedback.created_at < COALESCE(
                    ticket.closed_at,
                    ticket.handled_at,
                    ticket.submitted_at,
                    ticket.created_at
                )
               OR (
                    feedback.confirm_status = 'confirmed'
                    AND (
                        feedback.confirmed_at IS NULL
                        OR feedback.confirmed_at < feedback.created_at
                    )
                )
               OR (
                    feedback.confirm_status = 'not_confirmed'
                    AND feedback.confirmed_at IS NOT NULL
                )
            """,
            "support ticket feedback subject or time mismatch",
        )

    def validate_workflow_consistency(self) -> None:
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM workflow_instance workflow
            LEFT JOIN credit_application credit_application
                ON workflow.related_type = 'credit_application'
                AND credit_application.id = workflow.related_id
            LEFT JOIN loan_application application
                ON workflow.related_type = 'loan_application'
                AND application.id = workflow.related_id
            LEFT JOIN wealth_order wo
                ON workflow.related_type = 'wealth_order'
                AND wo.id = workflow.related_id
            LEFT JOIN risk_event event
                ON workflow.related_type = 'risk_event'
                AND event.id = workflow.related_id
            LEFT JOIN support_ticket ticket
                ON workflow.related_type = 'support_ticket'
                AND ticket.id = workflow.related_id
            LEFT JOIN fee_reduction reduction
                ON workflow.related_type = 'fee_reduction'
                AND reduction.id = workflow.related_id
            WHERE (
                    workflow.related_type = 'credit_application'
                    AND workflow.started_at < credit_application.submitted_at
                )
               OR (
                    workflow.related_type = 'loan_application'
                    AND workflow.started_at < application.submitted_at
                )
               OR (
                    workflow.related_type = 'wealth_order'
                    AND workflow.started_at < wo.submitted_at
                )
               OR (
                    workflow.related_type = 'credit_application'
                    AND credit_application.id IS NULL
                )
               OR (
                    workflow.related_type = 'wealth_order'
                    AND wo.id IS NULL
                )
               OR (
                    workflow.related_type = 'risk_event'
                    AND workflow.started_at < event.created_at
                )
               OR (
                    workflow.related_type = 'support_ticket'
                    AND workflow.started_at < ticket.created_at
                )
               OR (
                    workflow.related_type = 'fee_reduction'
                    AND workflow.started_at < reduction.created_at
                )
               OR (
                    workflow.instance_status IN ('approved', 'rejected', 'cancelled', 'completed')
                    AND workflow.completed_at IS NULL
                )
               OR (
                    workflow.instance_status = 'running'
                    AND workflow.completed_at IS NOT NULL
                )
               OR (
                    workflow.workflow_type = 'loan_approval'
                    AND workflow.related_type NOT IN ('credit_application', 'loan_application')
                )
               OR (
                    workflow.workflow_type = 'wealth_review'
                    AND workflow.related_type NOT IN ('wealth_order', 'risk_event')
                )
               OR (
                    workflow.workflow_type = 'fee_reduction'
                    AND workflow.related_type <> 'fee_reduction'
                )
               OR (
                    workflow.workflow_type = 'risk_review'
                    AND workflow.related_type <> 'risk_event'
                )
               OR (
                    workflow.workflow_type = 'support_ticket'
                    AND workflow.related_type <> 'support_ticket'
                )
            """,
            "workflow related time mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM workflow_task task
            JOIN workflow_instance workflow ON workflow.id = task.instance_id
            WHERE task.assigned_at < workflow.started_at
               OR (
                   workflow.completed_at IS NOT NULL
                   AND task.completed_at > workflow.completed_at
               )
               OR (
                   task.task_status IN ('approved', 'rejected', 'skipped', 'cancelled')
                   AND task.completed_at IS NULL
               )
               OR (
                   task.task_status NOT IN ('approved', 'rejected', 'skipped', 'cancelled')
                   AND task.completed_at IS NOT NULL
               )
            """,
            "workflow task time mismatch",
        )

    def validate_aml_consistency(self) -> None:
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM aml_case aml_case
            JOIN risk_event event ON event.id = aml_case.risk_event_id
            JOIN account_transaction tx
                ON tx.id = aml_case.primary_transaction_id
            WHERE aml_case.customer_id <> event.customer_id
               OR aml_case.customer_id <> tx.customer_id
               OR aml_case.currency_code <> tx.currency_code
               OR aml_case.opened_at < event.created_at
               OR aml_case.opened_at < tx.transaction_at
            """,
            "AML case primary subject mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM aml_case_transaction detail
            JOIN aml_case aml_case ON aml_case.id = detail.aml_case_id
            JOIN account_transaction tx ON tx.id = detail.transaction_id
            WHERE detail.customer_id <> aml_case.customer_id
               OR detail.customer_id <> tx.customer_id
               OR detail.currency_code <> aml_case.currency_code
               OR detail.currency_code <> tx.currency_code
               OR ABS(detail.transaction_amount - tx.transaction_amount) > 0.01
               OR detail.created_at < tx.transaction_at
               OR detail.created_at < aml_case.opened_at
            """,
            "AML case transaction detail mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM aml_case aml_case
            JOIN (
                SELECT
                    aml_case_id,
                    COUNT(*) AS transaction_count,
                    SUM(transaction_amount) AS total_transaction_amount
                FROM aml_case_transaction
                WHERE included_flag = 1
                GROUP BY aml_case_id
            ) detail ON detail.aml_case_id = aml_case.id
            WHERE aml_case.transaction_count <> detail.transaction_count
               OR ABS(aml_case.total_transaction_amount - detail.total_transaction_amount) > 0.01
            """,
            "AML case detail aggregate mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM suspicious_transaction_report report
            JOIN aml_case aml_case ON aml_case.id = report.aml_case_id
            WHERE report.customer_id <> aml_case.customer_id
               OR report.currency_code <> aml_case.currency_code
               OR report.transaction_count <> aml_case.transaction_count
               OR ABS(report.total_transaction_amount - aml_case.total_transaction_amount) > 0.01
               OR report.reported_at < aml_case.opened_at
            """,
            "suspicious transaction report mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM aml_review_result review
            JOIN aml_case aml_case ON aml_case.id = review.aml_case_id
            WHERE review.risk_event_id <> aml_case.risk_event_id
               OR review.reviewed_at < aml_case.opened_at
            """,
            "AML review event mismatch",
        )

    def validate_collection_consistency(self) -> None:
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM collection_case collection_case
            JOIN overdue_record overdue ON overdue.id = collection_case.overdue_id
            WHERE collection_case.customer_id <> overdue.customer_id
               OR collection_case.contract_id <> overdue.contract_id
               OR ABS(collection_case.case_amount - overdue.outstanding_amount) > 0.01
               OR DATE(collection_case.assigned_at) < overdue.overdue_start_date
            """,
            "collection case overdue mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM collection_action action
            JOIN collection_case collection_case ON collection_case.id = action.case_id
            WHERE action.customer_id <> collection_case.customer_id
               OR action.contract_id <> collection_case.contract_id
            """,
            "collection action subject mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM repayment_promise promise
            JOIN collection_case collection_case ON collection_case.id = promise.case_id
            LEFT JOIN repayment_record repayment
                ON repayment.id = promise.fulfilled_repayment_id
            WHERE promise.customer_id <> collection_case.customer_id
               OR (
                   promise.fulfilled_repayment_id IS NOT NULL
                   AND (
                       repayment.collection_case_id <> collection_case.id
                       OR repayment.customer_id <> promise.customer_id
                   )
               )
            """,
            "repayment promise subject mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM legal_case legal_case
            JOIN collection_case collection_case ON collection_case.id = legal_case.case_id
            WHERE legal_case.customer_id <> collection_case.customer_id
               OR legal_case.contract_id <> collection_case.contract_id
            """,
            "legal case subject mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM loan_write_off write_off
            JOIN collection_case collection_case ON collection_case.id = write_off.case_id
            WHERE write_off.customer_id <> collection_case.customer_id
               OR write_off.contract_id <> collection_case.contract_id
               OR ABS(
                   write_off.approved_amount
                   - write_off.approved_principal_amount
                   - write_off.approved_interest_amount
                   - write_off.approved_fee_amount
                   - write_off.approved_penalty_amount
               ) > 0.01
            """,
            "loan write off subject or amount mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM loan_restructure restructure
            JOIN collection_case collection_case
                ON collection_case.id = restructure.case_id
            WHERE restructure.customer_id <> collection_case.customer_id
               OR restructure.contract_id <> collection_case.contract_id
               OR ABS(
                   restructure.after_outstanding_principal_amount
                   - restructure.before_outstanding_principal_amount
                   - restructure.capitalized_amount
                   + restructure.reduced_amount
               ) > 0.01
            """,
            "loan restructure subject or amount mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM collateral_disposal disposal
            JOIN collection_case collection_case
                ON collection_case.id = disposal.case_id
            JOIN collateral_asset collateral
                ON collateral.id = disposal.collateral_id
            WHERE disposal.customer_id <> collection_case.customer_id
               OR disposal.contract_id <> collection_case.contract_id
               OR disposal.customer_id <> collateral.customer_id
               OR disposal.contract_id <> collateral.contract_id
               OR disposal.received_amount > disposal.disposal_amount
            """,
            "collateral disposal subject or amount mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM collection_performance_daily perf
            LEFT JOIN (
                SELECT
                    DATE(collection_case.created_at) AS stat_date,
                    collection_case.collector_id,
                    employee.branch_id,
                    collection_case.collection_stage,
                    overdue.currency_code,
                    SUM(collection_case.case_amount) AS assigned_amount
                FROM collection_case
                JOIN overdue_record overdue
                    ON overdue.id = collection_case.overdue_id
                JOIN dim_employee employee
                    ON employee.id = collection_case.collector_id
                GROUP BY
                    DATE(collection_case.created_at),
                    collection_case.collector_id,
                    employee.branch_id,
                    collection_case.collection_stage,
                    overdue.currency_code
            ) actual
                ON actual.stat_date = perf.stat_date
                AND actual.collector_id = perf.collector_id
                AND actual.branch_id = perf.branch_id
                AND actual.collection_stage = perf.collection_stage
                AND actual.currency_code = perf.currency_code
            WHERE ABS(perf.assigned_amount - COALESCE(actual.assigned_amount, 0)) > 0.01
            """,
            "collection performance assigned amount mismatch",
        )

    def validate_cross_layer_append_consistency(self) -> None:
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM account_transaction tx
            WHERE tx.transaction_type NOT IN (
                    'transfer',
                    'consume',
                    'deposit',
                    'withdraw',
                    'loan_disbursement',
                    'loan_repayment',
                    'wealth_purchase',
                    'wealth_redeem',
                    'wealth_income',
                    'refund',
                    'cancel',
                    'reversal',
                    'adjustment',
                    'collateral_disposal'
                )
               OR (
                    tx.transaction_type IN (
                        'transfer',
                        'consume',
                        'withdraw',
                        'loan_repayment',
                        'wealth_purchase'
                    )
                    AND tx.from_account_id IS NULL
                )
               OR (
                    tx.transaction_type IN (
                        'transfer',
                        'deposit',
                        'loan_disbursement',
                        'wealth_redeem',
                        'wealth_income',
                        'refund',
                        'collateral_disposal'
                    )
                    AND tx.to_account_id IS NULL
                )
               OR (
                    tx.transaction_type = 'adjustment'
                    AND tx.from_account_id IS NULL
                    AND tx.to_account_id IS NULL
                )
            """,
            "account transaction type or direction mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM account_transaction tx
            LEFT JOIN bank_account from_account
                ON from_account.id = tx.from_account_id
            LEFT JOIN bank_account to_account
                ON to_account.id = tx.to_account_id
            WHERE (
                    from_account.id IS NOT NULL
                    AND from_account.currency_code <> tx.currency_code
                )
               OR (
                    to_account.id IS NOT NULL
                    AND to_account.currency_code <> tx.currency_code
                )
            """,
            "account transaction account currency mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM account_ledger ledger
            JOIN bank_account account ON account.id = ledger.account_id
            LEFT JOIN account_transaction tx ON tx.id = ledger.transaction_id
            WHERE ledger.ledger_type NOT IN ('debit', 'credit', 'freeze', 'unfreeze', 'adjust')
               OR ledger.customer_id <> account.customer_id
               OR ledger.currency_code <> account.currency_code
               OR (
                    ledger.transaction_id IS NOT NULL
                    AND tx.transaction_status <> 'success'
                )
               OR (
                    ledger.ledger_type = 'debit'
                    AND CAST(ledger.amount_delta AS DECIMAL(18, 2)) >= 0
                )
               OR (
                    ledger.ledger_type = 'credit'
                    AND CAST(ledger.amount_delta AS DECIMAL(18, 2)) <= 0
                )
               OR (
                    ledger.ledger_type IN ('debit', 'credit', 'adjust')
                    AND ledger.transaction_id IS NULL
                )
            """,
            "account ledger type, currency or transaction mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM reconciliation_result result
            LEFT JOIN account_transaction tx ON tx.id = result.transaction_id
            LEFT JOIN channel_transaction channel_tx
                ON channel_tx.id = result.channel_transaction_id
            WHERE result.result_type NOT IN (
                    'matched',
                    'amount_mismatch',
                    'status_mismatch',
                    'channel_only',
                    'bank_only'
                )
               OR (
                    result.result_type IN ('matched', 'amount_mismatch', 'status_mismatch')
                    AND (
                        tx.id IS NULL
                        OR channel_tx.id IS NULL
                    )
                )
               OR (
                    result.result_type = 'bank_only'
                    AND (
                        tx.id IS NULL
                        OR channel_tx.id IS NOT NULL
                    )
                )
               OR (
                    result.result_type = 'channel_only'
                    AND (
                        tx.id IS NOT NULL
                        OR channel_tx.id IS NULL
                    )
                )
               OR (
                    result.result_type = 'matched'
                    AND (
                        tx.id IS NULL
                        OR channel_tx.id IS NULL
                        OR result.difference_amount <> 0
                        OR tx.reconcile_status <> 'matched'
                        OR channel_tx.reconcile_status <> 'matched'
                        OR tx.external_order_no <> channel_tx.channel_order_no
                        OR ABS(tx.transaction_amount - channel_tx.channel_amount) > 0.01
                        OR (
                            tx.transaction_status = 'success'
                            AND (
                                channel_tx.request_status <> 'success'
                                OR channel_tx.callback_status <> 'verified'
                            )
                        )
                        OR (
                            tx.transaction_status = 'failed'
                            AND channel_tx.request_status <> 'failed'
                        )
                    )
                )
               OR (
                    result.result_type = 'amount_mismatch'
                    AND result.difference_amount <= 0
                )
               OR (
                    result.result_type = 'status_mismatch'
                    AND (
                        tx.id IS NULL
                        OR channel_tx.id IS NULL
                        OR (
                            tx.transaction_status = 'success'
                            AND channel_tx.request_status = 'success'
                            AND channel_tx.callback_status = 'verified'
                        )
                        OR (
                            tx.transaction_status = 'failed'
                            AND channel_tx.request_status = 'failed'
                        )
                    )
                )
            """,
            "reconciliation result type or matched content mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM wealth_order wo
            JOIN account_transaction tx ON wo.transaction_id = tx.id
            WHERE tx.related_type <> 'wealth_order'
               OR tx.related_id <> wo.id
               OR tx.transaction_type <> IF(wo.order_type = 'redeem', 'wealth_redeem', 'wealth_purchase')
               OR wo.order_status <> 'confirmed'
            """,
            "wealth order transaction mapping mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM wealth_order
            WHERE (order_status = 'cancelled' AND transaction_id IS NOT NULL)
               OR (order_status = 'confirmed' AND transaction_id IS NULL)
            """,
            "wealth order transaction status mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM loan_disbursement ld
            JOIN account_transaction tx ON ld.transaction_id = tx.id
            WHERE tx.related_type <> 'loan_contract'
               OR tx.related_id <> ld.contract_id
               OR tx.transaction_type <> 'loan_disbursement'
               OR tx.to_account_id <> ld.account_id
               OR tx.currency_code <> ld.currency_code
               OR tx.transaction_at <> ld.disbursed_at
            """,
            "loan disbursement transaction mapping mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM repayment_record rr
            JOIN account_transaction tx ON rr.transaction_id = tx.id
            WHERE rr.transaction_id IS NOT NULL
              AND (
                  (
                      rr.bill_id IS NOT NULL
                      AND (
                          tx.related_type <> 'repayment_bill'
                          OR tx.related_id <> rr.bill_id
                      )
                  )
                  OR (
                      rr.bill_id IS NULL
                      AND (
                          tx.related_type <> 'loan_contract'
                          OR tx.related_id <> rr.contract_id
                      )
                  )
                  OR tx.transaction_type <> 'loan_repayment'
                  OR tx.from_account_id <> rr.account_id
                  OR tx.currency_code <> rr.currency_code
                  OR tx.transaction_at <> rr.repaid_at
              )
            """,
            "repayment transaction mapping mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM account_transaction tx
            LEFT JOIN channel_transaction ct ON ct.transaction_id = tx.id
            LEFT JOIN reconciliation_result rr ON rr.transaction_id = tx.id
            WHERE tx.transaction_status = 'success'
              AND (ct.id IS NULL OR rr.id IS NULL)
            """,
            "successful transaction missing channel or reconciliation row",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM credit_limit_change_log
            WHERE (change_type = 'grant' AND credit_application_id IS NULL)
               OR (change_type = 'freeze' AND loan_application_id IS NULL)
               OR (change_type = 'use' AND contract_id IS NULL)
               OR (change_type = 'release' AND repayment_id IS NULL)
            """,
            "credit limit change log missing business reference",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM wealth_income income
            JOIN wealth_position position ON position.id = income.position_id
            LEFT JOIN account_transaction tx ON tx.id = income.transaction_id
            LEFT JOIN account_ledger ledger ON ledger.id = income.ledger_id
            WHERE income.customer_id <> position.customer_id
               OR income.account_id <> position.account_id
               OR income.product_id <> position.product_id
               OR income.currency_code <> position.currency_code
               OR income.income_date < DATE(position.created_at)
               OR (
                    income.settled_flag = 1
                    AND (
                        income.transaction_id IS NULL
                        OR income.ledger_id IS NULL
                        OR income.settled_at IS NULL
                        OR tx.transaction_type <> 'wealth_income'
                        OR tx.related_type <> 'wealth_income'
                        OR tx.related_id <> income.id
                        OR tx.to_account_id <> income.account_id
                        OR tx.currency_code <> income.currency_code
                        OR ABS(tx.transaction_amount - income.income_amount) > 0.01
                        OR ledger.transaction_id <> tx.id
                        OR ledger.account_id <> income.account_id
                        OR ledger.ledger_type <> 'credit'
                    )
                )
               OR (
                    income.settled_flag = 0
                    AND (
                        income.transaction_id IS NOT NULL
                        OR income.ledger_id IS NOT NULL
                        OR income.settled_at IS NOT NULL
                    )
                )
            """,
            "wealth income position or fund mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM loan_contract contract
            JOIN loan_application application
                ON application.id = contract.application_id
            JOIN loan_approval_record approval
                ON approval.application_id = application.id
            WHERE application.application_status <> 'approved'
               OR approval.approval_result <> 'approved'
               OR ABS(contract.principal_amount - approval.approved_amount) > 0.01
            """,
            "loan contract not backed by approved application",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM overdue_record overdue
            JOIN repayment_bill bill ON bill.id = overdue.bill_id
            WHERE bill.bill_status <> 'overdue'
               OR overdue.contract_id <> bill.contract_id
               OR overdue.customer_id <> bill.customer_id
               OR ABS(overdue.outstanding_amount - bill.outstanding_amount) > 0.01
            """,
            "overdue record not backed by overdue bill",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM workflow_instance workflow
            WHERE (
                    workflow.related_type = 'credit_application'
                    AND NOT EXISTS (
                        SELECT 1 FROM credit_application application
                        WHERE application.id = workflow.related_id
                    )
                )
               OR (
                    workflow.related_type = 'loan_application'
                    AND NOT EXISTS (
                        SELECT 1 FROM loan_application application
                        WHERE application.id = workflow.related_id
                    )
                )
               OR (
                    workflow.related_type = 'wealth_order'
                    AND NOT EXISTS (
                        SELECT 1 FROM wealth_order wo
                        WHERE wo.id = workflow.related_id
                    )
                )
               OR (
                    workflow.related_type = 'risk_event'
                    AND NOT EXISTS (
                        SELECT 1 FROM risk_event event
                        WHERE event.id = workflow.related_id
                    )
                )
               OR (
                    workflow.related_type = 'support_ticket'
                    AND NOT EXISTS (
                        SELECT 1 FROM support_ticket ticket
                        WHERE ticket.id = workflow.related_id
                    )
                )
               OR (
                    workflow.related_type = 'fee_reduction'
                    AND NOT EXISTS (
                        SELECT 1 FROM fee_reduction reduction
                        WHERE reduction.id = workflow.related_id
                    )
                )
            """,
            "workflow related object missing",
        )

    def validate_global_time_order(self) -> None:
        checks = [
            ("customer", "opened_at", "updated_at"),
            ("bank_account", "opened_at", "updated_at"),
            ("wealth_order", "submitted_at", "updated_at"),
            ("loan_application", "submitted_at", "updated_at"),
            ("loan_contract", "signed_at", "updated_at"),
            ("repayment_record", "repaid_at", "updated_at"),
            ("support_ticket", "created_at", "updated_at"),
        ]
        for table, start_column, end_column in checks:
            self.expect_zero(
                f"""
                SELECT COUNT(*) AS cnt
                FROM `{table}`
                WHERE `{end_column}` < `{start_column}`
                """,
                f"{table} time order invalid",
            )

    def validate_amount_closure(self) -> None:
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM repayment_record
            WHERE ABS(
                repayment_amount
                - principal_paid_amount
                - interest_paid_amount
                - fee_paid_amount
                - penalty_paid_amount
            ) > 0.01
            """,
            "repayment record amount not closed",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM repayment_allocation
            WHERE ABS(
                allocated_amount
                - principal_amount
                - interest_amount
                - fee_amount
                - penalty_amount
            ) > 0.01
            """,
            "repayment allocation amount not closed",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM repayment_bill
            WHERE ABS(
                outstanding_amount
                - principal_amount
                - interest_amount
                - fee_amount
                - penalty_amount
                + reduced_amount
                + paid_amount
                + written_off_amount
                + restructured_amount
            ) > 0.01
            """,
            "repayment bill outstanding amount not closed",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM credit_limit_change_log
            WHERE ABS(
                after_total_amount
                - after_used_amount
                - after_frozen_amount
                - after_available_amount
            ) > 0.01
            """,
            "credit limit after amount not closed",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM wealth_order wo
            JOIN account_transaction tx ON tx.id = wo.transaction_id
            JOIN channel_transaction ct ON ct.transaction_id = tx.id
            JOIN fund_freeze ff ON ff.id = wo.freeze_id
            JOIN fund_freeze_operation ffo
                ON ffo.freeze_id = ff.id
                AND ffo.related_type = 'wealth_order'
                AND ffo.related_id = wo.id
            WHERE tx.customer_id <> wo.customer_id
               OR tx.currency_code <> wo.currency_code
               OR ct.currency_code <> wo.currency_code
               OR ff.currency_code <> wo.currency_code
               OR ffo.currency_code <> wo.currency_code
               OR ff.account_id <> wo.account_id
               OR ff.customer_id <> wo.customer_id
               OR ffo.account_id <> wo.account_id
               OR ffo.customer_id <> wo.customer_id
               OR ffo.transaction_id <> tx.id
               OR (
                   wo.order_type = 'purchase'
                   AND tx.from_account_id <> wo.account_id
               )
               OR (
                   wo.order_type = 'redeem'
                   AND tx.to_account_id <> wo.account_id
               )
               OR ABS(tx.transaction_amount - wo.order_amount) > 0.01
               OR ABS(ct.channel_amount - wo.order_amount) > 0.01
               OR ABS(ff.freeze_amount - wo.order_amount) > 0.01
               OR ABS(ffo.operation_amount - wo.order_amount) > 0.01
            """,
            "wealth order fund amount mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM loan_disbursement ld
            JOIN account_transaction tx ON tx.id = ld.transaction_id
            JOIN channel_transaction ct ON ct.transaction_id = tx.id
            WHERE ABS(tx.transaction_amount - ld.disbursement_amount) > 0.01
               OR ABS(ct.channel_amount - ld.disbursement_amount) > 0.01
            """,
            "loan disbursement fund amount mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM repayment_record rr
            JOIN account_transaction tx ON tx.id = rr.transaction_id
            JOIN channel_transaction ct ON ct.transaction_id = tx.id
            WHERE rr.transaction_id IS NOT NULL
              AND (
                  ABS(tx.transaction_amount - rr.repayment_amount) > 0.01
                  OR ABS(ct.channel_amount - rr.repayment_amount) > 0.01
              )
            """,
            "repayment fund amount mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM account_transaction tx
            JOIN account_ledger ledger ON ledger.transaction_id = tx.id
            WHERE ABS(ABS(CAST(ledger.amount_delta AS DECIMAL(18, 2))) - tx.transaction_amount) > 0.01
            """,
            "account ledger amount mismatch",
        )

    def validate_status_flow(self) -> None:
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM wealth_order
            WHERE (order_status = 'confirmed' AND confirmed_at IS NULL)
               OR (order_status = 'cancelled' AND (cancelled_at IS NULL OR cancel_reason IS NULL))
            """,
            "wealth order status timestamp invalid",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM loan_application
            WHERE (application_status = 'approved' AND approved_at IS NULL)
               OR (application_status = 'rejected' AND rejected_at IS NULL)
            """,
            "loan application status timestamp invalid",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM repayment_bill
            WHERE (bill_status = 'paid' AND paid_at IS NULL)
               OR (bill_status = 'overdue' AND outstanding_amount <= 0)
            """,
            "repayment bill status invalid",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM repayment_promise
            WHERE promise_status = 'fulfilled'
              AND fulfilled_at IS NULL
            """,
            "repayment promise status invalid",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM customer
            WHERE customer_status = 'closed'
              AND (closed_at IS NULL OR closed_at > CONCAT(CURDATE(), ' 23:59:59'))
            """,
            "customer closed timestamp invalid",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM bank_account
            WHERE account_status = 'closed'
              AND (closed_at IS NULL OR closed_at > CONCAT(CURDATE(), ' 23:59:59'))
            """,
            "bank account closed timestamp invalid",
        )

    def validate_business_stats_traceability(self) -> None:
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM business_stat_daily stat
            LEFT JOIN business_metric_dict metric
                ON stat.metric_id = metric.id
                AND stat.metric_code = metric.metric_code
            WHERE metric.id IS NULL
            """,
            "business stat metric not traceable",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM (
                SELECT
                    stat_date,
                    branch_id,
                    channel_id,
                    COALESCE(currency_code, '__NONE__') AS currency_code_key,
                    stat_domain,
                    metric_code
                FROM business_stat_daily
                GROUP BY
                    stat_date,
                    branch_id,
                    channel_id,
                    COALESCE(currency_code, '__NONE__'),
                    stat_domain,
                    metric_code
                HAVING COUNT(*) > 1
            ) duplicated
            """,
            "business stat daily duplicated",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM business_stat_daily stat
            JOIN business_metric_dict metric ON metric.id = stat.metric_id
            WHERE (
                    metric.currency_required_flag = 1
                    AND stat.currency_code IS NULL
                )
               OR (
                    metric.currency_required_flag = 0
                    AND stat.currency_code IS NOT NULL
                )
            """,
            "business stat currency requirement mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM business_stat_daily rollup
            LEFT JOIN (
                SELECT
                    stat_date,
                    branch_id,
                    COALESCE(currency_code, '__NONE__') AS currency_code_key,
                    stat_domain,
                    metric_code,
                    SUM(metric_value) AS metric_value
                FROM business_stat_daily
                WHERE branch_id <> 0
                  AND channel_id <> 0
                GROUP BY
                    stat_date,
                    branch_id,
                    COALESCE(currency_code, '__NONE__'),
                    stat_domain,
                    metric_code
            ) detail
                ON detail.stat_date = rollup.stat_date
                AND detail.branch_id = rollup.branch_id
                AND detail.currency_code_key = COALESCE(rollup.currency_code, '__NONE__')
                AND detail.stat_domain = rollup.stat_domain
                AND detail.metric_code = rollup.metric_code
            WHERE rollup.branch_id <> 0
              AND rollup.channel_id = 0
              AND ABS(rollup.metric_value - COALESCE(detail.metric_value, 0)) > 0.01
            """,
            "business stat channel rollup mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM business_stat_daily rollup
            LEFT JOIN (
                SELECT
                    stat_date,
                    channel_id,
                    COALESCE(currency_code, '__NONE__') AS currency_code_key,
                    stat_domain,
                    metric_code,
                    SUM(metric_value) AS metric_value
                FROM business_stat_daily
                WHERE branch_id <> 0
                  AND channel_id <> 0
                GROUP BY
                    stat_date,
                    channel_id,
                    COALESCE(currency_code, '__NONE__'),
                    stat_domain,
                    metric_code
            ) detail
                ON detail.stat_date = rollup.stat_date
                AND detail.channel_id = rollup.channel_id
                AND detail.currency_code_key = COALESCE(rollup.currency_code, '__NONE__')
                AND detail.stat_domain = rollup.stat_domain
                AND detail.metric_code = rollup.metric_code
            WHERE rollup.branch_id = 0
              AND rollup.channel_id <> 0
              AND ABS(rollup.metric_value - COALESCE(detail.metric_value, 0)) > 0.01
            """,
            "business stat branch rollup mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM business_stat_daily rollup
            LEFT JOIN (
                SELECT
                    stat_date,
                    COALESCE(currency_code, '__NONE__') AS currency_code_key,
                    stat_domain,
                    metric_code,
                    SUM(metric_value) AS metric_value
                FROM business_stat_daily
                WHERE branch_id <> 0
                  AND channel_id <> 0
                GROUP BY
                    stat_date,
                    COALESCE(currency_code, '__NONE__'),
                    stat_domain,
                    metric_code
            ) detail
                ON detail.stat_date = rollup.stat_date
                AND detail.currency_code_key = COALESCE(rollup.currency_code, '__NONE__')
                AND detail.stat_domain = rollup.stat_domain
                AND detail.metric_code = rollup.metric_code
            WHERE rollup.branch_id = 0
              AND rollup.channel_id = 0
              AND ABS(rollup.metric_value - COALESCE(detail.metric_value, 0)) > 0.01
            """,
            "business stat grand rollup mismatch",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM business_stat_daily stat
            LEFT JOIN (
                SELECT
                    DATE(tx.transaction_at) AS stat_date,
                    account.branch_id,
                    tx.channel_id,
                    COUNT(*) AS metric_value
                FROM account_transaction tx
                JOIN bank_account account
                    ON account.id = COALESCE(tx.from_account_id, tx.to_account_id)
                WHERE tx.transaction_status = 'success'
                GROUP BY DATE(tx.transaction_at), account.branch_id, tx.channel_id
            ) actual
                ON actual.stat_date = stat.stat_date
                AND actual.branch_id = stat.branch_id
                AND actual.channel_id = stat.channel_id
            WHERE stat.metric_code = 'TRANSACTION_COUNT'
              AND stat.branch_id <> 0
              AND stat.channel_id <> 0
              AND ABS(stat.metric_value - COALESCE(actual.metric_value, 0)) > 0.01
            """,
            "business stat transaction count not traceable",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM business_stat_daily stat
            LEFT JOIN (
                SELECT
                    DATE(tx.transaction_at) AS stat_date,
                    account.branch_id,
                    tx.channel_id,
                    tx.currency_code,
                    SUM(tx.transaction_amount) AS metric_value
                FROM account_transaction tx
                JOIN bank_account account
                    ON account.id = COALESCE(tx.from_account_id, tx.to_account_id)
                WHERE tx.transaction_status = 'success'
                GROUP BY
                    DATE(tx.transaction_at),
                    account.branch_id,
                    tx.channel_id,
                    tx.currency_code
            ) actual
                ON actual.stat_date = stat.stat_date
                AND actual.branch_id = stat.branch_id
                AND actual.channel_id = stat.channel_id
                AND actual.currency_code = stat.currency_code
            WHERE stat.metric_code = 'TRANSACTION_AMOUNT'
              AND stat.branch_id <> 0
              AND stat.channel_id <> 0
              AND ABS(stat.metric_value - COALESCE(actual.metric_value, 0)) > 0.01
            """,
            "business stat transaction amount not traceable",
        )
        self.expect_zero(
            """
            SELECT COUNT(*) AS cnt
            FROM business_stat_daily stat
            LEFT JOIN (
                SELECT
                    DATE(opened_at) AS stat_date,
                    branch_id,
                    register_channel_id AS channel_id,
                    COUNT(*) AS metric_value
                FROM customer
                GROUP BY DATE(opened_at), branch_id, register_channel_id
            ) actual
                ON actual.stat_date = stat.stat_date
                AND actual.branch_id = stat.branch_id
                AND actual.channel_id = stat.channel_id
            WHERE stat.metric_code = 'CUSTOMER_NEW_COUNT'
              AND stat.branch_id <> 0
              AND stat.channel_id <> 0
              AND ABS(stat.metric_value - COALESCE(actual.metric_value, 0)) > 0.01
            """,
            "business stat new customer count not traceable",
        )

    def validate_recent_indicators(self) -> None:
        checks = [
            ("customer", "opened_at"),
            ("account_transaction", "transaction_at"),
            ("loan_disbursement", "disbursed_at"),
            ("repayment_record", "repaid_at"),
            ("risk_event", "created_at"),
            ("collection_case", "created_at"),
            ("support_ticket", "created_at"),
        ]
        for table, column in checks:
            row = db.fetch_one(
                f"""
                SELECT COUNT(*) AS cnt
                FROM `{table}`
                WHERE `{column}` >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                """
            )
            actual = int(row["cnt"]) if row else 0
            if actual == 0:
                raise RuntimeError(f"{table}.{column} has no recent records")

    def find_broken_references(self) -> list[dict]:
        rows = db.fetch_all(
            """
            SELECT
                rc.CONSTRAINT_NAME AS constraint_name,
                kcu.TABLE_NAME AS table_name,
                kcu.COLUMN_NAME AS column_name,
                kcu.REFERENCED_TABLE_NAME AS referenced_table_name,
                kcu.REFERENCED_COLUMN_NAME AS referenced_column_name
            FROM information_schema.REFERENTIAL_CONSTRAINTS rc
            JOIN information_schema.KEY_COLUMN_USAGE kcu
                ON rc.CONSTRAINT_SCHEMA = kcu.CONSTRAINT_SCHEMA
                AND rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
                AND rc.TABLE_NAME = kcu.TABLE_NAME
            WHERE rc.CONSTRAINT_SCHEMA = DATABASE()
              AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
            """
        )
        broken: list[dict] = []
        for row in rows:
            sql = f"""
                SELECT 1
                FROM `{row["table_name"]}` child
                LEFT JOIN `{row["referenced_table_name"]}` parent
                    ON child.`{row["column_name"]}` = parent.`{row["referenced_column_name"]}`
                WHERE child.`{row["column_name"]}` IS NOT NULL
                  AND parent.`{row["referenced_column_name"]}` IS NULL
                LIMIT 1
            """
            if db.fetch_one(sql):
                broken.append(row)
        return broken
