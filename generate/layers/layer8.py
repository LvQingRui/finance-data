"""Layer8: operation support and daily statistics."""

from __future__ import annotations

from datetime import date, timedelta

from ..config import GENERATION_DEFAULTS, LAYERS
from ..db import db
from .base import BaseGenerator
from .common import clear_tables, code, dt, fetch_id_values, fetch_ids, max_id


class Layer8Generator(BaseGenerator):
    layer = 8

    def run(self) -> None:
        self.header()
        clear_tables(LAYERS[self.layer]["tables"])
        channel_ids = fetch_ids("dim_channel", "id >= 0")
        employee_ids = fetch_ids("dim_employee")
        service_ids = fetch_ids("dim_employee", "employee_role = 'customer_service'")
        branch_ids = fetch_ids("dim_branch", "id >= 0")
        metrics = fetch_id_values(
            "business_metric_dict",
            [
                "id",
                "metric_code",
                "metric_name",
                "stat_domain",
                "currency_required_flag",
            ],
        )
        ticket_count = int(GENERATION_DEFAULTS["support_tickets"])
        notification_count = max(ticket_count * 4, int(GENERATION_DEFAULTS["risk_events"]) // 2)
        workflow_count = ticket_count + max(1, max_id("manual_review_task") // 2)
        stat_days = int(GENERATION_DEFAULTS["stat_days"])
        transaction_sources = fetch_id_values(
            "account_transaction",
            ["id", "customer_id", "transaction_at"],
            "transaction_status = 'success'",
            limit=notification_count,
        )
        bill_sources = fetch_id_values(
            "repayment_bill",
            ["id", "customer_id", "created_at"],
            limit=notification_count,
        )
        push_customer_ids = {
            int(row["customer_id"])
            for row in fetch_id_values(
                "customer_device",
                ["customer_id"],
                "push_token IS NOT NULL AND device_type IN ('ios', 'android') AND risk_status <> 'blacklisted'",
            )
        }
        notification_sources = self.notification_sources(
            notification_count,
            transaction_sources,
            bill_sources,
        )
        ticket_sources = self.ticket_sources(ticket_count, transaction_sources, bill_sources)
        counts: dict[str, int] = {}
        counts["notification_message"] = self.stream_rows(
            "notification_message",
            self.iter_notifications(notification_sources, push_customer_ids),
            total_rows=notification_count,
            build_step_name="build notification_message",
        )
        counts["support_ticket"] = self.stream_rows(
            "support_ticket",
            self.iter_support_tickets(ticket_sources, channel_ids, service_ids or employee_ids),
            total_rows=ticket_count,
            build_step_name="build support_ticket",
        )
        tickets = fetch_id_values(
            "support_ticket",
            ["id", "customer_id", "submitted_at", "handled_at", "closed_at", "created_at"],
            "ticket_status IN ('closed', 'resolved')",
        )
        counts["support_ticket_feedback"] = self.stream_rows(
            "support_ticket_feedback",
            self.iter_ticket_feedback(tickets),
            total_rows=len(tickets),
            build_step_name="build support_ticket_feedback",
        )
        workflow_sources = self.workflow_sources(workflow_count)
        counts["workflow_instance"] = self.stream_rows(
            "workflow_instance",
            self.iter_workflow_instances(workflow_sources),
            total_rows=workflow_count,
            build_step_name="build workflow_instance",
        )
        counts["workflow_task"] = self.stream_rows(
            "workflow_task",
            self.iter_workflow_tasks(workflow_sources, employee_ids),
            total_rows=workflow_count * 2,
            build_step_name="build workflow_task",
        )
        counts["business_stat_daily"] = self.stream_rows(
            "business_stat_daily",
            self.iter_business_stats(stat_days, branch_ids, channel_ids, metrics),
            total_rows=stat_days * len(branch_ids) * len(channel_ids) * len(metrics),
            build_step_name="build business_stat_daily",
        )
        self.log_table_counts(counts)

    def notification_sources(
        self,
        total: int,
        transactions: list[dict],
        bills: list[dict],
    ) -> list[dict]:
        sources = []
        for row_id in range(1, total + 1):
            if row_id % 2 and transactions:
                tx = transactions[(row_id - 1) % len(transactions)]
                sources.append(
                    {
                        "customer_id": tx["customer_id"],
                        "related_type": "account_transaction",
                        "related_id": tx["id"],
                        "related_at": tx["transaction_at"],
                    }
                )
            else:
                bill = bills[(row_id - 1) % len(bills)]
                sources.append(
                    {
                        "customer_id": bill["customer_id"],
                        "related_type": "repayment_bill",
                        "related_id": bill["id"],
                        "related_at": bill["created_at"],
                    }
                )
        return sources

    def ticket_sources(
        self,
        total: int,
        transactions: list[dict],
        bills: list[dict],
    ) -> list[dict]:
        sources = []
        for row_id in range(1, total + 1):
            if row_id % 2 and transactions:
                tx = transactions[(row_id - 1) % len(transactions)]
                sources.append(
                    {
                        "customer_id": tx["customer_id"],
                        "related_type": "account_transaction",
                        "related_id": tx["id"],
                        "related_at": tx["transaction_at"],
                        "ticket_type": "transaction_issue",
                    }
                )
            else:
                bill = bills[(row_id - 1) % len(bills)]
                sources.append(
                    {
                        "customer_id": bill["customer_id"],
                        "related_type": "repayment_bill",
                        "related_id": bill["id"],
                        "related_at": bill["created_at"],
                        "ticket_type": "repayment_issue",
                    }
                )
        return sources

    def iter_notifications(self, sources: list[dict], push_customer_ids: set[int]):
        message_types = (
            "account",
            "transaction",
            "wealth",
            "loan",
            "repayment",
            "collection",
            "system",
        )
        for row_id, source in enumerate(sources, start=1):
            send_channels = (
                ("app_push", "sms", "email", "site_message")
                if int(source["customer_id"]) in push_customer_ids
                else ("sms", "email", "site_message")
            )
            sent = row_id % 12 != 0
            read = sent and row_id % 3 != 0
            created = source["related_at"] + timedelta(minutes=1)
            sent_at = created + timedelta(minutes=2) if sent else None
            read_at = created + timedelta(hours=2) if read else None
            yield {
                "id": row_id,
                "message_no": code("MSG", row_id, 10),
                "customer_id": source["customer_id"],
                "related_type": source["related_type"],
                "related_id": source["related_id"],
                "channel_txn_id": None,
                "message_type": message_types[(row_id - 1) % len(message_types)],
                "send_channel": send_channels[(row_id - 1) % len(send_channels)],
                "message_title": "业务通知",
                "message_content": "账户交易、还款或服务状态通知",
                "failure_reason": None if sent else "渠道暂不可用",
                "send_status": "success" if sent else "failed",
                "sent_at": sent_at,
                "read_status": "read" if read else "unread",
                "read_at": read_at,
                "created_at": created,
                "updated_at": read_at or sent_at or created,
            }

    def iter_support_tickets(
        self,
        sources: list[dict],
        channel_ids: list[int],
        employee_ids: list[int],
    ):
        for row_id, source in enumerate(sources, start=1):
            closed = row_id % 5 != 0
            submitted = source["related_at"] + timedelta(hours=1)
            handled_at = submitted + timedelta(hours=4) if closed else None
            closed_at = submitted + timedelta(days=1) if closed else None
            yield {
                "id": row_id,
                "ticket_no": code("TCK", row_id, 10),
                "customer_id": source["customer_id"],
                "channel_id": channel_ids[(row_id - 1) % len(channel_ids)],
                "assignee_id": employee_ids[(row_id - 1) % len(employee_ids)],
                "ticket_type": source["ticket_type"],
                "related_type": source["related_type"],
                "related_id": source["related_id"],
                "ticket_title": "客户服务工单",
                "ticket_content": "客户咨询、投诉或业务处理问题",
                "ticket_status": "closed" if closed else "processing",
                "handle_result": "已处理" if closed else "处理中",
                "submitted_at": submitted,
                "handled_at": handled_at,
                "closed_at": closed_at,
                "created_at": submitted,
                "updated_at": closed_at or handled_at or submitted,
            }

    def iter_ticket_feedback(self, tickets: list[dict]):
        for row_id, ticket in enumerate(tickets, start=1):
            confirmed = row_id % 5 != 0
            ticket_done_at = (
                ticket["closed_at"]
                or ticket["handled_at"]
                or ticket["submitted_at"]
                or ticket["created_at"]
            )
            created_at = ticket_done_at + timedelta(hours=1)
            confirmed_at = created_at + timedelta(hours=2) if confirmed else None
            yield {
                "id": row_id,
                "feedback_no": code("FBK", row_id, 10),
                "ticket_id": ticket["id"],
                "customer_id": ticket["customer_id"],
                "confirm_status": "confirmed" if confirmed else "not_confirmed",
                "satisfaction_score": 4 + row_id % 2 if confirmed else None,
                "feedback_content": "服务处理反馈",
                "confirmed_at": confirmed_at,
                "created_at": created_at,
                "updated_at": confirmed_at or created_at,
            }

    def workflow_sources(self, total: int) -> list[dict]:
        source_sets = [
            (
                "loan_approval",
                "loan_application",
                db.fetch_all(
                    """
                    SELECT
                        id,
                        submitted_at AS started_at,
                        COALESCE(approved_at, rejected_at, updated_at) AS completed_at
                    FROM loan_application
                    ORDER BY id
                    """
                ),
            ),
            (
                "risk_review",
                "risk_event",
                db.fetch_all(
                    """
                    SELECT id, created_at AS started_at, updated_at AS completed_at
                    FROM risk_event
                    ORDER BY id
                    """
                ),
            ),
            (
                "support_ticket",
                "support_ticket",
                db.fetch_all(
                    """
                    SELECT id, created_at AS started_at, COALESCE(closed_at, updated_at) AS completed_at
                    FROM support_ticket
                    ORDER BY id
                    """
                ),
            ),
            (
                "fee_reduction",
                "fee_reduction",
                db.fetch_all(
                    """
                    SELECT id, created_at AS started_at, COALESCE(approved_at, updated_at) AS completed_at
                    FROM fee_reduction
                    ORDER BY id
                    """
                ),
            ),
        ]
        sources = []
        for row_id in range(1, total + 1):
            workflow_type, related_type, rows = source_sets[(row_id - 1) % len(source_sets)]
            source = rows[(row_id - 1) % len(rows)]
            started_at = source["started_at"]
            completed_at = source["completed_at"]
            done = completed_at is not None
            if done and completed_at < started_at:
                completed_at = started_at
            sources.append(
                {
                    "id": row_id,
                    "workflow_type": workflow_type,
                    "related_type": related_type,
                    "related_id": source["id"],
                    "initiator_type": "service",
                    "initiator_no": "service.finance.workflow",
                    "started_at": started_at,
                    "completed_at": completed_at,
                    "done": done,
                }
            )
        return sources

    def iter_workflow_instances(self, sources: list[dict]):
        for source in sources:
            row_id = source["id"]
            done = source["done"]
            started = source["started_at"]
            completed_at = source["completed_at"] if done else None
            yield {
                "id": row_id,
                "instance_no": code("WFI", row_id, 10),
                "workflow_type": source["workflow_type"],
                "related_type": source["related_type"],
                "related_id": source["related_id"],
                "initiator_type": source["initiator_type"],
                "initiator_no": source["initiator_no"],
                "instance_status": "completed" if done else "running",
                "started_at": started,
                "completed_at": completed_at,
                "created_at": started,
                "updated_at": completed_at or started,
            }

    def iter_workflow_tasks(self, sources: list[dict], employee_ids: list[int]):
        row_id = 1
        nodes = (("submit", "提交"), ("review", "审核"))
        for source in sources:
            instance_id = source["id"]
            done = source["done"]
            for node_code, node_name in nodes:
                assigned_at = source["started_at"]
                completed_at = source["completed_at"] if done else None
                yield {
                    "id": row_id,
                    "task_no": code("WFT", row_id, 10),
                    "instance_id": instance_id,
                    "node_code": node_code,
                    "node_name": node_name,
                    "assignee_id": employee_ids[(row_id - 1) % len(employee_ids)],
                    "task_status": "approved" if done else "processing",
                    "task_result": "approved" if done else None,
                    "task_comment": "流程审核通过" if done else None,
                    "assigned_at": assigned_at,
                    "completed_at": completed_at,
                    "created_at": assigned_at,
                    "updated_at": completed_at or assigned_at,
                }
                row_id += 1

    def iter_business_stats(
        self,
        days: int,
        branch_ids: list[int],
        channel_ids: list[int],
        metrics: list[dict],
    ):
        stat_values = self.business_stat_values(days)
        row_id = 1
        for day in range(days):
            stat_date = dt(day).date()
            for branch_id in branch_ids:
                for channel_id in channel_ids:
                    for metric in metrics:
                        currency_code = (
                            "CNY" if int(metric["currency_required_flag"]) else None
                        )
                        yield {
                            "id": row_id,
                            "stat_date": stat_date,
                            "branch_id": branch_id,
                            "channel_id": channel_id,
                            "currency_code": currency_code,
                            "stat_domain": metric["stat_domain"],
                            "metric_code": metric["metric_code"],
                            "metric_id": metric["id"],
                            "metric_name": metric["metric_name"],
                            "metric_value": stat_values.get(
                                (
                                    metric["metric_code"],
                                    stat_date,
                                    branch_id,
                                    channel_id,
                                    currency_code,
                                ),
                                0,
                            ),
                            "created_at": dt(day, 23),
                        }
                        row_id += 1

    def business_stat_values(self, days: int) -> dict[tuple, float]:
        dates = [dt(day).date() for day in range(days)]
        min_date = min(dates)
        all_branch_id = self.all_id("dim_branch", "branch_code")
        all_channel_id = self.all_id("dim_channel", "channel_code")
        values: dict[tuple, float] = {}

        def add(
            metric_code: str,
            stat_date: date,
            branch_id: int,
            channel_id: int,
            currency_code: str | None,
            value: float,
        ) -> None:
            for target_branch_id in {branch_id, all_branch_id}:
                for target_channel_id in {channel_id, all_channel_id}:
                    key = (
                        metric_code,
                        stat_date,
                        target_branch_id,
                        target_channel_id,
                        currency_code,
                    )
                    values[key] = round(values.get(key, 0) + float(value), 2)

        def event_rows(sql: str) -> None:
            for row in db.fetch_all(sql):
                stat_date = row["stat_date"]
                if stat_date < min_date:
                    continue
                branch_id = int(row["branch_id"])
                channel_id = int(row["channel_id"])
                currency_code = row.get("currency_code")
                for metric_code, value in row.items():
                    if metric_code in {"stat_date", "branch_id", "channel_id", "currency_code"}:
                        continue
                    add(metric_code, stat_date, branch_id, channel_id, currency_code, value or 0)

        def cumulative_rows(rows: list[dict], metric_code: str, amount_column: str | None = None) -> None:
            for row in rows:
                row_date = row["stat_date"]
                branch_id = int(row["branch_id"])
                channel_id = int(row["channel_id"])
                currency_code = row.get("currency_code")
                value = float(row[amount_column]) if amount_column else 1
                for stat_date in dates:
                    if row_date <= stat_date:
                        add(metric_code, stat_date, branch_id, channel_id, currency_code, value)

        cumulative_rows(
            db.fetch_all(
                """
                SELECT DATE(opened_at) AS stat_date, branch_id, register_channel_id AS channel_id
                FROM customer
                WHERE customer_status IN ('normal', 'restricted')
                """
            ),
            "CUSTOMER_ACTIVE_COUNT",
        )
        event_rows(
            """
            SELECT
                DATE(opened_at) AS stat_date,
                branch_id,
                register_channel_id AS channel_id,
                COUNT(*) AS CUSTOMER_NEW_COUNT
            FROM customer
            GROUP BY DATE(opened_at), branch_id, register_channel_id
            """
        )
        cumulative_rows(
            db.fetch_all(
                """
                SELECT DATE(opened_at) AS stat_date, branch_id, open_channel_id AS channel_id
                FROM bank_account
                WHERE account_status = 'normal'
                """
            ),
            "ACCOUNT_ACTIVE_COUNT",
        )
        event_rows(
            """
            SELECT
                DATE(opened_at) AS stat_date,
                branch_id,
                open_channel_id AS channel_id,
                COUNT(*) AS ACCOUNT_NEW_COUNT
            FROM bank_account
            GROUP BY DATE(opened_at), branch_id, open_channel_id
            """
        )
        event_rows(
            """
            SELECT
                DATE(tx.transaction_at) AS stat_date,
                account.branch_id,
                tx.channel_id,
                tx.currency_code,
                SUM(CASE WHEN tx.transaction_status = 'success' THEN tx.transaction_amount ELSE 0 END) AS TRANSACTION_AMOUNT
            FROM account_transaction tx
            JOIN bank_account account
                ON account.id = COALESCE(tx.from_account_id, tx.to_account_id)
            GROUP BY DATE(tx.transaction_at), account.branch_id, tx.channel_id, tx.currency_code
            """
        )
        event_rows(
            """
            SELECT
                DATE(tx.transaction_at) AS stat_date,
                account.branch_id,
                tx.channel_id,
                COUNT(CASE WHEN tx.transaction_status = 'success' THEN 1 END) AS TRANSACTION_COUNT,
                COUNT(CASE WHEN tx.transaction_status = 'failed' THEN 1 END) AS TRANSACTION_FAILED_COUNT
            FROM account_transaction tx
            JOIN bank_account account
                ON account.id = COALESCE(tx.from_account_id, tx.to_account_id)
            GROUP BY DATE(tx.transaction_at), account.branch_id, tx.channel_id
            """
        )
        cumulative_rows(
            db.fetch_all(
                """
                SELECT
                    DATE(position.created_at) AS stat_date,
                    account.branch_id,
                    account.open_channel_id AS channel_id,
                    position.currency_code,
                    position.market_value_amount AS amount_value
                FROM wealth_position position
                JOIN bank_account account ON account.id = position.account_id
                WHERE position.position_status = 'active'
                """
            ),
            "WEALTH_AUM",
            "amount_value",
        )
        cumulative_rows(
            db.fetch_all(
                """
                SELECT
                    DATE(position.created_at) AS stat_date,
                    account.branch_id,
                    account.open_channel_id AS channel_id
                FROM wealth_position position
                JOIN bank_account account ON account.id = position.account_id
                WHERE position.position_status = 'active'
                """
            ),
            "WEALTH_POSITION_COUNT",
        )
        event_rows(
            """
            SELECT
                DATE(confirmed_at) AS stat_date,
                account.branch_id,
                wealth_order.channel_id,
                wealth_order.currency_code,
                SUM(confirmed_amount) AS WEALTH_ORDER_AMOUNT
            FROM wealth_order
            JOIN bank_account account ON account.id = wealth_order.account_id
            WHERE order_status = 'confirmed'
              AND confirmed_at IS NOT NULL
            GROUP BY DATE(confirmed_at), account.branch_id, wealth_order.channel_id, wealth_order.currency_code
            """
        )
        event_rows(
            """
            SELECT
                DATE(submitted_at) AS stat_date,
                customer.branch_id,
                loan_application.channel_id,
                COUNT(*) AS LOAN_APPLICATION_COUNT
            FROM loan_application
            JOIN customer ON customer.id = loan_application.customer_id
            GROUP BY DATE(submitted_at), customer.branch_id, loan_application.channel_id
            """
        )
        event_rows(
            """
            SELECT
                DATE(disbursement.disbursed_at) AS stat_date,
                account.branch_id,
                tx.channel_id,
                disbursement.currency_code,
                SUM(disbursement.disbursement_amount) AS LOAN_DISBURSE_AMOUNT
            FROM loan_disbursement disbursement
            JOIN bank_account account ON account.id = disbursement.account_id
            JOIN account_transaction tx ON tx.id = disbursement.transaction_id
            WHERE disbursement.disbursement_status = 'success'
            GROUP BY DATE(disbursement.disbursed_at), account.branch_id, tx.channel_id, disbursement.currency_code
            """
        )
        cumulative_rows(
            db.fetch_all(
                """
                SELECT
                    DATE(contract.signed_at) AS stat_date,
                    account.branch_id,
                    account.open_channel_id AS channel_id,
                    COUNT(*) AS row_count
                FROM loan_contract contract
                JOIN bank_account account ON account.id = contract.repayment_account_id
                WHERE contract.contract_status IN ('repaying', 'overdue', 'settled')
                GROUP BY contract.id, DATE(contract.signed_at), account.branch_id
                """
            ),
            "LOAN_CONTRACT_ACTIVE_COUNT",
        )
        cumulative_rows(
            db.fetch_all(
                """
                SELECT
                    DATE(contract.signed_at) AS stat_date,
                    account.branch_id,
                    account.open_channel_id AS channel_id,
                    contract.currency_code,
                    contract.outstanding_principal_amount AS amount_value
                FROM loan_contract contract
                JOIN bank_account account ON account.id = contract.repayment_account_id
                WHERE contract.contract_status IN ('repaying', 'overdue', 'settled')
                """
            ),
            "LOAN_OUTSTANDING_AMOUNT",
            "amount_value",
        )
        event_rows(
            """
            SELECT
                DATE(repayment.repaid_at) AS stat_date,
                account.branch_id,
                tx.channel_id,
                repayment.currency_code,
                SUM(repayment.repayment_amount) AS REPAYMENT_AMOUNT
            FROM repayment_record repayment
            JOIN bank_account account ON account.id = repayment.account_id
            JOIN account_transaction tx ON tx.id = repayment.transaction_id
            WHERE repayment.repayment_status = 'success'
            GROUP BY DATE(repayment.repaid_at), account.branch_id, tx.channel_id, repayment.currency_code
            """
        )
        cumulative_rows(
            db.fetch_all(
                """
                SELECT
                    DATE(overdue.created_at) AS stat_date,
                    customer.branch_id,
                    account.open_channel_id AS channel_id,
                    overdue.currency_code,
                    overdue.outstanding_amount AS amount_value
                FROM overdue_record overdue
                JOIN customer ON customer.id = overdue.customer_id
                JOIN loan_contract contract ON contract.id = overdue.contract_id
                JOIN bank_account account
                    ON account.id = contract.repayment_account_id
                WHERE overdue.overdue_status = 'active'
                """
            ),
            "OVERDUE_AMOUNT",
            "amount_value",
        )
        cumulative_rows(
            db.fetch_all(
                """
                SELECT
                    DATE(overdue.created_at) AS stat_date,
                    customer.branch_id,
                    account.open_channel_id AS channel_id
                FROM overdue_record overdue
                JOIN customer ON customer.id = overdue.customer_id
                JOIN loan_contract contract ON contract.id = overdue.contract_id
                JOIN bank_account account
                    ON account.id = contract.repayment_account_id
                WHERE overdue.overdue_status = 'active'
                """
            ),
            "OVERDUE_CONTRACT_COUNT",
        )
        event_rows(
            """
            SELECT
                DATE(event.created_at) AS stat_date,
                customer.branch_id,
                customer.register_channel_id AS channel_id,
                COUNT(*) AS RISK_EVENT_COUNT
            FROM risk_event event
            JOIN customer ON customer.id = event.customer_id
            GROUP BY DATE(event.created_at), customer.branch_id, customer.register_channel_id
            """
        )
        event_rows(
            """
            SELECT
                DATE(task.created_at) AS stat_date,
                customer.branch_id,
                customer.register_channel_id AS channel_id,
                COUNT(*) AS RISK_MANUAL_REVIEW_COUNT
            FROM manual_review_task task
            JOIN customer ON customer.id = task.customer_id
            GROUP BY DATE(task.created_at), customer.branch_id, customer.register_channel_id
            """
        )
        event_rows(
            """
            SELECT
                DATE(collection_case.created_at) AS stat_date,
                customer.branch_id,
                customer.register_channel_id AS channel_id,
                COUNT(*) AS COLLECTION_CASE_COUNT
            FROM collection_case
            JOIN customer ON customer.id = collection_case.customer_id
            GROUP BY
                DATE(collection_case.created_at),
                customer.branch_id,
                customer.register_channel_id
            """
        )
        event_rows(
            """
            SELECT
                DATE(repayment.repaid_at) AS stat_date,
                account.branch_id,
                tx.channel_id,
                repayment.currency_code,
                SUM(repayment.repayment_amount) AS COLLECTION_RECOVERED_AMOUNT
            FROM repayment_record repayment
            JOIN bank_account account ON account.id = repayment.account_id
            JOIN account_transaction tx ON tx.id = repayment.transaction_id
            WHERE repayment.repayment_type = 'collection'
              AND repayment.repayment_status = 'success'
            GROUP BY DATE(repayment.repaid_at), account.branch_id, tx.channel_id, repayment.currency_code
            """
        )
        self.add_collection_recovery_rate(values, dates, all_branch_id, all_channel_id)
        return self.rebuild_stat_rollups(values, all_branch_id, all_channel_id)

    def rebuild_stat_rollups(
        self,
        values: dict[tuple, float],
        all_branch_id: int,
        all_channel_id: int,
    ) -> dict[tuple, float]:
        rebuilt: dict[tuple, float] = {}
        for key, value in values.items():
            metric_code, stat_date, branch_id, channel_id, currency_code = key
            if branch_id == all_branch_id or channel_id == all_channel_id:
                continue
            for target_branch_id in {branch_id, all_branch_id}:
                for target_channel_id in {channel_id, all_channel_id}:
                    target_key = (
                        metric_code,
                        stat_date,
                        target_branch_id,
                        target_channel_id,
                        currency_code,
                    )
                    rebuilt[target_key] = round(rebuilt.get(target_key, 0) + float(value), 2)
        return rebuilt

    def add_collection_recovery_rate(
        self,
        values: dict[tuple, float],
        dates: list[date],
        all_branch_id: int,
        all_channel_id: int,
    ) -> None:
        assigned: dict[tuple, float] = {}
        recovered: dict[tuple, float] = {}

        def add_rollup(target: dict[tuple, float], stat_date: date, branch_id: int, channel_id: int, value: float) -> None:
            for target_branch_id in {branch_id, all_branch_id}:
                for target_channel_id in {channel_id, all_channel_id}:
                    key = (stat_date, target_branch_id, target_channel_id)
                    target[key] = target.get(key, 0) + float(value)

        for row in db.fetch_all(
            """
            SELECT
                DATE(collection_case.created_at) AS stat_date,
                customer.branch_id,
                customer.register_channel_id AS channel_id,
                SUM(collection_case.case_amount) AS assigned_amount
            FROM collection_case
            JOIN customer ON customer.id = collection_case.customer_id
            GROUP BY
                DATE(collection_case.created_at),
                customer.branch_id,
                customer.register_channel_id
            """
        ):
            if row["stat_date"] in dates:
                add_rollup(assigned, row["stat_date"], int(row["branch_id"]), int(row["channel_id"]), row["assigned_amount"])
        for row in db.fetch_all(
            """
            SELECT
                DATE(repayment.repaid_at) AS stat_date,
                account.branch_id,
                tx.channel_id,
                SUM(repayment.repayment_amount) AS recovered_amount
            FROM repayment_record repayment
            JOIN bank_account account ON account.id = repayment.account_id
            JOIN account_transaction tx ON tx.id = repayment.transaction_id
            WHERE repayment.repayment_type = 'collection'
              AND repayment.repayment_status = 'success'
            GROUP BY DATE(repayment.repaid_at), account.branch_id, tx.channel_id
            """
        ):
            if row["stat_date"] in dates:
                add_rollup(recovered, row["stat_date"], int(row["branch_id"]), int(row["channel_id"]), row["recovered_amount"])
        for key in set(assigned) | set(recovered):
            stat_date, branch_id, channel_id = key
            denominator = assigned.get(key, 0)
            value = round(recovered.get(key, 0) / denominator, 6) if denominator else 0
            values[("COLLECTION_RECOVERY_RATE", stat_date, branch_id, channel_id, None)] = value

    def all_id(self, table: str, code_column: str) -> int:
        row = db.fetch_one(f"SELECT id FROM {table} WHERE {code_column} = 'ALL'")
        return int(row["id"]) if row else 0
