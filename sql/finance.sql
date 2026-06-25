SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE dim_branch (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    parent_id BIGINT NULL,
    branch_code VARCHAR(64) NOT NULL,
    branch_name VARCHAR(128) NOT NULL,
    branch_level VARCHAR(64) NOT NULL,
    province VARCHAR(128) NOT NULL,
    city VARCHAR(128) NOT NULL,
    address VARCHAR(255) NOT NULL,
    service_phone VARCHAR(32) NULL,
    branch_status VARCHAR(64) NOT NULL,
    opened_at DATETIME NOT NULL,
    closed_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_dim_branch_code (branch_code),
    KEY idx_dim_branch_parent_id (parent_id),
    CONSTRAINT fk_dim_branch_parent FOREIGN KEY (
        parent_id
    ) REFERENCES dim_branch (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '银行机构维表，定义总行、分行、支行和营业网点';

CREATE TABLE dim_channel (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    channel_code VARCHAR(64) NOT NULL,
    channel_name VARCHAR(128) NOT NULL,
    channel_type VARCHAR(64) NOT NULL,
    channel_status VARCHAR(64) NOT NULL,
    yn TINYINT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_dim_channel_code (channel_code)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '业务渠道维表，定义开户、交易、贷款、理财和服务请求来源';

CREATE TABLE dim_currency (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    currency_code VARCHAR(64) NOT NULL,
    currency_name VARCHAR(128) NOT NULL,
    symbol VARCHAR(128) NOT NULL,
    precision_scale INT NOT NULL DEFAULT 0,
    yn TINYINT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_dim_currency_code (currency_code)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '币种维表，定义账户余额、交易金额、贷款金额和理财金额使用的币种';

CREATE TABLE dim_risk_level (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    risk_level_code VARCHAR(64) NOT NULL,
    risk_level_name VARCHAR(128) NOT NULL,
    risk_level_type VARCHAR(64) NOT NULL,
    risk_score_min INT NOT NULL DEFAULT 0,
    risk_score_max INT NOT NULL DEFAULT 0,
    sort_no INT NOT NULL DEFAULT 0,
    yn TINYINT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_dim_risk_level_code (risk_level_code)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '风险等级维表，统一定义客户、产品和事件风险等级';

CREATE TABLE dim_employee (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    employee_no VARCHAR(64) NOT NULL,
    employee_name VARCHAR(128) NOT NULL,
    branch_id BIGINT NOT NULL,
    employee_role VARCHAR(128) NOT NULL,
    permission_codes JSON NOT NULL,
    mobile VARCHAR(32) NULL,
    email VARCHAR(128) NULL,
    employee_status VARCHAR(64) NOT NULL,
    joined_at DATETIME NOT NULL,
    resigned_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_dim_employee_no (employee_no),
    UNIQUE KEY uk_dim_employee_mobile (mobile),
    UNIQUE KEY uk_dim_employee_email (email),
    KEY idx_dim_employee_branch_id (branch_id),
    CONSTRAINT fk_dim_employee_branch FOREIGN KEY (
        branch_id
    ) REFERENCES dim_branch (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '员工主数据维表，定义员工编号、姓名、所属机构、岗位角色、联系方式和在职状态';

CREATE TABLE dim_product_category (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    parent_id BIGINT NULL,
    category_code VARCHAR(64) NOT NULL,
    category_name VARCHAR(128) NOT NULL,
    category_type VARCHAR(64) NOT NULL,
    category_level VARCHAR(64) NOT NULL,
    sort_no INT NOT NULL DEFAULT 0,
    yn TINYINT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_dim_product_category_code (category_code),
    KEY idx_dim_product_category_parent_id (parent_id),
    CONSTRAINT fk_dim_product_category_parent FOREIGN KEY (
        parent_id
    ) REFERENCES dim_product_category (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '产品分类维表，定义账户、贷款、理财和服务产品分类';

CREATE TABLE account_product (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    product_code VARCHAR(64) NOT NULL,
    product_name VARCHAR(128) NOT NULL,
    category_id BIGINT NOT NULL,
    currency_code VARCHAR(64) NOT NULL,
    account_type VARCHAR(64) NOT NULL,
    min_open_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    daily_transfer_limit DECIMAL(18, 2) NOT NULL DEFAULT 0,
    daily_withdraw_limit DECIMAL(18, 2) NOT NULL DEFAULT 0,
    annual_fee_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    product_status VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_account_product_code (product_code),
    KEY idx_account_product_category_id (category_id),
    KEY idx_account_product_currency_code (currency_code),
    CONSTRAINT fk_account_product_category FOREIGN KEY (
        category_id
    ) REFERENCES dim_product_category (id),
    CONSTRAINT fk_account_product_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '账户产品表，维护账户类型、开户条件、限额和账户费率';

CREATE TABLE service_product (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    service_code VARCHAR(64) NOT NULL,
    service_name VARCHAR(128) NOT NULL,
    category_id BIGINT NOT NULL,
    currency_code VARCHAR(64) NOT NULL,
    service_type VARCHAR(64) NOT NULL,
    fee_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    service_status VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_service_product_code (service_code),
    KEY idx_service_product_category_id (category_id),
    KEY idx_service_product_currency_code (currency_code),
    CONSTRAINT fk_service_product_category FOREIGN KEY (
        category_id
    ) REFERENCES dim_product_category (id),
    CONSTRAINT fk_service_product_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '服务产品表，维护服务包、服务费用、适用渠道和服务状态';

CREATE TABLE customer (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    customer_no VARCHAR(64) NOT NULL,
    customer_type VARCHAR(64) NOT NULL,
    customer_name VARCHAR(128) NOT NULL,
    branch_id BIGINT NOT NULL,
    register_channel_id BIGINT NOT NULL,
    risk_level_id BIGINT NOT NULL,
    customer_status VARCHAR(64) NOT NULL,
    opened_at DATETIME NOT NULL,
    closed_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_customer_no (customer_no),
    KEY idx_customer_branch_id (branch_id),
    KEY idx_customer_register_channel_id (register_channel_id),
    KEY idx_customer_risk_level_id (risk_level_id),
    CONSTRAINT fk_customer_branch FOREIGN KEY (
        branch_id
    ) REFERENCES dim_branch (id),
    CONSTRAINT fk_customer_register_channel FOREIGN KEY (
        register_channel_id
    ) REFERENCES dim_channel (id),
    CONSTRAINT fk_customer_risk_level FOREIGN KEY (
        risk_level_id
    ) REFERENCES dim_risk_level (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '客户主表，统一存储个人客户和企业客户的客户号、客户类型和生命周期状态';

CREATE TABLE customer_status_history (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    customer_id BIGINT NOT NULL,
    change_seq INT NOT NULL DEFAULT 0,
    from_status VARCHAR(64) NOT NULL,
    to_status VARCHAR(64) NOT NULL,
    change_reason TEXT NOT NULL,
    related_type VARCHAR(64) NOT NULL,
    related_id BIGINT NULL,
    operator_id BIGINT NULL,
    changed_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    UNIQUE KEY uk_customer_status_history_seq (customer_id, change_seq),
    UNIQUE KEY uk_customer_status_history_time (
        customer_id, changed_at, to_status
    ),
    KEY idx_customer_status_history_operator_id (operator_id),
    CONSTRAINT fk_customer_status_history_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_customer_status_history_operator FOREIGN KEY (
        operator_id
    ) REFERENCES dim_employee (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '客户状态历史表，维护客户实名、限制、冻结和销户等状态变更';

CREATE TABLE customer_identity (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    customer_id BIGINT NOT NULL,
    identity_type VARCHAR(64) NOT NULL,
    identity_no VARCHAR(64) NOT NULL,
    legal_name VARCHAR(128) NOT NULL,
    legal_representative VARCHAR(128) NULL,
    identity_valid_from DATE NULL,
    identity_valid_to DATE NULL,
    verification_status VARCHAR(64) NULL,
    current_flag TINYINT NOT NULL DEFAULT 0,
    verified_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_customer_identity_no (identity_type, identity_no),
    UNIQUE KEY uk_customer_identity_current (customer_id, current_flag),
    CONSTRAINT fk_customer_identity_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '客户实名信息表，维护实名证件、认证状态和认证时间';

CREATE TABLE customer_contact (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    customer_id BIGINT NOT NULL,
    contact_type VARCHAR(64) NOT NULL,
    contact_value VARCHAR(128) NOT NULL,
    contact_name VARCHAR(128) NULL,
    is_primary VARCHAR(128) NOT NULL,
    verified_flag TINYINT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_customer_contact_primary (
        customer_id, contact_type, is_primary
    ),
    UNIQUE KEY uk_customer_contact_verified_mobile (
        contact_type, contact_value
    ),
    CONSTRAINT fk_customer_contact_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '客户联系方式表，维护客户手机号、邮箱和地址';

CREATE TABLE customer_device (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    device_no VARCHAR(64) NOT NULL,
    customer_id BIGINT NOT NULL,
    device_fingerprint VARCHAR(128) NOT NULL,
    device_type VARCHAR(64) NOT NULL,
    device_name VARCHAR(128) NOT NULL,
    app_version VARCHAR(64) NULL,
    os_version VARCHAR(64) NULL,
    push_token VARCHAR(255) NULL,
    ip_address VARCHAR(255) NULL,
    geo_location VARCHAR(255) NULL,
    first_seen_at DATETIME NOT NULL,
    last_seen_at DATETIME NOT NULL,
    trusted_flag TINYINT NOT NULL DEFAULT 0,
    risk_status VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_customer_device_no (device_no),
    UNIQUE KEY uk_customer_device_fingerprint (customer_id, device_fingerprint),
    CONSTRAINT fk_customer_device_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '客户设备表，维护登录设备、设备指纹和设备风险状态';

CREATE TABLE customer_kyc (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    customer_id BIGINT NOT NULL,
    occupation VARCHAR(128) NOT NULL,
    industry VARCHAR(128) NOT NULL,
    annual_income_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    income_currency_code VARCHAR(64) NOT NULL,
    fund_source VARCHAR(64) NOT NULL,
    employment_status VARCHAR(64) NOT NULL,
    kyc_status VARCHAR(64) NOT NULL,
    compliance_status VARCHAR(64) NOT NULL,
    review_result VARCHAR(64) NOT NULL,
    reject_reason TEXT NULL,
    review_comment TEXT NULL,
    reviewed_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_customer_kyc_customer (customer_id),
    KEY idx_customer_kyc_income_currency_code (income_currency_code),
    CONSTRAINT fk_customer_kyc_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_customer_kyc_currency FOREIGN KEY (
        income_currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '客户 KYC 表，维护职业、收入、行业、资金来源和合规状态';

CREATE TABLE enterprise_profile (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    customer_id BIGINT NOT NULL,
    company_name VARCHAR(128) NOT NULL,
    registration_no VARCHAR(64) NULL,
    uniform_social_credit_code VARCHAR(64) NOT NULL,
    legal_representative VARCHAR(128) NULL,
    registered_capital_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    registered_capital_currency_code VARCHAR(64) NOT NULL,
    established_date DATE NOT NULL,
    registered_address VARCHAR(255) NOT NULL,
    business_address VARCHAR(255) NULL,
    business_scope TEXT NOT NULL,
    industry VARCHAR(128) NOT NULL,
    company_scale VARCHAR(128) NULL,
    employee_count INT NOT NULL DEFAULT 0,
    annual_revenue_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    taxpayer_type VARCHAR(64) NULL,
    business_status VARCHAR(64) NOT NULL,
    compliance_status VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_enterprise_profile_customer (customer_id),
    UNIQUE KEY uk_enterprise_profile_credit_code (uniform_social_credit_code),
    KEY idx_enterprise_profile_registered_capital_currency_code (
        registered_capital_currency_code
    ),
    CONSTRAINT fk_enterprise_profile_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_enterprise_profile_capital_currency FOREIGN KEY (
        registered_capital_currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '企业客户档案表，维护企业注册信息、经营信息和规模信息';

CREATE TABLE beneficial_owner (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    customer_id BIGINT NOT NULL,
    owner_type VARCHAR(64) NOT NULL,
    owner_name VARCHAR(128) NOT NULL,
    identity_type VARCHAR(64) NOT NULL,
    identity_no VARCHAR(64) NOT NULL,
    mobile VARCHAR(32) NULL,
    email VARCHAR(128) NULL,
    ownership_ratio DECIMAL(12, 6) NOT NULL DEFAULT 0,
    control_description TEXT NOT NULL,
    authorization_valid_from DATE NULL,
    authorization_valid_to DATE NULL,
    verification_status VARCHAR(64) NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_beneficial_owner_identity (
        customer_id, owner_type, identity_type, identity_no
    ),
    CONSTRAINT fk_beneficial_owner_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '受益所有人表，维护企业客户实际控制人、股东和授权经办人';

CREATE TABLE customer_risk_assessment (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    assessment_no VARCHAR(64) NOT NULL,
    customer_id BIGINT NOT NULL,
    risk_level_id BIGINT NOT NULL,
    assessment_score INT NOT NULL DEFAULT 0,
    assessment_type VARCHAR(64) NOT NULL,
    assessment_status VARCHAR(64) NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    operator_id BIGINT NULL,
    adjust_reason TEXT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_customer_risk_assessment_no (assessment_no),
    KEY idx_customer_risk_assessment_customer_id (customer_id),
    KEY idx_customer_risk_assessment_risk_level_id (risk_level_id),
    KEY idx_customer_risk_assessment_operator_id (operator_id),
    CONSTRAINT fk_customer_risk_assessment_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_customer_risk_assessment_level FOREIGN KEY (
        risk_level_id
    ) REFERENCES dim_risk_level (id),
    CONSTRAINT fk_customer_risk_assessment_operator FOREIGN KEY (
        operator_id
    ) REFERENCES dim_employee (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '客户风险测评表，维护理财风险承受能力测评记录';

CREATE TABLE customer_tag (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    tag_code VARCHAR(64) NOT NULL,
    tag_name VARCHAR(128) NOT NULL,
    tag_type VARCHAR(64) NOT NULL,
    yn TINYINT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_customer_tag_code (tag_code)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '客户标签表，维护客户分群、营销标签、风险标签和运营标签';

CREATE TABLE customer_tag_rel (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    customer_id BIGINT NOT NULL,
    tag_id BIGINT NOT NULL,
    source_type VARCHAR(64) NOT NULL,
    source_id BIGINT NULL,
    source_ref VARCHAR(64) NULL,
    model_version VARCHAR(64) NULL,
    batch_no VARCHAR(64) NULL,
    effective_from DATE NOT NULL,
    effective_to DATE NULL,
    created_at DATETIME NOT NULL,
    UNIQUE KEY uk_customer_tag_rel_active (customer_id, tag_id, source_type),
    KEY idx_customer_tag_rel_tag_id (tag_id),
    CONSTRAINT fk_customer_tag_rel_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_customer_tag_rel_tag FOREIGN KEY (
        tag_id
    ) REFERENCES customer_tag (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '客户标签关系表，维护客户和标签的多对多关系';

CREATE TABLE bank_account (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    account_no VARCHAR(64) NOT NULL,
    customer_id BIGINT NOT NULL,
    branch_id BIGINT NOT NULL,
    open_channel_id BIGINT NOT NULL,
    account_product_id BIGINT NOT NULL,
    currency_code VARCHAR(64) NOT NULL,
    account_type VARCHAR(64) NOT NULL,
    account_status VARCHAR(64) NOT NULL,
    balance_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    frozen_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    available_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    opened_at DATETIME NOT NULL,
    closed_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_bank_account_no (account_no),
    KEY idx_bank_account_customer_id (customer_id),
    KEY idx_bank_account_branch_id (branch_id),
    KEY idx_bank_account_open_channel_id (open_channel_id),
    KEY idx_bank_account_account_product_id (account_product_id),
    KEY idx_bank_account_currency_code (currency_code),
    CONSTRAINT fk_bank_account_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_bank_account_branch FOREIGN KEY (
        branch_id
    ) REFERENCES dim_branch (id),
    CONSTRAINT fk_bank_account_open_channel FOREIGN KEY (
        open_channel_id
    ) REFERENCES dim_channel (id),
    CONSTRAINT fk_bank_account_product FOREIGN KEY (
        account_product_id
    ) REFERENCES account_product (id),
    CONSTRAINT fk_bank_account_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '银行账户表，维护客户资金账户和余额信息';

CREATE TABLE bank_account_status_history (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    account_id BIGINT NOT NULL,
    customer_id BIGINT NOT NULL,
    change_seq INT NOT NULL DEFAULT 0,
    from_status VARCHAR(64) NOT NULL,
    to_status VARCHAR(64) NOT NULL,
    change_reason TEXT NOT NULL,
    related_type VARCHAR(64) NOT NULL,
    related_id BIGINT NULL,
    operator_id BIGINT NULL,
    changed_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    UNIQUE KEY uk_bank_account_status_history_seq (account_id, change_seq),
    UNIQUE KEY uk_bank_account_status_history_time (
        account_id, changed_at, to_status
    ),
    KEY idx_bank_account_status_history_customer_id (customer_id),
    KEY idx_bank_account_status_history_operator_id (operator_id),
    CONSTRAINT fk_bank_account_status_history_account FOREIGN KEY (
        account_id
    ) REFERENCES bank_account (id),
    CONSTRAINT fk_bank_account_status_history_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_bank_account_status_history_operator FOREIGN KEY (
        operator_id
    ) REFERENCES dim_employee (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '账户状态历史表，维护账户正常、限制、冻结和销户等状态变更';

CREATE TABLE bank_card (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    card_no VARCHAR(64) NOT NULL,
    customer_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL,
    card_type VARCHAR(64) NOT NULL,
    card_level VARCHAR(64) NOT NULL,
    card_status VARCHAR(64) NOT NULL,
    issued_at DATETIME NOT NULL,
    expired_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_bank_card_no (card_no),
    KEY idx_bank_card_customer_id (customer_id),
    KEY idx_bank_card_account_id (account_id),
    CONSTRAINT fk_bank_card_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_bank_card_account FOREIGN KEY (
        account_id
    ) REFERENCES bank_account (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '银行卡表，维护客户银行卡和绑定账户';

CREATE TABLE account_transaction (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    transaction_no VARCHAR(64) NOT NULL,
    customer_id BIGINT NOT NULL,
    from_account_id BIGINT NULL,
    to_account_id BIGINT NULL,
    card_id BIGINT NULL,
    channel_id BIGINT NOT NULL,
    original_transaction_id BIGINT NULL,
    biz_order_no VARCHAR(64) NULL,
    external_order_no VARCHAR(64) NULL,
    merchant_no VARCHAR(64) NULL,
    merchant_name VARCHAR(128) NULL,
    counterparty_name VARCHAR(128) NULL,
    counterparty_account_no VARCHAR(64) NULL,
    counterparty_bank_name VARCHAR(128) NULL,
    transaction_type VARCHAR(64) NOT NULL,
    transaction_status VARCHAR(64) NOT NULL,
    reconcile_status VARCHAR(64) NOT NULL,
    currency_code VARCHAR(64) NOT NULL,
    transaction_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    fee_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    related_type VARCHAR(64) NOT NULL,
    related_id BIGINT NULL,
    transaction_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_account_transaction_no (transaction_no),
    UNIQUE KEY uk_account_transaction_external_order (
        channel_id, external_order_no
    ),
    KEY idx_account_transaction_customer_id (customer_id),
    KEY idx_account_transaction_from_account_id (from_account_id),
    KEY idx_account_transaction_to_account_id (to_account_id),
    KEY idx_account_transaction_card_id (card_id),
    KEY idx_account_transaction_original_transaction_id (
        original_transaction_id
    ),
    KEY idx_account_transaction_currency_code (currency_code),
    CONSTRAINT fk_account_transaction_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_account_transaction_from_account FOREIGN KEY (
        from_account_id
    ) REFERENCES bank_account (id),
    CONSTRAINT fk_account_transaction_to_account FOREIGN KEY (
        to_account_id
    ) REFERENCES bank_account (id),
    CONSTRAINT fk_account_transaction_card FOREIGN KEY (
        card_id
    ) REFERENCES bank_card (id),
    CONSTRAINT fk_account_transaction_channel FOREIGN KEY (
        channel_id
    ) REFERENCES dim_channel (id),
    CONSTRAINT fk_account_transaction_original FOREIGN KEY (
        original_transaction_id
    ) REFERENCES account_transaction (id),
    CONSTRAINT fk_account_transaction_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '账户交易表，维护客户资金交易主记录';

CREATE TABLE channel_transaction (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    channel_txn_no VARCHAR(64) NOT NULL,
    channel_id BIGINT NOT NULL,
    transaction_id BIGINT NULL,
    channel_order_no VARCHAR(64) NULL,
    channel_trade_no VARCHAR(64) NULL,
    request_no VARCHAR(64) NOT NULL,
    request_type VARCHAR(64) NOT NULL,
    request_status VARCHAR(64) NOT NULL,
    callback_status VARCHAR(64) NOT NULL,
    reconcile_status VARCHAR(64) NOT NULL,
    currency_code VARCHAR(64) NOT NULL,
    channel_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    channel_fee_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    error_code VARCHAR(64) NULL,
    error_message TEXT NULL,
    requested_at DATETIME NOT NULL,
    responded_at DATETIME NULL,
    callback_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_channel_transaction_no (channel_txn_no),
    UNIQUE KEY uk_channel_transaction_request (channel_id, request_no),
    UNIQUE KEY uk_channel_transaction_order (channel_id, channel_order_no),
    UNIQUE KEY uk_channel_transaction_trade (channel_id, channel_trade_no),
    KEY idx_channel_transaction_transaction_id (transaction_id),
    KEY idx_channel_transaction_currency_code (currency_code),
    CONSTRAINT fk_channel_transaction_channel FOREIGN KEY (
        channel_id
    ) REFERENCES dim_channel (id),
    CONSTRAINT fk_channel_transaction_account_transaction FOREIGN KEY (
        transaction_id
    ) REFERENCES account_transaction (id),
    CONSTRAINT fk_channel_transaction_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '渠道流水表，维护外部渠道订单、请求响应、回调和对账状态';

CREATE TABLE reconciliation_batch (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    batch_no VARCHAR(64) NOT NULL,
    channel_id BIGINT NOT NULL,
    reconcile_date DATE NOT NULL,
    active_reconcile_date_key DATE GENERATED ALWAYS AS (
        CASE
            WHEN batch_status IN ('created', 'processing', 'completed')
                THEN reconcile_date
        END
    ) STORED,
    file_name VARCHAR(128) NOT NULL,
    file_hash VARCHAR(128) NULL,
    batch_status VARCHAR(64) NOT NULL,
    started_at DATETIME NOT NULL,
    completed_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_reconciliation_batch_no (batch_no),
    UNIQUE KEY uk_reconciliation_batch_active_channel_date (
        channel_id, active_reconcile_date_key
    ),
    CONSTRAINT fk_reconciliation_batch_channel FOREIGN KEY (
        channel_id
    ) REFERENCES dim_channel (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '对账批次表，维护渠道对账文件、批次状态和对账范围';

CREATE TABLE reconciliation_result (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    result_no VARCHAR(64) NOT NULL,
    batch_id BIGINT NOT NULL,
    transaction_id BIGINT NULL,
    channel_transaction_id BIGINT NULL,
    result_type VARCHAR(64) NOT NULL,
    difference_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    process_status VARCHAR(64) NOT NULL,
    process_comment TEXT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_reconciliation_result_no (result_no),
    UNIQUE KEY uk_reconciliation_result_bank_only (batch_id, transaction_id),
    UNIQUE KEY uk_reconciliation_result_channel_only (
        batch_id, channel_transaction_id
    ),
    KEY idx_reconciliation_result_transaction_id (transaction_id),
    KEY idx_reconciliation_result_channel_transaction_id (
        channel_transaction_id
    ),
    CONSTRAINT fk_reconciliation_result_batch FOREIGN KEY (
        batch_id
    ) REFERENCES reconciliation_batch (id),
    CONSTRAINT fk_reconciliation_result_transaction FOREIGN KEY (
        transaction_id
    ) REFERENCES account_transaction (id),
    CONSTRAINT fk_reconciliation_result_channel_transaction FOREIGN KEY (
        channel_transaction_id
    ) REFERENCES channel_transaction (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '对账结果表，维护交易与渠道流水的匹配、差错和处理状态';

CREATE TABLE reconciliation_adjustment (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    adjustment_no VARCHAR(64) NOT NULL,
    result_id BIGINT NOT NULL,
    transaction_id BIGINT NULL,
    currency_code VARCHAR(64) NOT NULL,
    adjustment_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    adjustment_direction VARCHAR(128) NOT NULL,
    adjustment_status VARCHAR(64) NOT NULL,
    approved_by BIGINT NULL,
    approved_at DATETIME NULL,
    posted_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_reconciliation_adjustment_no (adjustment_no),
    KEY idx_reconciliation_adjustment_result_id (result_id),
    KEY idx_reconciliation_adjustment_transaction_id (transaction_id),
    KEY idx_reconciliation_adjustment_currency_code (currency_code),
    KEY idx_reconciliation_adjustment_approved_by (approved_by),
    CONSTRAINT fk_reconciliation_adjustment_result FOREIGN KEY (
        result_id
    ) REFERENCES reconciliation_result (id),
    CONSTRAINT fk_reconciliation_adjustment_transaction FOREIGN KEY (
        transaction_id
    ) REFERENCES account_transaction (id),
    CONSTRAINT fk_reconciliation_adjustment_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code),
    CONSTRAINT fk_reconciliation_adjustment_approver FOREIGN KEY (
        approved_by
    ) REFERENCES dim_employee (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '对账调账表，维护差错调账交易、调账金额和审批状态';

CREATE TABLE fund_freeze (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    freeze_no VARCHAR(64) NOT NULL,
    account_id BIGINT NOT NULL,
    customer_id BIGINT NOT NULL,
    freeze_type VARCHAR(64) NOT NULL,
    related_type VARCHAR(64) NOT NULL,
    related_id BIGINT NULL,
    judicial_instruction_no VARCHAR(64) NULL,
    currency_code VARCHAR(64) NOT NULL,
    freeze_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    released_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    freeze_status VARCHAR(64) NOT NULL,
    frozen_at DATETIME NOT NULL,
    released_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_fund_freeze_no (freeze_no),
    KEY idx_fund_freeze_account_id (account_id),
    KEY idx_fund_freeze_customer_id (customer_id),
    KEY idx_fund_freeze_currency_code (currency_code),
    CONSTRAINT fk_fund_freeze_account FOREIGN KEY (
        account_id
    ) REFERENCES bank_account (id),
    CONSTRAINT fk_fund_freeze_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_fund_freeze_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '资金冻结表，维护账户资金冻结、解冻和释放记录';

CREATE TABLE fund_freeze_operation (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    operation_no VARCHAR(64) NOT NULL,
    freeze_id BIGINT NULL,
    account_id BIGINT NOT NULL,
    customer_id BIGINT NOT NULL,
    transaction_id BIGINT NULL,
    related_type VARCHAR(64) NOT NULL,
    related_id BIGINT NULL,
    judicial_instruction_no VARCHAR(64) NULL,
    operation_type VARCHAR(64) NOT NULL,
    currency_code VARCHAR(64) NOT NULL,
    operation_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    before_frozen_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    after_frozen_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    operation_source VARCHAR(64) NULL,
    operator_id BIGINT NULL,
    operation_reason TEXT NULL,
    operated_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    UNIQUE KEY uk_fund_freeze_operation_no (operation_no),
    KEY idx_fund_freeze_operation_freeze_id (freeze_id),
    KEY idx_fund_freeze_operation_account_id (account_id),
    KEY idx_fund_freeze_operation_customer_id (customer_id),
    KEY idx_fund_freeze_operation_transaction_id (transaction_id),
    KEY idx_fund_freeze_operation_currency_code (currency_code),
    KEY idx_fund_freeze_operation_operator_id (operator_id),
    CONSTRAINT fk_fund_freeze_operation_freeze FOREIGN KEY (
        freeze_id
    ) REFERENCES fund_freeze (id),
    CONSTRAINT fk_fund_freeze_operation_account FOREIGN KEY (
        account_id
    ) REFERENCES bank_account (id),
    CONSTRAINT fk_fund_freeze_operation_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_fund_freeze_operation_transaction FOREIGN KEY (
        transaction_id
    ) REFERENCES account_transaction (id),
    CONSTRAINT fk_fund_freeze_operation_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code),
    CONSTRAINT fk_fund_freeze_operation_operator FOREIGN KEY (
        operator_id
    ) REFERENCES dim_employee (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '资金冻结操作明细表，维护每次冻结、解冻、释放和取消操作';

CREATE TABLE account_ledger (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    ledger_no VARCHAR(64) NOT NULL,
    account_id BIGINT NOT NULL,
    customer_id BIGINT NOT NULL,
    transaction_id BIGINT NULL,
    freeze_id BIGINT NULL,
    freeze_operation_id BIGINT NULL,
    ledger_type VARCHAR(64) NOT NULL,
    currency_code VARCHAR(64) NOT NULL,
    amount_delta VARCHAR(128) NOT NULL,
    frozen_delta VARCHAR(128) NOT NULL,
    balance_after VARCHAR(128) NOT NULL,
    frozen_after VARCHAR(128) NOT NULL,
    available_after VARCHAR(128) NOT NULL,
    created_at DATETIME NOT NULL,
    UNIQUE KEY uk_account_ledger_no (ledger_no),
    KEY idx_account_ledger_account_id (account_id),
    KEY idx_account_ledger_customer_id (customer_id),
    KEY idx_account_ledger_transaction_id (transaction_id),
    KEY idx_account_ledger_freeze_id (freeze_id),
    KEY idx_account_ledger_freeze_operation_id (freeze_operation_id),
    KEY idx_account_ledger_currency_code (currency_code),
    CONSTRAINT fk_account_ledger_account FOREIGN KEY (
        account_id
    ) REFERENCES bank_account (id),
    CONSTRAINT fk_account_ledger_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_account_ledger_transaction FOREIGN KEY (
        transaction_id
    ) REFERENCES account_transaction (id),
    CONSTRAINT fk_account_ledger_freeze FOREIGN KEY (
        freeze_id
    ) REFERENCES fund_freeze (id),
    CONSTRAINT fk_account_ledger_freeze_operation FOREIGN KEY (
        freeze_operation_id
    ) REFERENCES fund_freeze_operation (id),
    CONSTRAINT fk_account_ledger_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '账户流水表，维护账户余额变动和交易后余额';

CREATE TABLE wealth_product (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    product_code VARCHAR(64) NOT NULL,
    product_name VARCHAR(128) NOT NULL,
    category_id BIGINT NOT NULL,
    currency_code VARCHAR(64) NOT NULL,
    risk_level_id BIGINT NOT NULL,
    product_type VARCHAR(64) NOT NULL,
    operation_mode VARCHAR(64) NOT NULL,
    min_purchase_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    increment_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    expected_yield_rate DECIMAL(12, 6) NOT NULL DEFAULT 0,
    nav_based_flag TINYINT NOT NULL DEFAULT 0,
    sale_start_at DATETIME NOT NULL,
    sale_end_at DATETIME NULL,
    value_date_rule VARCHAR(64) NOT NULL,
    redeem_rule VARCHAR(64) NOT NULL,
    product_status VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_wealth_product_code (product_code),
    KEY idx_wealth_product_category_id (category_id),
    KEY idx_wealth_product_currency_code (currency_code),
    KEY idx_wealth_product_risk_level_id (risk_level_id),
    CONSTRAINT fk_wealth_product_category FOREIGN KEY (
        category_id
    ) REFERENCES dim_product_category (id),
    CONSTRAINT fk_wealth_product_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code),
    CONSTRAINT fk_wealth_product_risk_level FOREIGN KEY (
        risk_level_id
    ) REFERENCES dim_risk_level (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '理财产品表，定义理财产品基础信息、风险等级、开放规则和产品状态';

CREATE TABLE wealth_open_period (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    product_id BIGINT NOT NULL,
    period_no INT NOT NULL DEFAULT 0,
    purchase_start_at DATETIME NOT NULL,
    purchase_end_at DATETIME NOT NULL,
    redeem_start_at DATETIME NULL,
    redeem_end_at DATETIME NULL,
    period_status VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_wealth_open_period (product_id, period_no),
    CONSTRAINT fk_wealth_open_period_product FOREIGN KEY (
        product_id
    ) REFERENCES wealth_product (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '理财开放期表，维护开放式和定期开放产品的申购赎回窗口';

CREATE TABLE wealth_trade_calendar (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    product_id BIGINT NOT NULL,
    calendar_date DATE NOT NULL,
    trade_flag TINYINT NOT NULL DEFAULT 0,
    purchase_confirm_date DATE NOT NULL,
    redeem_confirm_date DATE NOT NULL,
    redeem_arrival_date DATE NOT NULL,
    created_at DATETIME NOT NULL,
    UNIQUE KEY uk_wealth_trade_calendar (product_id, calendar_date),
    CONSTRAINT fk_wealth_trade_calendar_product FOREIGN KEY (
        product_id
    ) REFERENCES wealth_product (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '理财交易日历表，维护交易日、确认日和到账日规则';

CREATE TABLE wealth_settlement_rule (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    product_id BIGINT NOT NULL,
    purchase_confirm_days INT NOT NULL DEFAULT 0,
    redeem_confirm_days INT NOT NULL DEFAULT 0,
    redeem_arrival_days INT NOT NULL DEFAULT 0,
    cutoff_time TIME NOT NULL,
    rule_status VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_wealth_settlement_rule_product (product_id),
    CONSTRAINT fk_wealth_settlement_rule_product FOREIGN KEY (
        product_id
    ) REFERENCES wealth_product (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '理财清算规则表，维护申购确认、赎回确认和到账周期';

CREATE TABLE wealth_nav (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    product_id BIGINT NOT NULL,
    nav_date DATE NOT NULL,
    unit_nav DECIMAL(18, 6) NOT NULL DEFAULT 0,
    accumulated_nav DECIMAL(18, 6) NOT NULL DEFAULT 0,
    daily_yield_rate DECIMAL(12, 6) NULL DEFAULT 0,
    annualized_yield_rate DECIMAL(12, 6) NULL DEFAULT 0,
    created_at DATETIME NOT NULL,
    UNIQUE KEY uk_wealth_nav_product_date (product_id, nav_date),
    CONSTRAINT fk_wealth_nav_product FOREIGN KEY (
        product_id
    ) REFERENCES wealth_product (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '理财产品净值表，维护理财产品每日净值';

CREATE TABLE wealth_position (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    customer_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    currency_code VARCHAR(64) NOT NULL,
    holding_share DECIMAL(18, 6) NOT NULL DEFAULT 0,
    available_share DECIMAL(18, 6) NOT NULL DEFAULT 0,
    frozen_share DECIMAL(18, 6) NOT NULL DEFAULT 0,
    cost_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    market_value_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    accumulated_income_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    last_nav DECIMAL(18, 6) NOT NULL DEFAULT 0,
    last_valuation_date DATE NOT NULL,
    position_status VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_wealth_position_active (customer_id, account_id, product_id),
    KEY idx_wealth_position_account_id (account_id),
    KEY idx_wealth_position_product_id (product_id),
    KEY idx_wealth_position_currency_code (currency_code),
    CONSTRAINT fk_wealth_position_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_wealth_position_account FOREIGN KEY (
        account_id
    ) REFERENCES bank_account (id),
    CONSTRAINT fk_wealth_position_product FOREIGN KEY (
        product_id
    ) REFERENCES wealth_product (id),
    CONSTRAINT fk_wealth_position_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '理财持仓表，维护客户理财份额、成本、市值和收益';

CREATE TABLE wealth_order (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_no VARCHAR(64) NOT NULL,
    customer_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    risk_assessment_id BIGINT NULL,
    original_order_id BIGINT NULL,
    transaction_id BIGINT NULL,
    freeze_id BIGINT NULL,
    position_id BIGINT NULL,
    order_type VARCHAR(64) NOT NULL,
    order_status VARCHAR(64) NOT NULL,
    currency_code VARCHAR(64) NOT NULL,
    order_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    order_share DECIMAL(18, 6) NOT NULL DEFAULT 0,
    confirmed_amount DECIMAL(18, 2) NULL DEFAULT 0,
    confirmed_share DECIMAL(18, 6) NULL DEFAULT 0,
    confirmed_nav VARCHAR(128) NULL,
    fee_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    cancel_reason TEXT NULL,
    submitted_at DATETIME NOT NULL,
    confirmed_at DATETIME NULL,
    cancelled_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_wealth_order_no (order_no),
    UNIQUE KEY uk_wealth_order_transaction (transaction_id),
    KEY idx_wealth_order_customer_id (customer_id),
    KEY idx_wealth_order_account_id (account_id),
    KEY idx_wealth_order_product_id (product_id),
    KEY idx_wealth_order_channel_id (channel_id),
    KEY idx_wealth_order_risk_assessment_id (risk_assessment_id),
    KEY idx_wealth_order_original_order_id (original_order_id),
    KEY idx_wealth_order_freeze_id (freeze_id),
    KEY idx_wealth_order_position_id (position_id),
    KEY idx_wealth_order_currency_code (currency_code),
    CONSTRAINT fk_wealth_order_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_wealth_order_account FOREIGN KEY (
        account_id
    ) REFERENCES bank_account (id),
    CONSTRAINT fk_wealth_order_product FOREIGN KEY (
        product_id
    ) REFERENCES wealth_product (id),
    CONSTRAINT fk_wealth_order_channel FOREIGN KEY (
        channel_id
    ) REFERENCES dim_channel (id),
    CONSTRAINT fk_wealth_order_risk_assessment FOREIGN KEY (
        risk_assessment_id
    ) REFERENCES customer_risk_assessment (id),
    CONSTRAINT fk_wealth_order_original FOREIGN KEY (
        original_order_id
    ) REFERENCES wealth_order (id),
    CONSTRAINT fk_wealth_order_transaction FOREIGN KEY (
        transaction_id
    ) REFERENCES account_transaction (id),
    CONSTRAINT fk_wealth_order_freeze FOREIGN KEY (
        freeze_id
    ) REFERENCES fund_freeze (id),
    CONSTRAINT fk_wealth_order_position FOREIGN KEY (
        position_id
    ) REFERENCES wealth_position (id),
    CONSTRAINT fk_wealth_order_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '理财订单表，维护申购、赎回、撤单和确认状态';

CREATE TABLE wealth_income (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    income_no VARCHAR(64) NOT NULL,
    customer_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL,
    position_id BIGINT NULL,
    product_id BIGINT NOT NULL,
    transaction_id BIGINT NULL,
    ledger_id BIGINT NULL,
    income_date DATE NOT NULL,
    income_type VARCHAR(64) NOT NULL,
    currency_code VARCHAR(64) NOT NULL,
    income_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    settled_flag TINYINT NOT NULL DEFAULT 0,
    settled_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    UNIQUE KEY uk_wealth_income_no (income_no),
    UNIQUE KEY uk_wealth_income_position_date_type (
        position_id, income_date, income_type
    ),
    KEY idx_wealth_income_customer_id (customer_id),
    KEY idx_wealth_income_account_id (account_id),
    KEY idx_wealth_income_product_id (product_id),
    KEY idx_wealth_income_transaction_id (transaction_id),
    KEY idx_wealth_income_ledger_id (ledger_id),
    KEY idx_wealth_income_currency_code (currency_code),
    CONSTRAINT fk_wealth_income_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_wealth_income_account FOREIGN KEY (
        account_id
    ) REFERENCES bank_account (id),
    CONSTRAINT fk_wealth_income_position FOREIGN KEY (
        position_id
    ) REFERENCES wealth_position (id),
    CONSTRAINT fk_wealth_income_product FOREIGN KEY (
        product_id
    ) REFERENCES wealth_product (id),
    CONSTRAINT fk_wealth_income_transaction FOREIGN KEY (
        transaction_id
    ) REFERENCES account_transaction (id),
    CONSTRAINT fk_wealth_income_ledger FOREIGN KEY (
        ledger_id
    ) REFERENCES account_ledger (id),
    CONSTRAINT fk_wealth_income_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '理财收益表，维护每日收益、分红和收益入账记录';

CREATE TABLE wealth_product_notice (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    notice_no VARCHAR(64) NOT NULL,
    product_id BIGINT NOT NULL,
    notice_type VARCHAR(64) NOT NULL,
    notice_title VARCHAR(128) NOT NULL,
    notice_content TEXT NOT NULL,
    published_at DATETIME NOT NULL,
    notice_status VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_wealth_product_notice_no (notice_no),
    KEY idx_wealth_product_notice_product_id (product_id),
    CONSTRAINT fk_wealth_product_notice_product FOREIGN KEY (
        product_id
    ) REFERENCES wealth_product (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '理财产品公告表，维护产品说明、开放期、分红和风险提示公告';

CREATE TABLE loan_product (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    product_code VARCHAR(64) NOT NULL,
    product_name VARCHAR(128) NOT NULL,
    category_id BIGINT NOT NULL,
    currency_code VARCHAR(64) NOT NULL,
    risk_level_id BIGINT NOT NULL,
    loan_type VARCHAR(64) NOT NULL,
    min_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    max_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    min_term_months INT NOT NULL DEFAULT 0,
    max_term_months INT NOT NULL DEFAULT 0,
    annual_interest_rate DECIMAL(12, 6) NOT NULL DEFAULT 0,
    min_interest_rate DECIMAL(12, 6) NOT NULL DEFAULT 0,
    max_interest_rate DECIMAL(12, 6) NOT NULL DEFAULT 0,
    collateral_required_flag TINYINT NOT NULL DEFAULT 0,
    guarantee_required_flag TINYINT NOT NULL DEFAULT 0,
    post_registration_allowed_flag TINYINT NOT NULL DEFAULT 0,
    min_guarantee_ratio DECIMAL(12, 6) NOT NULL DEFAULT 0,
    repayment_method VARCHAR(64) NOT NULL,
    product_status VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_loan_product_code (product_code),
    KEY idx_loan_product_category_id (category_id),
    KEY idx_loan_product_currency_code (currency_code),
    KEY idx_loan_product_risk_level_id (risk_level_id),
    CONSTRAINT fk_loan_product_category FOREIGN KEY (
        category_id
    ) REFERENCES dim_product_category (id),
    CONSTRAINT fk_loan_product_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code),
    CONSTRAINT fk_loan_product_risk_level FOREIGN KEY (
        risk_level_id
    ) REFERENCES dim_risk_level (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '贷款产品表，定义消费贷款产品的额度、期限、利率和还款方式';

CREATE TABLE loan_product_eligibility_rule (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    product_id BIGINT NOT NULL,
    rule_code VARCHAR(64) NOT NULL,
    rule_name VARCHAR(128) NOT NULL,
    rule_type VARCHAR(64) NOT NULL,
    rule_expression TEXT NOT NULL,
    threshold_value VARCHAR(128) NOT NULL,
    decision_action VARCHAR(64) NOT NULL,
    yn TINYINT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_loan_product_eligibility_rule (product_id, rule_code),
    CONSTRAINT fk_loan_product_eligibility_product FOREIGN KEY (
        product_id
    ) REFERENCES loan_product (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '贷款产品准入规则表，维护收入、负债、征信和客户类型准入条件';

CREATE TABLE loan_product_rate_tier (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    product_id BIGINT NOT NULL,
    tier_code VARCHAR(64) NOT NULL,
    score_min INT NOT NULL DEFAULT 0,
    score_max INT NOT NULL DEFAULT 0,
    term_min_months INT NOT NULL DEFAULT 0,
    term_max_months INT NOT NULL DEFAULT 0,
    amount_min VARCHAR(128) NOT NULL,
    amount_max VARCHAR(128) NOT NULL,
    annual_interest_rate DECIMAL(12, 6) NOT NULL DEFAULT 0,
    yn TINYINT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_loan_product_rate_tier (product_id, tier_code),
    CONSTRAINT fk_loan_product_rate_tier_product FOREIGN KEY (
        product_id
    ) REFERENCES loan_product (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '贷款产品利率档位表，维护评分、期限、金额对应的利率区间';

CREATE TABLE loan_product_required_material (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    product_id BIGINT NOT NULL,
    material_type VARCHAR(64) NOT NULL,
    required_stage VARCHAR(64) NOT NULL,
    required_flag TINYINT NOT NULL DEFAULT 0,
    waivable_flag TINYINT NOT NULL DEFAULT 0,
    yn TINYINT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_loan_product_required_material (
        product_id, material_type, required_stage
    ),
    CONSTRAINT fk_loan_product_required_material_product FOREIGN KEY (
        product_id
    ) REFERENCES loan_product (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '贷款产品必需材料表，维护申请、审批和放款所需材料';

CREATE TABLE credit_application (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    credit_application_no VARCHAR(64) NOT NULL,
    customer_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    apply_limit_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    currency_code VARCHAR(64) NOT NULL,
    application_status VARCHAR(64) NOT NULL,
    submitted_at DATETIME NOT NULL,
    approved_at DATETIME NULL,
    rejected_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_credit_application_no (credit_application_no),
    KEY idx_credit_application_customer_id (customer_id),
    KEY idx_credit_application_product_id (product_id),
    KEY idx_credit_application_channel_id (channel_id),
    KEY idx_credit_application_currency_code (currency_code),
    CONSTRAINT fk_credit_application_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_credit_application_product FOREIGN KEY (
        product_id
    ) REFERENCES loan_product (id),
    CONSTRAINT fk_credit_application_channel FOREIGN KEY (
        channel_id
    ) REFERENCES dim_channel (id),
    CONSTRAINT fk_credit_application_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '授信申请表，维护客户授信申请、申请额度、申请状态和渠道';

CREATE TABLE credit_application_material (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    material_no VARCHAR(64) NOT NULL,
    credit_application_id BIGINT NULL,
    customer_id BIGINT NOT NULL,
    material_type VARCHAR(64) NOT NULL,
    material_name VARCHAR(128) NOT NULL,
    file_url VARCHAR(512) NULL,
    file_hash VARCHAR(128) NULL,
    submitted_by VARCHAR(128) NOT NULL,
    verification_status VARCHAR(64) NULL,
    verified_by BIGINT NULL,
    verified_at DATETIME NULL,
    submitted_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_credit_application_material_no (material_no),
    UNIQUE KEY uk_credit_application_material_type (
        credit_application_id, material_type, material_name
    ),
    KEY idx_credit_application_material_customer_id (customer_id),
    KEY idx_credit_application_material_verified_by (verified_by),
    CONSTRAINT fk_credit_application_material_application FOREIGN KEY (
        credit_application_id
    ) REFERENCES credit_application (id),
    CONSTRAINT fk_credit_application_material_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_credit_application_material_verifier FOREIGN KEY (
        verified_by
    ) REFERENCES dim_employee (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '授信申请材料表，维护授信申请阶段的征信授权、收入证明和经营资料';

CREATE TABLE credit_approval_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    credit_application_id BIGINT NULL,
    approval_node VARCHAR(128) NOT NULL,
    approval_round INT NOT NULL DEFAULT 0,
    approver_id BIGINT NOT NULL,
    approval_result VARCHAR(64) NOT NULL,
    approved_limit_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    approval_comment TEXT NULL,
    approved_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    UNIQUE KEY uk_credit_approval_node_round (
        credit_application_id, approval_node, approval_round
    ),
    KEY idx_credit_approval_record_approver_id (approver_id),
    CONSTRAINT fk_credit_approval_application FOREIGN KEY (
        credit_application_id
    ) REFERENCES credit_application (id),
    CONSTRAINT fk_credit_approval_approver FOREIGN KEY (
        approver_id
    ) REFERENCES dim_employee (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '授信审批记录表，维护授信审批节点、审批额度和审批结论';

CREATE TABLE credit_limit (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    limit_no VARCHAR(64) NOT NULL,
    credit_application_id BIGINT NULL,
    customer_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    currency_code VARCHAR(64) NOT NULL,
    total_limit_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    used_limit_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    frozen_limit_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    available_limit_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    limit_status VARCHAR(64) NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_credit_limit_no (limit_no),
    UNIQUE KEY uk_credit_limit_active_customer_product (
        customer_id, product_id, limit_status
    ),
    KEY idx_credit_limit_credit_application_id (credit_application_id),
    KEY idx_credit_limit_product_id (product_id),
    KEY idx_credit_limit_currency_code (currency_code),
    CONSTRAINT fk_credit_limit_application FOREIGN KEY (
        credit_application_id
    ) REFERENCES credit_application (id),
    CONSTRAINT fk_credit_limit_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_credit_limit_product FOREIGN KEY (
        product_id
    ) REFERENCES loan_product (id),
    CONSTRAINT fk_credit_limit_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '授信额度表，维护客户额度、已用额度、冻结额度和额度状态';

CREATE TABLE loan_application (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    application_no VARCHAR(64) NOT NULL,
    customer_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    credit_limit_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    apply_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    apply_term_months INT NOT NULL DEFAULT 0,
    loan_purpose VARCHAR(64) NOT NULL,
    application_status VARCHAR(64) NOT NULL,
    risk_decision VARCHAR(128) NOT NULL,
    submitted_at DATETIME NOT NULL,
    approved_at DATETIME NULL,
    rejected_at DATETIME NULL,
    expired_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_loan_application_no (application_no),
    KEY idx_loan_application_customer_id (customer_id),
    KEY idx_loan_application_product_id (product_id),
    KEY idx_loan_application_credit_limit_id (credit_limit_id),
    KEY idx_loan_application_channel_id (channel_id),
    CONSTRAINT fk_loan_application_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_loan_application_product FOREIGN KEY (
        product_id
    ) REFERENCES loan_product (id),
    CONSTRAINT fk_loan_application_credit_limit FOREIGN KEY (
        credit_limit_id
    ) REFERENCES credit_limit (id),
    CONSTRAINT fk_loan_application_channel FOREIGN KEY (
        channel_id
    ) REFERENCES dim_channel (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '贷款申请表，维护客户贷款申请和申请状态';

CREATE TABLE loan_application_material (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    material_no VARCHAR(64) NOT NULL,
    application_id BIGINT NULL,
    customer_id BIGINT NOT NULL,
    material_type VARCHAR(64) NOT NULL,
    material_name VARCHAR(128) NOT NULL,
    file_url VARCHAR(512) NULL,
    file_hash VARCHAR(128) NULL,
    submitted_by VARCHAR(128) NOT NULL,
    verification_status VARCHAR(64) NULL,
    verified_by BIGINT NULL,
    verified_at DATETIME NULL,
    submitted_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_loan_application_material_no (material_no),
    UNIQUE KEY uk_loan_application_material_type (
        application_id, material_type, material_name
    ),
    KEY idx_loan_application_material_customer_id (customer_id),
    KEY idx_loan_application_material_verified_by (verified_by),
    CONSTRAINT fk_loan_application_material_application FOREIGN KEY (
        application_id
    ) REFERENCES loan_application (id),
    CONSTRAINT fk_loan_application_material_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_loan_application_material_verifier FOREIGN KEY (
        verified_by
    ) REFERENCES dim_employee (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '贷款申请材料表，维护收入证明、经营资料、征信授权和附件状态';

CREATE TABLE credit_assessment (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    assessment_no VARCHAR(64) NOT NULL,
    credit_application_id BIGINT NULL,
    application_id BIGINT NULL,
    customer_id BIGINT NOT NULL,
    credit_report_no VARCHAR(64) NOT NULL,
    credit_score INT NOT NULL DEFAULT 0,
    internal_score INT NOT NULL DEFAULT 0,
    debt_income_ratio DECIMAL(12, 6) NOT NULL DEFAULT 0,
    monthly_income_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    monthly_debt_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    existing_loan_count INT NOT NULL DEFAULT 0,
    existing_credit_card_count INT NOT NULL DEFAULT 0,
    overdue_count_24m INT NOT NULL DEFAULT 0,
    max_overdue_days_24m INT NOT NULL DEFAULT 0,
    query_count_6m INT NOT NULL DEFAULT 0,
    risk_level_id BIGINT NOT NULL,
    assessment_result VARCHAR(64) NOT NULL,
    assessment_summary TEXT NULL,
    assessed_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_credit_assessment_no (assessment_no),
    UNIQUE KEY uk_credit_assessment_credit_application (credit_application_id),
    UNIQUE KEY uk_credit_assessment_application (application_id),
    KEY idx_credit_assessment_customer_id (customer_id),
    KEY idx_credit_assessment_risk_level_id (risk_level_id),
    CONSTRAINT fk_credit_assessment_credit_application FOREIGN KEY (
        credit_application_id
    ) REFERENCES credit_application (id),
    CONSTRAINT fk_credit_assessment_application FOREIGN KEY (
        application_id
    ) REFERENCES loan_application (id),
    CONSTRAINT fk_credit_assessment_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_credit_assessment_risk_level FOREIGN KEY (
        risk_level_id
    ) REFERENCES dim_risk_level (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '征信评估表，维护征信摘要、负债水平、评分和评估结论';

CREATE TABLE loan_approval_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    application_id BIGINT NULL,
    approval_node VARCHAR(128) NOT NULL,
    approver_id BIGINT NOT NULL,
    approval_round INT NOT NULL DEFAULT 0,
    sequence_no INT NOT NULL DEFAULT 0,
    approval_result VARCHAR(64) NOT NULL,
    approval_comment TEXT NULL,
    approved_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    approved_term_months INT NOT NULL DEFAULT 0,
    approved_rate DECIMAL(12, 6) NOT NULL DEFAULT 0,
    approved_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    UNIQUE KEY uk_loan_approval_node_round (
        application_id, approval_node, approval_round
    ),
    KEY idx_loan_approval_record_approver_id (approver_id),
    CONSTRAINT fk_loan_approval_application FOREIGN KEY (
        application_id
    ) REFERENCES loan_application (id),
    CONSTRAINT fk_loan_approval_approver FOREIGN KEY (
        approver_id
    ) REFERENCES dim_employee (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '贷款审批记录表，维护审批节点、审批人、审批结论和审批意见';

CREATE TABLE loan_contract (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    contract_no VARCHAR(64) NOT NULL,
    loan_no VARCHAR(64) NOT NULL,
    application_id BIGINT NULL,
    customer_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    repayment_account_id BIGINT NOT NULL,
    currency_code VARCHAR(64) NOT NULL,
    principal_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    disbursed_principal_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    undisbursed_principal_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    written_off_principal_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    restructured_principal_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    outstanding_principal_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    annual_interest_rate DECIMAL(12, 6) NOT NULL DEFAULT 0,
    term_months INT NOT NULL DEFAULT 0,
    repayment_method VARCHAR(64) NOT NULL,
    contract_status VARCHAR(64) NOT NULL,
    signed_at DATETIME NULL,
    disbursed_at DATETIME NULL,
    settled_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_loan_contract_no (contract_no),
    UNIQUE KEY uk_loan_contract_loan_no (loan_no),
    KEY idx_loan_contract_application_id (application_id),
    KEY idx_loan_contract_customer_id (customer_id),
    KEY idx_loan_contract_product_id (product_id),
    KEY idx_loan_contract_repayment_account_id (repayment_account_id),
    KEY idx_loan_contract_currency_code (currency_code),
    CONSTRAINT fk_loan_contract_application FOREIGN KEY (
        application_id
    ) REFERENCES loan_application (id),
    CONSTRAINT fk_loan_contract_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_loan_contract_product FOREIGN KEY (
        product_id
    ) REFERENCES loan_product (id),
    CONSTRAINT fk_loan_contract_repayment_account FOREIGN KEY (
        repayment_account_id
    ) REFERENCES bank_account (id),
    CONSTRAINT fk_loan_contract_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '贷款合同借据表，维护贷款合同、借据金额、期限、利率和合同状态';

CREATE TABLE loan_contract_document (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    document_no VARCHAR(64) NOT NULL,
    contract_id BIGINT NULL,
    document_type VARCHAR(64) NOT NULL,
    document_version INT NOT NULL DEFAULT 0,
    file_url VARCHAR(512) NULL,
    file_hash VARCHAR(128) NULL,
    sign_status VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_loan_contract_document_no (document_no),
    UNIQUE KEY uk_loan_contract_document_version (
        contract_id, document_type, document_version
    ),
    CONSTRAINT fk_loan_contract_document_contract FOREIGN KEY (
        contract_id
    ) REFERENCES loan_contract (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '贷款合同文件表，维护合同文件、版本和签署状态';

CREATE TABLE contract_sign_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    sign_no VARCHAR(64) NOT NULL,
    contract_id BIGINT NULL,
    document_id BIGINT NULL,
    signer_type VARCHAR(64) NOT NULL,
    signer_name VARCHAR(128) NOT NULL,
    sign_channel_id BIGINT NOT NULL,
    sign_method VARCHAR(64) NOT NULL,
    seal_no VARCHAR(64) NULL,
    sign_status VARCHAR(64) NOT NULL,
    signed_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_contract_sign_record_no (sign_no),
    KEY idx_contract_sign_record_contract_id (contract_id),
    KEY idx_contract_sign_record_document_id (document_id),
    KEY idx_contract_sign_record_sign_channel_id (sign_channel_id),
    CONSTRAINT fk_contract_sign_record_contract FOREIGN KEY (
        contract_id
    ) REFERENCES loan_contract (id),
    CONSTRAINT fk_contract_sign_record_document FOREIGN KEY (
        document_id
    ) REFERENCES loan_contract_document (id),
    CONSTRAINT fk_contract_sign_record_channel FOREIGN KEY (
        sign_channel_id
    ) REFERENCES dim_channel (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '合同签署记录表，维护签署人、签署渠道、电子签章和签署结果';

CREATE TABLE collateral_asset (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    collateral_no VARCHAR(64) NOT NULL,
    application_id BIGINT NULL,
    contract_id BIGINT NULL,
    customer_id BIGINT NOT NULL,
    asset_type VARCHAR(64) NOT NULL,
    asset_name VARCHAR(128) NOT NULL,
    asset_owner_name VARCHAR(128) NOT NULL,
    ownership_certificate_no VARCHAR(64) NOT NULL,
    currency_code VARCHAR(64) NOT NULL,
    appraised_value_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    pledge_rate DECIMAL(12, 6) NOT NULL DEFAULT 0,
    secured_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    appraisal_org VARCHAR(128) NULL,
    appraised_at DATETIME NULL,
    registration_status VARCHAR(64) NOT NULL,
    pledge_rank INT NOT NULL DEFAULT 0,
    priority_rule VARCHAR(64) NOT NULL,
    collateral_status VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_collateral_asset_no (collateral_no),
    KEY idx_collateral_asset_application_id (application_id),
    KEY idx_collateral_asset_contract_id (contract_id),
    KEY idx_collateral_asset_customer_id (customer_id),
    KEY idx_collateral_asset_currency_code (currency_code),
    CONSTRAINT fk_collateral_asset_application FOREIGN KEY (
        application_id
    ) REFERENCES loan_application (id),
    CONSTRAINT fk_collateral_asset_contract FOREIGN KEY (
        contract_id
    ) REFERENCES loan_contract (id),
    CONSTRAINT fk_collateral_asset_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_collateral_asset_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '抵押质押资产表，维护房产、车辆、存单和应收账款等担保资产';

CREATE TABLE guarantee_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    guarantee_no VARCHAR(64) NOT NULL,
    application_id BIGINT NULL,
    contract_id BIGINT NULL,
    customer_id BIGINT NOT NULL,
    guarantor_customer_id BIGINT NULL,
    guarantor_name VARCHAR(128) NOT NULL,
    guarantor_identity_type VARCHAR(64) NOT NULL,
    guarantor_identity_no VARCHAR(64) NOT NULL,
    guarantee_type VARCHAR(64) NOT NULL,
    currency_code VARCHAR(64) NOT NULL,
    guarantee_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    guarantee_start_at DATETIME NOT NULL,
    guarantee_end_at DATETIME NOT NULL,
    guarantee_status VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_guarantee_record_no (guarantee_no),
    KEY idx_guarantee_record_application_id (application_id),
    KEY idx_guarantee_record_contract_id (contract_id),
    KEY idx_guarantee_record_customer_id (customer_id),
    KEY idx_guarantee_record_guarantor_customer_id (guarantor_customer_id),
    KEY idx_guarantee_record_currency_code (currency_code),
    CONSTRAINT fk_guarantee_record_application FOREIGN KEY (
        application_id
    ) REFERENCES loan_application (id),
    CONSTRAINT fk_guarantee_record_contract FOREIGN KEY (
        contract_id
    ) REFERENCES loan_contract (id),
    CONSTRAINT fk_guarantee_record_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_guarantee_record_guarantor_customer FOREIGN KEY (
        guarantor_customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_guarantee_record_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '担保记录表，维护保证人、担保方式、担保金额和担保状态';

CREATE TABLE loan_disbursement (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    disbursement_no VARCHAR(64) NOT NULL,
    contract_id BIGINT NULL,
    customer_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL,
    transaction_id BIGINT NULL,
    original_disbursement_id BIGINT NULL,
    currency_code VARCHAR(64) NOT NULL,
    disbursement_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    disbursement_status VARCHAR(64) NOT NULL,
    disbursed_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_loan_disbursement_no (disbursement_no),
    UNIQUE KEY uk_loan_disbursement_transaction (transaction_id),
    KEY idx_loan_disbursement_contract_id (contract_id),
    KEY idx_loan_disbursement_customer_id (customer_id),
    KEY idx_loan_disbursement_account_id (account_id),
    KEY idx_loan_disbursement_original_disbursement_id (
        original_disbursement_id
    ),
    KEY idx_loan_disbursement_currency_code (currency_code),
    CONSTRAINT fk_loan_disbursement_contract FOREIGN KEY (
        contract_id
    ) REFERENCES loan_contract (id),
    CONSTRAINT fk_loan_disbursement_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_loan_disbursement_account FOREIGN KEY (
        account_id
    ) REFERENCES bank_account (id),
    CONSTRAINT fk_loan_disbursement_transaction FOREIGN KEY (
        transaction_id
    ) REFERENCES account_transaction (id),
    CONSTRAINT fk_loan_disbursement_original FOREIGN KEY (
        original_disbursement_id
    ) REFERENCES loan_disbursement (id),
    CONSTRAINT fk_loan_disbursement_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '放款记录表，维护放款金额、放款账户、放款交易和放款状态';

CREATE TABLE repayment_schedule (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    contract_id BIGINT NULL,
    customer_id BIGINT NOT NULL,
    schedule_version INT NOT NULL DEFAULT 0,
    period_no INT NOT NULL DEFAULT 0,
    due_date DATE NOT NULL,
    currency_code VARCHAR(64) NOT NULL,
    principal_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    interest_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    fee_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    total_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    schedule_status VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_repayment_schedule_period (
        contract_id, schedule_version, period_no
    ),
    KEY idx_repayment_schedule_customer_id (customer_id),
    KEY idx_repayment_schedule_currency_code (currency_code),
    CONSTRAINT fk_repayment_schedule_contract FOREIGN KEY (
        contract_id
    ) REFERENCES loan_contract (id),
    CONSTRAINT fk_repayment_schedule_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_repayment_schedule_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '还款计划表，维护贷款合同每期应还金额';

CREATE TABLE repayment_bill (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    bill_no VARCHAR(64) NOT NULL,
    contract_id BIGINT NULL,
    schedule_id BIGINT NOT NULL,
    customer_id BIGINT NOT NULL,
    period_no INT NOT NULL DEFAULT 0,
    due_date DATE NOT NULL,
    currency_code VARCHAR(64) NOT NULL,
    principal_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    interest_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    fee_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    penalty_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    reduced_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    paid_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    written_off_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    restructured_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    outstanding_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    bill_status VARCHAR(64) NOT NULL,
    billed_at DATETIME NOT NULL,
    paid_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_repayment_bill_no (bill_no),
    UNIQUE KEY uk_repayment_bill_schedule (schedule_id),
    KEY idx_repayment_bill_contract_id (contract_id),
    KEY idx_repayment_bill_customer_id (customer_id),
    KEY idx_repayment_bill_currency_code (currency_code),
    CONSTRAINT fk_repayment_bill_contract FOREIGN KEY (
        contract_id
    ) REFERENCES loan_contract (id),
    CONSTRAINT fk_repayment_bill_schedule FOREIGN KEY (
        schedule_id
    ) REFERENCES repayment_schedule (id),
    CONSTRAINT fk_repayment_bill_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_repayment_bill_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '还款账单表，维护每期账单应还、已还、减免和逾期状态';

CREATE TABLE repayment_authorization (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    authorization_no VARCHAR(64) NOT NULL,
    contract_id BIGINT NULL,
    customer_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL,
    authorization_type VARCHAR(64) NOT NULL,
    authorization_status VARCHAR(64) NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    signed_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_repayment_authorization_no (authorization_no),
    KEY idx_repayment_authorization_contract_id (contract_id),
    KEY idx_repayment_authorization_customer_id (customer_id),
    KEY idx_repayment_authorization_account_id (account_id),
    CONSTRAINT fk_repayment_authorization_contract FOREIGN KEY (
        contract_id
    ) REFERENCES loan_contract (id),
    CONSTRAINT fk_repayment_authorization_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_repayment_authorization_account FOREIGN KEY (
        account_id
    ) REFERENCES bank_account (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '还款授权表，维护自动扣款、代扣协议和授权状态';

CREATE TABLE overdue_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    overdue_no VARCHAR(64) NOT NULL,
    bill_id BIGINT NULL,
    contract_id BIGINT NULL,
    customer_id BIGINT NOT NULL,
    period_no INT NOT NULL DEFAULT 0,
    overdue_start_date DATE NOT NULL,
    overdue_days INT NOT NULL DEFAULT 0,
    currency_code VARCHAR(64) NOT NULL,
    overdue_principal_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    overdue_interest_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    overdue_fee_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    penalty_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    overdue_total_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    paid_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    reduced_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    written_off_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    restructured_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    recovered_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    outstanding_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    overdue_level VARCHAR(64) NOT NULL,
    overdue_status VARCHAR(64) NOT NULL,
    settled_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_overdue_record_no (overdue_no),
    UNIQUE KEY uk_overdue_record_bill (bill_id),
    KEY idx_overdue_record_contract_id (contract_id),
    KEY idx_overdue_record_customer_id (customer_id),
    KEY idx_overdue_record_currency_code (currency_code),
    CONSTRAINT fk_overdue_record_bill FOREIGN KEY (
        bill_id
    ) REFERENCES repayment_bill (id),
    CONSTRAINT fk_overdue_record_contract FOREIGN KEY (
        contract_id
    ) REFERENCES loan_contract (id),
    CONSTRAINT fk_overdue_record_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_overdue_record_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '逾期记录表，维护账单逾期、逾期天数、逾期金额和处置状态';

CREATE TABLE fee_reduction (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    reduction_no VARCHAR(64) NOT NULL,
    bill_id BIGINT NULL,
    contract_id BIGINT NULL,
    customer_id BIGINT NOT NULL,
    reduction_type VARCHAR(64) NOT NULL,
    currency_code VARCHAR(64) NOT NULL,
    apply_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    approved_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    approved_interest_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    approved_fee_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    approved_penalty_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    reduction_status VARCHAR(64) NOT NULL,
    approved_by BIGINT NULL,
    approval_comment TEXT NULL,
    approved_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_fee_reduction_no (reduction_no),
    KEY idx_fee_reduction_bill_id (bill_id),
    KEY idx_fee_reduction_contract_id (contract_id),
    KEY idx_fee_reduction_customer_id (customer_id),
    KEY idx_fee_reduction_currency_code (currency_code),
    KEY idx_fee_reduction_approved_by (approved_by),
    CONSTRAINT fk_fee_reduction_bill FOREIGN KEY (
        bill_id
    ) REFERENCES repayment_bill (id),
    CONSTRAINT fk_fee_reduction_contract FOREIGN KEY (
        contract_id
    ) REFERENCES loan_contract (id),
    CONSTRAINT fk_fee_reduction_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_fee_reduction_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code),
    CONSTRAINT fk_fee_reduction_approver FOREIGN KEY (
        approved_by
    ) REFERENCES dim_employee (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '费用减免表，维护罚息、违约金、手续费等费用减免';

CREATE TABLE risk_strategy (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    strategy_code VARCHAR(64) NOT NULL,
    strategy_name VARCHAR(128) NOT NULL,
    strategy_type VARCHAR(64) NOT NULL,
    applicable_event_type VARCHAR(64) NOT NULL,
    decision_mode VARCHAR(64) NOT NULL,
    strategy_version VARCHAR(64) NOT NULL,
    risk_level_id BIGINT NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE NULL,
    strategy_status VARCHAR(64) NOT NULL,
    created_by BIGINT NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_risk_strategy_code_version (strategy_code, strategy_version),
    KEY idx_risk_strategy_risk_level_id (risk_level_id),
    KEY idx_risk_strategy_created_by (created_by),
    CONSTRAINT fk_risk_strategy_level FOREIGN KEY (
        risk_level_id
    ) REFERENCES dim_risk_level (id),
    CONSTRAINT fk_risk_strategy_creator FOREIGN KEY (
        created_by
    ) REFERENCES dim_employee (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '风控策略表，维护策略编码、适用场景、决策模式、版本和启停状态';

CREATE TABLE risk_rule (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    rule_code VARCHAR(64) NOT NULL,
    rule_name VARCHAR(128) NOT NULL,
    rule_type VARCHAR(64) NOT NULL,
    risk_level_id BIGINT NOT NULL,
    rule_expression TEXT NOT NULL,
    rule_version VARCHAR(64) NOT NULL,
    threshold_value VARCHAR(128) NOT NULL,
    decision_action VARCHAR(64) NOT NULL,
    rule_status VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_risk_rule_code_version (rule_code, rule_version),
    KEY idx_risk_rule_risk_level_id (risk_level_id),
    CONSTRAINT fk_risk_rule_level FOREIGN KEY (
        risk_level_id
    ) REFERENCES dim_risk_level (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '风控规则表，定义反欺诈、反洗钱、信贷准入和交易监控规则';

CREATE TABLE risk_strategy_rule_rel (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    strategy_id BIGINT NOT NULL,
    rule_id BIGINT NOT NULL,
    execute_order INT NOT NULL DEFAULT 0,
    rule_weight DECIMAL(12, 6) NOT NULL DEFAULT 0,
    required_flag TINYINT NOT NULL DEFAULT 0,
    stop_on_hit_flag TINYINT NOT NULL DEFAULT 0,
    decision_override VARCHAR(128) NOT NULL,
    yn TINYINT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_risk_strategy_rule (strategy_id, rule_id),
    UNIQUE KEY uk_risk_strategy_rule_order (strategy_id, execute_order),
    KEY idx_risk_strategy_rule_rel_rule_id (rule_id),
    CONSTRAINT fk_risk_strategy_rule_strategy FOREIGN KEY (
        strategy_id
    ) REFERENCES risk_strategy (id),
    CONSTRAINT fk_risk_strategy_rule_rule FOREIGN KEY (
        rule_id
    ) REFERENCES risk_rule (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '风控策略规则关系表，维护策略下规则编排、优先级和权重';

CREATE TABLE risk_event (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    event_no VARCHAR(64) NOT NULL,
    customer_id BIGINT NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    related_type VARCHAR(64) NOT NULL,
    related_id BIGINT NULL,
    strategy_id BIGINT NOT NULL,
    risk_level_id BIGINT NOT NULL,
    risk_score INT NOT NULL DEFAULT 0,
    decision_action VARCHAR(64) NOT NULL,
    hit_flag TINYINT NOT NULL DEFAULT 0,
    no_hit_reason VARCHAR(64) NULL,
    decision_reason TEXT NULL,
    event_status VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_risk_event_no (event_no),
    KEY idx_risk_event_customer_id (customer_id),
    KEY idx_risk_event_strategy_id (strategy_id),
    KEY idx_risk_event_risk_level_id (risk_level_id),
    CONSTRAINT fk_risk_event_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_risk_event_strategy FOREIGN KEY (
        strategy_id
    ) REFERENCES risk_strategy (id),
    CONSTRAINT fk_risk_event_level FOREIGN KEY (
        risk_level_id
    ) REFERENCES dim_risk_level (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '风险事件表，维护业务触发的风险事件和最终决策';

CREATE TABLE risk_hit_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    event_id BIGINT NOT NULL,
    rule_id BIGINT NOT NULL,
    hit_score INT NOT NULL DEFAULT 0,
    hit_detail TEXT NOT NULL,
    decision_action VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL,
    UNIQUE KEY uk_risk_hit_record_event_rule (event_id, rule_id),
    KEY idx_risk_hit_record_rule_id (rule_id),
    CONSTRAINT fk_risk_hit_record_event FOREIGN KEY (
        event_id
    ) REFERENCES risk_event (id),
    CONSTRAINT fk_risk_hit_record_rule FOREIGN KEY (
        rule_id
    ) REFERENCES risk_rule (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '风险命中记录表，维护风险事件命中的具体规则';

CREATE TABLE blacklist_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    blacklist_no VARCHAR(64) NOT NULL,
    subject_type VARCHAR(64) NOT NULL,
    subject_value VARCHAR(128) NOT NULL,
    risk_level_id BIGINT NOT NULL,
    blacklist_reason TEXT NOT NULL,
    blacklist_status VARCHAR(64) NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE NULL,
    removed_reason VARCHAR(64) NULL,
    removed_by BIGINT NULL,
    removed_at DATETIME NULL,
    approval_ref VARCHAR(64) NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_blacklist_record_no (blacklist_no),
    UNIQUE KEY uk_blacklist_active_subject (subject_type, subject_value),
    KEY idx_blacklist_record_risk_level_id (risk_level_id),
    KEY idx_blacklist_record_removed_by (removed_by),
    CONSTRAINT fk_blacklist_record_level FOREIGN KEY (
        risk_level_id
    ) REFERENCES dim_risk_level (id),
    CONSTRAINT fk_blacklist_record_removed_by FOREIGN KEY (
        removed_by
    ) REFERENCES dim_employee (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '黑名单记录表，维护客户、证件、手机号、账户和设备黑名单';

CREATE TABLE aml_case (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    case_no VARCHAR(64) NOT NULL,
    risk_event_id BIGINT NULL,
    customer_id BIGINT NOT NULL,
    primary_transaction_id BIGINT NULL,
    transaction_count INT NOT NULL DEFAULT 0,
    total_transaction_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    currency_code VARCHAR(64) NOT NULL,
    case_type VARCHAR(64) NOT NULL,
    case_status VARCHAR(64) NOT NULL,
    risk_level_id BIGINT NOT NULL,
    case_summary TEXT NOT NULL,
    opened_at DATETIME NOT NULL,
    closed_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_aml_case_no (case_no),
    KEY idx_aml_case_risk_event_id (risk_event_id),
    KEY idx_aml_case_customer_id (customer_id),
    KEY idx_aml_case_primary_transaction_id (primary_transaction_id),
    KEY idx_aml_case_currency_code (currency_code),
    KEY idx_aml_case_risk_level_id (risk_level_id),
    CONSTRAINT fk_aml_case_event FOREIGN KEY (
        risk_event_id
    ) REFERENCES risk_event (id),
    CONSTRAINT fk_aml_case_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_aml_case_primary_transaction FOREIGN KEY (
        primary_transaction_id
    ) REFERENCES account_transaction (id),
    CONSTRAINT fk_aml_case_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code),
    CONSTRAINT fk_aml_case_risk_level FOREIGN KEY (
        risk_level_id
    ) REFERENCES dim_risk_level (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '反洗钱案件表，维护可疑交易调查、复核和处置状态';

CREATE TABLE aml_case_transaction (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    aml_case_id BIGINT NOT NULL,
    transaction_id BIGINT NULL,
    customer_id BIGINT NOT NULL,
    currency_code VARCHAR(64) NOT NULL,
    transaction_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    included_flag TINYINT NOT NULL DEFAULT 0,
    include_reason TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    UNIQUE KEY uk_aml_case_transaction (aml_case_id, transaction_id),
    KEY idx_aml_case_transaction_transaction_id (transaction_id),
    KEY idx_aml_case_transaction_customer_id (customer_id),
    KEY idx_aml_case_transaction_currency_code (currency_code),
    CONSTRAINT fk_aml_case_transaction_case FOREIGN KEY (
        aml_case_id
    ) REFERENCES aml_case (id),
    CONSTRAINT fk_aml_case_transaction_transaction FOREIGN KEY (
        transaction_id
    ) REFERENCES account_transaction (id),
    CONSTRAINT fk_aml_case_transaction_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_aml_case_transaction_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '反洗钱案件交易明细表，维护 AML 案件涉及的账户交易范围';

CREATE TABLE suspicious_transaction_report (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    report_no VARCHAR(64) NOT NULL,
    aml_case_id BIGINT NOT NULL,
    customer_id BIGINT NOT NULL,
    transaction_count INT NOT NULL DEFAULT 0,
    total_transaction_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    currency_code VARCHAR(64) NOT NULL,
    report_period_start DATE NOT NULL,
    report_period_end DATE NOT NULL,
    report_type VARCHAR(64) NOT NULL,
    report_status VARCHAR(64) NOT NULL,
    reported_at DATETIME NOT NULL,
    accepted_at DATETIME NULL,
    report_content TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_suspicious_transaction_report_no (report_no),
    KEY idx_suspicious_transaction_report_aml_case_id (aml_case_id),
    KEY idx_suspicious_transaction_report_customer_id (customer_id),
    KEY idx_suspicious_transaction_report_currency_code (currency_code),
    CONSTRAINT fk_suspicious_report_case FOREIGN KEY (
        aml_case_id
    ) REFERENCES aml_case (id),
    CONSTRAINT fk_suspicious_report_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_suspicious_report_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '可疑交易报告表，维护反洗钱报送记录和报送状态';

CREATE TABLE aml_review_result (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    review_no VARCHAR(64) NOT NULL,
    aml_case_id BIGINT NOT NULL,
    risk_event_id BIGINT NOT NULL,
    reviewer_id BIGINT NOT NULL,
    review_result VARCHAR(64) NOT NULL,
    review_comment TEXT NULL,
    reviewed_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    UNIQUE KEY uk_aml_review_no (review_no),
    KEY idx_aml_review_result_aml_case_id (aml_case_id),
    KEY idx_aml_review_result_risk_event_id (risk_event_id),
    KEY idx_aml_review_result_reviewer_id (reviewer_id),
    CONSTRAINT fk_aml_review_case FOREIGN KEY (
        aml_case_id
    ) REFERENCES aml_case (id),
    CONSTRAINT fk_aml_review_event FOREIGN KEY (
        risk_event_id
    ) REFERENCES risk_event (id),
    CONSTRAINT fk_aml_review_reviewer FOREIGN KEY (
        reviewer_id
    ) REFERENCES dim_employee (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '反洗钱复核结果表，维护 AML 人工复核结论和处置建议';

CREATE TABLE manual_review_task (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_no VARCHAR(64) NOT NULL,
    customer_id BIGINT NOT NULL,
    risk_event_id BIGINT NULL,
    related_type VARCHAR(64) NOT NULL,
    related_id BIGINT NULL,
    assignee_id BIGINT NULL,
    task_type VARCHAR(64) NOT NULL,
    task_status VARCHAR(64) NOT NULL,
    review_result VARCHAR(64) NULL,
    review_comment TEXT NULL,
    assigned_at DATETIME NOT NULL,
    completed_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_manual_review_task_no (task_no),
    KEY idx_manual_review_task_customer_id (customer_id),
    KEY idx_manual_review_task_risk_event_id (risk_event_id),
    KEY idx_manual_review_task_assignee_id (assignee_id),
    CONSTRAINT fk_manual_review_task_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_manual_review_task_event FOREIGN KEY (
        risk_event_id
    ) REFERENCES risk_event (id),
    CONSTRAINT fk_manual_review_task_assignee FOREIGN KEY (
        assignee_id
    ) REFERENCES dim_employee (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '人工复核任务表，维护风控和业务审批相关复核任务';

CREATE TABLE collection_case (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    case_no VARCHAR(64) NOT NULL,
    overdue_id BIGINT NOT NULL,
    contract_id BIGINT NULL,
    customer_id BIGINT NOT NULL,
    collector_id BIGINT NOT NULL,
    collection_stage VARCHAR(64) NOT NULL,
    case_status VARCHAR(64) NOT NULL,
    case_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    assigned_at DATETIME NOT NULL,
    closed_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_collection_case_no (case_no),
    UNIQUE KEY uk_collection_case_active_overdue (overdue_id),
    KEY idx_collection_case_contract_id (contract_id),
    KEY idx_collection_case_customer_id (customer_id),
    KEY idx_collection_case_collector_id (collector_id),
    CONSTRAINT fk_collection_case_overdue FOREIGN KEY (
        overdue_id
    ) REFERENCES overdue_record (id),
    CONSTRAINT fk_collection_case_contract FOREIGN KEY (
        contract_id
    ) REFERENCES loan_contract (id),
    CONSTRAINT fk_collection_case_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_collection_case_collector FOREIGN KEY (
        collector_id
    ) REFERENCES dim_employee (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '催收案件表，维护逾期案件、催收阶段、分案和案件状态';

CREATE TABLE repayment_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    repayment_no VARCHAR(64) NOT NULL,
    bill_id BIGINT NULL,
    contract_id BIGINT NULL,
    customer_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL,
    transaction_id BIGINT NULL,
    authorization_id BIGINT NULL,
    collection_case_id BIGINT NULL,
    repayment_promise_id BIGINT NULL,
    original_repayment_id BIGINT NULL,
    repayment_type VARCHAR(64) NOT NULL,
    currency_code VARCHAR(64) NOT NULL,
    repayment_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    principal_paid_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    interest_paid_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    fee_paid_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    penalty_paid_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    repayment_status VARCHAR(64) NOT NULL,
    repaid_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_repayment_record_no (repayment_no),
    UNIQUE KEY uk_repayment_record_transaction (transaction_id),
    KEY idx_repayment_record_bill_id (bill_id),
    KEY idx_repayment_record_contract_id (contract_id),
    KEY idx_repayment_record_customer_id (customer_id),
    KEY idx_repayment_record_account_id (account_id),
    KEY idx_repayment_record_authorization_id (authorization_id),
    KEY idx_repayment_record_collection_case_id (collection_case_id),
    KEY idx_repayment_record_repayment_promise_id (repayment_promise_id),
    KEY idx_repayment_record_original_repayment_id (original_repayment_id),
    KEY idx_repayment_record_currency_code (currency_code),
    CONSTRAINT fk_repayment_record_bill FOREIGN KEY (
        bill_id
    ) REFERENCES repayment_bill (id),
    CONSTRAINT fk_repayment_record_contract FOREIGN KEY (
        contract_id
    ) REFERENCES loan_contract (id),
    CONSTRAINT fk_repayment_record_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_repayment_record_account FOREIGN KEY (
        account_id
    ) REFERENCES bank_account (id),
    CONSTRAINT fk_repayment_record_transaction FOREIGN KEY (
        transaction_id
    ) REFERENCES account_transaction (id),
    CONSTRAINT fk_repayment_record_authorization FOREIGN KEY (
        authorization_id
    ) REFERENCES repayment_authorization (id),
    CONSTRAINT fk_repayment_record_collection_case FOREIGN KEY (
        collection_case_id
    ) REFERENCES collection_case (id),
    CONSTRAINT fk_repayment_record_original FOREIGN KEY (
        original_repayment_id
    ) REFERENCES repayment_record (id),
    CONSTRAINT fk_repayment_record_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '还款记录表，维护还款交易、入账和冲正记录';

CREATE TABLE credit_limit_change_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    change_no VARCHAR(64) NOT NULL,
    credit_limit_id BIGINT NOT NULL,
    change_seq INT NOT NULL DEFAULT 0,
    credit_application_id BIGINT NULL,
    loan_application_id BIGINT NULL,
    contract_id BIGINT NULL,
    repayment_id BIGINT NULL,
    change_type VARCHAR(64) NOT NULL,
    currency_code VARCHAR(64) NOT NULL,
    change_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    before_total_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    after_total_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    before_used_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    after_used_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    before_frozen_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    after_frozen_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    before_available_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    after_available_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    changed_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    UNIQUE KEY uk_credit_limit_change_no (change_no),
    UNIQUE KEY uk_credit_limit_change_seq (credit_limit_id, change_seq),
    KEY idx_credit_limit_change_log_credit_application_id (
        credit_application_id
    ),
    KEY idx_credit_limit_change_log_loan_application_id (loan_application_id),
    KEY idx_credit_limit_change_log_contract_id (contract_id),
    KEY idx_credit_limit_change_log_repayment_id (repayment_id),
    KEY idx_credit_limit_change_log_currency_code (currency_code),
    CONSTRAINT fk_credit_limit_change_limit FOREIGN KEY (
        credit_limit_id
    ) REFERENCES credit_limit (id),
    CONSTRAINT fk_credit_limit_change_credit_application FOREIGN KEY (
        credit_application_id
    ) REFERENCES credit_application (id),
    CONSTRAINT fk_credit_limit_change_loan_application FOREIGN KEY (
        loan_application_id
    ) REFERENCES loan_application (id),
    CONSTRAINT fk_credit_limit_change_contract FOREIGN KEY (
        contract_id
    ) REFERENCES loan_contract (id),
    CONSTRAINT fk_credit_limit_change_repayment FOREIGN KEY (
        repayment_id
    ) REFERENCES repayment_record (id),
    CONSTRAINT fk_credit_limit_change_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '授信额度变更流水表，维护额度冻结、占用、释放和关闭记录';

CREATE TABLE repayment_allocation (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    allocation_no VARCHAR(64) NOT NULL,
    repayment_id BIGINT NULL,
    bill_id BIGINT NULL,
    contract_id BIGINT NULL,
    period_no INT NOT NULL DEFAULT 0,
    currency_code VARCHAR(64) NOT NULL,
    principal_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    interest_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    fee_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    penalty_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    allocated_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL,
    UNIQUE KEY uk_repayment_allocation_no (allocation_no),
    UNIQUE KEY uk_repayment_allocation_bill (repayment_id, bill_id),
    KEY idx_repayment_allocation_bill_id (bill_id),
    KEY idx_repayment_allocation_contract_id (contract_id),
    KEY idx_repayment_allocation_currency_code (currency_code),
    CONSTRAINT fk_repayment_allocation_repayment FOREIGN KEY (
        repayment_id
    ) REFERENCES repayment_record (id),
    CONSTRAINT fk_repayment_allocation_bill FOREIGN KEY (
        bill_id
    ) REFERENCES repayment_bill (id),
    CONSTRAINT fk_repayment_allocation_contract FOREIGN KEY (
        contract_id
    ) REFERENCES loan_contract (id),
    CONSTRAINT fk_repayment_allocation_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '还款分配明细表，维护还款金额在账单、期次和费用项之间的分配';

CREATE TABLE collection_action (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    action_no VARCHAR(64) NOT NULL,
    case_id BIGINT NOT NULL,
    customer_id BIGINT NOT NULL,
    contract_id BIGINT NULL,
    action_type VARCHAR(64) NOT NULL,
    action_status VARCHAR(64) NOT NULL,
    action_result TEXT NOT NULL,
    operator_id BIGINT NULL,
    action_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_collection_action_no (action_no),
    KEY idx_collection_action_case_id (case_id),
    KEY idx_collection_action_customer_id (customer_id),
    KEY idx_collection_action_contract_id (contract_id),
    KEY idx_collection_action_operator_id (operator_id),
    CONSTRAINT fk_collection_action_case FOREIGN KEY (
        case_id
    ) REFERENCES collection_case (id),
    CONSTRAINT fk_collection_action_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_collection_action_contract FOREIGN KEY (
        contract_id
    ) REFERENCES loan_contract (id),
    CONSTRAINT fk_collection_action_operator FOREIGN KEY (
        operator_id
    ) REFERENCES dim_employee (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '催收处置动作表，维护协商、停催、外访、法诉、核销和重组等处置动作';

CREATE TABLE collection_contact_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    case_id BIGINT NOT NULL,
    collector_id BIGINT NOT NULL,
    assistant_collector_id BIGINT NOT NULL,
    contact_method VARCHAR(64) NOT NULL,
    contact_result VARCHAR(64) NOT NULL,
    contact_content TEXT NOT NULL,
    next_contact_at DATETIME NULL,
    contacted_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    KEY idx_collection_contact_record_case_id (case_id),
    KEY idx_collection_contact_record_collector_id (collector_id),
    KEY idx_collection_contact_record_assistant_collector_id (
        assistant_collector_id
    ),
    CONSTRAINT fk_collection_contact_case FOREIGN KEY (
        case_id
    ) REFERENCES collection_case (id),
    CONSTRAINT fk_collection_contact_collector FOREIGN KEY (
        collector_id
    ) REFERENCES dim_employee (id),
    CONSTRAINT fk_collection_contact_assistant_collector FOREIGN KEY (
        assistant_collector_id
    ) REFERENCES dim_employee (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '催收联系记录表，维护催收联系渠道、联系结果和客户反馈';

CREATE TABLE repayment_promise (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    promise_no VARCHAR(64) NOT NULL,
    case_id BIGINT NOT NULL,
    customer_id BIGINT NOT NULL,
    currency_code VARCHAR(64) NOT NULL,
    promise_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    promise_date DATE NOT NULL,
    promise_status VARCHAR(64) NOT NULL,
    fulfilled_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    fulfilled_repayment_id BIGINT NULL,
    fulfilled_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_repayment_promise_no (promise_no),
    KEY idx_repayment_promise_case_id (case_id),
    KEY idx_repayment_promise_customer_id (customer_id),
    KEY idx_repayment_promise_fulfilled_repayment_id (fulfilled_repayment_id),
    KEY idx_repayment_promise_currency_code (currency_code),
    CONSTRAINT fk_repayment_promise_case FOREIGN KEY (
        case_id
    ) REFERENCES collection_case (id),
    CONSTRAINT fk_repayment_promise_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_repayment_promise_fulfilled_repayment FOREIGN KEY (
        fulfilled_repayment_id
    ) REFERENCES repayment_record (id) ON DELETE SET NULL,
    CONSTRAINT fk_repayment_promise_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '承诺还款表，维护客户承诺还款日期、金额和履约状态';

CREATE TABLE legal_case (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    legal_case_no VARCHAR(64) NOT NULL,
    action_id BIGINT NULL,
    case_id BIGINT NOT NULL,
    contract_id BIGINT NULL,
    customer_id BIGINT NOT NULL,
    legal_type VARCHAR(64) NOT NULL,
    legal_status VARCHAR(64) NOT NULL,
    claim_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    accepted_at DATETIME NULL,
    closed_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_legal_case_no (legal_case_no),
    UNIQUE KEY uk_legal_case_action (action_id),
    KEY idx_legal_case_case_id (case_id),
    KEY idx_legal_case_contract_id (contract_id),
    KEY idx_legal_case_customer_id (customer_id),
    CONSTRAINT fk_legal_case_action FOREIGN KEY (
        action_id
    ) REFERENCES collection_action (id),
    CONSTRAINT fk_legal_case_collection FOREIGN KEY (
        case_id
    ) REFERENCES collection_case (id),
    CONSTRAINT fk_legal_case_contract FOREIGN KEY (
        contract_id
    ) REFERENCES loan_contract (id),
    CONSTRAINT fk_legal_case_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '法诉案件表，维护诉讼、仲裁、执行和法务状态';

CREATE TABLE loan_write_off (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    write_off_no VARCHAR(64) NOT NULL,
    action_id BIGINT NULL,
    case_id BIGINT NOT NULL,
    contract_id BIGINT NULL,
    customer_id BIGINT NOT NULL,
    currency_code VARCHAR(64) NOT NULL,
    apply_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    approved_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    approved_principal_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    approved_interest_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    approved_fee_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    approved_penalty_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    write_off_status VARCHAR(64) NOT NULL,
    approved_by BIGINT NULL,
    approval_comment TEXT NULL,
    approved_at DATETIME NULL,
    posted_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_loan_write_off_no (write_off_no),
    UNIQUE KEY uk_loan_write_off_action (action_id),
    KEY idx_loan_write_off_case_id (case_id),
    KEY idx_loan_write_off_contract_id (contract_id),
    KEY idx_loan_write_off_customer_id (customer_id),
    KEY idx_loan_write_off_currency_code (currency_code),
    KEY idx_loan_write_off_approved_by (approved_by),
    CONSTRAINT fk_loan_write_off_action FOREIGN KEY (
        action_id
    ) REFERENCES collection_action (id),
    CONSTRAINT fk_loan_write_off_case FOREIGN KEY (
        case_id
    ) REFERENCES collection_case (id),
    CONSTRAINT fk_loan_write_off_contract FOREIGN KEY (
        contract_id
    ) REFERENCES loan_contract (id),
    CONSTRAINT fk_loan_write_off_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_loan_write_off_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code),
    CONSTRAINT fk_loan_write_off_approver FOREIGN KEY (
        approved_by
    ) REFERENCES dim_employee (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '贷款核销表，维护核销申请、审批、核销金额和核销状态';

CREATE TABLE loan_restructure (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    restructure_no VARCHAR(64) NOT NULL,
    action_id BIGINT NULL,
    case_id BIGINT NOT NULL,
    contract_id BIGINT NULL,
    customer_id BIGINT NOT NULL,
    before_outstanding_principal_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    capitalized_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    reduced_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    after_outstanding_principal_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    original_schedule_version INT NOT NULL DEFAULT 0,
    new_schedule_version INT NOT NULL DEFAULT 0,
    restructure_type VARCHAR(64) NOT NULL,
    new_term_months INT NOT NULL DEFAULT 0,
    new_interest_rate DECIMAL(12, 6) NOT NULL DEFAULT 0,
    restructure_status VARCHAR(64) NOT NULL,
    approved_by BIGINT NULL,
    approved_at DATETIME NULL,
    effective_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_loan_restructure_no (restructure_no),
    UNIQUE KEY uk_loan_restructure_action (action_id),
    KEY idx_loan_restructure_case_id (case_id),
    KEY idx_loan_restructure_contract_id (contract_id),
    KEY idx_loan_restructure_customer_id (customer_id),
    KEY idx_loan_restructure_approved_by (approved_by),
    CONSTRAINT fk_loan_restructure_action FOREIGN KEY (
        action_id
    ) REFERENCES collection_action (id),
    CONSTRAINT fk_loan_restructure_case FOREIGN KEY (
        case_id
    ) REFERENCES collection_case (id),
    CONSTRAINT fk_loan_restructure_contract FOREIGN KEY (
        contract_id
    ) REFERENCES loan_contract (id),
    CONSTRAINT fk_loan_restructure_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_loan_restructure_approver FOREIGN KEY (
        approved_by
    ) REFERENCES dim_employee (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '贷款重组表，维护展期、降息、延期和重组方案';

CREATE TABLE collateral_disposal (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    disposal_no VARCHAR(64) NOT NULL,
    action_id BIGINT NULL,
    case_id BIGINT NOT NULL,
    collateral_id BIGINT NOT NULL,
    contract_id BIGINT NULL,
    customer_id BIGINT NOT NULL,
    repayment_id BIGINT NULL,
    transaction_id BIGINT NULL,
    ledger_id BIGINT NULL,
    currency_code VARCHAR(64) NOT NULL,
    disposal_method VARCHAR(64) NOT NULL,
    disposal_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    received_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    disposal_status VARCHAR(64) NOT NULL,
    completed_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_collateral_disposal_no (disposal_no),
    UNIQUE KEY uk_collateral_disposal_action (action_id),
    KEY idx_collateral_disposal_case_id (case_id),
    KEY idx_collateral_disposal_collateral_id (collateral_id),
    KEY idx_collateral_disposal_contract_id (contract_id),
    KEY idx_collateral_disposal_customer_id (customer_id),
    KEY idx_collateral_disposal_repayment_id (repayment_id),
    KEY idx_collateral_disposal_transaction_id (transaction_id),
    KEY idx_collateral_disposal_ledger_id (ledger_id),
    KEY idx_collateral_disposal_currency_code (currency_code),
    CONSTRAINT fk_collateral_disposal_action FOREIGN KEY (
        action_id
    ) REFERENCES collection_action (id),
    CONSTRAINT fk_collateral_disposal_case FOREIGN KEY (
        case_id
    ) REFERENCES collection_case (id),
    CONSTRAINT fk_collateral_disposal_collateral FOREIGN KEY (
        collateral_id
    ) REFERENCES collateral_asset (id),
    CONSTRAINT fk_collateral_disposal_contract FOREIGN KEY (
        contract_id
    ) REFERENCES loan_contract (id),
    CONSTRAINT fk_collateral_disposal_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_collateral_disposal_repayment FOREIGN KEY (
        repayment_id
    ) REFERENCES repayment_record (id),
    CONSTRAINT fk_collateral_disposal_transaction FOREIGN KEY (
        transaction_id
    ) REFERENCES account_transaction (id),
    CONSTRAINT fk_collateral_disposal_ledger FOREIGN KEY (
        ledger_id
    ) REFERENCES account_ledger (id),
    CONSTRAINT fk_collateral_disposal_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '抵押质押资产处置表，维护处置方式、处置金额和入账结果';

CREATE TABLE collection_performance_daily (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    stat_date DATE NOT NULL,
    collector_id BIGINT NOT NULL,
    branch_id BIGINT NOT NULL,
    collection_stage VARCHAR(64) NOT NULL,
    assigned_case_count INT NOT NULL DEFAULT 0,
    active_case_count INT NOT NULL DEFAULT 0,
    contact_attempt_count INT NOT NULL DEFAULT 0,
    connected_count INT NOT NULL DEFAULT 0,
    promise_count INT NOT NULL DEFAULT 0,
    currency_code VARCHAR(64) NOT NULL,
    assigned_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    promised_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    recovered_amount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    settled_case_count INT NOT NULL DEFAULT 0,
    broken_promise_count INT NOT NULL DEFAULT 0,
    recovery_rate DECIMAL(12, 6) NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL,
    UNIQUE KEY uk_collection_performance_daily (
        stat_date, collector_id, collection_stage, currency_code
    ),
    KEY idx_collection_performance_daily_collector_id (collector_id),
    KEY idx_collection_performance_daily_branch_id (branch_id),
    KEY idx_collection_performance_daily_currency_code (currency_code),
    CONSTRAINT fk_collection_performance_collector FOREIGN KEY (
        collector_id
    ) REFERENCES dim_employee (id),
    CONSTRAINT fk_collection_performance_branch FOREIGN KEY (
        branch_id
    ) REFERENCES dim_branch (id),
    CONSTRAINT fk_collection_performance_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '催收绩效日表，维护催收员每日案件、联系、承诺和回收指标';

CREATE TABLE workflow_instance (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    instance_no VARCHAR(64) NOT NULL,
    workflow_type VARCHAR(64) NOT NULL,
    related_type VARCHAR(64) NOT NULL,
    related_id BIGINT NULL,
    initiator_type VARCHAR(32) NOT NULL,
    initiator_no VARCHAR(64) NOT NULL,
    instance_status VARCHAR(64) NOT NULL,
    started_at DATETIME NOT NULL,
    completed_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_workflow_instance_no (instance_no)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '流程实例表，维护业务审批和处理流程实例';

CREATE TABLE workflow_task (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_no VARCHAR(64) NOT NULL,
    instance_id BIGINT NOT NULL,
    node_code VARCHAR(64) NOT NULL,
    node_name VARCHAR(128) NOT NULL,
    assignee_id BIGINT NULL,
    task_status VARCHAR(64) NOT NULL,
    task_result VARCHAR(64) NULL,
    task_comment TEXT NULL,
    assigned_at DATETIME NOT NULL,
    completed_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_workflow_task_no (task_no),
    KEY idx_workflow_task_instance_id (instance_id),
    KEY idx_workflow_task_assignee_id (assignee_id),
    CONSTRAINT fk_workflow_task_instance FOREIGN KEY (
        instance_id
    ) REFERENCES workflow_instance (id),
    CONSTRAINT fk_workflow_task_assignee FOREIGN KEY (
        assignee_id
    ) REFERENCES dim_employee (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '流程任务表，维护流程节点、处理人、处理结果和完成时间';

CREATE TABLE notification_message (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    message_no VARCHAR(64) NOT NULL,
    customer_id BIGINT NOT NULL,
    related_type VARCHAR(64) NOT NULL,
    related_id BIGINT NULL,
    channel_txn_id BIGINT NULL,
    message_type VARCHAR(64) NOT NULL,
    send_channel VARCHAR(64) NOT NULL,
    message_title VARCHAR(128) NOT NULL,
    message_content TEXT NOT NULL,
    failure_reason TEXT NULL,
    send_status VARCHAR(64) NOT NULL,
    sent_at DATETIME NULL,
    read_status VARCHAR(64) NOT NULL,
    read_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_notification_message_no (message_no),
    KEY idx_notification_message_customer_id (customer_id),
    KEY idx_notification_message_channel_txn_id (channel_txn_id),
    CONSTRAINT fk_notification_message_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_notification_message_channel_txn FOREIGN KEY (
        channel_txn_id
    ) REFERENCES channel_transaction (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '通知消息表，维护客户通知、交易通知、还款提醒和催收提醒';

CREATE TABLE support_ticket (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    ticket_no VARCHAR(64) NOT NULL,
    customer_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    assignee_id BIGINT NULL,
    ticket_type VARCHAR(64) NOT NULL,
    related_type VARCHAR(64) NOT NULL,
    related_id BIGINT NULL,
    ticket_title VARCHAR(128) NOT NULL,
    ticket_content TEXT NOT NULL,
    ticket_status VARCHAR(64) NOT NULL,
    handle_result TEXT NOT NULL,
    submitted_at DATETIME NOT NULL,
    handled_at DATETIME NULL,
    closed_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_support_ticket_no (ticket_no),
    KEY idx_support_ticket_customer_id (customer_id),
    KEY idx_support_ticket_channel_id (channel_id),
    KEY idx_support_ticket_assignee_id (assignee_id),
    CONSTRAINT fk_support_ticket_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id),
    CONSTRAINT fk_support_ticket_channel FOREIGN KEY (
        channel_id
    ) REFERENCES dim_channel (id),
    CONSTRAINT fk_support_ticket_assignee FOREIGN KEY (
        assignee_id
    ) REFERENCES dim_employee (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '客服工单表，维护客户咨询、投诉和业务问题处理';

CREATE TABLE support_ticket_feedback (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    feedback_no VARCHAR(64) NOT NULL,
    ticket_id BIGINT NOT NULL,
    customer_id BIGINT NOT NULL,
    confirm_status VARCHAR(64) NOT NULL,
    satisfaction_score INT NULL,
    feedback_content TEXT NOT NULL,
    confirmed_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_support_ticket_feedback_no (feedback_no),
    UNIQUE KEY uk_support_ticket_feedback_ticket (ticket_id),
    KEY idx_support_ticket_feedback_customer_id (customer_id),
    CONSTRAINT fk_support_ticket_feedback_ticket FOREIGN KEY (
        ticket_id
    ) REFERENCES support_ticket (id),
    CONSTRAINT fk_support_ticket_feedback_customer FOREIGN KEY (
        customer_id
    ) REFERENCES customer (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '客服工单反馈表，维护客户确认、满意度和反馈内容';

CREATE TABLE business_metric_dict (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    metric_code VARCHAR(64) NOT NULL,
    metric_name VARCHAR(128) NOT NULL,
    stat_domain VARCHAR(64) NOT NULL,
    metric_type VARCHAR(64) NOT NULL,
    metric_unit VARCHAR(64) NOT NULL,
    currency_required_flag TINYINT NOT NULL DEFAULT 0,
    calculation_rule TEXT NOT NULL,
    yn TINYINT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_business_metric_code (metric_code)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '业务指标字典表，维护指标编码、统计口径、单位和适用统计域';

CREATE TABLE business_stat_daily (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    stat_date DATE NOT NULL,
    branch_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    currency_code VARCHAR(64) NULL,
    currency_code_key VARCHAR(64) GENERATED ALWAYS AS (
        COALESCE(currency_code, '__NONE__')
    ) STORED,
    stat_domain VARCHAR(64) NOT NULL,
    metric_code VARCHAR(64) NOT NULL,
    metric_id BIGINT NOT NULL,
    metric_name VARCHAR(128) NOT NULL,
    metric_value DECIMAL(18, 2) NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL,
    UNIQUE KEY uk_business_stat_daily_key (
        stat_date,
        branch_id,
        channel_id,
        currency_code_key,
        stat_domain,
        metric_code
    ),
    KEY idx_business_stat_daily_branch_id (branch_id),
    KEY idx_business_stat_daily_channel_id (channel_id),
    KEY idx_business_stat_daily_currency_code (currency_code),
    KEY idx_business_stat_daily_metric_id (metric_id),
    CONSTRAINT fk_business_stat_daily_branch FOREIGN KEY (
        branch_id
    ) REFERENCES dim_branch (id),
    CONSTRAINT fk_business_stat_daily_channel FOREIGN KEY (
        channel_id
    ) REFERENCES dim_channel (id),
    CONSTRAINT fk_business_stat_daily_currency FOREIGN KEY (
        currency_code
    ) REFERENCES dim_currency (currency_code),
    CONSTRAINT fk_business_stat_daily_metric FOREIGN KEY (
        metric_id
    ) REFERENCES business_metric_dict (id)
) ENGINE
= InnoDB DEFAULT CHARSET
= utf8mb4 COMMENT
= '业务日统计表，维护客户、账户、交易、理财、信贷和催收日指标';

SET FOREIGN_KEY_CHECKS = 1;

ALTER TABLE repayment_record
ADD CONSTRAINT fk_repayment_record_promise FOREIGN KEY (repayment_promise_id)
REFERENCES repayment_promise (id);
