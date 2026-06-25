"""Layer2: customer master data."""

from __future__ import annotations

from datetime import timedelta

from ..config import GENERATION_DEFAULTS, LAYERS
from .base import BaseGenerator
from .common import clear_tables, code, dt, fetch_ids


class Layer2Generator(BaseGenerator):
    layer = 2

    def run(self) -> None:
        self.header()
        clear_tables(LAYERS[self.layer]["tables"])
        total = int(GENERATION_DEFAULTS["customers"])
        enterprise_count = int(total * float(GENERATION_DEFAULTS["enterprise_ratio"]))
        personal_count = total - enterprise_count
        branch_ids = fetch_ids("dim_branch", "id > 0")
        channel_ids = fetch_ids("dim_channel", "id > 0")
        employee_ids = fetch_ids("dim_employee")
        customer_risk_ids = fetch_ids("dim_risk_level", "risk_level_type = 'customer'")

        counts: dict[str, int] = {}
        counts["customer"] = self.stream_rows(
            "customer",
            self.iter_customers(total, enterprise_count, branch_ids, channel_ids, customer_risk_ids),
            total_rows=total,
            build_step_name="build customer",
        )
        counts["customer_status_history"] = self.stream_rows(
            "customer_status_history",
            self.iter_customer_status_history(total, employee_ids),
            total_rows=total,
            build_step_name="build customer_status_history",
        )
        counts["customer_identity"] = self.stream_rows(
            "customer_identity",
            self.iter_customer_identity(total, personal_count),
            total_rows=total,
            build_step_name="build customer_identity",
        )
        counts["customer_contact"] = self.stream_rows(
            "customer_contact",
            self.iter_customer_contact(total),
            total_rows=total * 2,
            build_step_name="build customer_contact",
        )
        counts["customer_device"] = self.stream_rows(
            "customer_device",
            self.iter_customer_device(personal_count),
            total_rows=personal_count,
            build_step_name="build customer_device",
        )
        counts["customer_kyc"] = self.stream_rows(
            "customer_kyc",
            self.iter_customer_kyc(total),
            total_rows=total,
            build_step_name="build customer_kyc",
        )
        counts["enterprise_profile"] = self.stream_rows(
            "enterprise_profile",
            self.iter_enterprise_profile(personal_count + 1, total),
            total_rows=enterprise_count,
            build_step_name="build enterprise_profile",
        )
        counts["beneficial_owner"] = self.stream_rows(
            "beneficial_owner",
            self.iter_beneficial_owner(personal_count + 1, total),
            total_rows=enterprise_count * 2,
            build_step_name="build beneficial_owner",
        )
        counts["customer_risk_assessment"] = self.stream_rows(
            "customer_risk_assessment",
            self.iter_customer_risk_assessment(total, customer_risk_ids, employee_ids),
            total_rows=total,
            build_step_name="build customer_risk_assessment",
        )
        counts["customer_tag"] = self.stream_rows(
            "customer_tag",
            self.iter_customer_tags(),
            total_rows=8,
            build_step_name="build customer_tag",
        )
        counts["customer_tag_rel"] = self.stream_rows(
            "customer_tag_rel",
            self.iter_customer_tag_rel(total),
            total_rows=total,
            build_step_name="build customer_tag_rel",
        )
        self.log_table_counts(counts)

    def iter_customers(
        self,
        total: int,
        enterprise_count: int,
        branch_ids: list[int],
        channel_ids: list[int],
        risk_ids: list[int],
    ):
        personal_count = total - enterprise_count
        for customer_id in range(1, total + 1):
            is_enterprise = customer_id > personal_count
            status = self.customer_status(customer_id)
            opened_at = dt((customer_id * 7) % 1095, 9)
            closed_at = min(opened_at + timedelta(days=540), dt(0, 17)) if status == "closed" else None
            yield {
                "id": customer_id,
                "customer_no": code("CUS", customer_id, 8),
                "customer_type": "enterprise" if is_enterprise else "personal",
                "customer_name": (
                    f"中州企业{customer_id - personal_count:05d}"
                    if is_enterprise
                    else f"客户{customer_id:08d}"
                ),
                "branch_id": branch_ids[(customer_id - 1) % len(branch_ids)],
                "register_channel_id": channel_ids[(customer_id - 1) % len(channel_ids)],
                "risk_level_id": risk_ids[(customer_id - 1) % len(risk_ids)],
                "customer_status": status,
                "opened_at": opened_at,
                "closed_at": closed_at,
                "created_at": opened_at,
                "updated_at": closed_at or opened_at,
            }

    def customer_status(self, customer_id: int) -> str:
        mod = customer_id % 100
        if mod < 90:
            return "normal"
        if mod < 94:
            return "frozen"
        if mod < 98:
            return "restricted"
        return "closed"

    def iter_customer_status_history(self, total: int, employee_ids: list[int]):
        for customer_id in range(1, total + 1):
            status = self.customer_status(customer_id)
            yield {
                "id": customer_id,
                "customer_id": customer_id,
                "change_seq": 1,
                "from_status": "none",
                "to_status": status,
                "change_reason": "开户注册",
                "related_type": "none",
                "related_id": None,
                "operator_id": employee_ids[(customer_id - 1) % len(employee_ids)],
                "changed_at": dt((customer_id * 7) % 1095, 9),
                "created_at": dt((customer_id * 7) % 1095, 9),
            }

    def iter_customer_identity(self, total: int, personal_count: int):
        for customer_id in range(1, total + 1):
            is_enterprise = customer_id > personal_count
            yield {
                "id": customer_id,
                "customer_id": customer_id,
                "identity_type": "business_license" if is_enterprise else "id_card",
                "identity_no": (
                    f"91310000{customer_id:010d}"
                    if is_enterprise
                    else f"310101199001{customer_id:08d}"
                ),
                "legal_name": (
                    f"中州企业{customer_id - personal_count:05d}"
                    if is_enterprise
                    else f"客户{customer_id:08d}"
                ),
                "legal_representative": f"法人{customer_id:06d}" if is_enterprise else None,
                "identity_valid_from": dt(900).date(),
                "identity_valid_to": dt(-3650).date(),
                "verification_status": "verified",
                "current_flag": 1,
                "verified_at": dt((customer_id * 7) % 900, 10),
                "created_at": dt((customer_id * 7) % 900, 10),
                "updated_at": dt((customer_id * 7) % 900, 10),
            }

    def iter_customer_contact(self, total: int):
        row_id = 1
        for customer_id in range(1, total + 1):
            for contact_type, value in (
                ("mobile", f"138{customer_id:08d}"[-11:]),
                ("email", f"customer{customer_id:08d}@finance.example"),
            ):
                yield {
                    "id": row_id,
                    "customer_id": customer_id,
                    "contact_type": contact_type,
                    "contact_value": value,
                    "contact_name": f"联系人{customer_id:08d}",
                    "is_primary": "1" if contact_type == "mobile" else "0",
                    "verified_flag": 1,
                    "created_at": dt((customer_id * 7) % 900, 10),
                    "updated_at": dt((customer_id * 7) % 900, 10),
                }
                row_id += 1

    def iter_customer_device(self, personal_count: int):
        for customer_id in range(1, personal_count + 1):
            last_seen_at = dt((customer_id * 5) % 30, 18)
            yield {
                "id": customer_id,
                "device_no": code("DEV", customer_id, 8),
                "customer_id": customer_id,
                "device_fingerprint": f"fp-{customer_id:012d}",
                "device_type": "android" if customer_id % 2 else "ios",
                "device_name": f"Mobile-{customer_id % 20}",
                "app_version": "6.2.0",
                "os_version": "Android 15" if customer_id % 2 else "iOS 19",
                "push_token": code("PUSH", customer_id, 16),
                "ip_address": f"10.{customer_id % 255}.{customer_id // 255 % 255}.{customer_id % 254 + 1}",
                "geo_location": "上海市",
                "first_seen_at": dt((customer_id * 5) % 900, 12),
                "last_seen_at": last_seen_at,
                "trusted_flag": 1 if customer_id % 10 else 0,
                "risk_status": "normal" if customer_id % 10 else "suspicious",
                "created_at": dt((customer_id * 5) % 900, 12),
                "updated_at": last_seen_at,
            }

    def iter_customer_kyc(self, total: int):
        industries = ["金融", "制造", "零售", "互联网", "服务"]
        for customer_id in range(1, total + 1):
            annual_income = 120000 + (customer_id % 80) * 5000
            yield {
                "id": customer_id,
                "customer_id": customer_id,
                "occupation": "企业经营" if customer_id % 20 == 0 else "职员",
                "industry": industries[customer_id % len(industries)],
                "annual_income_amount": annual_income,
                "income_currency_code": "CNY",
                "fund_source": "salary" if customer_id % 20 else "business_income",
                "employment_status": "employed",
                "kyc_status": "valid",
                "compliance_status": "passed",
                "review_result": "approved",
                "reject_reason": None,
                "review_comment": "KYC审核通过",
                "reviewed_at": dt((customer_id * 7) % 900, 11),
                "created_at": dt((customer_id * 7) % 900, 10),
                "updated_at": dt((customer_id * 7) % 900, 11),
            }

    def iter_enterprise_profile(self, start_customer_id: int, end_customer_id: int):
        row_id = 1
        for customer_id in range(start_customer_id, end_customer_id + 1):
            yield {
                "id": row_id,
                "customer_id": customer_id,
                "company_name": f"中州企业{row_id:05d}",
                "registration_no": f"REG{row_id:010d}",
                "uniform_social_credit_code": f"91310000{row_id:010d}",
                "legal_representative": f"法人{row_id:06d}",
                "registered_capital_amount": 1_000_000 + row_id * 10_000,
                "registered_capital_currency_code": "CNY",
                "established_date": dt(3650 - row_id % 1000).date(),
                "registered_address": "上海市浦东新区金融大道 88 号",
                "business_address": "上海市浦东新区金融大道 88 号",
                "business_scope": "金融科技、供应链服务、企业经营服务",
                "industry": "服务",
                "company_scale": "small",
                "employee_count": 20 + row_id % 500,
                "annual_revenue_amount": 2_000_000 + row_id * 20_000,
                "taxpayer_type": "general",
                "business_status": "active",
                "compliance_status": "passed",
                "created_at": dt(row_id % 900, 9),
                "updated_at": dt(row_id % 900, 9),
            }
            row_id += 1

    def iter_beneficial_owner(self, start_customer_id: int, end_customer_id: int):
        row_id = 1
        for customer_id in range(start_customer_id, end_customer_id + 1):
            for owner_index, ratio in enumerate((60, 40), start=1):
                yield {
                    "id": row_id,
                    "customer_id": customer_id,
                    "owner_type": "natural_person",
                    "owner_name": f"受益人{customer_id:06d}-{owner_index}",
                    "identity_type": "id_card",
                    "identity_no": f"3101011988{customer_id % 10000:04d}{owner_index:04d}",
                    "mobile": f"137{row_id:08d}"[-11:],
                    "email": f"owner{row_id:08d}@finance.example",
                    "ownership_ratio": ratio,
                    "control_description": "直接持股",
                    "authorization_valid_from": dt(900).date(),
                    "authorization_valid_to": dt(-3650).date(),
                    "verification_status": "verified",
                    "created_at": dt(row_id % 900, 9),
                    "updated_at": dt(row_id % 900, 9),
                }
                row_id += 1

    def iter_customer_risk_assessment(
        self,
        total: int,
        risk_ids: list[int],
        employee_ids: list[int],
    ):
        for customer_id in range(1, total + 1):
            score = 20 + customer_id % 70
            yield {
                "id": customer_id,
                "assessment_no": code("CRA", customer_id, 8),
                "customer_id": customer_id,
                "risk_level_id": risk_ids[(customer_id - 1) % len(risk_ids)],
                "assessment_score": score,
                "assessment_type": "initial",
                "assessment_status": "valid",
                "valid_from": dt((customer_id * 7) % 900).date(),
                "valid_to": dt(-365).date(),
                "operator_id": employee_ids[(customer_id - 1) % len(employee_ids)],
                "adjust_reason": None,
                "created_at": dt((customer_id * 7) % 900, 10),
                "updated_at": dt((customer_id * 7) % 900, 10),
            }

    def iter_customer_tags(self):
        tags = [
            ("NEW", "新客户", "lifecycle"),
            ("ACTIVE", "活跃客户", "behavior"),
            ("WEALTH", "理财客户", "product"),
            ("LOAN", "信贷客户", "product"),
            ("HIGH_VALUE", "高价值客户", "value"),
            ("SALARY", "代发客户", "source"),
            ("SME", "小微企业", "enterprise"),
            ("ATTENTION", "关注客户", "risk"),
        ]
        for row_id, (tag_code, tag_name, tag_type) in enumerate(tags, start=1):
            yield {
                "id": row_id,
                "tag_code": tag_code,
                "tag_name": tag_name,
                "tag_type": tag_type,
                "yn": 1,
                "created_at": dt(900),
                "updated_at": dt(900),
            }

    def iter_customer_tag_rel(self, total: int):
        for customer_id in range(1, total + 1):
            yield {
                "id": customer_id,
                "customer_id": customer_id,
                "tag_id": customer_id % 8 + 1,
                "source_type": "rule",
                "source_id": None,
                "source_ref": "customer_profile",
                "model_version": "v1",
                "batch_no": "BATCH20260615",
                "effective_from": dt((customer_id * 7) % 900).date(),
                "effective_to": None,
                "created_at": dt((customer_id * 7) % 900, 11),
            }
