# 金融业务数据表结构说明

> 本文档为自动生成的表结构、字段约束与 API 清单，供开发查阅。

## 数据定义
### 通用约束
本节定义跨域通用约束，适用于所有业务表。

- 多态业务对象引用字段统一使用 `related_type` 和 `related_id` 表示，`related_type = none` 时 `related_id` 必须为空，其他枚举值时 `related_id` 必须不为空。
- 多态业务对象引用必须在数据生成和入库校验阶段按枚举值映射到真实目标表，目标记录不存在时不得落库。
- 多态业务对象引用必须校验客户、账户、合同、订单、案件等主体一致性，不得只校验 `related_id` 非空。
- 多态业务对象引用不得指向已物理删除或业务状态无效的目标记录。
- 同一业务对象被流程、通知、风控、冻结、交易或人工复核引用时，引用时间不得早于目标对象创建时间。

### 基础维度
本域用于维护金融业务共享的机构、渠道、币种、产品分类、风险等级和员工等基础主数据。

表说明：

- `dim_branch`：银行机构维表，维护总行、分行、支行和营业网点。
- `dim_channel`：业务渠道维表，维护手机银行、网上银行、柜面、开放银行、合作渠道等渠道。
- `dim_currency`：币种维表，维护账户、交易、贷款和理财使用的币种。
- `dim_risk_level`：风险等级维表，维护客户风险等级、产品风险等级和风控等级。
- `dim_employee`：员工主数据维表，维护员工编号、姓名、所属机构、岗位角色、联系方式和在职状态。
- `dim_product_category`：产品分类维表，维护账户产品、贷款产品、理财产品和服务产品分类。
- `account_product`：账户产品表，维护账户类型、开户条件、限额和账户费率。
- `service_product`：服务产品表，维护服务包、服务费用、适用渠道和服务状态。

依赖关系说明：

- `dim_branch` 通过 `parent_id` 自关联形成机构层级。
- `dim_employee` 依赖 `dim_branch`，员工归属于一个机构。
- `dim_product_category` 通过 `parent_id` 自关联形成产品分类树。
- `account_product` 和 `service_product` 依赖 `dim_product_category` 和 `dim_currency`。
- `dim_channel` 被开户注册、交易、贷款申请、理财交易和客服工单引用。
- `dim_risk_level` 被客户、理财产品、贷款产品、风控事件和人工复核引用。

#### `dim_branch`
银行机构维表，定义总行、分行、支行和营业网点。

- `id`：主键 ID。
- `parent_id`：父机构 ID，关联 `dim_branch.id`，总行为空。
- `branch_code`：机构编码，业务唯一标识。
- `branch_name`：机构名称。
- `branch_level`：机构层级。枚举值：
  - `head_office`：总行
  - `branch`：分行
  - `sub_branch`：支行
  - `outlet`：营业网点
- `province`：所在省份。
- `city`：所在城市。
- `address`：机构地址。
- `service_phone`：客服电话。
- `branch_status`：机构状态。枚举值：
  - `active`：启用
  - `suspended`：暂停
  - `closed`：关闭
- `opened_at`：开业时间。
- `closed_at`：关闭时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_dim_branch_code (branch_code)`
- 外键约束：
  - `fk_dim_branch_parent (parent_id -> dim_branch.id)`
- 业务约束：
  - 总行 `parent_id` 必须为空。
  - 非总行机构 `parent_id` 必须不为空。
  - `parent_id` 不能等于本机构 `id`。
  - 机构层级必须按总行、分行、支行、营业网点顺序逐级挂接。
  - 同一父机构下 `branch_name` 不得重复。
  - `branch_status = active` 时 `closed_at` 必须为空。
  - `branch_status = closed` 时不得作为新客户、账户、员工、贷款和催收案件的归属机构。
  - 汇总统计使用 `branch_code = ALL` 的机构汇总行，汇总行不得用于业务办理。
  - 启用员工、客户账户、贷款合同和催收任务引用的机构不得物理删除。
  - `closed_at` 不为空时 `branch_status` 必须为 `closed`。
  - `closed_at` 不为空时 `opened_at` 必须早于 `closed_at`。
  - `updated_at >= created_at`

#### `dim_channel`
业务渠道维表，定义开户、交易、贷款、理财和服务请求来源。

- `id`：主键 ID。
- `channel_code`：渠道编码，业务唯一标识。
- `channel_name`：渠道名称。
- `channel_type`：渠道类型。枚举值：
  - `mobile_bank`：手机银行
  - `online_bank`：网上银行
  - `counter`：柜面
  - `open_api`：开放银行
  - `partner`：合作渠道
  - `batch`：批处理
- `channel_status`：渠道状态。枚举值：
  - `active`：启用
  - `suspended`：暂停
  - `offline`：下线
- `yn`：是否启用，`1` 表示启用，`0` 表示停用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_dim_channel_code (channel_code)`
- 外键约束：
  - 无
- 业务约束：
  - 启用渠道才能用于开户注册、资金交易、贷款申请和理财交易。
  - 已被业务流水引用的渠道不得物理删除，只能停用。
  - `channel_status = active` 时 `yn` 必须为 `1`。
  - `channel_status IN ('suspended', 'offline')` 时 `yn` 必须为 `0`。
  - 批处理渠道只能用于批量入账、批量扣款、日终统计和系统补偿类业务。
  - 合作渠道必须在业务订单、渠道流水或客服工单中保留外部渠道标识。
  - 下线渠道不得新增业务流水，但历史流水仍可用于查询、对账和统计。
  - 汇总统计使用 `channel_code = ALL` 的渠道汇总行，汇总行不得用于业务办理。
  - `updated_at >= created_at`

#### `dim_currency`
币种维表，定义账户余额、交易金额、贷款金额和理财金额使用的币种。

- `id`：主键 ID。
- `currency_code`：币种代码，业务唯一标识。
- `currency_name`：币种名称。
- `symbol`：币种符号。
- `precision_scale`：金额精度位数。
- `yn`：是否启用，`1` 表示启用，`0` 表示停用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_dim_currency_code (currency_code)`
- 外键约束：
  - 无
- 业务约束：
  - 启用币种才能用于新开账户、交易、贷款和理财产品。
  - 人民币 `currency_code = CNY` 的 `precision_scale` 固定为 `2`。
  - `currency_code` 必须使用 ISO 4217 三位大写代码。
  - `precision_scale >= 0`
  - 金额字段的小数位数不得超过币种 `precision_scale`。
  - 已停用币种不得用于新增账户、交易、贷款产品和理财产品。
  - 已被业务数据引用的币种不得物理删除，只能停用。
  - `updated_at >= created_at`

#### `dim_risk_level`
风险等级维表，统一定义客户、产品和事件风险等级。

- `id`：主键 ID。
- `risk_level_code`：风险等级编码，业务唯一标识。
- `risk_level_name`：风险等级名称。
- `risk_level_type`：等级类型。枚举值：
  - `customer`：客户风险等级
  - `product`：产品风险等级
  - `event`：事件风险等级
- `risk_score_min`：等级分数下限。
- `risk_score_max`：等级分数上限。
- `sort_no`：排序号。
- `yn`：是否启用，`1` 表示启用，`0` 表示停用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_dim_risk_level_code (risk_level_code)`
- 外键约束：
  - 无
- 业务约束：
  - 同一 `risk_level_type` 下分数区间不得重叠。
  - `risk_score_min <= risk_score_max`
  - 同一 `risk_level_type` 下 `sort_no` 不得重复。
  - 同一 `risk_level_type` 下启用等级应覆盖业务使用的完整评分区间。
  - 客户风险等级只能引用 `risk_level_type = customer` 的记录。
  - 产品风险等级只能引用 `risk_level_type = product` 的记录。
  - 风控事件和黑名单风险等级只能引用 `risk_level_type = event` 的记录。
  - 理财适当性校验使用客户风险等级和产品风险等级的 `sort_no` 比较，`sort_no` 越大表示可承受或产品风险越高。
  - 客户风险等级覆盖产品风险等级时，客户等级 `sort_no` 必须大于等于产品等级 `sort_no`。
  - `updated_at >= created_at`

#### `dim_employee`
员工主数据维表，定义员工编号、姓名、所属机构、岗位角色、联系方式和在职状态。

- `id`：主键 ID。
- `employee_no`：员工编号，业务唯一标识。
- `employee_name`：员工姓名。
- `branch_id`：所属机构 ID，关联 `dim_branch.id`。
- `employee_role`：员工角色。枚举值：
  - `relationship_manager`：客户经理
  - `loan_approver`：信贷审批员
  - `risk_officer`：风控员
  - `collector`：催收员
  - `operator`：运营人员
  - `customer_service`：客服人员
- `permission_codes`：员工权限编码集合。
- `mobile`：手机号。
- `email`：邮箱。
- `employee_status`：员工状态。枚举值：
  - `active`：在职
  - `suspended`：停用
  - `resigned`：离职
- `joined_at`：入职时间。
- `resigned_at`：离职时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_dim_employee_no (employee_no)`
  - `uk_dim_employee_mobile (mobile)`
  - `uk_dim_employee_email (email)`
- 外键约束：
  - `fk_dim_employee_branch (branch_id -> dim_branch.id)`
- 业务约束：
  - `employee_status = resigned` 时 `resigned_at` 必须不为空。
  - `employee_status IN ('active', 'suspended')` 时 `resigned_at` 必须为空。
  - `resigned_at` 不为空时 `joined_at` 必须早于 `resigned_at`。
  - 所属机构必须处于启用状态才能新增在职员工。
  - 只有在职员工才能分配审批、复核、催收和客服任务。
  - 离职员工不得作为新增审批、复核、催收、客服和操作记录的处理人。
  - 员工角色必须与任务类型匹配，信贷审批任务使用 `loan_approver`，风控复核任务使用 `risk_officer`，催收任务使用 `collector`。
  - 费用减免、客服处理、人工复核和运营操作必须校验员工角色及对应 `permission_codes`。
  - `updated_at >= created_at`

#### `dim_product_category`
产品分类维表，定义账户、贷款、理财和服务产品分类。

- `id`：主键 ID。
- `parent_id`：父分类 ID，关联 `dim_product_category.id`，顶级分类为空。
- `category_code`：分类编码，业务唯一标识。
- `category_name`：分类名称。
- `category_type`：分类类型。枚举值：
  - `account`：账户产品
  - `loan`：贷款产品
  - `wealth`：理财产品
  - `service`：服务产品
- `category_level`：分类层级。
- `sort_no`：排序号。
- `yn`：是否启用，`1` 表示启用，`0` 表示停用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_dim_product_category_code (category_code)`
- 外键约束：
  - `fk_dim_product_category_parent (parent_id -> dim_product_category.id)`
- 业务约束：
  - 顶级分类 `parent_id` 必须为空。
  - 非顶级分类 `parent_id` 必须不为空。
  - `parent_id` 不能等于本分类 `id`。
  - 子分类的 `category_type` 必须与父分类一致。
  - 子分类的 `category_level` 必须等于父分类 `category_level + 1`。
  - 同一父分类下 `category_name` 不得重复。
  - 已停用分类不得被新增产品引用。
  - 已被产品引用的分类不得物理删除，只能停用。
  - `updated_at >= created_at`

#### `account_product`
账户产品表，维护账户类型、开户条件、限额和账户费率。
- `id`：主键 ID。
- `product_code`：账户产品编码，业务唯一标识。
- `product_name`：账户产品名称。
- `category_id`：产品分类 ID，关联 `dim_product_category.id`。
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `account_type`：账户类型。枚举值：
  - `demand_deposit`：活期存款账户
  - `settlement`：结算账户
  - `loan_repayment`：贷款还款账户
  - `wealth_settlement`：理财结算账户
- `min_open_amount`：最低开户金额。
- `daily_transfer_limit`：日转账限额。
- `daily_withdraw_limit`：日提现限额。
- `annual_fee_amount`：年费金额。
- `product_status`：产品状态。枚举值：
  - `draft`：草稿
  - `active`：启用
  - `paused`：暂停
  - `offline`：下线
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_account_product_code (product_code)`
- 外键约束：
  - `fk_account_product_category (category_id -> dim_product_category.id)`
  - `fk_account_product_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - 产品分类必须为 `category_type = account`。
  - 金额和限额字段必须大于等于 `0`。
  - 只有启用账户产品才能用于新开账户。
  - 银行账户的 `account_type` 必须与账户产品的 `account_type` 一致。
  - 下线账户产品不得新增账户，存量账户保留原产品规则。
  - `updated_at >= created_at`

#### `service_product`
服务产品表，维护服务包、服务费用、适用渠道和服务状态。
- `id`：主键 ID。
- `service_code`：服务产品编码，业务唯一标识。
- `service_name`：服务产品名称。
- `category_id`：产品分类 ID，关联 `dim_product_category.id`。
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `service_type`：服务类型。枚举值：
  - `account_service`：账户服务
  - `transaction_service`：交易服务
  - `wealth_service`：理财服务
  - `loan_service`：贷款服务
  - `support_service`：客服服务
- `fee_amount`：服务费用金额。
- `service_status`：服务状态。枚举值：
  - `draft`：草稿
  - `active`：启用
  - `paused`：暂停
  - `offline`：下线
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_service_product_code (service_code)`
- 外键约束：
  - `fk_service_product_category (category_id -> dim_product_category.id)`
  - `fk_service_product_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - 产品分类必须为 `category_type = service`。
  - `fee_amount >= 0`
  - 服务产品作为账户、交易、理财、贷款和客服流程的服务能力及收费配置，不单独生成服务订购链路。
  - 只有启用服务产品才能被新增业务流程引用或用于手续费计算。
  - 下线服务产品不得用于新增服务费计算或新增业务流程配置。
  - `updated_at >= created_at`

### 客户域
本域用于维护客户主体、实名认证、KYC、联系方式、风险测评和客户标签。

表说明：

- `customer`：客户主表，维护个人客户和企业客户的统一客户号、状态和归属机构。
- `customer_status_history`：客户状态历史表，维护客户实名、限制、冻结和销户等状态变更。
- `customer_identity`：客户实名信息表，维护证件、姓名、实名状态和认证结果。
- `customer_contact`：客户联系方式表，维护手机号、邮箱、地址和默认联系方式。
- `customer_device`：客户设备表，维护登录设备、设备指纹和设备风险状态。
- `customer_kyc`：客户 KYC 表，维护职业、收入、资金来源、行业和合规状态。
- `enterprise_profile`：企业客户档案表，维护企业注册信息、经营信息和规模信息。
- `beneficial_owner`：受益所有人表，维护企业客户实际控制人、股东和授权经办人。
- `customer_risk_assessment`：客户风险测评表，维护理财风险承受能力和测评结果。
- `customer_tag`：客户标签表，维护客户分群、营销标签、风险标签和运营标签。
- `customer_tag_rel`：客户标签关系表，维护客户和标签的多对多关系。

依赖关系说明：

- `customer_status_history`、`customer_identity`、`customer_contact`、`customer_device`、`customer_kyc`、`enterprise_profile`、`beneficial_owner` 和 `customer_risk_assessment` 依赖 `customer`。
- `customer` 依赖 `dim_branch`、`dim_channel` 和 `dim_risk_level`。
- `customer_tag_rel` 依赖 `customer` 和 `customer_tag`。
- 信贷、理财、账户、交易、风控和催收均以 `customer.id` 作为客户主体。

#### `customer`
客户主表，统一存储个人客户和企业客户的客户号、客户类型和生命周期状态。

- `id`：主键 ID。
- `customer_no`：客户号，业务唯一标识。
- `customer_type`：客户类型。枚举值：
  - `personal`：个人客户
  - `enterprise`：企业客户
- `customer_name`：客户名称，个人客户为姓名，企业客户为企业名称。
- `branch_id`：归属机构 ID，关联 `dim_branch.id`。
- `register_channel_id`：注册渠道 ID，关联 `dim_channel.id`。
- `risk_level_id`：客户风险等级 ID，关联 `dim_risk_level.id`。
- `customer_status`：客户状态。枚举值：
  - `pending_kyc`：待实名
  - `active`：正常
  - `restricted`：限制
  - `frozen`：冻结
  - `closed`：销户
- `opened_at`：开户注册时间。
- `closed_at`：销户时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_customer_no (customer_no)`
- 外键约束：
  - `fk_customer_branch (branch_id -> dim_branch.id)`
  - `fk_customer_register_channel (register_channel_id -> dim_channel.id)`
  - `fk_customer_risk_level (risk_level_id -> dim_risk_level.id)`
- 业务约束：
  - `customer_status = closed` 时 `closed_at` 必须不为空。
  - `customer_status != closed` 时 `closed_at` 必须为空。
  - `closed_at` 不为空时 `opened_at` 不得晚于 `closed_at`。
  - 客户激活、开户注册、申贷和申购前，个人客户必须存在已认证个人证件实名信息。
  - 客户激活、开户注册、申贷和申购前，企业客户必须存在已认证企业证件实名信息和企业客户档案。
  - `risk_level_id` 必须引用 `risk_level_type = customer` 的风险等级。
  - 限制、冻结和销户客户不得新增账户、贷款申请、理财申购、普通支出和投资类交易。
  - 限制、冻结和销户客户允许存量贷款还款、催收回款、退款、冲正和调账等清偿或纠错交易，并继续受账户状态、余额、授权、风控和对账约束。
  - 客户状态变更必须写入 `customer_status_history`。
  - 未完成实名的客户不能开立资金账户、申请贷款或申购理财。
  - 已有关联账户、贷款、理财持仓或交易流水的客户不得物理删除。
  - `updated_at >= created_at`

#### `customer_status_history`
客户状态历史表，维护客户实名、限制、冻结和销户等状态变更。
- `id`：主键 ID。
- `customer_id`：客户 ID，关联 `customer.id`。
- `change_seq`：客户内状态变更序号。
- `from_status`：变更前客户状态。
- `to_status`：变更后客户状态。
- `change_reason`：变更原因。
- `related_type`：关联对象类型。枚举值：
  - `none`：无
  - `risk_event`：风险事件
  - `blacklist_record`：黑名单记录
  - `fund_freeze`：资金冻结
  - `support_ticket`：客服工单
- `related_id`：关联对象 ID。
- `operator_id`：操作员工 ID，关联 `dim_employee.id`。
- `changed_at`：变更时间。
- `created_at`：创建时间。

- 唯一性约束：
  - `uk_customer_status_history_seq (customer_id, change_seq)`
  - `uk_customer_status_history_time (customer_id, changed_at, to_status)`
- 外键约束：
  - `fk_customer_status_history_customer (customer_id -> customer.id)`
  - `fk_customer_status_history_operator (operator_id -> dim_employee.id)`
- 业务约束：
  - `from_status` 和 `to_status` 不能相同。
  - 第一条状态历史的 `change_seq` 必须为 `1`，`from_status` 可以为空。
  - 后续记录的 `change_seq` 必须连续递增，`from_status` 必须等于上一条记录的 `to_status`。
  - 只有同一客户 `change_seq` 最大的状态历史记录，其 `to_status` 必须等于当前 `customer.customer_status`。
  - 非最新状态历史记录的 `to_status` 只表示当次变更后的历史状态，不要求等于当前 `customer.customer_status`。
  - 状态变更时间 `changed_at` 必须晚于客户创建时间。
  - 人工变更客户状态时 `operator_id` 必须不为空。
  - 由风控、黑名单、司法冻结或销户触发的状态变更必须填写 `related_type` 和 `related_id`。
  - 客户状态变更必须写入历史记录。
  - 状态历史不得物理删除。

#### `customer_identity`
客户实名信息表，维护实名证件、认证状态和认证时间。

- `id`：主键 ID。
- `customer_id`：客户 ID，关联 `customer.id`。
- `identity_type`：证件类型。枚举值：
  - `id_card`：居民身份证
  - `passport`：护照
  - `business_license`：营业执照
  - `uniform_social_credit_code`：统一社会信用代码
- `identity_no`：证件号码。
- `legal_name`：证件姓名或企业法定名称。
- `legal_representative`：法定代表人，企业客户使用。
- `identity_valid_from`：证件有效期开始日期。
- `identity_valid_to`：证件有效期结束日期。
- `verification_status`：认证状态。枚举值：
  - `pending`：待认证
  - `verified`：已认证
  - `failed`：认证失败
  - `expired`：证件过期
- `current_flag`：是否当前实名信息，`1` 表示是，`0` 表示否。
- `verified_at`：认证通过时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_customer_identity_no (identity_type, identity_no)`
  - `uk_customer_identity_current (customer_id, current_flag)`，仅限制 `current_flag = 1` 的当前实名信息。
- 外键约束：
  - `fk_customer_identity_customer (customer_id -> customer.id)`
- 业务约束：
  - 一个客户最多有一条当前实名信息。
  - `verification_status = verified` 时 `verified_at` 必须不为空。
  - `verification_status != verified` 时不得作为开户注册、贷款申请和理财申购的有效实名信息。
  - 个人客户证件类型只能使用 `id_card` 或 `passport`。
  - 企业客户证件类型只能使用 `business_license` 或 `uniform_social_credit_code`。
  - 企业客户的 `legal_representative` 必须不为空。
  - `identity_valid_to` 不为空时必须晚于 `identity_valid_from`。
  - 当前日期超过 `identity_valid_to` 时 `verification_status` 应更新为 `expired`。
  - 实名证件号命中有效黑名单时不得认证通过。
  - 证件过期客户不能新增贷款申请和理财申购。
  - `updated_at >= created_at`

#### `customer_contact`
客户联系方式表，维护客户手机号、邮箱和地址。

- `id`：主键 ID。
- `customer_id`：客户 ID，关联 `customer.id`。
- `contact_type`：联系方式类型。枚举值：
  - `mobile`：手机号
  - `email`：邮箱
  - `address`：地址
  - `emergency_contact`：紧急联系人
- `contact_value`：联系方式内容。
- `contact_name`：联系人姓名。
- `is_primary`：是否主联系方式，`1` 表示是，`0` 表示否。
- `verified_flag`：是否已验证，`1` 表示已验证，`0` 表示未验证。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_customer_contact_primary (customer_id, contact_type, is_primary)`，仅限制 `is_primary = 1` 的主联系方式。
  - `uk_customer_contact_verified_mobile (contact_type, contact_value)`，仅限制已验证手机号。
- 外键约束：
  - `fk_customer_contact_customer (customer_id -> customer.id)`
- 业务约束：
  - 同一客户同一 `contact_type` 最多一个主联系方式。
  - 同一客户至少需要一个主手机号或主邮箱。
  - `contact_type = mobile` 时 `contact_value` 必须符合手机号格式。
  - `contact_type = email` 时 `contact_value` 必须符合邮箱格式。
  - `contact_type = emergency_contact` 时 `contact_name` 必须不为空。
  - 主手机号用于贷款申请前必须完成验证。
  - 已验证联系方式变更后 `verified_flag` 必须重新置为 `0`。
  - 贷款申请必须存在已验证手机号。
  - `updated_at >= created_at`

#### `customer_device`
客户设备表，维护登录设备、设备指纹和设备风险状态。
- `id`：主键 ID。
- `device_no`：设备编号，业务唯一标识。
- `customer_id`：客户 ID，关联 `customer.id`。
- `device_fingerprint`：设备指纹。
- `device_type`：设备类型。枚举值：
  - `ios`：iOS
  - `android`：Android
  - `web`：网页
  - `mini_program`：小程序
  - `other`：其他
- `device_name`：设备名称。
- `app_version`：App 版本。
- `os_version`：操作系统版本。
- `push_token`：App 推送令牌。
- `ip_address`：最近登录 IP。
- `geo_location`：最近登录地理位置。
- `first_seen_at`：首次出现时间。
- `last_seen_at`：最近出现时间。
- `trusted_flag`：是否可信设备，`1` 表示是，`0` 表示否。
- `risk_status`：设备风险状态。枚举值：
  - `normal`：正常
  - `suspicious`：可疑
  - `blacklisted`：黑名单
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_customer_device_no (device_no)`
  - `uk_customer_device_fingerprint (customer_id, device_fingerprint)`
- 外键约束：
  - `fk_customer_device_customer (customer_id -> customer.id)`
- 业务约束：
  - 已拉黑设备不得发起开户注册、交易、贷款申请和理财申购。
  - 同一设备指纹绑定多个客户时必须触发风控事件。
  - `risk_status = blacklisted` 时必须存在有效黑名单记录。
  - `trusted_flag = 1` 时 `risk_status` 必须为 `normal`。
  - 设备首次出现时必须记录 `first_seen_at`。
  - `device_type IN ('ios', 'android')` 且用于 App 推送时 `push_token` 必须不为空。
  - 设备每次登录或交易后必须更新 `last_seen_at`。
  - `last_seen_at` 必须晚于或等于 `first_seen_at`。
  - `updated_at >= created_at`

#### `customer_kyc`
客户 KYC 表，维护职业、收入、行业、资金来源和合规状态。

- `id`：主键 ID。
- `customer_id`：客户 ID，关联 `customer.id`。
- `occupation`：职业。
- `industry`：行业。
- `annual_income_amount`：年收入金额。
- `income_currency_code`：收入币种，关联 `dim_currency.currency_code`。
- `fund_source`：资金来源。枚举值：
  - `salary`：工资
  - `business`：经营所得
  - `investment`：投资收益
  - `inheritance`：继承
  - `other`：其他
- `employment_status`：就业状态。枚举值：
  - `employed`：受雇
  - `self_employed`：自雇
  - `retired`：退休
  - `student`：学生
  - `unemployed`：无业
- `kyc_status`：KYC 状态。枚举值：
  - `pending`：待完善
  - `approved`：通过
  - `rejected`：拒绝
  - `expired`：过期
- `compliance_status`：合规状态。枚举值：
  - `normal`：正常
  - `enhanced_review`：强化审核
  - `restricted`：限制
  - `blocked`：阻断
- `review_result`：审核结论。
- `reject_reason`：拒绝原因。
- `review_comment`：审核备注。
- `reviewed_at`：审核时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_customer_kyc_customer (customer_id)`
- 外键约束：
  - `fk_customer_kyc_customer (customer_id -> customer.id)`
  - `fk_customer_kyc_currency (income_currency_code -> dim_currency.currency_code)`
- 业务约束：
  - `annual_income_amount >= 0`
  - `income_currency_code` 必须为启用币种。
  - `kyc_status = approved` 时 `reviewed_at` 必须不为空。
  - `kyc_status = rejected` 时应保留拒绝原因或审核结论。
  - 企业客户的行业、资金来源和合规状态必须与 `enterprise_profile` 保持一致。
  - KYC 过期后不得新增高风险交易、贷款申请和高风险理财申购。
  - KYC 信息发生职业、行业、收入或资金来源重大变更时必须重新审核。
  - KYC 未通过客户不能新增贷款申请和高风险理财申购。
  - `kyc_status IN ('approved', 'rejected')` 时 `reviewed_at` 必须不为空。
  - `updated_at >= created_at`

#### `enterprise_profile`
企业客户档案表，维护企业注册信息、经营信息和规模信息。
- `id`：主键 ID。
- `customer_id`：企业客户 ID，关联 `customer.id`。
- `company_name`：企业名称。
- `registration_no`：工商注册号。
- `uniform_social_credit_code`：统一社会信用代码。
- `legal_representative`：法定代表人。
- `registered_capital_amount`：注册资本金额。
- `registered_capital_currency_code`：注册资本币种，关联 `dim_currency.currency_code`。
- `established_date`：成立日期。
- `registered_address`：注册地址。
- `business_address`：经营地址。
- `business_scope`：经营范围。
- `industry`：所属行业。
- `company_scale`：企业规模。枚举值：
  - `micro`：微型
  - `small`：小型
  - `medium`：中型
  - `large`：大型
- `employee_count`：员工人数。
- `annual_revenue_amount`：年营业收入金额。
- `taxpayer_type`：纳税人类型。枚举值：
  - `general`：一般纳税人
  - `small_scale`：小规模纳税人
  - `non_taxpayer`：非纳税主体
- `business_status`：经营状态。枚举值：
  - `normal`：正常
  - `abnormal`：经营异常
  - `revoked`：吊销
  - `cancelled`：注销
- `compliance_status`：企业合规状态。枚举值：
  - `normal`：正常
  - `enhanced_review`：强化审核
  - `restricted`：限制
  - `blocked`：阻断
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_enterprise_profile_customer (customer_id)`
  - `uk_enterprise_profile_credit_code (uniform_social_credit_code)`
- 外键约束：
  - `fk_enterprise_profile_customer (customer_id -> customer.id)`
  - `fk_enterprise_profile_capital_currency (registered_capital_currency_code -> dim_currency.currency_code)`
- 业务约束：
  - `customer.customer_type` 必须为 `enterprise`。
  - `registered_capital_amount >= 0`
  - `employee_count >= 0`
  - `annual_revenue_amount >= 0`
  - 企业客户统一社会信用代码必须与企业实名信息一致。
  - `business_status = normal` 时企业实名信息和受益所有人信息必须核验通过。
  - `established_date` 不得晚于当前日期。
  - 经营地址为空时默认使用注册地址。
  - 企业经营范围为空时不得新增经营贷申请。
  - 企业客户经营状态变更为异常、吊销或注销时必须同步限制客户状态。
  - 经营异常、吊销或注销企业不得新增贷款申请和理财申购。
  - `updated_at >= created_at`

#### `beneficial_owner`
受益所有人表，维护企业客户实际控制人、股东和授权经办人。
- `id`：主键 ID。
- `customer_id`：企业客户 ID，关联 `customer.id`。
- `owner_type`：人员类型。枚举值：
  - `actual_controller`：实际控制人
  - `shareholder`：股东
  - `legal_representative`：法定代表人
  - `authorized_operator`：授权经办人
  - `senior_manager`：高级管理人员
- `owner_name`：人员姓名。
- `identity_type`：证件类型。
- `identity_no`：证件号码。
- `mobile`：手机号。
- `email`：邮箱。
- `ownership_ratio`：持股比例。
- `control_description`：控制关系说明。
- `authorization_valid_from`：授权有效期开始日期。
- `authorization_valid_to`：授权有效期结束日期。
- `verification_status`：核验状态。枚举值：
  - `pending`：待核验
  - `verified`：已核验
  - `failed`：核验失败
  - `expired`：已过期
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_beneficial_owner_identity (customer_id, owner_type, identity_type, identity_no)`
- 外键约束：
  - `fk_beneficial_owner_customer (customer_id -> customer.id)`
- 业务约束：
  - `customer.customer_type` 必须为 `enterprise`。
  - `ownership_ratio` 为空或满足 `ownership_ratio >= 0 AND ownership_ratio <= 100`。
  - 企业客户至少维护一名法定代表人。
  - 企业客户至少维护一名实际控制人或持股比例大于等于 25 的股东。
  - 同一企业下已核验股东的 `ownership_ratio` 合计不得超过 `100`。
  - `owner_type = authorized_operator` 时授权有效期必须不为空。
  - `verification_status = verified` 时证件和联系方式必须完成核验。
  - 证件号码或手机号命中有效黑名单时不得核验通过。
  - 已过期授权经办人不得发起企业客户业务。
  - 授权经办人发起开户、交易、贷款或理财业务时必须处于已核验且授权有效状态。
  - `authorization_valid_to` 不为空时必须晚于 `authorization_valid_from`。
  - `updated_at >= created_at`

#### `customer_risk_assessment`
客户风险测评表，维护理财风险承受能力测评记录。

- `id`：主键 ID。
- `assessment_no`：测评编号，业务唯一标识。
- `customer_id`：客户 ID，关联 `customer.id`。
- `risk_level_id`：测评风险等级 ID，关联 `dim_risk_level.id`。
- `assessment_score`：测评分数。
- `assessment_type`：测评类型。枚举值：
  - `initial`：首次测评
  - `renewal`：重新测评
  - `manual`：人工调整
- `assessment_status`：测评状态。枚举值：
  - `valid`：有效
  - `expired`：过期
  - `revoked`：撤销
- `valid_from`：生效时间。
- `valid_to`：失效时间。
- `operator_id`：人工调整员工 ID，关联 `dim_employee.id`。
- `adjust_reason`：人工调整原因。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_customer_risk_assessment_no (assessment_no)`
- 外键约束：
  - `fk_customer_risk_assessment_customer (customer_id -> customer.id)`
  - `fk_customer_risk_assessment_level (risk_level_id -> dim_risk_level.id)`
  - `fk_customer_risk_assessment_operator (operator_id -> dim_employee.id)`
- 业务约束：
  - 同一客户同一时间只能有一条有效风险测评。
  - 有效测评 `valid_to` 必须晚于 `valid_from`。
  - `risk_level_id` 必须引用 `risk_level_type = customer` 的风险等级。
  - `assessment_score` 必须落入对应风险等级的分数区间。
  - `assessment_status = valid` 时当前时间必须位于 `valid_from` 和 `valid_to` 之间。
  - `assessment_status IN ('expired', 'revoked')` 的测评不得用于理财申购。
  - 人工调整测评必须记录员工操作来源。
  - 新测评生效后同一客户旧有效测评必须置为过期或撤销。
  - 理财申购必须使用有效风险测评。
  - `updated_at >= created_at`

#### `customer_tag`
客户标签表，维护客户分群、营销标签、风险标签和运营标签。

- `id`：主键 ID。
- `tag_code`：标签编码，业务唯一标识。
- `tag_name`：标签名称。
- `tag_type`：标签类型。枚举值：
  - `segment`：客户分群
  - `marketing`：营销标签
  - `risk`：风险标签
  - `operation`：运营标签
- `yn`：是否启用，`1` 表示启用，`0` 表示停用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_customer_tag_code (tag_code)`
- 外键约束：
  - 无
- 业务约束：
  - 已被客户引用的标签不得物理删除，只能停用。
  - 风险标签可被风控规则和催收策略引用。
  - 已停用标签不得新增客户标签关系。
  - 同一 `tag_type` 下 `tag_name` 不得重复。
  - 风险标签用于风控规则时必须保持启用状态。
  - 标签编码停用后不得被重新用于不同业务含义。
  - `updated_at >= created_at`

#### `customer_tag_rel`
客户标签关系表，维护客户和标签的多对多关系。

- `id`：主键 ID。
- `customer_id`：客户 ID，关联 `customer.id`。
- `tag_id`：标签 ID，关联 `customer_tag.id`。
- `source_type`：来源类型。枚举值：
  - `manual`：人工标记
  - `rule`：规则生成
  - `model`：模型生成
  - `import`：导入
- `source_id`：来源对象 ID。
- `source_ref`：来源对象引用。
- `model_version`：模型版本。
- `batch_no`：导入或计算批次号。
- `effective_from`：生效时间。
- `effective_to`：失效时间。
- `created_at`：创建时间。

- 唯一性约束：
  - `uk_customer_tag_rel_active (customer_id, tag_id, source_type)`，仅限制 `effective_to` 为空的有效关系。
- 外键约束：
  - `fk_customer_tag_rel_customer (customer_id -> customer.id)`
  - `fk_customer_tag_rel_tag (tag_id -> customer_tag.id)`
- 业务约束：
  - `effective_to` 为空表示长期有效。
  - `effective_to` 不为空时必须晚于 `effective_from`。
  - 同一客户同一标签同一来源在同一时间只能存在一条有效关系。
  - 标签关系生效前标签必须处于启用状态。
  - 来源为 `rule` 或 `model` 时 `source_id` 或 `source_ref` 必须不为空。
  - 来源为 `model` 时 `model_version` 必须不为空。
  - 来源为 `import` 时 `batch_no` 必须不为空。
  - 客户销户后不得新增标签关系。
  - 标签关系不得物理删除，失效应更新 `effective_to`。

### 账户交易域
本域用于维护银行账户、银行卡、账户余额、资金交易和账户流水。

表说明：

- `bank_account`：银行账户表，维护账户号、账户类型、余额、冻结金额和账户状态。
- `bank_account_status_history`：账户状态历史表，维护账户正常、限制、冻结和销户等状态变更。
- `bank_card`：银行卡表，维护卡号、卡类型、绑定账户和卡片状态。
- `account_transaction`：账户交易表，维护转账、消费、充值、提现、退款和冲正等交易。
- `channel_transaction`：渠道流水表，维护外部渠道订单、请求响应、回调和对账状态。
- `reconciliation_batch`：对账批次表，维护渠道对账文件、批次状态和对账范围。
- `reconciliation_result`：对账结果表，维护交易与渠道流水的匹配、差错和处理状态。
- `reconciliation_adjustment`：对账调账表，维护差错调账交易、调账金额和审批状态。
- `account_ledger`：账户流水表，维护账户余额变动、冻结变动和交易后余额。
- `fund_freeze`：资金冻结表，维护交易、贷款、理财相关的冻结和解冻记录。
- `fund_freeze_operation`：资金冻结操作明细表，维护每次冻结、解冻、释放和取消操作。

依赖关系说明：

- `bank_account` 依赖 `customer`、`dim_branch` 和 `dim_currency`。
- `bank_account_status_history` 和 `bank_card` 依赖 `bank_account`。
- `account_transaction` 依赖 `customer`、`bank_account` 和 `dim_channel`。
- `channel_transaction` 依赖 `dim_channel`，并在已匹配银行侧交易时依赖 `account_transaction`。
- `reconciliation_batch` 依赖 `dim_channel`。
- `reconciliation_result` 依赖 `reconciliation_batch`、`account_transaction` 和 `channel_transaction`。
- `reconciliation_adjustment` 依赖 `reconciliation_result` 和 `account_transaction`。
- `account_ledger` 依赖 `bank_account` 和 `account_transaction`。
- `fund_freeze` 依赖 `bank_account`，并可关联交易、贷款、理财订单或风控事件。
- `fund_freeze_operation` 依赖 `fund_freeze`、`bank_account` 和 `account_transaction`。

#### `bank_account`
银行账户表，维护客户资金账户和余额信息。

- `id`：主键 ID。
- `account_no`：账户号，业务唯一标识。
- `customer_id`：客户 ID，关联 `customer.id`。
- `branch_id`：开户机构 ID，关联 `dim_branch.id`。
- `open_channel_id`：开户渠道 ID，关联 `dim_channel.id`。
- `account_product_id`：账户产品 ID，关联 `account_product.id`。
- `currency_code`：账户币种，关联 `dim_currency.currency_code`。
- `account_type`：账户类型。枚举值：
  - `demand_deposit`：活期存款账户
  - `settlement`：结算账户
  - `loan_repayment`：贷款还款账户
  - `wealth_settlement`：理财结算账户
- `account_status`：账户状态。枚举值：
  - `active`：正常
  - `frozen`：冻结
  - `restricted`：限制
  - `closed`：销户
- `balance_amount`：账户余额。
- `frozen_amount`：冻结金额。
- `available_amount`：可用余额。
- `opened_at`：开户时间。
- `closed_at`：销户时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_bank_account_no (account_no)`
- 外键约束：
  - `fk_bank_account_customer (customer_id -> customer.id)`
  - `fk_bank_account_branch (branch_id -> dim_branch.id)`
  - `fk_bank_account_open_channel (open_channel_id -> dim_channel.id)`
  - `fk_bank_account_product (account_product_id -> account_product.id)`
  - `fk_bank_account_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - `balance_amount >= 0`
  - `frozen_amount >= 0`
  - `available_amount = balance_amount - frozen_amount`
  - `available_amount >= 0`
  - 账户币种必须为启用币种。
  - 账户产品必须为启用账户产品，且产品币种必须与账户币种一致。
  - 开户客户必须为已实名、KYC 有效且未冻结、未限制、未销户状态。
  - 账户所属机构必须处于启用状态。
  - 开户渠道必须为启用渠道。
  - 账户状态变更必须写入 `bank_account_status_history`。
  - 冻结账户不得发起支出类交易，限制账户只能发起允许范围内的交易。
  - 账户余额变化只能由账户流水汇总产生，不得直接手工改余额。
  - 账户销户前余额和冻结金额必须为 `0`。
  - `account_status = closed` 时 `closed_at` 必须不为空。
  - `updated_at >= created_at`

#### `bank_account_status_history`
账户状态历史表，维护账户正常、限制、冻结和销户等状态变更。
- `id`：主键 ID。
- `account_id`：账户 ID，关联 `bank_account.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `change_seq`：账户内状态变更序号。
- `from_status`：变更前账户状态。
- `to_status`：变更后账户状态。
- `change_reason`：变更原因。
- `related_type`：关联对象类型。枚举值：
  - `none`：无
  - `risk_event`：风险事件
  - `fund_freeze`：资金冻结
  - `account_transaction`：账户交易
  - `support_ticket`：客服工单
- `related_id`：关联对象 ID。
- `operator_id`：操作员工 ID，关联 `dim_employee.id`。
- `changed_at`：变更时间。
- `created_at`：创建时间。

- 唯一性约束：
  - `uk_bank_account_status_history_seq (account_id, change_seq)`
  - `uk_bank_account_status_history_time (account_id, changed_at, to_status)`
- 外键约束：
  - `fk_bank_account_status_history_account (account_id -> bank_account.id)`
  - `fk_bank_account_status_history_customer (customer_id -> customer.id)`
  - `fk_bank_account_status_history_operator (operator_id -> dim_employee.id)`
- 业务约束：
  - `from_status` 和 `to_status` 不能相同。
  - 第一条状态历史的 `change_seq` 必须为 `1`，`from_status` 可以为空。
  - 后续记录的 `change_seq` 必须连续递增，`from_status` 必须等于上一条记录的 `to_status`。
  - 只有同一账户 `change_seq` 最大的状态历史记录，其 `to_status` 必须等于当前 `bank_account.account_status`。
  - 非最新状态历史记录的 `to_status` 只表示当次变更后的历史状态，不要求等于当前 `bank_account.account_status`。
  - 状态变更时间 `changed_at` 必须晚于账户开户时间。
  - 人工变更账户状态时 `operator_id` 必须不为空。
  - 由风控冻结、司法冻结、交易异常或销户触发的状态变更必须填写 `related_type` 和 `related_id`。
  - 账户状态变更必须写入历史记录。
  - 状态历史不得物理删除。

#### `bank_card`
银行卡表，维护客户银行卡和绑定账户。

- `id`：主键 ID。
- `card_no`：银行卡号，业务唯一标识。
- `customer_id`：客户 ID，关联 `customer.id`。
- `account_id`：绑定账户 ID，关联 `bank_account.id`。
- `card_type`：卡类型。枚举值：
  - `debit`：借记卡
  - `virtual`：虚拟卡
- `card_level`：卡等级。枚举值：
  - `standard`：标准卡
  - `gold`：金卡
  - `platinum`：白金卡
  - `diamond`：钻石卡
- `card_status`：卡状态。枚举值：
  - `active`：正常
  - `frozen`：冻结
  - `lost`：挂失
  - `expired`：过期
  - `cancelled`：注销
- `issued_at`：发卡时间。
- `expired_at`：卡片到期时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_bank_card_no (card_no)`
- 外键约束：
  - `fk_bank_card_customer (customer_id -> customer.id)`
  - `fk_bank_card_account (account_id -> bank_account.id)`
- 业务约束：
  - 卡片客户必须与绑定账户客户一致。
  - 已挂失、冻结、过期或注销的卡不能发起新交易。
  - `expired_at` 必须晚于 `issued_at`。
  - 虚拟卡必须绑定有效银行账户。
  - `card_status = active` 时绑定账户必须为正常状态。
  - `card_status = expired` 时当前日期必须晚于或等于 `expired_at`。
  - `card_status = cancelled` 后不得恢复为正常状态。
  - 同一银行卡号不得重复发卡。
  - `updated_at >= created_at`

#### `account_transaction`
账户交易表，维护客户资金交易主记录。

- `id`：主键 ID。
- `transaction_no`：交易编号，业务唯一标识。
- `customer_id`：客户 ID，关联 `customer.id`。
- `from_account_id`：付款账户 ID，关联 `bank_account.id`。
- `to_account_id`：收款账户 ID，关联 `bank_account.id`。
- `card_id`：交易银行卡 ID，关联 `bank_card.id`。
- `channel_id`：渠道 ID，关联 `dim_channel.id`。
- `original_transaction_id`：原交易 ID，退款、冲正和撤销交易使用，关联 `account_transaction.id`。
- `biz_order_no`：业务订单号。
- `external_order_no`：外部订单号。
- `merchant_no`：商户号。
- `merchant_name`：商户名称。
- `counterparty_name`：交易对手名称。
- `counterparty_account_no`：交易对手账户号。
- `counterparty_bank_name`：交易对手开户行。
- `transaction_type`：交易类型。枚举值：
  - `transfer`：转账
  - `consume`：消费
  - `deposit`：入金
  - `withdraw`：出金
  - `loan_disbursement`：贷款放款
  - `loan_repayment`：贷款还款
  - `wealth_purchase`：理财申购
  - `wealth_redeem`：理财赎回
  - `wealth_income`：理财收益入账
  - `refund`：退款
  - `cancel`：撤销
  - `reversal`：冲正
  - `adjustment`：调账
- `transaction_status`：交易状态。枚举值：
  - `created`：已创建
  - `processing`：处理中
  - `success`：成功
  - `failed`：失败
  - `reversed`：已冲正
- `reconcile_status`：对账状态。枚举值：
  - `not_required`：无需对账
  - `pending`：待对账
  - `matched`：已匹配
  - `mismatched`：差错
  - `adjusted`：已调账
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `transaction_amount`：交易金额。
- `fee_amount`：手续费金额。
- `related_type`：关联对象类型。枚举值：
  - `none`：无
  - `loan_contract`：贷款合同
  - `repayment_bill`：还款账单
  - `wealth_order`：理财订单
  - `wealth_income`：理财收益
  - `risk_event`：风控事件
- `related_id`：关联对象 ID。
- `transaction_at`：交易时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_account_transaction_no (transaction_no)`
  - `uk_account_transaction_external_order (channel_id, external_order_no)`，仅限制 `external_order_no` 非空的外部订单。
- 外键约束：
  - `fk_account_transaction_customer (customer_id -> customer.id)`
  - `fk_account_transaction_from_account (from_account_id -> bank_account.id)`
  - `fk_account_transaction_to_account (to_account_id -> bank_account.id)`
  - `fk_account_transaction_card (card_id -> bank_card.id)`
  - `fk_account_transaction_channel (channel_id -> dim_channel.id)`
  - `fk_account_transaction_original (original_transaction_id -> account_transaction.id)`
  - `fk_account_transaction_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - `transaction_amount > 0`
  - `fee_amount >= 0`
  - 支出类交易必须有 `from_account_id`。
  - 入账类交易必须有 `to_account_id`。
  - 退款、撤销和冲正交易必须关联 `original_transaction_id`。
  - `transaction_type IN ('transfer', 'consume', 'withdraw', 'loan_repayment', 'wealth_purchase')` 时必须填写 `from_account_id`。
  - `transaction_type IN ('transfer', 'deposit', 'loan_disbursement', 'wealth_redeem', 'wealth_income', 'refund')` 时必须填写 `to_account_id`。
  - `transaction_type IN ('cancel', 'reversal')` 时账户方向必须与原交易相反，金额不得超过原交易可撤销或可冲正余额。
  - `transaction_type = adjustment` 时必须至少填写付款账户或收款账户之一，并通过调账审批记录入账。
  - 成功支出类交易必须生成付款账户借记流水，成功入账类交易必须生成收款账户贷记流水，转账类交易必须同时生成借记和贷记流水。
  - 手续费大于 `0` 时必须在付款账户或客户承担账户生成额外借记流水。
  - 同一外部渠道下 `external_order_no` 不得重复。
  - `from_account_id` 和 `to_account_id` 同时存在时不得相同，调整类交易除外。
  - 付款账户和收款账户币种必须与 `currency_code` 一致。
  - 交易客户必须与付款账户或收款账户客户一致。
  - 支出类交易成功前付款账户可用余额必须大于等于 `transaction_amount + fee_amount`。
  - 手续费按客户账户侧扣减并体现在 `fee_amount`，银行手续费收入不单独建账时必须在统计口径中排除内部收入账户校验。
  - 涉及清算机构或合作渠道的交易必须通过渠道流水和对账结果完成客户账户侧闭环。
  - 冻结、限制、销户账户不得作为普通支出账户。
  - 交易成功后必须同步生成借贷方向匹配的账户流水。
  - 交易失败不得改变账户余额和冻结金额。
  - 冲正交易金额必须等于原交易可冲正余额。
  - 退款交易金额不得超过原交易可退款金额。
  - `transaction_status IN ('failed', 'reversed')` 时不得再次进入成功状态。
  - `transaction_at` 不得早于账户开户时间。
  - `transaction_status = success` 时必须生成账户流水。
  - `updated_at >= created_at`

#### `channel_transaction`
渠道流水表，维护外部渠道订单、请求响应、回调和对账状态。
- `id`：主键 ID。
- `channel_txn_no`：渠道流水编号，业务唯一标识。
- `channel_id`：渠道 ID，关联 `dim_channel.id`。
- `transaction_id`：账户交易 ID，关联 `account_transaction.id`，渠道单边流水可为空。
- `channel_order_no`：渠道订单号。
- `channel_trade_no`：渠道交易号。
- `request_no`：请求流水号。
- `request_type`：请求类型。枚举值：
  - `payment`：支付
  - `transfer`：转账
  - `refund`：退款
  - `reversal`：冲正
  - `query`：查询
  - `callback`：回调
- `request_status`：请求状态。枚举值：
  - `created`：已创建
  - `sent`：已发送
  - `accepted`：已受理
  - `success`：成功
  - `failed`：失败
  - `timeout`：超时
- `callback_status`：回调状态。枚举值：
  - `none`：无需回调
  - `pending`：待回调
  - `received`：已收到
  - `verified`：已验签
  - `invalid`：验签失败
- `reconcile_status`：对账状态。枚举值：
  - `pending`：待对账
  - `matched`：已匹配
  - `mismatched`：差错
  - `adjusted`：已调账
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `channel_amount`：渠道金额。
- `channel_fee_amount`：渠道手续费金额。
- `error_code`：渠道错误码。
- `error_message`：渠道错误信息。
- `requested_at`：请求时间。
- `responded_at`：响应时间。
- `callback_at`：回调时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_channel_transaction_no (channel_txn_no)`
  - `uk_channel_transaction_request (channel_id, request_no)`
  - `uk_channel_transaction_order (channel_id, channel_order_no)`，仅限制 `channel_order_no` 非空的渠道订单。
  - `uk_channel_transaction_trade (channel_id, channel_trade_no)`，仅限制 `channel_trade_no` 非空的渠道交易。
- 外键约束：
  - `fk_channel_transaction_channel (channel_id -> dim_channel.id)`
  - `fk_channel_transaction_account_transaction (transaction_id -> account_transaction.id)`
  - `fk_channel_transaction_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - `channel_amount > 0`
  - `channel_fee_amount >= 0`
  - `request_status = success` 时 `responded_at` 必须不为空。
  - `callback_status IN ('received', 'verified', 'invalid')` 时 `callback_at` 必须不为空。
  - 对账差错必须保留渠道金额和渠道订单号，非渠道单边差错必须保留账户交易关联。
  - `transaction_id` 不为空时，渠道流水金额必须与关联账户交易金额一致，手续费差异需进入对账差错。
  - 同一渠道订单只能关联一笔最终成功账户交易。
  - 请求超时后允许补查，但不得重复入账。
  - `callback_status = verified` 后才能更新关联交易为成功。
  - `reconcile_status = matched` 时渠道金额、渠道订单号和交易状态必须匹配。
  - `reconcile_status = adjusted` 时必须存在调账交易，或在对账结果中保留处理状态和处理说明。
  - 响应时间 `responded_at` 不得早于请求时间 `requested_at`。
  - 回调时间 `callback_at` 不得早于请求时间 `requested_at`。
  - `updated_at >= created_at`

#### `reconciliation_batch`
对账批次表，维护渠道对账文件、批次状态和对账范围。
- `id`：主键 ID。
- `batch_no`：对账批次号，业务唯一标识。
- `channel_id`：渠道 ID，关联 `dim_channel.id`。
- `reconcile_date`：对账日期。
- `file_name`：对账文件名称。
- `file_hash`：对账文件哈希。
- `batch_status`：批次状态。枚举值：
  - `created`：已创建
  - `processing`：处理中
  - `completed`：已完成
  - `failed`：失败
  - `cancelled`：已取消
- `started_at`：开始时间。
- `completed_at`：完成时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_reconciliation_batch_no (batch_no)`
  - `uk_reconciliation_batch_active_channel_date (channel_id, active_reconcile_date_key)`，仅限制 `batch_status IN ('created', 'processing', 'completed')` 的有效对账批次。
- 外键约束：
  - `fk_reconciliation_batch_channel (channel_id -> dim_channel.id)`
- 业务约束：
  - 同一渠道同一对账日期只能有一个有效对账批次。
  - `batch_status = completed` 时 `completed_at` 必须不为空。
  - `completed_at` 不为空时必须晚于或等于 `started_at`。
  - 已完成批次不得物理删除。
  - `updated_at >= created_at`

#### `reconciliation_result`
对账结果表，维护交易与渠道流水的匹配、差错和处理状态。
- `id`：主键 ID。
- `result_no`：对账结果编号，业务唯一标识。
- `batch_id`：对账批次 ID，关联 `reconciliation_batch.id`。
- `transaction_id`：账户交易 ID，关联 `account_transaction.id`。
- `channel_transaction_id`：渠道流水 ID，关联 `channel_transaction.id`。
- `result_type`：结果类型。枚举值：
  - `matched`：匹配
  - `amount_mismatch`：金额不一致
  - `status_mismatch`：状态不一致
  - `channel_only`：渠道单边
  - `bank_only`：银行单边
- `difference_amount`：差异金额。
- `process_status`：处理状态。枚举值：
  - `pending`：待处理
  - `processing`：处理中
  - `adjusted`：已调账
  - `ignored`：已忽略
  - `closed`：已关闭
- `process_comment`：处理说明。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_reconciliation_result_no (result_no)`
  - `uk_reconciliation_result_bank_only (batch_id, transaction_id)`，限制同一对账批次内同一银行侧交易只能出现一次。
  - `uk_reconciliation_result_channel_only (batch_id, channel_transaction_id)`，限制同一对账批次内同一渠道侧流水只能出现一次。
- 外键约束：
  - `fk_reconciliation_result_batch (batch_id -> reconciliation_batch.id)`
  - `fk_reconciliation_result_transaction (transaction_id -> account_transaction.id)`
  - `fk_reconciliation_result_channel_transaction (channel_transaction_id -> channel_transaction.id)`
- 业务约束：
  - `difference_amount >= 0`
  - 匹配结果的差异金额必须为 `0`。
  - 差错结果关闭前必须完成调账、忽略或人工处理。
  - 单边结果允许账户交易或渠道流水其中一方为空，但不得同时为空。
  - `result_type = bank_only` 时 `transaction_id` 必须不为空且 `channel_transaction_id` 必须为空。
  - `result_type = channel_only` 时 `channel_transaction_id` 必须不为空且 `transaction_id` 必须为空。
  - `result_type IN ('matched', 'amount_mismatch', 'status_mismatch')` 时 `transaction_id` 和 `channel_transaction_id` 必须同时不为空。
  - 对账结果不得物理删除。

#### `reconciliation_adjustment`
对账调账表，维护差错调账交易、调账金额和审批状态。
- `id`：主键 ID。
- `adjustment_no`：调账编号，业务唯一标识。
- `result_id`：对账结果 ID，关联 `reconciliation_result.id`。
- `transaction_id`：调账交易 ID，关联 `account_transaction.id`。
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `adjustment_amount`：调账金额。
- `adjustment_direction`：调账方向。枚举值：
  - `debit`：调减
  - `credit`：调增
- `adjustment_status`：调账状态。枚举值：
  - `submitted`：已提交
  - `approved`：已通过
  - `rejected`：已拒绝
  - `posted`：已入账
  - `cancelled`：已取消
- `approved_by`：审批员工 ID，关联 `dim_employee.id`。
- `approved_at`：审批时间。
- `posted_at`：入账时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_reconciliation_adjustment_no (adjustment_no)`
- 外键约束：
  - `fk_reconciliation_adjustment_result (result_id -> reconciliation_result.id)`
  - `fk_reconciliation_adjustment_transaction (transaction_id -> account_transaction.id)`
  - `fk_reconciliation_adjustment_currency (currency_code -> dim_currency.currency_code)`
  - `fk_reconciliation_adjustment_approver (approved_by -> dim_employee.id)`
- 业务约束：
  - `adjustment_amount > 0`
  - `adjustment_status IN ('approved', 'rejected')` 时 `approved_at` 必须不为空。
  - `adjustment_status = posted` 时 `posted_at` 和 `transaction_id` 必须不为空。
  - 调账入账后必须更新对应对账结果处理状态。
  - `updated_at >= created_at`

#### `account_ledger`
账户流水表，维护账户余额变动和交易后余额。

- `id`：主键 ID。
- `ledger_no`：流水编号，业务唯一标识。
- `account_id`：账户 ID，关联 `bank_account.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `transaction_id`：交易 ID，关联 `account_transaction.id`。
- `freeze_id`：资金冻结 ID，关联 `fund_freeze.id`。
- `freeze_operation_id`：冻结操作 ID，关联 `fund_freeze_operation.id`。
- `ledger_type`：流水类型。枚举值：
  - `debit`：借记
  - `credit`：贷记
  - `freeze`：冻结
  - `unfreeze`：解冻
  - `adjust`：调整
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `amount_delta`：余额变动金额。
- `frozen_delta`：冻结金额变动。
- `balance_after`：交易后账户余额。
- `frozen_after`：交易后冻结金额。
- `available_after`：交易后可用余额。
- `created_at`：创建时间。

- 唯一性约束：
  - `uk_account_ledger_no (ledger_no)`
- 外键约束：
  - `fk_account_ledger_account (account_id -> bank_account.id)`
  - `fk_account_ledger_customer (customer_id -> customer.id)`
  - `fk_account_ledger_transaction (transaction_id -> account_transaction.id)`
  - `fk_account_ledger_freeze (freeze_id -> fund_freeze.id)`
  - `fk_account_ledger_freeze_operation (freeze_operation_id -> fund_freeze_operation.id)`
  - `fk_account_ledger_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - `available_after = balance_after - frozen_after`
  - `balance_after >= 0`
  - `frozen_after >= 0`
  - `available_after >= 0`
  - 流水客户必须与账户客户一致。
  - 流水币种必须与账户币种一致。
  - `ledger_type IN ('debit', 'credit', 'adjust')` 时必须关联账户交易。
  - `ledger_type IN ('freeze', 'unfreeze')` 时必须关联资金冻结和冻结操作。
  - `ledger_type = debit` 时 `amount_delta < 0` 且 `frozen_delta = 0`。
  - `ledger_type = credit` 时 `amount_delta > 0` 且 `frozen_delta = 0`。
  - `ledger_type = freeze` 时 `amount_delta = 0` 且 `frozen_delta > 0`。
  - `ledger_type = unfreeze` 时 `amount_delta = 0` 且 `frozen_delta < 0`。
  - `ledger_type = adjust` 时 `amount_delta` 或 `frozen_delta` 至少一个不为 `0`。
  - 冻结流水的账户、客户、币种和冻结变动金额必须与冻结操作一致。
  - 成功转账交易必须至少生成付款账户借记流水和收款账户贷记流水。
  - 成功冻结操作必须生成冻结流水，成功解冻、释放或取消操作必须生成解冻流水。
  - 同一账户流水必须按创建时间和流水号形成可追溯顺序。
  - 任一账户最新流水的余额、冻结金额和可用余额必须等于账户当前余额、冻结金额和可用余额。
  - 同一账户任一时点的 `frozen_after` 必须等于该账户所有未完全释放且未取消冻结记录的 `freeze_amount - released_amount` 合计。
  - 同一交易对同一账户可产生多条流水，但流水号必须唯一。
  - 流水不得物理删除。

#### `fund_freeze`
资金冻结表，维护账户资金冻结、解冻和释放记录。

- `id`：主键 ID。
- `freeze_no`：冻结编号，业务唯一标识。
- `account_id`：账户 ID，关联 `bank_account.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `freeze_type`：冻结类型。枚举值：
  - `transaction`：交易冻结
  - `wealth_purchase`：理财申购冻结
  - `loan_repayment`：贷款还款冻结
  - `risk_control`：风控冻结
  - `judicial`：司法冻结
- `related_type`：关联对象类型。枚举值：
  - `none`：无
  - `account_transaction`：账户交易
  - `wealth_order`：理财订单
  - `loan_contract`：贷款合同
  - `repayment_bill`：还款账单
  - `risk_event`：风控事件
- `related_id`：关联对象 ID。
- `judicial_instruction_no`：司法指令编号。
- `currency_code`：冻结币种，关联 `dim_currency.currency_code`。
- `freeze_amount`：冻结金额。
- `released_amount`：已释放金额。
- `freeze_status`：冻结状态。枚举值：
  - `frozen`：冻结中
  - `partial_released`：部分释放
  - `released`：已释放
  - `cancelled`：已取消
- `frozen_at`：冻结时间。
- `released_at`：全部释放时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_fund_freeze_no (freeze_no)`
- 外键约束：
  - `fk_fund_freeze_account (account_id -> bank_account.id)`
  - `fk_fund_freeze_customer (customer_id -> customer.id)`
  - `fk_fund_freeze_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - `freeze_amount > 0`
  - `released_amount >= 0`
  - `released_amount <= freeze_amount`
  - `freeze_status = released` 时 `released_amount = freeze_amount`。
  - `freeze_status = frozen` 时 `released_amount = 0`。
  - `freeze_status = partial_released` 时 `released_amount > 0 AND released_amount < freeze_amount`。
  - `freeze_status = cancelled` 时 `released_amount = freeze_amount`，账户冻结余额中不得再包含该冻结记录。
  - `freeze_status = cancelled` 时不得再发生释放或解冻操作。
  - 冻结账户必须与冻结客户一致。
  - 冻结币种必须与账户币种一致。
  - 冻结金额不得超过账户可用余额。
  - 同一账户新增冻结后，所有冻结中和部分释放冻结记录的未释放金额合计不得超过账户余额。
  - 同一账户所有未完全释放且未取消冻结记录的未释放金额合计必须等于账户当前 `frozen_amount`。
  - `frozen_at` 不得早于账户开户时间。
  - `released_at` 不为空时必须晚于或等于 `frozen_at`。
  - 风控冻结必须填写 `related_type = risk_event` 和 `related_id`。
  - 司法冻结必须填写 `judicial_instruction_no`，且 `related_type = none`、`related_id` 为空。
  - 每次冻结状态和金额变化必须写入 `fund_freeze_operation`。
  - `updated_at >= created_at`

#### `fund_freeze_operation`
资金冻结操作明细表，维护每次冻结、解冻、释放和取消操作。
- `id`：主键 ID。
- `operation_no`：操作编号，业务唯一标识。
- `freeze_id`：冻结记录 ID，关联 `fund_freeze.id`。
- `account_id`：账户 ID，关联 `bank_account.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `transaction_id`：账户交易 ID，关联 `account_transaction.id`。
- `related_type`：关联对象类型。枚举值：
  - `none`：无
  - `fund_freeze`：资金冻结
  - `account_transaction`：账户交易
  - `risk_event`：风控事件
- `related_id`：关联对象 ID。
- `judicial_instruction_no`：司法指令编号。
- `operation_type`：操作类型。枚举值：
  - `freeze`：冻结
  - `unfreeze`：解冻
  - `release`：释放
  - `cancel`：取消
  - `adjust`：调整
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `operation_amount`：操作金额。
- `before_frozen_amount`：操作前冻结金额。
- `after_frozen_amount`：操作后冻结金额。
- `operation_source`：操作来源。枚举值：
  - `transaction`：交易系统
  - `wealth`：理财系统
  - `loan`：信贷系统
  - `risk`：风控系统
  - `judicial`：司法指令
  - `manual`：人工处理
- `operator_id`：操作员工 ID，关联 `dim_employee.id`。
- `operation_reason`：操作原因。
- `operated_at`：操作时间。
- `created_at`：创建时间。

- 唯一性约束：
  - `uk_fund_freeze_operation_no (operation_no)`
- 外键约束：
  - `fk_fund_freeze_operation_freeze (freeze_id -> fund_freeze.id)`
  - `fk_fund_freeze_operation_account (account_id -> bank_account.id)`
  - `fk_fund_freeze_operation_customer (customer_id -> customer.id)`
  - `fk_fund_freeze_operation_transaction (transaction_id -> account_transaction.id)`
  - `fk_fund_freeze_operation_currency (currency_code -> dim_currency.currency_code)`
  - `fk_fund_freeze_operation_operator (operator_id -> dim_employee.id)`
- 业务约束：
  - `operation_amount > 0`
  - `before_frozen_amount >= 0`
  - `after_frozen_amount >= 0`
  - 操作客户必须与冻结记录客户一致。
  - 操作账户必须与冻结记录账户一致。
  - 操作币种必须与账户币种一致。
  - `operation_type = freeze` 时 `after_frozen_amount = before_frozen_amount + operation_amount`。
  - `operation_type IN ('unfreeze', 'release')` 时 `after_frozen_amount = before_frozen_amount - operation_amount`。
  - `operation_type IN ('unfreeze', 'release')` 时 `operation_amount` 不得大于 `before_frozen_amount`。
  - `operation_type = cancel` 时 `after_frozen_amount = 0` 且 `operation_amount = before_frozen_amount`。
  - `operation_type = adjust` 时 `after_frozen_amount` 必须等于调整后的有效冻结余额，并保留人工操作原因。
  - 司法来源操作必须填写 `judicial_instruction_no`，且 `related_type = none` 或 `fund_freeze`。
  - 人工操作必须填写 `operator_id` 和 `operation_reason`。
  - 最后一条操作后的冻结金额必须与 `fund_freeze.freeze_amount - fund_freeze.released_amount` 一致。
  - 同一 `freeze_id` 下操作时间必须按冻结生命周期顺序递增。
  - 操作明细不得物理删除。

### 理财域
本域用于维护理财产品、净值、风险适当性、申购赎回、份额持仓和收益记录。

表说明：

- `wealth_product`：理财产品表，维护产品代码、产品类型、风险等级、开放规则和产品状态。
- `wealth_open_period`：理财开放期表，维护开放式和定期开放产品的申购赎回窗口。
- `wealth_trade_calendar`：理财交易日历表，维护交易日、确认日和到账日规则。
- `wealth_settlement_rule`：理财清算规则表，维护申购确认、赎回确认和到账周期。
- `wealth_nav`：理财产品净值表，维护产品每日单位净值和累计净值。
- `wealth_order`：理财订单表，维护申购、赎回、撤单和确认状态。
- `wealth_position`：理财持仓表，维护客户持有份额、成本、市值和累计收益。
- `wealth_income`：理财收益表，维护每日收益、分红和收益入账记录。
- `wealth_product_notice`：理财产品公告表，维护产品说明、开放期、分红和风险提示公告。

依赖关系说明：

- `wealth_product` 依赖 `dim_product_category`、`dim_currency` 和 `dim_risk_level`。
- `wealth_open_period`、`wealth_trade_calendar`、`wealth_settlement_rule`、`wealth_nav`、`wealth_order`、`wealth_position`、`wealth_income` 和 `wealth_product_notice` 依赖 `wealth_product`。
- `wealth_order` 依赖 `customer`、`bank_account`、`dim_channel` 和 `customer_risk_assessment`。
- `wealth_position` 依赖 `customer`、`bank_account` 和 `wealth_product`。
- 理财申购确认后更新 `wealth_position`，并生成账户交易和账户流水。

#### `wealth_product`
理财产品表，定义理财产品基础信息、风险等级、开放规则和产品状态。

- `id`：主键 ID。
- `product_code`：产品编码，业务唯一标识。
- `product_name`：产品名称。
- `category_id`：产品分类 ID，关联 `dim_product_category.id`。
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `risk_level_id`：产品风险等级 ID，关联 `dim_risk_level.id`。
- `product_type`：产品类型。枚举值：
  - `cash_management`：现金管理类
  - `fixed_income`：固定收益类
  - `mixed`：混合类
  - `equity`：权益类
  - `structured_deposit`：结构性存款
- `operation_mode`：运作模式。枚举值：
  - `open`：开放式
  - `closed`：封闭式
  - `periodic_open`：定期开放
- `min_purchase_amount`：起购金额。
- `increment_amount`：递增金额。
- `expected_yield_rate`：业绩比较基准或预期收益率。
- `nav_based_flag`：是否净值型，`1` 表示是，`0` 表示否。
- `sale_start_at`：销售开始时间。
- `sale_end_at`：销售结束时间。
- `value_date_rule`：起息规则。
- `redeem_rule`：赎回规则。
- `product_status`：产品状态。枚举值：
  - `draft`：草稿
  - `selling`：销售中
  - `running`：运作中
  - `paused`：暂停
  - `matured`：已到期
  - `terminated`：已终止
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_wealth_product_code (product_code)`
- 外键约束：
  - `fk_wealth_product_category (category_id -> dim_product_category.id)`
  - `fk_wealth_product_currency (currency_code -> dim_currency.currency_code)`
  - `fk_wealth_product_risk_level (risk_level_id -> dim_risk_level.id)`
- 业务约束：
  - `min_purchase_amount > 0`
  - `increment_amount > 0`
  - `sale_end_at` 必须晚于 `sale_start_at`。
  - 产品分类必须为 `category_type = wealth`。
  - 产品币种必须为启用币种。
  - 产品风险等级必须引用 `risk_level_type = product` 的风险等级。
  - `expected_yield_rate` 不为空时不得小于 `0`。
  - `nav_based_flag = 1` 的产品必须维护净值记录。
  - `operation_mode = closed` 的产品在运行期不得新增赎回订单，产品规则允许提前赎回除外。
  - `product_status = selling` 时当前时间必须位于销售开始和销售结束时间之间。
  - `product_status IN ('matured', 'terminated')` 时不得新增申购和赎回订单。
  - 递增金额校验规则为申购金额减起购金额后必须是 `increment_amount` 的整数倍。
  - 产品销售中才能新增申购订单。
  - `updated_at >= created_at`

#### `wealth_open_period`
理财开放期表，维护开放式和定期开放产品的申购赎回窗口。
- `id`：主键 ID。
- `product_id`：产品 ID，关联 `wealth_product.id`。
- `period_no`：开放期编号。
- `purchase_start_at`：申购开始时间。
- `purchase_end_at`：申购结束时间。
- `redeem_start_at`：赎回开始时间。
- `redeem_end_at`：赎回结束时间。
- `period_status`：开放期状态。枚举值：
  - `planned`：计划中
  - `open`：开放中
  - `closed`：已关闭
  - `cancelled`：已取消
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_wealth_open_period (product_id, period_no)`
- 外键约束：
  - `fk_wealth_open_period_product (product_id -> wealth_product.id)`
- 业务约束：
  - 申购结束时间必须晚于申购开始时间。
  - 赎回结束时间必须晚于赎回开始时间。
  - 同一产品开放期时间不得重叠。
  - 定期开放产品申购和赎回必须落在有效开放期内。
  - `updated_at >= created_at`

#### `wealth_trade_calendar`
理财交易日历表，维护交易日、确认日和到账日规则。
- `id`：主键 ID。
- `product_id`：产品 ID，关联 `wealth_product.id`。
- `calendar_date`：日历日期。
- `trade_flag`：是否交易日，`1` 表示是，`0` 表示否。
- `purchase_confirm_date`：申购确认日期。
- `redeem_confirm_date`：赎回确认日期。
- `redeem_arrival_date`：赎回到账日期。
- `created_at`：创建时间。

- 唯一性约束：
  - `uk_wealth_trade_calendar (product_id, calendar_date)`
- 外键约束：
  - `fk_wealth_trade_calendar_product (product_id -> wealth_product.id)`
- 业务约束：
  - 交易日才能提交申购和赎回订单。
  - 申购确认日期、赎回确认日期和赎回到账日期不得早于日历日期。
  - 非交易日应指向下一个可用确认日或到账日。

#### `wealth_settlement_rule`
理财清算规则表，维护申购确认、赎回确认和到账周期。
- `id`：主键 ID。
- `product_id`：产品 ID，关联 `wealth_product.id`。
- `purchase_confirm_days`：申购确认天数。
- `redeem_confirm_days`：赎回确认天数。
- `redeem_arrival_days`：赎回到账天数。
- `cutoff_time`：交易截止时间。
- `rule_status`：规则状态。枚举值：
  - `active`：启用
  - `inactive`：停用
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_wealth_settlement_rule_product (product_id)`
- 外键约束：
  - `fk_wealth_settlement_rule_product (product_id -> wealth_product.id)`
- 业务约束：
  - 确认天数和到账天数必须大于等于 `0`。
  - 赎回到账天数必须大于或等于赎回确认天数。
  - 启用理财产品必须存在启用清算规则。
  - `updated_at >= created_at`

#### `wealth_nav`
理财产品净值表，维护理财产品每日净值。

- `id`：主键 ID。
- `product_id`：产品 ID，关联 `wealth_product.id`。
- `nav_date`：净值日期。
- `unit_nav`：单位净值。
- `accumulated_nav`：累计净值。
- `daily_yield_rate`：日收益率。
- `annualized_yield_rate`：七日年化或年化收益率。
- `created_at`：创建时间。

- 唯一性约束：
  - `uk_wealth_nav_product_date (product_id, nav_date)`
- 外键约束：
  - `fk_wealth_nav_product (product_id -> wealth_product.id)`
- 业务约束：
  - `unit_nav > 0`
  - `accumulated_nav >= unit_nav`
  - 净值日期不得晚于当前日期。
  - 同一产品净值日期不得早于产品销售开始日期。
  - 净值型产品确认申购、赎回和估值必须使用有效净值。
  - `daily_yield_rate` 可以为负，但必须与相邻净值变化保持一致。
  - 非净值型产品可不维护每日单位净值，但收益计算必须保留年化收益率。
  - 同一产品同一净值日期只能有一条净值记录。

#### `wealth_order`
理财订单表，维护申购、赎回、撤单和确认状态。

- `id`：主键 ID。
- `order_no`：订单编号，业务唯一标识。
- `customer_id`：客户 ID，关联 `customer.id`。
- `account_id`：结算账户 ID，关联 `bank_account.id`。
- `product_id`：产品 ID，关联 `wealth_product.id`。
- `channel_id`：渠道 ID，关联 `dim_channel.id`。
- `risk_assessment_id`：客户风险测评 ID，关联 `customer_risk_assessment.id`。
- `original_order_id`：原订单 ID，撤单使用，关联 `wealth_order.id`。
- `transaction_id`：账户交易 ID，关联 `account_transaction.id`。
- `freeze_id`：资金冻结 ID，关联 `fund_freeze.id`。
- `position_id`：理财持仓 ID，关联 `wealth_position.id`。
- `order_type`：订单类型。枚举值：
  - `purchase`：申购
  - `redeem`：赎回
  - `cancel`：撤单
- `order_status`：订单状态。枚举值：
  - `created`：已创建
  - `risk_checked`：已适当性校验
  - `frozen`：已冻结资金
  - `submitted`：已提交
  - `confirmed`：已确认
  - `failed`：失败
  - `cancelled`：已撤销
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `order_amount`：订单金额。
- `order_share`：订单份额。
- `confirmed_amount`：确认金额。
- `confirmed_share`：确认份额。
- `confirmed_nav`：确认净值。
- `fee_amount`：手续费金额。
- `cancel_reason`：撤单原因。
- `submitted_at`：提交时间。
- `confirmed_at`：确认时间。
- `cancelled_at`：撤单时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_wealth_order_no (order_no)`
  - `uk_wealth_order_transaction (transaction_id)`，仅限制 `transaction_id` 非空的确认订单。
- 外键约束：
  - `fk_wealth_order_customer (customer_id -> customer.id)`
  - `fk_wealth_order_account (account_id -> bank_account.id)`
  - `fk_wealth_order_product (product_id -> wealth_product.id)`
  - `fk_wealth_order_channel (channel_id -> dim_channel.id)`
  - `fk_wealth_order_risk_assessment (risk_assessment_id -> customer_risk_assessment.id)`
  - `fk_wealth_order_original (original_order_id -> wealth_order.id)`
  - `fk_wealth_order_transaction (transaction_id -> account_transaction.id)`
  - `fk_wealth_order_freeze (freeze_id -> fund_freeze.id)`
  - `fk_wealth_order_position (position_id -> wealth_position.id)`
  - `fk_wealth_order_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - 申购订单 `order_amount > 0`。
  - 赎回订单 `order_share > 0`。
  - 客户风险等级必须覆盖产品风险等级。
  - `order_status = confirmed` 时 `confirmed_at` 必须不为空。
  - 订单客户必须与结算账户客户一致。
  - 订单币种必须与产品币种和结算账户币种一致。
  - 申购订单金额必须满足起购金额和递增金额规则。
  - 申购订单提交前必须完成客户实名、KYC 和有效风险测评。
  - 申购订单冻结资金前账户可用余额必须大于等于订单金额和手续费。
  - 赎回订单份额不得超过持仓可用份额。
  - 赎回订单提交后必须冻结对应持仓份额，更新 `wealth_position.available_share` 和 `frozen_share`。
  - 赎回订单失败或撤单时必须释放已冻结份额，恢复持仓可用份额。
  - 赎回订单确认成功时必须扣减持仓 `holding_share` 和 `frozen_share`，并更新成本、市值和清仓状态。
  - 撤单订单必须关联可撤销的原申购或赎回订单。
  - `order_type = cancel` 时 `original_order_id`、`cancel_reason` 和 `cancelled_at` 必须不为空。
  - `order_status = frozen` 时必须存在资金冻结记录。
  - 申购冻结资金时必须填写 `freeze_id`。
  - 已冻结申购订单失败或撤单时必须释放或取消对应资金冻结，并生成冻结操作和账户流水。
  - 申购订单确认成功时必须释放对应申购冻结，并生成冻结释放操作和账户流水。
  - `order_type = purchase AND order_status = confirmed` 时必须填写 `transaction_id`、`freeze_id` 和 `position_id`。
  - `order_type = redeem AND order_status = confirmed` 时必须填写 `transaction_id` 和 `position_id`。
  - 申购确认交易的 `transaction_type` 必须为 `wealth_purchase`，赎回确认交易的 `transaction_type` 必须为 `wealth_redeem`。
  - 确认交易的客户、账户、币种、金额和关联对象必须与理财订单一致。
  - 确认成功的申购和赎回订单必须生成账户交易和账户流水。
  - `order_status IN ('failed', 'cancelled')` 时不得确认份额和确认金额。
  - `confirmed_amount >= 0`
  - `confirmed_share >= 0`
  - `updated_at >= created_at`

#### `wealth_position`
理财持仓表，维护客户理财份额、成本、市值和收益。

- `id`：主键 ID。
- `customer_id`：客户 ID，关联 `customer.id`。
- `account_id`：结算账户 ID，关联 `bank_account.id`。
- `product_id`：产品 ID，关联 `wealth_product.id`。
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `holding_share`：持有份额。
- `available_share`：可赎回份额。
- `frozen_share`：冻结份额。
- `cost_amount`：持仓成本金额。
- `market_value_amount`：持仓市值金额。
- `accumulated_income_amount`：累计收益金额。
- `last_nav`：最近净值。
- `last_valuation_date`：最近估值日期。
- `position_status`：持仓状态。枚举值：
  - `active`：持有中
  - `closed`：已清仓
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_wealth_position_active (customer_id, account_id, product_id)`，仅限制 `position_status = active` 的有效持仓。
- 外键约束：
  - `fk_wealth_position_customer (customer_id -> customer.id)`
  - `fk_wealth_position_account (account_id -> bank_account.id)`
  - `fk_wealth_position_product (product_id -> wealth_product.id)`
  - `fk_wealth_position_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - `holding_share >= 0`
  - `available_share >= 0`
  - `frozen_share >= 0`
  - `holding_share = available_share + frozen_share`
  - `position_status = closed` 时 `holding_share` 必须为 `0`。
  - 持仓客户必须与结算账户客户一致。
  - 持仓币种必须与产品币种一致。
  - `cost_amount >= 0`
  - `market_value_amount >= 0`
  - `last_nav > 0`
  - 持仓市值必须等于持有份额乘最近净值，允许按币种精度四舍五入。
  - 赎回冻结份额不得超过可用份额。
  - 同一持仓的待确认赎回订单冻结份额合计必须等于 `frozen_share`。
  - 赎回确认后的持仓份额、成本和市值必须与赎回订单一致。
  - 持仓清仓后不得新增收益，后续再次申购应重新激活或新建持仓记录。
  - `updated_at >= created_at`

#### `wealth_income`
理财收益表，维护每日收益、分红和收益入账记录。

- `id`：主键 ID。
- `income_no`：收益编号，业务唯一标识。
- `customer_id`：客户 ID，关联 `customer.id`。
- `account_id`：入账账户 ID，关联 `bank_account.id`。
- `position_id`：持仓 ID，关联 `wealth_position.id`。
- `product_id`：产品 ID，关联 `wealth_product.id`。
- `transaction_id`：入账交易 ID，关联 `account_transaction.id`。
- `ledger_id`：入账流水 ID，关联 `account_ledger.id`。
- `income_date`：收益日期。
- `income_type`：收益类型。枚举值：
  - `daily_income`：每日收益
  - `dividend`：分红
  - `redeem_profit`：赎回收益
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `income_amount`：收益金额。
- `settled_flag`：是否已入账，`1` 表示已入账，`0` 表示未入账。
- `settled_at`：入账时间。
- `created_at`：创建时间。

- 唯一性约束：
  - `uk_wealth_income_no (income_no)`
  - `uk_wealth_income_position_date_type (position_id, income_date, income_type)`
- 外键约束：
  - `fk_wealth_income_customer (customer_id -> customer.id)`
  - `fk_wealth_income_account (account_id -> bank_account.id)`
  - `fk_wealth_income_position (position_id -> wealth_position.id)`
  - `fk_wealth_income_product (product_id -> wealth_product.id)`
  - `fk_wealth_income_transaction (transaction_id -> account_transaction.id)`
  - `fk_wealth_income_ledger (ledger_id -> account_ledger.id)`
  - `fk_wealth_income_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - 已入账收益 `settled_at` 必须不为空。
  - 收益客户必须与持仓客户一致。
  - 收益入账账户必须与持仓账户一致。
  - 收益产品必须与持仓产品一致。
  - 收益币种必须与产品币种一致。
  - 净值型产品允许 `income_amount < 0`，负收益只冲减持仓累计收益和市值，不生成入账交易。
  - `income_type = daily_income` 时同一持仓同一收益日期只能有一条记录。
  - 未入账收益 `settled_at` 必须为空。
  - `settled_flag = 1` 时 `income_amount` 必须大于 `0`。
  - `settled_flag = 1` 时 `account_id`、`transaction_id`、`ledger_id` 和 `settled_at` 必须不为空。
  - `settled_flag = 0` 时 `transaction_id` 和 `ledger_id` 必须为空。
  - 入账交易和入账流水的客户、账户、币种、金额必须与收益记录一致。
  - 理财收益入账交易的 `transaction_type` 必须为 `wealth_income`，`related_type` 必须为 `wealth_income`。
  - 日收益日期不得早于持仓创建日期。
  - 已结清持仓不得新增日收益。
  - 收益记录不得物理删除。

#### `wealth_product_notice`
理财产品公告表，维护产品说明、开放期、分红和风险提示公告。

- `id`：主键 ID。
- `notice_no`：公告编号，业务唯一标识。
- `product_id`：产品 ID，关联 `wealth_product.id`。
- `notice_type`：公告类型。枚举值：
  - `product_intro`：产品说明
  - `open_period`：开放期公告
  - `dividend`：分红公告
  - `risk_tip`：风险提示
  - `maturity`：到期公告
- `notice_title`：公告标题。
- `notice_content`：公告内容。
- `published_at`：发布时间。
- `notice_status`：公告状态。枚举值：
  - `draft`：草稿
  - `published`：已发布
  - `offline`：已下线
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_wealth_product_notice_no (notice_no)`
- 外键约束：
  - `fk_wealth_product_notice_product (product_id -> wealth_product.id)`
- 业务约束：
  - `notice_status = published` 时 `published_at` 必须不为空。
  - `notice_status != published` 时不得面向客户展示。
  - 已发布公告不得物理删除，只能下线。
  - 开放期公告必须关联开放式或定期开放产品。
  - 分红公告必须在分红收益入账前发布。
  - 到期公告必须关联已到期或即将到期产品。
  - 公告产品不得为空且必须处于非草稿状态。
  - `updated_at >= created_at`

### 信贷域
本域用于维护贷款产品、授信额度、贷款申请、审批记录、合同借据和放款记录。

表说明：

- `loan_product`：贷款产品表，维护产品额度、期限、利率、还款方式和准入条件。
- `loan_product_eligibility_rule`：贷款产品准入规则表，维护收入、负债、征信和客户类型准入条件。
- `loan_product_rate_tier`：贷款产品利率档位表，维护评分、期限、金额对应的利率区间。
- `loan_product_required_material`：贷款产品必需材料表，维护申请、审批和放款所需材料。
- `credit_application`：授信申请表，维护客户授信申请、申请额度、申请状态和渠道。
- `credit_application_material`：授信申请材料表，维护授信征信授权、收入证明和经营资料。
- `credit_approval_record`：授信审批记录表，维护授信审批节点、审批额度和审批结论。
- `credit_limit`：授信额度表，维护客户总额度、已用额度、冻结额度和可用额度。
- `credit_limit_change_log`：授信额度变更流水表，维护额度冻结、占用、释放和关闭记录。
- `loan_application`：贷款申请表，维护申请金额、期限、用途、状态和申请渠道。
- `loan_application_material`：贷款申请材料表，维护收入证明、经营资料、征信授权和附件状态。
- `credit_assessment`：征信评估表，维护征信摘要、负债水平、评分和评估结论。
- `loan_approval_record`：贷款审批记录表，维护审批节点、审批人、审批结论和审批意见。
- `loan_contract`：贷款合同借据表，维护合同号、借据金额、利率、期限、状态和结清状态。
- `loan_contract_document`：贷款合同文件表，维护合同文件、版本和签署状态。
- `contract_sign_record`：合同签署记录表，维护签署人、签署渠道、电子签章和签署结果。
- `collateral_asset`：抵押质押资产表，维护房产、车辆、存单和应收账款等担保资产。
- `guarantee_record`：担保记录表，维护保证人、担保方式、担保金额和担保状态。
- `loan_disbursement`：放款记录表，维护放款金额、放款账户、放款交易和放款状态。

依赖关系说明：

- `loan_product` 依赖 `dim_product_category`、`dim_currency` 和 `dim_risk_level`。
- `loan_product_eligibility_rule`、`loan_product_rate_tier` 和 `loan_product_required_material` 依赖 `loan_product`。
- `credit_application`、`credit_application_material`、`credit_limit`、`loan_application`、`loan_contract` 依赖 `customer`。
- `credit_approval_record` 依赖 `credit_application` 和 `dim_employee`。
- `credit_limit_change_log` 依赖 `credit_limit`、`credit_application` 和 `loan_application`。
- `loan_application_material` 和 `credit_assessment` 依赖 `loan_application`。
- `loan_approval_record` 依赖 `loan_application` 和 `dim_employee`。
- `loan_contract_document` 和 `contract_sign_record` 依赖 `loan_contract`。
- `collateral_asset` 和 `guarantee_record` 依赖 `loan_application`、`loan_contract` 和 `customer`。
- `loan_disbursement` 依赖 `loan_contract`、`bank_account` 和 `account_transaction`。
- 授信审批通过后生成或更新 `credit_limit`，贷款审批通过后生成 `loan_contract`，放款成功后生成还款计划。

#### `loan_product`
贷款产品表，定义消费贷款产品的额度、期限、利率和还款方式。

- `id`：主键 ID。
- `product_code`：产品编码，业务唯一标识。
- `product_name`：产品名称。
- `category_id`：产品分类 ID，关联 `dim_product_category.id`。
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `risk_level_id`：产品风险等级 ID，关联 `dim_risk_level.id`。
- `loan_type`：贷款类型。枚举值：
  - `consumer`：消费贷
  - `cash`：现金贷
  - `installment`：分期贷
  - `business`：经营贷
- `min_amount`：最低申请金额。
- `max_amount`：最高申请金额。
- `min_term_months`：最短期限月数。
- `max_term_months`：最长期限月数。
- `annual_interest_rate`：年化利率。
- `min_interest_rate`：最低年化利率。
- `max_interest_rate`：最高年化利率。
- `collateral_required_flag`：是否要求抵押质押，`1` 表示是，`0` 表示否。
- `guarantee_required_flag`：是否要求保证担保，`1` 表示是，`0` 表示否。
- `post_registration_allowed_flag`：是否允许放款后补登记，`1` 表示是，`0` 表示否。
- `min_guarantee_ratio`：最低担保覆盖比例。
- `repayment_method`：还款方式。枚举值：
  - `equal_principal_interest`：等额本息
  - `equal_principal`：等额本金
  - `interest_first`：先息后本
  - `one_time`：一次性还本付息
- `product_status`：产品状态。枚举值：
  - `draft`：草稿
  - `active`：启用
  - `paused`：暂停
  - `offline`：下线
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_loan_product_code (product_code)`
- 外键约束：
  - `fk_loan_product_category (category_id -> dim_product_category.id)`
  - `fk_loan_product_currency (currency_code -> dim_currency.currency_code)`
  - `fk_loan_product_risk_level (risk_level_id -> dim_risk_level.id)`
- 业务约束：
  - `min_amount > 0`
  - `max_amount >= min_amount`
  - `min_term_months > 0`
  - `max_term_months >= min_term_months`
  - `annual_interest_rate >= 0`
  - `min_interest_rate >= 0`
  - `max_interest_rate >= min_interest_rate`
  - `annual_interest_rate` 必须位于最低和最高年化利率之间。
  - `min_guarantee_ratio` 为空或大于等于 `0`。
  - 产品分类必须为 `category_type = loan`。
  - 产品币种必须为启用币种。
  - 产品风险等级必须引用 `risk_level_type = product` 的风险等级。
  - 启用产品必须配置还款方式、额度区间、期限区间和利率。
  - 启用产品必须配置准入规则、利率档位和必需材料。
  - 下线产品不得新增贷款申请，但存量合同继续按原产品规则还款。
  - 经营贷产品只能面向企业客户或具备经营资料的个人经营主体。
  - 一次性还本付息产品的最长期限应受产品规则限制。
  - 只有启用产品才能创建贷款申请。
  - `updated_at >= created_at`

#### `loan_product_eligibility_rule`
贷款产品准入规则表，维护收入、负债、征信和客户类型准入条件。
- `id`：主键 ID。
- `product_id`：贷款产品 ID，关联 `loan_product.id`。
- `rule_code`：准入规则编码。
- `rule_name`：准入规则名称。
- `rule_type`：准入规则类型。枚举值：
  - `customer_type`：客户类型
  - `income`：收入
  - `debt_ratio`：负债收入比
  - `credit_score`：征信评分
  - `overdue`：逾期
  - `blacklist`：黑名单
  - `material`：材料
- `rule_expression`：规则表达式。
- `threshold_value`：准入阈值。
- `decision_action`：不满足时动作。枚举值：
  - `reject`：拒绝
  - `manual_review`：人工审核
  - `supplement_material`：补充材料
- `yn`：是否启用，`1` 表示启用，`0` 表示停用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_loan_product_eligibility_rule (product_id, rule_code)`
- 外键约束：
  - `fk_loan_product_eligibility_product (product_id -> loan_product.id)`
- 业务约束：
  - 启用规则的 `rule_expression` 必须不为空。
  - 启用贷款产品至少应配置一条准入规则。
  - 准入规则不得物理删除，只能停用。
  - `updated_at >= created_at`

#### `loan_product_rate_tier`
贷款产品利率档位表，维护评分、期限、金额对应的利率区间。
- `id`：主键 ID。
- `product_id`：贷款产品 ID，关联 `loan_product.id`。
- `tier_code`：档位编码。
- `score_min`：评分下限。
- `score_max`：评分上限。
- `term_min_months`：期限下限月数。
- `term_max_months`：期限上限月数。
- `amount_min`：金额下限。
- `amount_max`：金额上限。
- `annual_interest_rate`：年化利率。
- `yn`：是否启用，`1` 表示启用，`0` 表示停用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_loan_product_rate_tier (product_id, tier_code)`
- 外键约束：
  - `fk_loan_product_rate_tier_product (product_id -> loan_product.id)`
- 业务约束：
  - `score_min <= score_max`
  - `term_min_months <= term_max_months`
  - `amount_min <= amount_max`
  - `annual_interest_rate >= 0`
  - 同一产品启用档位的评分、期限和金额区间不得重叠。
  - 审批利率必须来自启用利率档位或在产品利率区间内。
  - `updated_at >= created_at`

#### `loan_product_required_material`
贷款产品必需材料表，维护申请、审批和放款所需材料。
- `id`：主键 ID。
- `product_id`：贷款产品 ID，关联 `loan_product.id`。
- `material_type`：材料类型，复用 `credit_application_material.material_type` 和 `loan_application_material.material_type`。
- `required_stage`：要求阶段。枚举值：
  - `application`：申请
  - `approval`：审批
  - `contract`：签约
  - `disbursement`：放款
- `required_flag`：是否必需，`1` 表示是，`0` 表示否。
- `waivable_flag`：是否可豁免，`1` 表示是，`0` 表示否。
- `yn`：是否启用，`1` 表示启用，`0` 表示停用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_loan_product_required_material (product_id, material_type, required_stage)`
- 外键约束：
  - `fk_loan_product_required_material_product (product_id -> loan_product.id)`
- 业务约束：
  - 必需材料必须在对应阶段前提交并核验通过或豁免。
  - 产品必需材料类型必须能被授信申请材料或贷款申请材料覆盖。
  - 不可豁免材料不得通过人工豁免跳过。
  - `updated_at >= created_at`

#### `credit_application`
授信申请表，维护客户授信申请、申请额度、申请状态和渠道。
- `id`：主键 ID。
- `credit_application_no`：授信申请编号，业务唯一标识。
- `customer_id`：客户 ID，关联 `customer.id`。
- `product_id`：贷款产品 ID，关联 `loan_product.id`。
- `channel_id`：申请渠道 ID，关联 `dim_channel.id`。
- `apply_limit_amount`：申请授信额度。
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `application_status`：授信申请状态。枚举值：
  - `created`：已创建
  - `submitted`：已提交
  - `risk_reviewing`：风控审核中
  - `manual_reviewing`：人工审批中
  - `approved`：审批通过
  - `rejected`：审批拒绝
  - `cancelled`：已取消
  - `expired`：已过期
- `submitted_at`：提交时间。
- `approved_at`：审批通过时间。
- `rejected_at`：审批拒绝时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_credit_application_no (credit_application_no)`
- 外键约束：
  - `fk_credit_application_customer (customer_id -> customer.id)`
  - `fk_credit_application_product (product_id -> loan_product.id)`
  - `fk_credit_application_channel (channel_id -> dim_channel.id)`
  - `fk_credit_application_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - `apply_limit_amount > 0`
  - 授信产品必须为启用贷款产品。
  - 授信币种必须与贷款产品币种一致。
  - 授信申请渠道必须为启用渠道。
  - 授信申请客户必须完成实名、KYC 和征信授权。
  - 授信申请客户不得处于冻结、限制、销户或有效黑名单状态。
  - 审批通过前必须存在征信评估或授信评估结果。
  - 审批通过额度不得超过申请授信额度和贷款产品额度上限。
  - `application_status = approved` 时 `approved_at` 必须不为空。
  - `application_status = rejected` 时 `rejected_at` 必须不为空。
  - 审批通过后必须生成或更新授信额度。
  - `updated_at >= created_at`

#### `credit_application_material`
授信申请材料表，维护授信申请阶段的征信授权、收入证明和经营资料。
- `id`：主键 ID。
- `material_no`：材料编号，业务唯一标识。
- `credit_application_id`：授信申请 ID，关联 `credit_application.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `material_type`：材料类型。枚举值：
  - `identity`：身份证明
  - `income`：收入证明
  - `employment`：工作证明
  - `business_license`：营业执照
  - `tax_record`：纳税记录
  - `bank_statement`：银行流水
  - `credit_authorization`：征信授权
  - `other`：其他
- `material_name`：材料名称。
- `file_url`：文件地址。
- `file_hash`：文件哈希。
- `submitted_by`：提交人类型。枚举值：
  - `customer`：客户
  - `employee`：员工
  - `partner`：合作方
  - `system`：系统
- `verification_status`：核验状态。枚举值：
  - `pending`：待核验
  - `valid`：有效
  - `invalid`：无效
  - `expired`：过期
  - `waived`：已豁免
- `verified_by`：核验员工 ID，关联 `dim_employee.id`。
- `verified_at`：核验时间。
- `submitted_at`：提交时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_credit_application_material_no (material_no)`
  - `uk_credit_application_material_type (credit_application_id, material_type, material_name)`
- 外键约束：
  - `fk_credit_application_material_application (credit_application_id -> credit_application.id)`
  - `fk_credit_application_material_customer (customer_id -> customer.id)`
  - `fk_credit_application_material_verifier (verified_by -> dim_employee.id)`
- 业务约束：
  - 材料客户必须与授信申请客户一致。
  - `material_type = credit_authorization` 的有效材料是执行授信征信评估的前置条件。
  - `verification_status IN ('valid', 'invalid', 'expired', 'waived')` 时 `verified_at` 必须不为空。
  - 授信审批通过前必需材料必须处于有效或已豁免状态。
  - `file_url` 或 `file_hash` 至少一个不为空。
  - 同一授信申请同一材料类型的有效材料不得重复。
  - 征信授权材料必须早于授信征信评估时间提交。
  - 材料核验员工必须为在职员工。
  - `updated_at >= created_at`

#### `credit_approval_record`
授信审批记录表，维护授信审批节点、审批额度和审批结论。
- `id`：主键 ID。
- `credit_application_id`：授信申请 ID，关联 `credit_application.id`。
- `approval_node`：审批节点。枚举值：
  - `risk_engine`：风控引擎
  - `manual_review`：人工审批
  - `final_review`：终审
- `approval_round`：审批轮次。
- `approver_id`：审批员工 ID，关联 `dim_employee.id`。
- `approval_result`：审批结果。枚举值：
  - `pass`：通过
  - `reject`：拒绝
  - `return`：退回
- `approved_limit_amount`：审批授信额度。
- `approval_comment`：审批意见。
- `approved_at`：审批时间。
- `created_at`：创建时间。

- 唯一性约束：
  - `uk_credit_approval_node_round (credit_application_id, approval_node, approval_round)`
- 外键约束：
  - `fk_credit_approval_application (credit_application_id -> credit_application.id)`
  - `fk_credit_approval_approver (approver_id -> dim_employee.id)`
- 业务约束：
  - `approval_round > 0`
  - 审批通过时 `approved_limit_amount` 必须大于 `0`。
  - 审批拒绝或退回时 `approval_comment` 必须不为空。
  - 终审通过后才能生成授信额度。
  - 审批记录不得物理删除。

#### `credit_limit`
授信额度表，维护客户额度、已用额度、冻结额度和额度状态。

- `id`：主键 ID。
- `limit_no`：授信编号，业务唯一标识。
- `credit_application_id`：授信申请 ID，关联 `credit_application.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `product_id`：贷款产品 ID，关联 `loan_product.id`。
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `total_limit_amount`：总授信额度。
- `used_limit_amount`：已用额度。
- `frozen_limit_amount`：冻结额度。
- `available_limit_amount`：可用额度。
- `limit_status`：额度状态。枚举值：
  - `active`：有效
  - `frozen`：冻结
  - `expired`：过期
  - `closed`：关闭
- `valid_from`：生效时间。
- `valid_to`：失效时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_credit_limit_no (limit_no)`
  - `uk_credit_limit_active_customer_product (customer_id, product_id, limit_status)`，仅限制 `limit_status = active` 的有效额度。
- 外键约束：
  - `fk_credit_limit_application (credit_application_id -> credit_application.id)`
  - `fk_credit_limit_customer (customer_id -> customer.id)`
  - `fk_credit_limit_product (product_id -> loan_product.id)`
  - `fk_credit_limit_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - `total_limit_amount >= 0`
  - `used_limit_amount >= 0`
  - `frozen_limit_amount >= 0`
  - `available_limit_amount = total_limit_amount - used_limit_amount - frozen_limit_amount`
  - `valid_to` 必须晚于 `valid_from`。
  - `available_limit_amount >= 0`
  - 授信客户必须完成实名、KYC 和授信审批。
  - 授信产品必须为启用贷款产品。
  - 授信客户、产品和币种必须与授信申请一致。
  - 同一客户同一产品同一时间只能有一条有效授信额度。
  - 贷款申请提交后应冻结对应额度，申请取消、拒绝或过期后释放冻结额度。
  - 放款成功后应将冻结额度转为已用额度。
  - 合同结清后应按产品规则释放或恢复已用额度。
  - `limit_status = active` 时当前时间必须位于有效期内。
  - `limit_status IN ('expired', 'closed')` 时不得新增贷款申请。
  - `updated_at >= created_at`

#### `credit_limit_change_log`
授信额度变更流水表，维护额度冻结、占用、释放和关闭记录。
- `id`：主键 ID。
- `change_no`：变更编号，业务唯一标识。
- `credit_limit_id`：授信额度 ID，关联 `credit_limit.id`。
- `change_seq`：额度内变更序号。
- `credit_application_id`：授信申请 ID，关联 `credit_application.id`。
- `loan_application_id`：贷款申请 ID，关联 `loan_application.id`，授信授予类流水为空。
- `contract_id`：贷款合同 ID，关联 `loan_contract.id`。
- `repayment_id`：还款记录 ID，关联 `repayment_record.id`。
- `change_type`：变更类型。枚举值：
  - `grant`：授予
  - `freeze`：冻结
  - `unfreeze`：解冻
  - `use`：占用
  - `release`：释放
  - `expire`：过期
  - `close`：关闭
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `change_amount`：变更金额。
- `before_total_amount`：变更前总额度。
- `after_total_amount`：变更后总额度。
- `before_used_amount`：变更前已用额度。
- `after_used_amount`：变更后已用额度。
- `before_frozen_amount`：变更前冻结额度。
- `after_frozen_amount`：变更后冻结额度。
- `before_available_amount`：变更前可用额度。
- `after_available_amount`：变更后可用额度。
- `changed_at`：变更时间。
- `created_at`：创建时间。

- 唯一性约束：
  - `uk_credit_limit_change_no (change_no)`
  - `uk_credit_limit_change_seq (credit_limit_id, change_seq)`
- 外键约束：
  - `fk_credit_limit_change_limit (credit_limit_id -> credit_limit.id)`
  - `fk_credit_limit_change_credit_application (credit_application_id -> credit_application.id)`
  - `fk_credit_limit_change_loan_application (loan_application_id -> loan_application.id)`
  - `fk_credit_limit_change_contract (contract_id -> loan_contract.id)`
  - `fk_credit_limit_change_repayment (repayment_id -> repayment_record.id)`
  - `fk_credit_limit_change_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - `change_amount > 0`
  - 额度变更后总额度、已用额度和冻结额度必须大于等于 `0`。
  - `before_available_amount = before_total_amount - before_used_amount - before_frozen_amount`
  - `after_available_amount = after_total_amount - after_used_amount - after_frozen_amount`
  - 第一条额度流水的 `change_seq` 必须为 `1`，后续流水必须连续递增。
  - 后一条额度流水的所有 `before_*` 金额必须等于上一条额度流水的对应 `after_*` 金额。
  - 同一额度最新流水的所有 `after_*` 金额必须等于 `credit_limit` 当前总额度、已用额度、冻结额度和可用额度。
  - `change_type = grant` 时 `after_total_amount = before_total_amount + change_amount`。
  - `change_type = freeze` 时 `after_frozen_amount = before_frozen_amount + change_amount` 且 `after_available_amount = before_available_amount - change_amount`。
  - `change_type = unfreeze` 时 `after_frozen_amount = before_frozen_amount - change_amount` 且 `after_available_amount = before_available_amount + change_amount`。
  - `change_type = use` 时 `after_used_amount = before_used_amount + change_amount` 且 `after_frozen_amount = before_frozen_amount - change_amount`。
  - `change_type = release` 时 `after_used_amount = before_used_amount - change_amount` 且 `after_available_amount = before_available_amount + change_amount`。
  - `change_type IN ('expire', 'close')` 时 `after_available_amount = 0`。
  - 授予额度必须关联授信申请。
  - 冻结和解冻额度必须关联贷款申请。
  - 占用和释放额度必须关联贷款合同。
  - 还款触发的额度释放必须关联还款记录。
  - 额度变更流水不得物理删除。

#### `loan_application`
贷款申请表，维护客户贷款申请和申请状态。

- `id`：主键 ID。
- `application_no`：申请编号，业务唯一标识。
- `customer_id`：客户 ID，关联 `customer.id`。
- `product_id`：贷款产品 ID，关联 `loan_product.id`。
- `credit_limit_id`：授信额度 ID，关联 `credit_limit.id`，审批前可为空。
- `channel_id`：申请渠道 ID，关联 `dim_channel.id`。
- `apply_amount`：申请金额。
- `apply_term_months`：申请期限月数。
- `loan_purpose`：贷款用途。
- `application_status`：申请状态。枚举值：
  - `created`：已创建
  - `risk_reviewing`：风控审核中
  - `manual_reviewing`：人工审批中
  - `approved`：审批通过
  - `rejected`：审批拒绝
  - `cancelled`：已取消
  - `expired`：已过期
- `risk_decision`：风控决策。枚举值：
  - `pass`：通过
  - `manual`：转人工
  - `reject`：拒绝
- `submitted_at`：提交时间。
- `approved_at`：审批通过时间。
- `rejected_at`：审批拒绝时间。
- `expired_at`：过期时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_loan_application_no (application_no)`
- 外键约束：
  - `fk_loan_application_customer (customer_id -> customer.id)`
  - `fk_loan_application_product (product_id -> loan_product.id)`
  - `fk_loan_application_credit_limit (credit_limit_id -> credit_limit.id)`
  - `fk_loan_application_channel (channel_id -> dim_channel.id)`
- 业务约束：
  - `apply_amount > 0`
  - `apply_term_months > 0`
  - 申请已提交且存在授信额度时，申请金额不能超过授信可用额度。
  - `application_status = approved` 时 `approved_at` 必须不为空。
  - `application_status = rejected` 时 `rejected_at` 必须不为空。
  - `application_status = expired` 时 `expired_at` 必须不为空。
  - 申请客户必须完成实名、KYC 和有效联系方式校验。
  - 企业贷款申请必须存在企业客户档案和受益所有人信息。
  - 申请金额必须位于贷款产品最低和最高金额之间。
  - 申请期限必须位于贷款产品最短和最长期限之间。
  - 申请渠道必须为启用渠道。
  - 关联授信额度时，授信客户、产品和币种必须与贷款申请客户、产品和贷款产品币种一致。
  - 申请提交前必须存在征信授权材料。
  - 审批通过前必须存在有效征信评估。
  - `risk_decision = reject` 时申请状态不得审批通过。
  - `risk_decision = manual` 时必须生成审批或复核任务。
  - 已取消、已拒绝申请不得生成合同。
  - `application_status IN ('risk_reviewing', 'manual_reviewing', 'approved')` 时必须关联有效授信额度。
  - 审批通过金额不得超过申请金额和授信可用额度。
  - `updated_at >= created_at`

#### `loan_application_material`
贷款申请材料表，维护收入证明、经营资料、征信授权和附件状态。
- `id`：主键 ID。
- `material_no`：材料编号，业务唯一标识。
- `application_id`：贷款申请 ID，关联 `loan_application.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `material_type`：材料类型，复用 `credit_application_material.material_type` 并扩展抵押和担保资料。枚举值：
  - `identity`：身份证明
  - `income`：收入证明
  - `employment`：工作证明
  - `business_license`：营业执照
  - `tax_record`：纳税记录
  - `bank_statement`：银行流水
  - `credit_authorization`：征信授权
  - `collateral_document`：抵押质押资料
  - `guarantee_document`：担保资料
  - `other`：其他
- `material_name`：材料名称。
- `file_url`：文件地址。
- `file_hash`：文件哈希。
- `submitted_by`：提交人类型。枚举值：
  - `customer`：客户
  - `employee`：员工
  - `partner`：合作方
  - `system`：系统
- `verification_status`：核验状态。枚举值：
  - `pending`：待核验
  - `valid`：有效
  - `invalid`：无效
  - `expired`：过期
  - `waived`：已豁免
- `verified_by`：核验员工 ID，关联 `dim_employee.id`。
- `verified_at`：核验时间。
- `submitted_at`：提交时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_loan_application_material_no (material_no)`
  - `uk_loan_application_material_type (application_id, material_type, material_name)`
- 外键约束：
  - `fk_loan_application_material_application (application_id -> loan_application.id)`
  - `fk_loan_application_material_customer (customer_id -> customer.id)`
  - `fk_loan_application_material_verifier (verified_by -> dim_employee.id)`
- 业务约束：
  - `material_type = credit_authorization` 的有效材料是执行征信评估的前置条件。
  - `verification_status IN ('valid', 'invalid', 'expired', 'waived')` 时 `verified_at` 必须不为空。
  - 审批通过前必需材料必须处于有效或已豁免状态。
  - 材料客户必须与贷款申请客户一致。
  - `file_url` 或 `file_hash` 至少一个不为空。
  - 同一申请同一材料类型的有效材料不得重复。
  - 材料失效或过期后不得作为审批通过依据。
  - 材料核验员工必须为在职员工。
  - 征信授权材料必须早于征信评估时间提交。
  - 抵押质押或担保类产品必须提交对应资料。
  - `updated_at >= created_at`

#### `credit_assessment`
征信评估表，维护征信摘要、负债水平、评分和评估结论。
- `id`：主键 ID。
- `assessment_no`：评估编号，业务唯一标识。
- `credit_application_id`：授信申请 ID，关联 `credit_application.id`。
- `application_id`：贷款申请 ID，关联 `loan_application.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `credit_report_no`：征信报告编号。
- `credit_score`：征信评分。
- `internal_score`：内部评分。
- `debt_income_ratio`：负债收入比。
- `monthly_income_amount`：月收入金额。
- `monthly_debt_amount`：月负债金额。
- `existing_loan_count`：存量贷款笔数。
- `existing_credit_card_count`：存量信用卡数量。
- `overdue_count_24m`：近 24 个月逾期次数。
- `max_overdue_days_24m`：近 24 个月最大逾期天数。
- `query_count_6m`：近 6 个月征信查询次数。
- `risk_level_id`：评估风险等级 ID，关联 `dim_risk_level.id`。
- `assessment_result`：评估结果。枚举值：
  - `pass`：通过
  - `manual`：转人工
  - `reject`：拒绝
- `assessment_summary`：评估摘要。
- `assessed_at`：评估时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_credit_assessment_no (assessment_no)`
  - `uk_credit_assessment_credit_application (credit_application_id)`，仅限制 `credit_application_id` 非空的授信申请评估。
  - `uk_credit_assessment_application (application_id)`，仅限制 `application_id` 非空的贷款申请评估。
- 外键约束：
  - `fk_credit_assessment_credit_application (credit_application_id -> credit_application.id)`
  - `fk_credit_assessment_application (application_id -> loan_application.id)`
  - `fk_credit_assessment_customer (customer_id -> customer.id)`
  - `fk_credit_assessment_risk_level (risk_level_id -> dim_risk_level.id)`
- 业务约束：
  - `credit_score >= 0`
  - `internal_score >= 0`
  - `debt_income_ratio >= 0`
  - `monthly_income_amount >= 0`
  - `monthly_debt_amount >= 0`
  - 评估客户必须与授信申请或贷款申请客户一致。
  - 评估必须关联授信申请或贷款申请之一。
  - `credit_application_id` 和 `application_id` 必须且只能有一个不为空。
  - 贷款申请评估需要追溯授信申请时，必须通过 `loan_application` 关联的客户和额度链路反推，不得同时填写两个申请 ID。
  - `risk_level_id` 必须引用 `risk_level_type = event` 的风险等级。
  - `assessment_result = pass` 时内部评分必须达到产品准入阈值。
  - `assessment_result = reject` 时贷款申请不得审批通过。
  - 近 24 个月最大逾期天数、逾期次数和查询次数必须大于等于 `0`。
  - 负债收入比超过产品准入阈值时评估结果不得为直接通过。
  - 征信报告编号相同的评估不得重复用于不同客户。
  - 征信评估时间必须晚于征信授权材料提交时间。
  - 贷款审批通过前必须存在征信评估记录。
  - `updated_at >= created_at`

#### `loan_approval_record`
贷款审批记录表，维护审批节点、审批人、审批结论和审批意见。

- `id`：主键 ID。
- `application_id`：贷款申请 ID，关联 `loan_application.id`。
- `approval_node`：审批节点。枚举值：
  - `risk_engine`：风控引擎
  - `manual_review`：人工审批
  - `final_review`：终审
- `approver_id`：审批员工 ID，关联 `dim_employee.id`。
- `approval_round`：审批轮次。
- `sequence_no`：审批序号。
- `approval_result`：审批结果。枚举值：
  - `pass`：通过
  - `reject`：拒绝
  - `return`：退回
  - `manual`：转人工
- `approval_comment`：审批意见。
- `approved_amount`：审批金额。
- `approved_term_months`：审批期限月数。
- `approved_rate`：审批利率。
- `approved_at`：审批时间。
- `created_at`：创建时间。

- 唯一性约束：
  - `uk_loan_approval_node_round (application_id, approval_node, approval_round)`
- 外键约束：
  - `fk_loan_approval_application (application_id -> loan_application.id)`
  - `fk_loan_approval_approver (approver_id -> dim_employee.id)`
- 业务约束：
  - 审批通过时 `approved_amount`、`approved_term_months` 和 `approved_rate` 必须不为空。
  - `approval_round > 0`
  - `sequence_no > 0`
  - 审批拒绝时 `approval_comment` 必须不为空。
  - 审批员工必须为在职信贷审批员或风控员。
  - 审批金额必须大于 `0` 且不得超过申请金额。
  - 审批期限必须大于 `0` 且不得超过申请期限。
  - 审批利率必须来自启用利率档位或位于贷款产品利率区间内。
  - 同一申请的审批节点必须按风控、人工审批、终审顺序流转。
  - 退回审批必须填写审批意见。
  - 终审通过后才能生成贷款合同。
  - 已审批完成节点不得重复审批。
  - 审批记录不得物理删除。

#### `loan_contract`
贷款合同借据表，维护贷款合同、借据金额、期限、利率和合同状态。

- `id`：主键 ID。
- `contract_no`：合同编号，业务唯一标识。
- `loan_no`：借据编号，业务唯一标识。
- `application_id`：贷款申请 ID，关联 `loan_application.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `product_id`：贷款产品 ID，关联 `loan_product.id`。
- `repayment_account_id`：还款账户 ID，关联 `bank_account.id`。
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `principal_amount`：借据本金。
- `disbursed_principal_amount`：已放款本金。
- `undisbursed_principal_amount`：未放款本金。
- `written_off_principal_amount`：已核销本金。
- `restructured_principal_amount`：已重组本金。
- `outstanding_principal_amount`：剩余本金。
- `annual_interest_rate`：年化利率。
- `term_months`：贷款期限月数。
- `repayment_method`：还款方式。
- `contract_status`：合同状态。枚举值：
  - `created`：已创建
  - `signed`：已签约
  - `disbursed`：已放款
  - `repaying`：还款中
  - `overdue`：逾期
  - `settled`：已结清
  - `written_off`：已核销
  - `cancelled`：已取消
- `signed_at`：签约时间。
- `disbursed_at`：放款时间。
- `settled_at`：结清时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_loan_contract_no (contract_no)`
  - `uk_loan_contract_loan_no (loan_no)`
- 外键约束：
  - `fk_loan_contract_application (application_id -> loan_application.id)`
  - `fk_loan_contract_customer (customer_id -> customer.id)`
  - `fk_loan_contract_product (product_id -> loan_product.id)`
  - `fk_loan_contract_repayment_account (repayment_account_id -> bank_account.id)`
  - `fk_loan_contract_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - `principal_amount > 0`
  - `disbursed_principal_amount >= 0`
  - `undisbursed_principal_amount >= 0`
  - `written_off_principal_amount >= 0`
  - `restructured_principal_amount >= 0`
  - `outstanding_principal_amount >= 0`
  - `disbursed_principal_amount + undisbursed_principal_amount = principal_amount`
  - `outstanding_principal_amount <= principal_amount`
  - `outstanding_principal_amount <= disbursed_principal_amount`
  - 剩余本金必须由成功放款本金减成功归还本金、还款冲正影响、核销本金和重组本金调整后回算。
  - 合同结清时 `outstanding_principal_amount = 0`。
  - 合同客户、产品必须与贷款申请一致。
  - 还款账户客户必须与合同客户一致。
  - 合同币种必须与产品币种和还款账户币种一致。
  - 合同本金不得超过审批金额。
  - 合同还款方式必须来自贷款产品 `repayment_method` 枚举，并与最终审批结果一致。
  - 合同期限和利率必须与最终审批结果一致。
  - `contract_status = signed` 时 `signed_at` 必须不为空。
  - `contract_status IN ('disbursed', 'repaying', 'overdue', 'settled', 'written_off')` 时 `disbursed_at` 必须不为空。
  - `contract_status = settled` 时 `settled_at` 必须不为空。
  - `contract_status = written_off` 时 `outstanding_principal_amount = 0` 且 `written_off_principal_amount > 0`。
  - 已取消合同不得放款。
  - 合同放款后必须按已放款本金生成还款计划，未完成全部放款时不得按合同总本金提前出全量还款计划。
  - 合同状态为逾期时必须存在有效逾期记录。
  - `updated_at >= created_at`

#### `loan_contract_document`
贷款合同文件表，维护合同文件、版本和签署状态。
- `id`：主键 ID。
- `document_no`：合同文件编号，业务唯一标识。
- `contract_id`：贷款合同 ID，关联 `loan_contract.id`。
- `document_type`：文件类型。枚举值：
  - `loan_contract`：贷款合同
  - `guarantee_contract`：担保合同
  - `collateral_contract`：抵押质押合同
  - `authorization`：授权文件
  - `other`：其他
- `document_version`：文件版本号。
- `file_url`：文件地址。
- `file_hash`：文件哈希。
- `sign_status`：签署状态。枚举值：
  - `draft`：草稿
  - `pending_sign`：待签署
  - `signed`：已签署
  - `cancelled`：已取消
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_loan_contract_document_no (document_no)`
  - `uk_loan_contract_document_version (contract_id, document_type, document_version)`
- 外键约束：
  - `fk_loan_contract_document_contract (contract_id -> loan_contract.id)`
- 业务约束：
  - 合同签约前必须生成贷款合同文件。
  - `file_url` 或 `file_hash` 至少一个不为空。
  - `sign_status = signed` 时必须存在完成的签署记录。
  - 已签署文件不得修改文件地址和哈希。
  - `updated_at >= created_at`

#### `contract_sign_record`
合同签署记录表，维护签署人、签署渠道、电子签章和签署结果。
- `id`：主键 ID。
- `sign_no`：签署编号，业务唯一标识。
- `contract_id`：贷款合同 ID，关联 `loan_contract.id`。
- `document_id`：合同文件 ID，关联 `loan_contract_document.id`。
- `signer_type`：签署人类型。枚举值：
  - `customer`：客户
  - `guarantor`：保证人
  - `bank`：银行
  - `authorized_operator`：授权经办人
- `signer_name`：签署人名称。
- `sign_channel_id`：签署渠道 ID，关联 `dim_channel.id`。
- `sign_method`：签署方式。枚举值：
  - `electronic`：电子签署
  - `paper`：纸质签署
  - `counter`：柜面签署
- `seal_no`：电子签章编号。
- `sign_status`：签署状态。枚举值：
  - `pending`：待签署
  - `signed`：已签署
  - `failed`：签署失败
  - `cancelled`：已取消
- `signed_at`：签署时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_contract_sign_record_no (sign_no)`
- 外键约束：
  - `fk_contract_sign_record_contract (contract_id -> loan_contract.id)`
  - `fk_contract_sign_record_document (document_id -> loan_contract_document.id)`
  - `fk_contract_sign_record_channel (sign_channel_id -> dim_channel.id)`
- 业务约束：
  - `sign_status = signed` 时 `signed_at` 必须不为空。
  - 签署记录的合同文件必须属于同一贷款合同。
  - 同一合同文件要求的签署方全部签署完成后合同才能进入已签约状态。
  - 电子签署必须记录电子签章编号。
  - 签署渠道必须为启用渠道。
  - `updated_at >= created_at`

#### `collateral_asset`
抵押质押资产表，维护房产、车辆、存单和应收账款等担保资产。
- `id`：主键 ID。
- `collateral_no`：抵押质押编号，业务唯一标识。
- `application_id`：贷款申请 ID，关联 `loan_application.id`。
- `contract_id`：贷款合同 ID，关联 `loan_contract.id`，审批通过生成合同后回填。
- `customer_id`：客户 ID，关联 `customer.id`。
- `asset_type`：资产类型。枚举值：
  - `real_estate`：房产
  - `vehicle`：车辆
  - `deposit_certificate`：存单
  - `receivable`：应收账款
  - `fund_share`：基金份额
  - `other`：其他
- `asset_name`：资产名称。
- `asset_owner_name`：资产所有人名称。
- `ownership_certificate_no`：权属证明编号。
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `appraised_value_amount`：评估价值金额。
- `pledge_rate`：抵质押率。
- `secured_amount`：担保金额。
- `appraisal_org`：评估机构。
- `appraised_at`：评估时间。
- `registration_status`：登记状态。枚举值：
  - `pending`：待登记
  - `registered`：已登记
  - `released`：已解除
  - `failed`：登记失败
- `pledge_rank`：抵押质押顺位。
- `priority_rule`：顺位规则说明。
- `collateral_status`：资产状态。枚举值：
  - `pending`：待生效
  - `active`：生效中
  - `released`：已解除
  - `disposed`：已处置
  - `invalid`：无效
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_collateral_asset_no (collateral_no)`
- 外键约束：
  - `fk_collateral_asset_application (application_id -> loan_application.id)`
  - `fk_collateral_asset_contract (contract_id -> loan_contract.id)`
  - `fk_collateral_asset_customer (customer_id -> customer.id)`
  - `fk_collateral_asset_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - `appraised_value_amount > 0`
  - `pledge_rate > 0 AND pledge_rate <= 100`
  - `secured_amount <= appraised_value_amount`
  - 需要抵押质押的产品在放款前必须存在有效担保资产。
  - `registration_status = registered` 时资产才能作为有效放款条件。
  - 抵押质押客户必须与贷款申请客户一致。
  - `contract_id` 不为空时，抵押质押资产关联合同必须来源于同一贷款申请。
  - 抵押质押币种必须与贷款产品币种一致。
  - `secured_amount` 不得超过 `appraised_value_amount * pledge_rate / 100`。
  - 已释放、已处置或无效资产不得作为新增放款条件。
  - 放款前登记状态必须为已登记，产品规则允许后补登记除外。
  - 资产评估时间不得晚于合同签约时间，合同未生成时不得晚于审批通过时间。
  - 同一权属证明编号的生效资产不得重复抵押给多个未结清合同，允许顺位抵押时必须填写 `pledge_rank` 和 `priority_rule`。
  - 合同结清后抵押质押资产应解除或进入处置流程。
  - `updated_at >= created_at`

#### `guarantee_record`
担保记录表，维护保证人、担保方式、担保金额和担保状态。
- `id`：主键 ID。
- `guarantee_no`：担保编号，业务唯一标识。
- `application_id`：贷款申请 ID，关联 `loan_application.id`。
- `contract_id`：贷款合同 ID，关联 `loan_contract.id`，审批通过生成合同后回填。
- `customer_id`：借款客户 ID，关联 `customer.id`。
- `guarantor_customer_id`：保证人客户 ID，关联 `customer.id`。
- `guarantor_name`：保证人名称。
- `guarantor_identity_type`：保证人证件类型。
- `guarantor_identity_no`：保证人证件号码。
- `guarantee_type`：担保方式。枚举值：
  - `joint_liability`：连带责任保证
  - `general_guarantee`：一般保证
  - `counter_guarantee`：反担保
  - `third_party_company`：第三方企业担保
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `guarantee_amount`：担保金额。
- `guarantee_start_at`：担保开始时间。
- `guarantee_end_at`：担保结束时间。
- `guarantee_status`：担保状态。枚举值：
  - `pending`：待生效
  - `active`：生效中
  - `released`：已解除
  - `claimed`：已代偿
  - `invalid`：无效
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_guarantee_record_no (guarantee_no)`
- 外键约束：
  - `fk_guarantee_record_application (application_id -> loan_application.id)`
  - `fk_guarantee_record_contract (contract_id -> loan_contract.id)`
  - `fk_guarantee_record_customer (customer_id -> customer.id)`
  - `fk_guarantee_record_guarantor_customer (guarantor_customer_id -> customer.id)`
  - `fk_guarantee_record_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - `guarantee_amount > 0`
  - `guarantee_end_at` 必须晚于 `guarantee_start_at`。
  - 需要保证担保的产品在放款前必须存在有效担保记录。
  - `guarantee_status = active` 时担保期限必须覆盖贷款期限。
  - `contract_id` 不为空时，担保记录关联合同必须来源于同一贷款申请。
  - 借款客户和保证人客户不得相同，关联企业互保需按产品规则校验。
  - 担保币种必须与贷款产品币种一致。
  - `guarantee_amount` 不得小于合同要求的最低担保金额。
  - 保证人必须完成实名、KYC 和黑名单校验。
  - 已解除、已代偿或无效担保不得作为新增放款条件。
  - 担保开始时间不得晚于合同签约时间。
  - 合同结清后担保记录应解除。
  - `updated_at >= created_at`

#### `loan_disbursement`
放款记录表，维护放款金额、放款账户、放款交易和放款状态。

- `id`：主键 ID。
- `disbursement_no`：放款编号，业务唯一标识。
- `contract_id`：合同 ID，关联 `loan_contract.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `account_id`：收款账户 ID，关联 `bank_account.id`。
- `transaction_id`：账户交易 ID，关联 `account_transaction.id`。
- `original_disbursement_id`：原放款记录 ID，冲正放款使用，关联 `loan_disbursement.id`。
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `disbursement_amount`：放款金额。
- `disbursement_status`：放款状态。枚举值：
  - `created`：已创建
  - `processing`：处理中
  - `success`：成功
  - `failed`：失败
  - `reversed`：已冲正
- `disbursed_at`：放款成功时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_loan_disbursement_no (disbursement_no)`
  - `uk_loan_disbursement_transaction (transaction_id)`，仅限制 `transaction_id` 非空的成功放款记录。
- 外键约束：
  - `fk_loan_disbursement_contract (contract_id -> loan_contract.id)`
  - `fk_loan_disbursement_customer (customer_id -> customer.id)`
  - `fk_loan_disbursement_account (account_id -> bank_account.id)`
  - `fk_loan_disbursement_transaction (transaction_id -> account_transaction.id)`
  - `fk_loan_disbursement_original (original_disbursement_id -> loan_disbursement.id)`
  - `fk_loan_disbursement_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - `disbursement_amount > 0`
  - `disbursement_status = success` 时 `disbursed_at` 和 `transaction_id` 必须不为空。
  - 同一合同成功放款总额不得超过合同本金。
  - 同一合同成功放款总额必须等于合同 `disbursed_principal_amount`。
  - 同一合同未冲正成功放款总额与未放款本金之和必须等于合同本金。
  - 放款客户必须与合同客户一致。
  - 放款账户客户必须与合同客户一致。
  - 放款币种必须与合同币种和收款账户币种一致。
  - 合同必须已签约且未取消才能发起放款。
  - 需要担保、抵押或质押的合同必须满足有效放款条件。
  - 放款成功必须生成账户交易、账户流水并更新合同放款时间、已放款本金、未放款本金和剩余本金。
  - 放款交易的 `transaction_type` 必须为 `loan_disbursement`，交易客户、收款账户、币种、金额和关联合同必须与放款记录一致。
  - 放款失败不得更新合同已放款本金、剩余本金、还款计划和账户余额。
  - 冲正放款必须关联原成功放款记录和原成功放款交易。
  - 放款冲正成功后必须回滚合同已放款本金、未放款本金和剩余本金，并取消或重算未出账还款计划。
  - 放款冲正后原放款交易状态必须更新为已冲正，并生成反向账户交易、账户流水和额度变更流水。
  - 同一合同全部放款成功后合同状态应进入已放款或还款中。
  - `updated_at >= created_at`

### 还款逾期域
本域用于维护还款计划、还款账单、还款记录、逾期记录和费用减免。

表说明：

- `repayment_schedule`：还款计划表，维护每期应还本金、利息、费用和到期日。
- `repayment_bill`：还款账单表，维护账单应还、已还、减免、逾期和结清状态。
- `repayment_authorization`：还款授权表，维护自动扣款、代扣协议和授权状态。
- `repayment_record`：还款记录表，维护主动还款、自动扣款、代扣和冲正记录。
- `repayment_allocation`：还款分配明细表，维护还款金额在账单、期次和费用项之间的分配。
- `overdue_record`：逾期记录表，维护逾期期数、逾期天数、逾期金额和逾期状态。
- `fee_reduction`：费用减免表，维护罚息、违约金、手续费等减免记录。

依赖关系说明：

- `repayment_schedule`、`repayment_bill`、`overdue_record` 和 `fee_reduction` 依赖 `loan_contract`。
- `repayment_authorization` 依赖 `loan_contract` 和 `bank_account`。
- `repayment_record` 依赖 `repayment_bill`、`bank_account`、`repayment_authorization` 和 `account_transaction`。
- `repayment_allocation` 依赖 `repayment_record` 和 `repayment_bill`。
- 还款成功后更新账单、还款计划、合同剩余本金和账户流水。
- 账单逾期后生成逾期记录，并可进入催收域。

#### `repayment_schedule`
还款计划表，维护贷款合同每期应还金额。

- `id`：主键 ID。
- `contract_id`：合同 ID，关联 `loan_contract.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `schedule_version`：还款计划版本号。
- `period_no`：期数。
- `due_date`：应还日期。
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `principal_amount`：应还本金。
- `interest_amount`：应还利息。
- `fee_amount`：应还费用。
- `total_amount`：应还总额。
- `schedule_status`：计划状态。枚举值：
  - `pending`：待还
  - `billed`：已出账
  - `paid`：已还清
  - `overdue`：已逾期
  - `cancelled`：已取消
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_repayment_schedule_period (contract_id, schedule_version, period_no)`
- 外键约束：
  - `fk_repayment_schedule_contract (contract_id -> loan_contract.id)`
  - `fk_repayment_schedule_customer (customer_id -> customer.id)`
  - `fk_repayment_schedule_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - `principal_amount >= 0`
  - `interest_amount >= 0`
  - `fee_amount >= 0`
  - `total_amount = principal_amount + interest_amount + fee_amount`
  - 同一合同同一计划版本内期数必须从 `1` 开始连续递增。
  - 还款计划客户必须与合同客户一致。
  - 还款计划币种必须与合同币种一致。
  - 当前有效计划版本的期次应还本金合计必须等于合同已放款本金或重组后剩余本金。
  - 历史计划版本不得物理删除，重组后必须生成新的 `schedule_version`。
  - 首期到期日必须晚于放款日期。
  - 后续期次到期日必须晚于上一期到期日。
  - 计划状态为已出账时必须存在对应还款账单。
  - 计划状态为已还清时对应账单必须已结清。
  - 计划状态为已逾期时必须存在对应逾期记录。
  - 合同取消时未出账计划应置为已取消。
  - `updated_at >= created_at`

#### `repayment_bill`
还款账单表，维护每期账单应还、已还、减免和逾期状态。

- `id`：主键 ID。
- `bill_no`：账单编号，业务唯一标识。
- `contract_id`：合同 ID，关联 `loan_contract.id`。
- `schedule_id`：还款计划 ID，关联 `repayment_schedule.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `period_no`：期数。
- `due_date`：应还日期。
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `principal_amount`：应还本金。
- `interest_amount`：应还利息。
- `fee_amount`：应还费用。
- `penalty_amount`：罚息金额。
- `reduced_amount`：减免金额。
- `paid_amount`：已还金额。
- `written_off_amount`：已核销金额。
- `restructured_amount`：已重组迁移金额。
- `outstanding_amount`：未还金额。
- `bill_status`：账单状态。枚举值：
  - `unpaid`：未还
  - `partial_paid`：部分还款
  - `paid`：已结清
  - `overdue`：逾期
  - `waived`：已减免
  - `written_off`：已核销
  - `restructured`：已重组迁移
- `billed_at`：出账时间。
- `paid_at`：结清时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_repayment_bill_no (bill_no)`
  - `uk_repayment_bill_schedule (schedule_id)`
- 外键约束：
  - `fk_repayment_bill_contract (contract_id -> loan_contract.id)`
  - `fk_repayment_bill_schedule (schedule_id -> repayment_schedule.id)`
  - `fk_repayment_bill_customer (customer_id -> customer.id)`
  - `fk_repayment_bill_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - `outstanding_amount = principal_amount + interest_amount + fee_amount + penalty_amount - reduced_amount - paid_amount - written_off_amount - restructured_amount`
  - `principal_amount >= 0`
  - `interest_amount >= 0`
  - `fee_amount >= 0`
  - `paid_amount >= 0`
  - `reduced_amount >= 0`
  - `written_off_amount >= 0`
  - `restructured_amount >= 0`
  - `bill_status = paid` 时 `outstanding_amount = 0`。
  - `penalty_amount >= 0`
  - `outstanding_amount >= 0`
  - 账单客户必须与合同客户一致。
  - 账单币种必须与合同币种一致。
  - 账单期数必须与还款计划期数一致。
  - `paid_amount + reduced_amount + written_off_amount + restructured_amount` 不得超过应还本金、利息、费用和罚息合计。
  - `bill_status = partial_paid` 时 `paid_amount > 0 AND outstanding_amount > 0`。
  - `bill_status = overdue` 时当前日期必须晚于 `due_date` 且 `outstanding_amount > 0`。
  - `bill_status = waived` 时 `reduced_amount` 必须大于 `0`。
  - `bill_status = written_off` 时 `written_off_amount` 必须大于 `0`。
  - `bill_status = restructured` 时 `restructured_amount` 必须大于 `0`。
  - 账单结清时间 `paid_at` 不得早于出账时间 `billed_at`。
  - 成功还款、减免或核销后必须同步更新账单未还金额。
  - `updated_at >= created_at`

#### `repayment_record`
还款记录表，维护还款交易、入账和冲正记录。

- `id`：主键 ID。
- `repayment_no`：还款编号，业务唯一标识。
- `bill_id`：账单 ID，关联 `repayment_bill.id`，提前还款和批量还款可为空。
- `contract_id`：合同 ID，关联 `loan_contract.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `account_id`：还款账户 ID，关联 `bank_account.id`。
- `transaction_id`：账户交易 ID，关联 `account_transaction.id`。
- `authorization_id`：还款授权 ID，关联 `repayment_authorization.id`。
- `collection_case_id`：催收案件 ID，催收还款时关联 `collection_case.id`。
- `repayment_promise_id`：承诺还款 ID，承诺履约还款时关联 `repayment_promise.id`。
- `original_repayment_id`：原还款记录 ID，冲正使用，关联 `repayment_record.id`。
- `repayment_type`：还款类型。枚举值：
  - `normal`：正常还款
  - `auto_debit`：自动扣款
  - `early`：提前还款
  - `partial`：部分还款
  - `collection`：催收还款
  - `reversal`：还款冲正
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `repayment_amount`：还款金额。
- `principal_paid_amount`：归还本金。
- `interest_paid_amount`：归还利息。
- `fee_paid_amount`：归还费用。
- `penalty_paid_amount`：归还罚息。
- `repayment_status`：还款状态。枚举值：
  - `created`：已创建
  - `processing`：处理中
  - `success`：成功
  - `failed`：失败
  - `reversed`：已冲正
- `repaid_at`：还款成功时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_repayment_record_no (repayment_no)`
  - `uk_repayment_record_transaction (transaction_id)`，仅限制 `transaction_id` 非空的成功还款记录。
- 外键约束：
  - `fk_repayment_record_bill (bill_id -> repayment_bill.id)`
  - `fk_repayment_record_contract (contract_id -> loan_contract.id)`
  - `fk_repayment_record_customer (customer_id -> customer.id)`
  - `fk_repayment_record_account (account_id -> bank_account.id)`
  - `fk_repayment_record_transaction (transaction_id -> account_transaction.id)`
  - `fk_repayment_record_authorization (authorization_id -> repayment_authorization.id)`
  - `fk_repayment_record_collection_case (collection_case_id -> collection_case.id)`
  - `fk_repayment_record_promise (repayment_promise_id -> repayment_promise.id)`
  - `fk_repayment_record_original (original_repayment_id -> repayment_record.id)`
  - `fk_repayment_record_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - `repayment_amount > 0`
  - `repayment_amount = principal_paid_amount + interest_paid_amount + fee_paid_amount + penalty_paid_amount`
  - `repayment_status = success` 时 `repaid_at` 和 `transaction_id` 必须不为空。
  - 各分项还款金额必须大于等于 `0`。
  - 还款客户必须与合同客户一致。
  - `bill_id` 不为空时，还款客户和合同必须与账单一致。
  - 还款账户客户必须与还款客户一致。
  - 还款币种必须与合同币种和账户币种一致，`bill_id` 不为空时还必须与账单币种一致。
  - `bill_id` 不为空时成功还款金额不得超过账单未还金额，提前还款按提前结清规则处理并写入还款分配明细。
  - 自动扣款和代扣还款必须存在有效授权和可用余额。
  - `repayment_type = collection` 时 `collection_case_id` 或 `repayment_promise_id` 必须至少一个不为空。
  - 催收还款必须关联有效催收案件或承诺还款记录。
  - `repayment_promise_id` 不为空时，承诺还款所属催收案件必须与 `collection_case_id` 一致，或由承诺还款反推催收案件。
  - 还款成功必须生成账户交易和账户流水。
  - 还款交易的 `transaction_type` 必须为 `loan_repayment`，交易客户、付款账户、币种、金额和关联合同或账单必须与还款记录一致。
  - 还款失败不得更新账单、计划和合同剩余本金。
  - 还款冲正必须关联原成功还款交易，且冲正金额不得超过可冲正金额。
  - 还款冲正成功后必须反向更新账单已还金额和未还金额、还款分配、合同剩余本金、逾期记录、催收案件状态和授信额度释放流水。
  - 还款冲正后原还款交易状态必须更新为已冲正，并生成反向账户交易、账户流水和对账结果。
  - 成功归还本金后必须同步扣减合同剩余本金。
  - `updated_at >= created_at`

#### `repayment_authorization`
还款授权表，维护自动扣款、代扣协议和授权状态。
- `id`：主键 ID。
- `authorization_no`：授权编号，业务唯一标识。
- `contract_id`：贷款合同 ID，关联 `loan_contract.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `account_id`：授权扣款账户 ID，关联 `bank_account.id`。
- `authorization_type`：授权类型。枚举值：
  - `auto_debit`：自动扣款
  - `withholding`：代扣
- `authorization_status`：授权状态。枚举值：
  - `active`：有效
  - `suspended`：暂停
  - `expired`：过期
  - `cancelled`：取消
- `valid_from`：生效时间。
- `valid_to`：失效时间。
- `signed_at`：签约时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_repayment_authorization_no (authorization_no)`
- 外键约束：
  - `fk_repayment_authorization_contract (contract_id -> loan_contract.id)`
  - `fk_repayment_authorization_customer (customer_id -> customer.id)`
  - `fk_repayment_authorization_account (account_id -> bank_account.id)`
- 业务约束：
  - 授权客户必须与合同客户一致。
  - 授权账户客户必须与授权客户一致。
  - `valid_to` 不为空时必须晚于 `valid_from`。
  - `authorization_status = active` 时当前时间必须位于授权有效期内。
  - 自动扣款和代扣还款必须引用有效授权。
  - `updated_at >= created_at`

#### `repayment_allocation`
还款分配明细表，维护还款金额在账单、期次和费用项之间的分配。
- `id`：主键 ID。
- `allocation_no`：分配编号，业务唯一标识。
- `repayment_id`：还款记录 ID，关联 `repayment_record.id`。
- `bill_id`：账单 ID，关联 `repayment_bill.id`。
- `contract_id`：贷款合同 ID，关联 `loan_contract.id`。
- `period_no`：期数。
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `principal_amount`：分配本金金额。
- `interest_amount`：分配利息金额。
- `fee_amount`：分配费用金额。
- `penalty_amount`：分配罚息金额。
- `allocated_amount`：分配总金额。
- `created_at`：创建时间。

- 唯一性约束：
  - `uk_repayment_allocation_no (allocation_no)`
  - `uk_repayment_allocation_bill (repayment_id, bill_id)`
- 外键约束：
  - `fk_repayment_allocation_repayment (repayment_id -> repayment_record.id)`
  - `fk_repayment_allocation_bill (bill_id -> repayment_bill.id)`
  - `fk_repayment_allocation_contract (contract_id -> loan_contract.id)`
  - `fk_repayment_allocation_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - 各分项分配金额必须大于等于 `0`。
  - `allocated_amount = principal_amount + interest_amount + fee_amount + penalty_amount`
  - 同一还款记录的分配总额必须等于还款金额。
  - 分配明细只能引用 `repayment_status = success` 的还款记录。
  - 分配合同、客户和币种必须与还款记录一致。
  - `bill_id` 不为空时，分配合同、期数、客户和币种必须与账单一致。
  - 同一还款记录分配到多个账单时，所有账单必须属于同一合同和客户。
  - 分配到逾期账单的成功还款必须同步更新 `overdue_record.paid_amount`、`outstanding_amount`、`overdue_status` 和 `settled_at`。
  - 逾期结清后必须同步回写关联催收案件状态，催收案件存在未完成处置时不得直接关闭。
  - 还款冲正对应的分配必须反向回滚账单、逾期记录和催收案件状态。
  - 提前还款、批量还款和跨期还款必须生成分配明细。
  - 分配明细不得物理删除。

#### `overdue_record`
逾期记录表，维护账单逾期、逾期天数、逾期金额和处置状态。

- `id`：主键 ID。
- `overdue_no`：逾期编号，业务唯一标识。
- `bill_id`：账单 ID，关联 `repayment_bill.id`。
- `contract_id`：合同 ID，关联 `loan_contract.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `period_no`：逾期期数。
- `overdue_start_date`：逾期开始日期。
- `overdue_days`：逾期天数。
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `overdue_principal_amount`：逾期本金。
- `overdue_interest_amount`：逾期利息。
- `overdue_fee_amount`：逾期费用。
- `penalty_amount`：罚息金额。
- `overdue_total_amount`：逾期总额。
- `paid_amount`：已还金额。
- `reduced_amount`：已减免金额。
- `written_off_amount`：已核销金额。
- `restructured_amount`：已重组迁移金额。
- `recovered_amount`：处置回收金额，属于已还金额的统计子集。
- `outstanding_amount`：当前未结清金额。
- `overdue_level`：逾期等级。枚举值：
  - `m1`：逾期 1-30 天
  - `m2`：逾期 31-60 天
  - `m3`：逾期 61-90 天
  - `m4_plus`：逾期 90 天以上
- `overdue_status`：逾期状态。枚举值：
  - `active`：逾期中
  - `partially_settled`：部分结清
  - `settled`：已结清
  - `written_off`：已核销
  - `restructured`：已重组迁移
- `settled_at`：逾期结清时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_overdue_record_no (overdue_no)`
  - `uk_overdue_record_bill (bill_id)`
- 外键约束：
  - `fk_overdue_record_bill (bill_id -> repayment_bill.id)`
  - `fk_overdue_record_contract (contract_id -> loan_contract.id)`
  - `fk_overdue_record_customer (customer_id -> customer.id)`
  - `fk_overdue_record_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - `overdue_days >= 1`
  - `overdue_total_amount = overdue_principal_amount + overdue_interest_amount + overdue_fee_amount + penalty_amount`
  - `paid_amount >= 0`
  - `reduced_amount >= 0`
  - `written_off_amount >= 0`
  - `restructured_amount >= 0`
  - `recovered_amount >= 0`
  - `outstanding_amount = overdue_total_amount - paid_amount - reduced_amount - written_off_amount - restructured_amount`
  - `outstanding_amount >= 0`
  - `recovered_amount <= paid_amount`
  - `overdue_status = settled` 时 `settled_at` 必须不为空。
  - `overdue_status = settled` 时 `outstanding_amount = 0`。
  - `overdue_status = active` 时 `outstanding_amount > 0`。
  - `overdue_status = restructured` 时 `restructured_amount` 必须大于 `0`。
  - 逾期客户必须与账单和合同客户一致。
  - 逾期币种必须与账单币种一致。
  - 各逾期金额和罚息金额必须大于等于 `0`。
  - `overdue_start_date` 必须晚于账单到期日。
  - `overdue_days` 必须按当前日期或结清日期与逾期开始日期计算。
  - 逾期等级必须与逾期天数匹配。
  - 同一账单只能存在一条有效逾期记录。
  - `overdue_status = active` 时账单状态必须为逾期或部分还款。
  - `overdue_status = written_off` 时必须存在核销或处置依据。
  - 逾期记录的已还、减免和核销金额必须与还款分配、费用减免和核销入账结果一致。
  - 逾期结清后关联催收案件应结清或关闭。
  - `updated_at >= created_at`

#### `fee_reduction`
费用减免表，维护罚息、违约金、手续费等费用减免。

- `id`：主键 ID。
- `reduction_no`：减免编号，业务唯一标识。
- `bill_id`：账单 ID，关联 `repayment_bill.id`。
- `contract_id`：合同 ID，关联 `loan_contract.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `reduction_type`：减免类型。枚举值：
  - `interest`：利息减免
  - `fee`：费用减免
  - `penalty`：罚息减免
  - `mixed`：综合减免
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `apply_amount`：申请减免金额。
- `approved_amount`：审批减免金额。
- `approved_interest_amount`：审批减免利息金额。
- `approved_fee_amount`：审批减免费用金额。
- `approved_penalty_amount`：审批减免罚息金额。
- `reduction_status`：减免状态。枚举值：
  - `submitted`：已提交
  - `approved`：已通过
  - `rejected`：已拒绝
  - `cancelled`：已取消
- `approved_by`：审批员工 ID，关联 `dim_employee.id`。
- `approval_comment`：审批意见。
- `approved_at`：审批时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_fee_reduction_no (reduction_no)`
- 外键约束：
  - `fk_fee_reduction_bill (bill_id -> repayment_bill.id)`
  - `fk_fee_reduction_contract (contract_id -> loan_contract.id)`
  - `fk_fee_reduction_customer (customer_id -> customer.id)`
  - `fk_fee_reduction_currency (currency_code -> dim_currency.currency_code)`
  - `fk_fee_reduction_approver (approved_by -> dim_employee.id)`
- 业务约束：
  - `apply_amount > 0`
  - `approved_amount >= 0`
  - `approved_amount <= apply_amount`
  - `approved_interest_amount >= 0`
  - `approved_fee_amount >= 0`
  - `approved_penalty_amount >= 0`
  - `approved_amount = approved_interest_amount + approved_fee_amount + approved_penalty_amount`
  - `reduction_status IN ('approved', 'rejected')` 时 `approved_at` 必须不为空。
  - 减免客户必须与账单和合同客户一致。
  - 减免币种必须与账单币种一致。
  - 已结清账单不得新增减免申请。
  - 审批通过的减免金额不得超过账单可减免金额。
  - `reduction_type = interest` 时 `approved_amount = approved_interest_amount`。
  - `reduction_type = fee` 时 `approved_amount = approved_fee_amount`。
  - `reduction_type = penalty` 时 `approved_amount = approved_penalty_amount`。
  - `reduction_type = mixed` 时必须至少两个分项减免金额大于 `0`。
  - 减免审批员工必须为在职且具备费用减免权限的员工。
  - `reduction_status = approved` 时 `approved_by` 必须不为空。
  - `reduction_status = approved` 且账单存在逾期记录时，审批减免金额必须计入 `overdue_record.reduced_amount`。
  - `reduction_status = rejected` 时 `approval_comment` 必须不为空。
  - 减免审批通过后必须同步更新账单减免金额和未还金额。
  - 已审批通过或拒绝的减免申请不得重复审批。
  - `updated_at >= created_at`

### 风控催收域
本域用于维护风控规则、风险事件、黑名单、人工复核、逾期催收任务和催收联系记录。

表说明：

- `risk_strategy`：风控策略表，维护策略编码、适用场景、决策模式、版本和启停状态。
- `risk_strategy_rule_rel`：风控策略规则关系表，维护策略下规则编排、优先级和权重。
- `risk_rule`：风控规则表，维护规则编码、规则类型、规则阈值和启停状态。
- `risk_event`：风险事件表，维护客户、交易、贷款或理财订单触发的风险事件。
- `risk_hit_record`：风险命中记录表，维护风险事件命中的具体规则和处置建议。
- `blacklist_record`：黑名单记录表，维护客户、证件、手机号、账户和设备黑名单。
- `aml_case`：反洗钱案件表，维护可疑交易调查、复核和处置状态。
- `aml_case_transaction`：反洗钱案件交易明细表，维护 AML 案件纳入调查和报送的交易范围。
- `suspicious_transaction_report`：可疑交易报告表，维护反洗钱报送记录和报送状态。
- `aml_review_result`：反洗钱复核结果表，维护 AML 人工复核结论和处置建议。
- `manual_review_task`：人工复核任务表，维护风控和信贷审批相关复核任务。
- `collection_case`：催收案件表，维护逾期案件、催收阶段、分案和案件状态。
- `collection_action`：催收处置动作表，维护协商、停催、外访、法诉、核销和重组等处置动作。
- `collection_contact_record`：催收联系记录表，维护电话、短信、上门和协商结果。
- `repayment_promise`：承诺还款表，维护客户承诺还款日期、金额和履约状态。
- `legal_case`：法诉案件表，维护诉讼、仲裁、执行和法务状态。
- `loan_write_off`：贷款核销表，维护核销申请、审批、核销金额和核销状态。
- `loan_restructure`：贷款重组表，维护展期、降息、延期和重组方案。
- `collateral_disposal`：抵押质押资产处置表，维护处置方式、处置金额和入账结果。
- `collection_performance_daily`：催收绩效日表，维护催收员每日案件、联系、承诺和回收指标。

依赖关系说明：

- `risk_strategy_rule_rel` 依赖 `risk_strategy` 和 `risk_rule`。
- `risk_event` 依赖 `customer` 和 `risk_strategy`，并可关联交易、贷款申请、理财订单或账户。
- `risk_hit_record` 依赖 `risk_event` 和 `risk_rule`。
- `aml_case`、`aml_case_transaction`、`suspicious_transaction_report` 和 `aml_review_result` 依赖 `risk_event`、`customer` 和 `account_transaction`。
- `manual_review_task` 依赖 `risk_event`、`credit_application`、`loan_application`、`wealth_order`、`fee_reduction`、`aml_case` 和 `dim_employee`。
- `collection_case` 依赖 `overdue_record`、`loan_contract`、`customer` 和 `dim_employee`。
- `collection_action`、`collection_contact_record` 和 `repayment_promise` 依赖 `collection_case`。
- `legal_case`、`loan_write_off`、`loan_restructure` 和 `collateral_disposal` 依赖 `collection_case`、`loan_contract` 和 `customer`。
- `collection_performance_daily` 依赖 `dim_employee` 和 `dim_branch`。

#### `risk_strategy`
风控策略表，维护策略编码、适用场景、决策模式、版本和启停状态。
- `id`：主键 ID。
- `strategy_code`：策略编码，业务唯一标识。
- `strategy_name`：策略名称。
- `strategy_type`：策略类型。枚举值：
  - `fraud`：反欺诈
  - `aml`：反洗钱
  - `credit`：信贷准入
  - `transaction`：交易监控
  - `wealth_suitability`：理财适当性
  - `collection`：催收分案
- `applicable_event_type`：适用事件类型。
- `decision_mode`：决策模式。枚举值：
  - `first_hit`：首次命中
  - `highest_risk`：最高风险
  - `score_sum`：分数汇总
  - `weighted_score`：加权评分
  - `manual_only`：仅人工
- `strategy_version`：策略版本号。
- `risk_level_id`：默认风险等级 ID，关联 `dim_risk_level.id`。
- `effective_from`：生效时间。
- `effective_to`：失效时间。
- `strategy_status`：策略状态。枚举值：
  - `draft`：草稿
  - `active`：启用
  - `paused`：暂停
  - `offline`：下线
- `created_by`：创建员工 ID，关联 `dim_employee.id`。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_risk_strategy_code_version (strategy_code, strategy_version)`
- 外键约束：
  - `fk_risk_strategy_level (risk_level_id -> dim_risk_level.id)`
  - `fk_risk_strategy_creator (created_by -> dim_employee.id)`
- 业务约束：
  - 同一 `strategy_code` 同一时间只能有一个启用版本。
  - `effective_to` 不为空时必须晚于 `effective_from`。
  - 只有启用且在有效期内的策略参与风险决策。
  - 启用策略必须至少关联一条启用规则。
  - `strategy_status = active` 时 `effective_from` 必须不为空。
  - `strategy_status IN ('paused', 'offline')` 时不得产生新的风险事件。
  - 同一策略版本发布后不得修改规则编排，调整必须发布新版本。
  - 策略类型必须与适用事件类型匹配。
  - 策略默认风险等级必须引用 `risk_level_type = event` 的风险等级。
  - 创建员工必须为在职风控员或运营人员。
  - `updated_at >= created_at`

#### `risk_strategy_rule_rel`
风控策略规则关系表，维护策略下规则编排、优先级和权重。
- `id`：主键 ID。
- `strategy_id`：风控策略 ID，关联 `risk_strategy.id`。
- `rule_id`：风控规则 ID，关联 `risk_rule.id`。
- `execute_order`：执行顺序。
- `rule_weight`：规则权重。
- `required_flag`：是否必执行，`1` 表示是，`0` 表示否。
- `stop_on_hit_flag`：命中后是否停止后续规则，`1` 表示是，`0` 表示否。
- `decision_override`：决策覆盖动作。
- `yn`：是否启用，`1` 表示启用，`0` 表示停用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_risk_strategy_rule (strategy_id, rule_id)`
  - `uk_risk_strategy_rule_order (strategy_id, execute_order)`
- 外键约束：
  - `fk_risk_strategy_rule_strategy (strategy_id -> risk_strategy.id)`
  - `fk_risk_strategy_rule_rule (rule_id -> risk_rule.id)`
- 业务约束：
  - `execute_order > 0`
  - `rule_weight >= 0`
  - 启用策略至少包含一条启用规则。
  - 规则类型必须与策略类型兼容。
  - 同一策略内执行顺序必须连续且不可重复。
  - `decision_override` 不为空时必须属于规则支持的决策动作。
  - `stop_on_hit_flag = 1` 的规则命中后不得继续执行后续非必执行规则。
  - `required_flag = 1` 的规则执行失败时策略结果必须转人工或失败。
  - 关联规则停用后该关系不得继续参与策略执行。
  - 催收分案策略只能关联催收规则或与催收事件兼容的规则。
  - `updated_at >= created_at`

#### `risk_rule`
风控规则表，定义反欺诈、反洗钱、信贷准入和交易监控规则。

- `id`：主键 ID。
- `rule_code`：规则编码，业务唯一标识。
- `rule_name`：规则名称。
- `rule_type`：规则类型。枚举值：
  - `fraud`：反欺诈
  - `aml`：反洗钱
  - `credit`：信贷准入
  - `transaction`：交易监控
  - `wealth_suitability`：理财适当性
  - `collection`：催收分案
- `risk_level_id`：风险等级 ID，关联 `dim_risk_level.id`。
- `rule_expression`：规则表达式。
- `rule_version`：规则版本号。
- `threshold_value`：规则阈值。
- `decision_action`：决策动作。枚举值：
  - `pass`：通过
  - `reject`：拒绝
  - `manual_review`：人工复核
  - `freeze`：冻结
  - `alert`：预警
- `rule_status`：规则状态。枚举值：
  - `draft`：草稿
  - `active`：启用
  - `paused`：暂停
  - `offline`：下线
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_risk_rule_code_version (rule_code, rule_version)`
- 外键约束：
  - `fk_risk_rule_level (risk_level_id -> dim_risk_level.id)`
- 业务约束：
  - 只有启用规则参与风险决策。
  - `rule_expression` 不能为空。
  - `threshold_value` 不为空时必须能被 `rule_expression` 引用。
  - 同一规则编码同一时间只能有一个启用版本。
  - 规则风险等级必须引用 `risk_level_type = event` 的风险等级。
  - 决策动作为冻结时必须能关联账户、客户或交易对象。
  - 决策动作为拒绝时必须保留命中明细。
  - 规则下线后历史命中记录仍保留原规则版本。
  - `updated_at >= created_at`

#### `risk_event`
风险事件表，维护业务触发的风险事件和最终决策。

- `id`：主键 ID。
- `event_no`：事件编号，业务唯一标识。
- `customer_id`：客户 ID，关联 `customer.id`。
- `event_type`：事件类型。枚举值：
  - `account_opening`：开户注册
  - `transaction`：交易
  - `credit_application`：授信申请
  - `loan_application`：贷款申请
  - `wealth_order`：理财订单
  - `aml`：反洗钱
  - `suspicious_transaction`：可疑交易
  - `collection`：催收
- `related_type`：关联对象类型。枚举值：
  - `none`：无
  - `customer`：客户
  - `account_transaction`：账户交易
  - `bank_account`：银行账户
  - `credit_application`：授信申请
  - `loan_application`：贷款申请
  - `wealth_order`：理财订单
  - `collection_case`：催收案件
- `related_id`：关联对象 ID。
- `strategy_id`：执行策略 ID，关联 `risk_strategy.id`。
- `risk_level_id`：风险等级 ID，关联 `dim_risk_level.id`。
- `risk_score`：风险分数。
- `decision_action`：决策动作。
- `hit_flag`：是否命中规则，`1` 表示是，`0` 表示否。
- `no_hit_reason`：未命中原因。
- `decision_reason`：决策原因。
- `event_status`：事件状态。枚举值：
  - `created`：已创建
  - `processed`：已处理
  - `manual_reviewing`：人工复核中
  - `closed`：已关闭
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_risk_event_no (event_no)`
- 外键约束：
  - `fk_risk_event_customer (customer_id -> customer.id)`
  - `fk_risk_event_strategy (strategy_id -> risk_strategy.id)`
  - `fk_risk_event_level (risk_level_id -> dim_risk_level.id)`
- 业务约束：
  - `risk_score >= 0`
  - 风险事件决策动作必须来自执行策略命中规则的 `decision_action` 或策略覆盖动作。
  - `decision_action = manual_review` 时必须生成复核任务。
  - 风险事件客户必须与关联业务对象客户一致。
  - `event_type = account_opening` 时 `related_type` 必须为 `customer` 或 `bank_account`。
  - `event_type = transaction` 时 `related_type` 必须为 `account_transaction`。
  - `event_type = credit_application` 时 `related_type` 必须为 `credit_application`。
  - `event_type = loan_application` 时 `related_type` 必须为 `loan_application`。
  - `event_type = wealth_order` 时 `related_type` 必须为 `wealth_order`。
  - `event_type IN ('aml', 'suspicious_transaction')` 时 `related_type` 必须为 `customer` 或 `account_transaction`。
  - `event_type = collection` 时 `related_type` 必须为 `collection_case`。
  - 风险等级必须引用 `risk_level_type = event` 的风险等级。
  - 风险分数必须落入风险等级分数区间。
  - 风险事件必须关联实际执行的策略版本。
  - `event_status = processed` 时必须存在至少一条命中记录，或 `hit_flag = 0` 且 `no_hit_reason` 不为空。
  - 决策动作为冻结时必须生成资金冻结、客户冻结或账户冻结记录。
  - 决策动作为拒绝时关联业务对象不得进入成功或审批通过状态。
  - `event_status = closed` 后不得新增命中记录或复核任务。
  - `updated_at >= created_at`

#### `risk_hit_record`
风险命中记录表，维护风险事件命中的具体规则。

- `id`：主键 ID。
- `event_id`：风险事件 ID，关联 `risk_event.id`。
- `rule_id`：规则 ID，关联 `risk_rule.id`。
- `hit_score`：命中分数。
- `hit_detail`：命中明细。
- `decision_action`：规则建议动作。
- `created_at`：创建时间。

- 唯一性约束：
  - `uk_risk_hit_record_event_rule (event_id, rule_id)`
- 外键约束：
  - `fk_risk_hit_record_event (event_id -> risk_event.id)`
  - `fk_risk_hit_record_rule (rule_id -> risk_rule.id)`
- 业务约束：
  - `hit_score >= 0`
  - 命中记录决策动作必须来自 `risk_rule.decision_action` 枚举。
  - 命中规则必须属于风险事件执行策略。
  - 命中动作必须与规则决策动作一致，允许策略覆盖动作。
  - 同一风险事件同一规则只能记录一次命中。
  - 命中明细必须包含触发字段、触发值或规则表达式结果。
  - 风险事件关闭后不得新增命中记录。
  - 命中记录不得物理删除。

#### `blacklist_record`
黑名单记录表，维护客户、证件、手机号、账户和设备黑名单。

- `id`：主键 ID。
- `blacklist_no`：黑名单编号，业务唯一标识。
- `subject_type`：主体类型。枚举值：
  - `customer`：客户
  - `identity`：证件
  - `mobile`：手机号
  - `account`：账户
  - `device`：设备
- `subject_value`：主体值。
- `risk_level_id`：风险等级 ID，关联 `dim_risk_level.id`。
- `blacklist_reason`：黑名单原因。
- `blacklist_status`：黑名单状态。枚举值：
  - `active`：有效
  - `expired`：过期
  - `removed`：移除
- `effective_from`：生效时间。
- `effective_to`：失效时间。
- `removed_reason`：移除原因。
- `removed_by`：移除操作员工 ID，关联 `dim_employee.id`。
- `removed_at`：移除时间。
- `approval_ref`：移除审批依据。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_blacklist_record_no (blacklist_no)`
  - `uk_blacklist_active_subject (subject_type, subject_value)`，仅限制 `blacklist_status = active` 的有效黑名单。
- 外键约束：
  - `fk_blacklist_record_level (risk_level_id -> dim_risk_level.id)`
  - `fk_blacklist_record_removed_by (removed_by -> dim_employee.id)`
- 业务约束：
  - 同一主体只能有一条有效黑名单记录。
  - 有效黑名单客户不能开户注册、申贷、申购理财、普通支出和投资类交易。
  - 有效黑名单客户允许存量贷款还款、催收回款、退款、冲正和调账等清偿或纠错交易，并继续受账户状态、余额、授权、风控和对账约束。
  - `blacklist_status = active` 时当前时间必须位于生效期内。
  - `effective_to` 不为空时必须晚于 `effective_from`。
  - `blacklist_status IN ('expired', 'removed')` 时不得拦截新增业务。
  - 黑名单主体类型为客户时 `subject_value` 必须对应有效客户号或客户 ID。
  - 黑名单主体类型为账户时 `subject_value` 必须对应有效账户号或账户 ID。
  - 黑名单移除必须保留移除原因或审批依据，并填写移除操作员工和移除时间。
  - 命中黑名单的交易、申贷和理财申购必须生成风险事件。
  - `updated_at >= created_at`

#### `aml_case`
反洗钱案件表，维护可疑交易调查、复核和处置状态。
- `id`：主键 ID。
- `case_no`：AML 案件编号，业务唯一标识。
- `risk_event_id`：风险事件 ID，关联 `risk_event.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `primary_transaction_id`：主要可疑交易 ID，关联 `account_transaction.id`。
- `transaction_count`：涉案交易笔数。
- `total_transaction_amount`：涉案交易总金额。
- `currency_code`：涉案交易币种，关联 `dim_currency.currency_code`。
- `case_type`：案件类型。枚举值：
  - `suspicious_transaction`：可疑交易
  - `blacklist_hit`：名单命中
  - `large_transaction`：大额交易
  - `abnormal_behavior`：异常行为
- `case_status`：案件状态。枚举值：
  - `created`：已创建
  - `reviewing`：调查中
  - `reported`：已报送
  - `closed`：已关闭
  - `excluded`：已排除
- `risk_level_id`：风险等级 ID，关联 `dim_risk_level.id`。
- `case_summary`：案件摘要。
- `opened_at`：立案时间。
- `closed_at`：关闭时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_aml_case_no (case_no)`
- 外键约束：
  - `fk_aml_case_event (risk_event_id -> risk_event.id)`
  - `fk_aml_case_customer (customer_id -> customer.id)`
  - `fk_aml_case_primary_transaction (primary_transaction_id -> account_transaction.id)`
  - `fk_aml_case_currency (currency_code -> dim_currency.currency_code)`
  - `fk_aml_case_risk_level (risk_level_id -> dim_risk_level.id)`
- 业务约束：
  - AML 案件客户必须与风险事件客户一致。
  - `case_type IN ('suspicious_transaction', 'large_transaction')` 时 `primary_transaction_id`、`transaction_count`、`total_transaction_amount` 和 `currency_code` 必须不为空。
  - `case_type IN ('suspicious_transaction', 'large_transaction')` 时 `transaction_count > 0` 且 `total_transaction_amount > 0`。
  - `case_type IN ('blacklist_hit', 'abnormal_behavior')` 时允许交易字段为空。
  - 涉案交易客户必须与 AML 案件客户一致，并通过 `aml_case_transaction` 保留明细。
  - `transaction_count`、`total_transaction_amount` 和 `currency_code` 必须与纳入案件的 `aml_case_transaction` 明细汇总一致。
  - `case_status IN ('closed', 'excluded')` 时 `closed_at` 必须不为空。
  - 可疑交易案件关闭前必须存在复核结果。
  - 已报送案件必须存在可疑交易报告。
  - `updated_at >= created_at`

#### `aml_case_transaction`
反洗钱案件交易明细表，维护 AML 案件涉及的账户交易范围。
- `id`：主键 ID。
- `aml_case_id`：AML 案件 ID，关联 `aml_case.id`。
- `transaction_id`：账户交易 ID，关联 `account_transaction.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `transaction_amount`：交易金额。
- `included_flag`：是否纳入案件统计和报送，`1` 表示是，`0` 表示否。
- `include_reason`：纳入原因。
- `created_at`：创建时间。

- 唯一性约束：
  - `uk_aml_case_transaction (aml_case_id, transaction_id)`
- 外键约束：
  - `fk_aml_case_transaction_case (aml_case_id -> aml_case.id)`
  - `fk_aml_case_transaction_transaction (transaction_id -> account_transaction.id)`
  - `fk_aml_case_transaction_customer (customer_id -> customer.id)`
  - `fk_aml_case_transaction_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - 明细客户必须与 AML 案件客户和账户交易客户一致。
  - 明细币种和金额必须与账户交易一致。
  - `included_flag = 1` 时 `include_reason` 必须不为空。
  - 纳入案件的明细交易必须发生在案件立案前或调查周期内。
  - 同一案件同一交易只能出现一次。
  - 明细不得物理删除。

#### `suspicious_transaction_report`
可疑交易报告表，维护反洗钱报送记录和报送状态。
- `id`：主键 ID。
- `report_no`：报告编号，业务唯一标识。
- `aml_case_id`：AML 案件 ID，关联 `aml_case.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `transaction_count`：报送交易笔数。
- `total_transaction_amount`：报送交易总金额。
- `currency_code`：报送交易币种，关联 `dim_currency.currency_code`。
- `report_period_start`：报送交易起始日期。
- `report_period_end`：报送交易结束日期。
- `report_type`：报告类型。枚举值：
  - `initial`：首次报送
  - `supplement`：补充报送
  - `correction`：更正报送
- `report_status`：报送状态。枚举值：
  - `draft`：草稿
  - `submitted`：已提交
  - `accepted`：已受理
  - `rejected`：已退回
  - `cancelled`：已取消
- `reported_at`：报送时间。
- `accepted_at`：受理时间。
- `report_content`：报送内容。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_suspicious_transaction_report_no (report_no)`
- 外键约束：
  - `fk_suspicious_report_case (aml_case_id -> aml_case.id)`
  - `fk_suspicious_report_customer (customer_id -> customer.id)`
  - `fk_suspicious_report_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - 报告客户必须与 AML 案件客户一致。
  - 报送交易笔数、金额和币种必须与报告周期内纳入报送的 `aml_case_transaction` 明细一致，补充报送和更正报送除外。
  - `transaction_count > 0`
  - `total_transaction_amount > 0`
  - `report_period_end` 必须晚于或等于 `report_period_start`。
  - `report_status IN ('submitted', 'accepted')` 时 `reported_at` 必须不为空。
  - `report_status = accepted` 时 `accepted_at` 必须不为空。
  - 已受理报告不得物理删除。
  - `updated_at >= created_at`

#### `aml_review_result`
反洗钱复核结果表，维护 AML 人工复核结论和处置建议。
- `id`：主键 ID。
- `review_no`：复核编号，业务唯一标识。
- `aml_case_id`：AML 案件 ID，关联 `aml_case.id`。
- `risk_event_id`：风险事件 ID，关联 `risk_event.id`。
- `reviewer_id`：复核员工 ID，关联 `dim_employee.id`。
- `review_result`：复核结果。枚举值：
  - `false_positive`：误报
  - `suspicious`：可疑
  - `blocked`：阻断
  - `report_required`：需报送
- `review_comment`：复核意见。
- `reviewed_at`：复核时间。
- `created_at`：创建时间。

- 唯一性约束：
  - `uk_aml_review_no (review_no)`
- 外键约束：
  - `fk_aml_review_case (aml_case_id -> aml_case.id)`
  - `fk_aml_review_event (risk_event_id -> risk_event.id)`
  - `fk_aml_review_reviewer (reviewer_id -> dim_employee.id)`
- 业务约束：
  - AML 复核员工必须为在职风控员。
  - AML 复核风险事件必须等于 AML 案件关联的风险事件。
  - AML 复核风险事件客户必须与 AML 案件客户一致。
  - `review_result = report_required` 时必须生成可疑交易报告。
  - 复核结果不得物理删除。

#### `manual_review_task`
人工复核任务表，维护风控和业务审批相关复核任务。

- `id`：主键 ID。
- `task_no`：任务编号，业务唯一标识。
- `customer_id`：客户 ID，关联 `customer.id`。
- `risk_event_id`：风险事件 ID，关联 `risk_event.id`，信贷审批和理财复核任务可为空。
- `related_type`：关联对象类型。枚举值：
  - `risk_event`：风险事件
  - `credit_application`：授信申请
  - `loan_application`：贷款申请
  - `wealth_order`：理财订单
  - `fee_reduction`：费用减免
  - `aml_case`：反洗钱案件
- `related_id`：关联对象 ID。
- `assignee_id`：处理员工 ID，关联 `dim_employee.id`。
- `task_type`：任务类型。枚举值：
  - `risk_review`：风控复核
  - `loan_review`：信贷复核
  - `wealth_review`：理财适当性复核
  - `aml_review`：反洗钱复核
  - `fee_reduction_review`：费用减免复核
- `task_status`：任务状态。枚举值：
  - `pending`：待处理
  - `processing`：处理中
  - `approved`：通过
  - `rejected`：拒绝
  - `cancelled`：取消
- `review_result`：复核结果。
- `review_comment`：复核意见。
- `assigned_at`：分配时间。
- `completed_at`：完成时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_manual_review_task_no (task_no)`
- 外键约束：
  - `fk_manual_review_task_customer (customer_id -> customer.id)`
  - `fk_manual_review_task_event (risk_event_id -> risk_event.id)`
  - `fk_manual_review_task_assignee (assignee_id -> dim_employee.id)`
- 业务约束：
  - `task_status IN ('approved', 'rejected')` 时 `completed_at` 必须不为空。
  - 已完成任务不得重新分配。
  - 复核任务客户必须与风险事件或关联业务对象客户一致。
  - 任务处理人必须为在职且角色匹配的员工。
  - `completed_at` 不为空时 `assigned_at` 不得晚于 `completed_at`。
  - `task_status = pending` 时不得填写 `completed_at`。
  - `task_status IN ('approved', 'rejected')` 时 `review_result` 必须不为空。
  - 风险事件决策为人工复核时必须存在一条待处理或已完成复核任务。
  - `task_type = risk_review` 或 `aml_review` 时 `risk_event_id` 必须不为空。
  - `task_type = loan_review` 时 `related_type` 必须为 `credit_application` 或 `loan_application`。
  - `task_type = wealth_review` 时 `related_type` 必须为 `wealth_order`。
  - `task_type = fee_reduction_review` 时 `related_type` 必须为 `fee_reduction`，处理人必须具备费用减免权限。
  - 复核结果必须回写关联风险事件和业务对象状态。
  - `updated_at >= created_at`

#### `collection_case`
催收案件表，维护逾期案件、催收阶段、分案和案件状态。

- `id`：主键 ID。
- `case_no`：案件编号，业务唯一标识。
- `overdue_id`：逾期记录 ID，关联 `overdue_record.id`。
- `contract_id`：合同 ID，关联 `loan_contract.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `collector_id`：催收员工 ID，关联 `dim_employee.id`。
- `collection_stage`：催收阶段。枚举值：
  - `m1`：早期催收
  - `m2`：中期催收
  - `m3`：后期催收
  - `legal`：法务催收
  - `write_off`：核销处置
- `case_status`：案件状态。枚举值：
  - `assigned`：已分案
  - `contacting`：联系中
  - `promised`：已承诺
  - `settled`：已结清
  - `failed`：催收失败
  - `closed`：已关闭
- `case_amount`：案件金额。
- `assigned_at`：分案时间。
- `closed_at`：关闭时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_collection_case_no (case_no)`
  - `uk_collection_case_active_overdue (overdue_id)`，仅限制未关闭催收案件。
- 外键约束：
  - `fk_collection_case_overdue (overdue_id -> overdue_record.id)`
  - `fk_collection_case_contract (contract_id -> loan_contract.id)`
  - `fk_collection_case_customer (customer_id -> customer.id)`
  - `fk_collection_case_collector (collector_id -> dim_employee.id)`
- 业务约束：
  - `case_amount > 0`
  - 只有逾期中记录才能生成催收案件。
  - `case_status IN ('settled', 'failed', 'closed')` 时 `closed_at` 必须不为空。
  - 催收案件客户必须与逾期记录和合同客户一致。
  - 催收员必须为在职催收员。
  - 催收阶段必须与逾期等级或案件策略匹配。
  - 同一逾期记录同一时间只能存在一个未关闭催收案件。
  - `case_amount` 必须等于逾期未结清金额或分案策略指定金额。
  - `assigned_at` 不得早于逾期开始日期。
  - 案件结清时逾期记录和账单必须已结清。
  - 案件关闭后不得新增联系记录和承诺还款。
  - `updated_at >= created_at`

#### `collection_action`
催收处置动作表，维护协商、停催、外访、法诉、核销和重组等处置动作。
- `id`：主键 ID。
- `action_no`：处置动作编号，业务唯一标识。
- `case_id`：催收案件 ID，关联 `collection_case.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `contract_id`：贷款合同 ID，关联 `loan_contract.id`。
- `action_type`：处置动作类型。枚举值：
  - `negotiate`：协商
  - `stop_collection`：停催
  - `field_visit`：外访
  - `legal`：法诉
  - `write_off`：核销
  - `restructure`：重组
  - `collateral_disposal`：抵押质押处置
- `action_status`：动作状态。枚举值：
  - `created`：已创建
  - `processing`：处理中
  - `completed`：已完成
  - `cancelled`：已取消
- `action_result`：处置结果。
- `operator_id`：操作员工 ID，关联 `dim_employee.id`。
- `action_at`：处置时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_collection_action_no (action_no)`
- 外键约束：
  - `fk_collection_action_case (case_id -> collection_case.id)`
  - `fk_collection_action_customer (customer_id -> customer.id)`
  - `fk_collection_action_contract (contract_id -> loan_contract.id)`
  - `fk_collection_action_operator (operator_id -> dim_employee.id)`
- 业务约束：
  - 处置客户和合同必须与催收案件一致。
  - `action_status = completed` 时 `action_result` 必须不为空。
  - 法诉、核销、重组和抵押质押处置动作必须生成对应业务记录。
  - 已关闭案件不得新增处置动作。
  - `updated_at >= created_at`

#### `collection_contact_record`
催收联系记录表，维护催收联系渠道、联系结果和客户反馈。

- `id`：主键 ID。
- `case_id`：催收案件 ID，关联 `collection_case.id`。
- `collector_id`：催收员工 ID，关联 `dim_employee.id`。
- `assistant_collector_id`：协催员工 ID，关联 `dim_employee.id`。
- `contact_method`：联系方式。枚举值：
  - `phone`：电话
  - `sms`：短信
  - `app_push`：App 推送
  - `email`：邮件
  - `visit`：上门
  - `legal_letter`：律师函
- `contact_result`：联系结果。枚举值：
  - `connected`：已接通
  - `unreachable`：无法联系
  - `refused`：拒绝沟通
  - `promised`：承诺还款
  - `paid`：已还款
  - `invalid_contact`：联系方式无效
- `contact_content`：联系内容。
- `next_contact_at`：下次联系时间。
- `contacted_at`：联系时间。
- `created_at`：创建时间。

- 唯一性约束：
  - 无
- 外键约束：
  - `fk_collection_contact_case (case_id -> collection_case.id)`
  - `fk_collection_contact_collector (collector_id -> dim_employee.id)`
  - `fk_collection_contact_assistant_collector (assistant_collector_id -> dim_employee.id)`
- 业务约束：
  - 联系记录不得物理删除。
  - `contact_result = promised` 时必须生成承诺还款记录。
  - 联系记录催收员必须与案件催收员一致，协催场景必须填写 `assistant_collector_id`。
  - 协催员工必须为在职催收员，且不得与主催收员相同。
  - 联系时间不得早于案件分案时间。
  - 已关闭案件不得新增联系记录。
  - 上门、律师函等强处置方式必须匹配催收阶段或法务状态。
  - `next_contact_at` 不为空时必须晚于 `contacted_at`。
  - 联系结果为无效联系方式时应同步更新客户联系方式或生成客服工单。
  - 联系结果为已还款时必须存在成功还款记录。

#### `repayment_promise`
承诺还款表，维护客户承诺还款日期、金额和履约状态。

- `id`：主键 ID。
- `promise_no`：承诺编号，业务唯一标识。
- `case_id`：催收案件 ID，关联 `collection_case.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `promise_amount`：承诺还款金额。
- `promise_date`：承诺还款日期。
- `promise_status`：承诺状态。枚举值：
  - `active`：有效
  - `fulfilled`：已履约
  - `broken`：已违约
  - `cancelled`：已取消
- `fulfilled_amount`：已履约金额。
- `fulfilled_repayment_id`：完成履约的还款记录 ID，关联 `repayment_record.id`，还款记录物理删除时置空。
- `fulfilled_at`：履约时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_repayment_promise_no (promise_no)`
- 外键约束：
  - `fk_repayment_promise_case (case_id -> collection_case.id)`
  - `fk_repayment_promise_customer (customer_id -> customer.id)`
  - `fk_repayment_promise_fulfilled_repayment (fulfilled_repayment_id -> repayment_record.id ON DELETE SET NULL)`
  - `fk_repayment_promise_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - `promise_amount > 0`
  - `fulfilled_amount >= 0`
  - `fulfilled_amount <= promise_amount`
  - `promise_status = fulfilled` 时 `fulfilled_amount = promise_amount`。
  - `promise_status = fulfilled` 时 `fulfilled_repayment_id` 和 `fulfilled_at` 必须不为空。
  - 承诺客户必须与催收案件客户一致。
  - 承诺币种必须与催收案件关联合同币种一致。
  - 承诺金额不得超过案件未结清金额。
  - `promise_date` 不得早于创建日期。
  - `promise_status = active` 时承诺日期未到或仍在宽限期内。
  - `promise_status = broken` 时当前日期必须晚于承诺日期且履约金额小于承诺金额。
  - 履约金额必须由关联本承诺的成功催收还款记录汇总产生。
  - 案件关闭后不得新增有效承诺。
  - `updated_at >= created_at`

#### `legal_case`
法诉案件表，维护诉讼、仲裁、执行和法务状态。
- `id`：主键 ID。
- `legal_case_no`：法诉案件编号，业务唯一标识。
- `action_id`：催收处置动作 ID，关联 `collection_action.id`。
- `case_id`：催收案件 ID，关联 `collection_case.id`。
- `contract_id`：贷款合同 ID，关联 `loan_contract.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `legal_type`：法务类型。枚举值：
  - `lawsuit`：诉讼
  - `arbitration`：仲裁
  - `execution`：执行
  - `legal_letter`：律师函
- `legal_status`：法务状态。枚举值：
  - `submitted`：已提交
  - `accepted`：已受理
  - `hearing`：审理中
  - `executing`：执行中
  - `closed`：已关闭
- `claim_amount`：诉请金额。
- `accepted_at`：受理时间。
- `closed_at`：关闭时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_legal_case_no (legal_case_no)`
  - `uk_legal_case_action (action_id)`，仅限制 `action_id` 非空的法诉动作。
- 外键约束：
  - `fk_legal_case_action (action_id -> collection_action.id)`
  - `fk_legal_case_collection (case_id -> collection_case.id)`
  - `fk_legal_case_contract (contract_id -> loan_contract.id)`
  - `fk_legal_case_customer (customer_id -> customer.id)`
- 业务约束：
  - `claim_amount > 0`
  - 法诉客户和合同必须与催收案件一致。
  - 法诉记录关联的催收动作必须为 `action_type = legal`。
  - `legal_status = closed` 时 `closed_at` 必须不为空。
  - 法诉案件关闭后应回写催收处置结果。
  - `updated_at >= created_at`

#### `loan_write_off`
贷款核销表，维护核销申请、审批、核销金额和核销状态。
- `id`：主键 ID。
- `write_off_no`：核销编号，业务唯一标识。
- `action_id`：催收处置动作 ID，关联 `collection_action.id`。
- `case_id`：催收案件 ID，关联 `collection_case.id`。
- `contract_id`：贷款合同 ID，关联 `loan_contract.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `apply_amount`：申请核销金额。
- `approved_amount`：审批核销金额。
- `approved_principal_amount`：审批核销本金金额。
- `approved_interest_amount`：审批核销利息金额。
- `approved_fee_amount`：审批核销费用金额。
- `approved_penalty_amount`：审批核销罚息金额。
- `write_off_status`：核销状态。枚举值：
  - `submitted`：已提交
  - `approved`：已通过
  - `rejected`：已拒绝
  - `posted`：已入账
  - `cancelled`：已取消
- `approved_by`：审批员工 ID，关联 `dim_employee.id`。
- `approval_comment`：审批意见。
- `approved_at`：审批时间。
- `posted_at`：入账时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_loan_write_off_no (write_off_no)`
  - `uk_loan_write_off_action (action_id)`，仅限制 `action_id` 非空的核销动作。
- 外键约束：
  - `fk_loan_write_off_action (action_id -> collection_action.id)`
  - `fk_loan_write_off_case (case_id -> collection_case.id)`
  - `fk_loan_write_off_contract (contract_id -> loan_contract.id)`
  - `fk_loan_write_off_customer (customer_id -> customer.id)`
  - `fk_loan_write_off_currency (currency_code -> dim_currency.currency_code)`
  - `fk_loan_write_off_approver (approved_by -> dim_employee.id)`
- 业务约束：
  - `apply_amount > 0`
  - `approved_amount >= 0`
  - `approved_amount <= apply_amount`
  - `approved_principal_amount >= 0`
  - `approved_interest_amount >= 0`
  - `approved_fee_amount >= 0`
  - `approved_penalty_amount >= 0`
  - `approved_amount = approved_principal_amount + approved_interest_amount + approved_fee_amount + approved_penalty_amount`
  - 核销记录关联的催收动作必须为 `action_type = write_off`。
  - 核销客户、合同和币种必须与催收案件、逾期记录和账单一致。
  - 审批核销金额不得超过逾期未结清金额。
  - 审批核销本金不得超过合同剩余本金。
  - `write_off_status IN ('approved', 'posted')` 时 `approved_by` 和 `approved_at` 必须不为空。
  - `write_off_status = posted` 时 `posted_at` 必须不为空。
  - 核销入账后必须按核销本金更新合同 `written_off_principal_amount` 和剩余本金，并按核销分项更新还款账单和逾期记录。
  - 全额核销入账后合同状态必须更新为 `written_off`。
  - 核销入账后必须同步更新账单 `written_off_amount`、`outstanding_amount` 和 `bill_status`。
  - `updated_at >= created_at`

#### `loan_restructure`
贷款重组表，维护展期、降息、延期和重组方案。
- `id`：主键 ID。
- `restructure_no`：重组编号，业务唯一标识。
- `action_id`：催收处置动作 ID，关联 `collection_action.id`。
- `case_id`：催收案件 ID，关联 `collection_case.id`。
- `contract_id`：原贷款合同 ID，关联 `loan_contract.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `before_outstanding_principal_amount`：重组前剩余本金。
- `capitalized_amount`：资本化金额。
- `reduced_amount`：减免金额。
- `after_outstanding_principal_amount`：重组后剩余本金。
- `original_schedule_version`：原还款计划版本号。
- `new_schedule_version`：新还款计划版本号。
- `restructure_type`：重组类型。枚举值：
  - `extension`：展期
  - `rate_reduction`：降息
  - `deferment`：延期
  - `term_adjustment`：期限调整
  - `mixed`：综合重组
- `new_term_months`：重组后期限月数。
- `new_interest_rate`：重组后利率。
- `restructure_status`：重组状态。枚举值：
  - `submitted`：已提交
  - `approved`：已通过
  - `rejected`：已拒绝
  - `effective`：已生效
  - `cancelled`：已取消
- `approved_by`：审批员工 ID，关联 `dim_employee.id`。
- `approved_at`：审批时间。
- `effective_at`：生效时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_loan_restructure_no (restructure_no)`
  - `uk_loan_restructure_action (action_id)`，仅限制 `action_id` 非空的重组动作。
- 外键约束：
  - `fk_loan_restructure_action (action_id -> collection_action.id)`
  - `fk_loan_restructure_case (case_id -> collection_case.id)`
  - `fk_loan_restructure_contract (contract_id -> loan_contract.id)`
  - `fk_loan_restructure_customer (customer_id -> customer.id)`
  - `fk_loan_restructure_approver (approved_by -> dim_employee.id)`
- 业务约束：
  - 重组客户和合同必须与催收案件一致。
  - 重组记录关联的催收动作必须为 `action_type = restructure`。
  - `before_outstanding_principal_amount > 0`
  - `capitalized_amount >= 0`
  - `reduced_amount >= 0`
  - `after_outstanding_principal_amount > 0`
  - `after_outstanding_principal_amount = before_outstanding_principal_amount + capitalized_amount - reduced_amount`
  - 资本化金额不得使重组后剩余本金超过合同已放款本金扣减已核销本金后的本金上限，超出部分应进入利息或费用计划。
  - `new_schedule_version` 必须大于 `original_schedule_version`。
  - `new_term_months` 为空或大于 `0`。
  - `new_interest_rate` 为空或大于等于 `0`。
  - `restructure_status = approved` 时 `approved_by` 和 `approved_at` 必须不为空。
  - `restructure_status = effective` 时 `effective_at` 必须不为空。
  - 重组生效后必须回写合同 `restructured_principal_amount`、`outstanding_principal_amount` 和合同状态。
  - 重组生效后必须按重组结果关闭、调整或迁移原未结清账单、逾期记录和催收案件。
  - 重组迁移旧账单或逾期金额时，必须同步更新 `repayment_bill.restructured_amount`、`overdue_record.restructured_amount`、未结清金额和对应重组状态。
  - 重组生效后必须按 `after_outstanding_principal_amount` 和 `new_schedule_version` 重新生成还款计划。
  - 新还款计划本金合计必须等于 `after_outstanding_principal_amount`。
  - 原还款计划不得物理删除，应通过版本号保留审计轨迹。
  - `updated_at >= created_at`

#### `collateral_disposal`
抵押质押资产处置表，维护处置方式、处置金额和入账结果。
- `id`：主键 ID。
- `disposal_no`：处置编号，业务唯一标识。
- `action_id`：催收处置动作 ID，关联 `collection_action.id`。
- `case_id`：催收案件 ID，关联 `collection_case.id`。
- `collateral_id`：抵押质押资产 ID，关联 `collateral_asset.id`。
- `contract_id`：贷款合同 ID，关联 `loan_contract.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `repayment_id`：处置回款还款记录 ID，关联 `repayment_record.id`。
- `transaction_id`：处置回款交易 ID，关联 `account_transaction.id`。
- `ledger_id`：处置回款流水 ID，关联 `account_ledger.id`。
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `disposal_method`：处置方式。枚举值：
  - `auction`：拍卖
  - `sale`：变卖
  - `transfer`：转让
  - `debt_offset`：抵债
- `disposal_amount`：处置金额。
- `received_amount`：回款金额。
- `disposal_status`：处置状态。枚举值：
  - `submitted`：已提交
  - `processing`：处理中
  - `completed`：已完成
  - `failed`：失败
  - `cancelled`：已取消
- `completed_at`：完成时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_collateral_disposal_no (disposal_no)`
  - `uk_collateral_disposal_action (action_id)`，仅限制 `action_id` 非空的抵押质押处置动作。
- 外键约束：
  - `fk_collateral_disposal_action (action_id -> collection_action.id)`
  - `fk_collateral_disposal_case (case_id -> collection_case.id)`
  - `fk_collateral_disposal_collateral (collateral_id -> collateral_asset.id)`
  - `fk_collateral_disposal_contract (contract_id -> loan_contract.id)`
  - `fk_collateral_disposal_customer (customer_id -> customer.id)`
  - `fk_collateral_disposal_repayment (repayment_id -> repayment_record.id)`
  - `fk_collateral_disposal_transaction (transaction_id -> account_transaction.id)`
  - `fk_collateral_disposal_ledger (ledger_id -> account_ledger.id)`
  - `fk_collateral_disposal_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - `disposal_amount > 0`
  - `received_amount >= 0`
  - `received_amount <= disposal_amount`
  - 处置客户和合同必须与催收案件一致。
  - 抵押质押处置记录关联的催收动作必须为 `action_type = collateral_disposal`。
  - `disposal_status = completed` 时 `completed_at` 必须不为空。
  - `disposal_status = completed AND received_amount > 0` 时 `repayment_id`、`transaction_id` 和 `ledger_id` 必须不为空。
  - 处置完成后必须更新抵押质押资产状态、还款记录、账户流水和逾期回收金额。
  - 处置回款必须通过 `repayment_record` 计入逾期已还金额，`overdue_record.recovered_amount` 只作为 `paid_amount` 的处置回收子集统计。
  - 处置回款还款记录、交易和流水的客户、合同、币种、金额必须与处置记录一致。
  - `updated_at >= created_at`

#### `collection_performance_daily`
催收绩效日表，维护催收员每日案件、联系、承诺和回收指标。
- `id`：主键 ID。
- `stat_date`：统计日期。
- `collector_id`：催收员工 ID，关联 `dim_employee.id`。
- `branch_id`：机构 ID，关联 `dim_branch.id`。
- `collection_stage`：催收阶段。
- `assigned_case_count`：当日分案数。
- `active_case_count`：在催案件数。
- `contact_attempt_count`：联系尝试次数。
- `connected_count`：有效接通次数。
- `promise_count`：承诺还款次数。
- `currency_code`：币种，关联 `dim_currency.currency_code`。
- `assigned_amount`：分案金额。
- `promised_amount`：承诺金额。
- `recovered_amount`：回收金额。
- `settled_case_count`：结清案件数。
- `broken_promise_count`：承诺违约次数。
- `recovery_rate`：回收率。
- `created_at`：创建时间。

- 唯一性约束：
  - `uk_collection_performance_daily (stat_date, collector_id, collection_stage, currency_code)`
- 外键约束：
  - `fk_collection_performance_collector (collector_id -> dim_employee.id)`
  - `fk_collection_performance_branch (branch_id -> dim_branch.id)`
  - `fk_collection_performance_currency (currency_code -> dim_currency.currency_code)`
- 业务约束：
  - 数量类指标必须大于等于 `0`。
  - 金额类指标必须大于等于 `0`。
  - `recovery_rate` 为空或满足 `recovery_rate >= 0 AND recovery_rate <= 100`。
  - 催收员必须为在职或统计日曾在职催收员。
  - 绩效币种必须与案件统计币种一致。
  - `recovered_amount` 不得大于 `assigned_amount`，跨期回收按绩效口径允许例外时必须保留统计规则。
  - `promise_count` 不得大于有效接通次数，批量承诺导入场景除外。
  - `settled_case_count` 不得大于在催案件数。
  - `recovery_rate` 必须按 `recovered_amount / assigned_amount` 计算，允许按币种精度四舍五入。
  - `assigned_amount = 0` 时 `recovery_rate` 必须为空或为 `0`。
  - 同一统计日同一催收员同一阶段同一币种只能保留一条结果。
  - 日绩效记录可重算覆盖，不物理删除。

### 运营支撑域
本域用于维护审批流程、通知消息、客服工单和业务统计。

表说明：

- `workflow_instance`：流程实例表，维护贷款审批、理财复核、费用减免和客服处理流程。
- `workflow_task`：流程任务表，维护流程节点、处理人、处理结果和完成时间。
- `notification_message`：通知消息表，维护短信、站内信、邮件和 App 推送。
- `support_ticket`：客服工单表，维护客户咨询、投诉、交易问题和贷款理财问题。
- `support_ticket_feedback`：客服工单反馈表，维护客户确认、满意度和反馈内容。
- `business_metric_dict`：业务指标字典表，维护指标编码、统计口径、单位和适用统计域。
- `business_stat_daily`：业务日统计表，维护客户、账户、交易、理财、信贷和催收指标。

依赖关系说明：

- `workflow_instance` 可关联授信申请、贷款申请、理财订单、费用减免、风险事件和客服工单。
- `workflow_task` 依赖 `workflow_instance` 和 `dim_employee`。
- `notification_message` 依赖 `customer`。
- `support_ticket` 依赖 `customer`、`dim_channel` 和 `dim_employee`。
- `support_ticket_feedback` 依赖 `support_ticket` 和 `customer`。
- `business_stat_daily` 依赖 `business_metric_dict`。
- `business_stat_daily` 按统计日期、机构、渠道和业务域聚合。

#### `workflow_instance`
流程实例表，维护业务审批和处理流程实例。

- `id`：主键 ID。
- `instance_no`：流程实例编号，业务唯一标识。
- `workflow_type`：流程类型。枚举值：
  - `loan_approval`：贷款审批
  - `wealth_review`：理财复核
  - `fee_reduction`：费用减免
  - `risk_review`：风控复核
  - `support_ticket`：客服工单
- `related_type`：关联对象类型。枚举值：
  - `credit_application`：授信申请
  - `loan_application`：贷款申请
  - `wealth_order`：理财订单
  - `fee_reduction`：费用减免
  - `risk_event`：风险事件
  - `support_ticket`：客服工单
- `related_id`：关联对象 ID。
- `initiator_type`：发起人类型。枚举值：
  - `customer`：客户
  - `employee`：员工
  - `service`：系统服务
- `initiator_no`：发起人编号，客户号、员工编号或服务账号。
- `instance_status`：实例状态。枚举值：
  - `running`：运行中
  - `approved`：通过
  - `rejected`：拒绝
  - `cancelled`：取消
  - `completed`：完成
- `started_at`：开始时间。
- `completed_at`：完成时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_workflow_instance_no (instance_no)`
- 外键约束：
  - 无
- 业务约束：
  - `instance_status IN ('approved', 'rejected', 'cancelled', 'completed')` 时 `completed_at` 必须不为空。
  - `instance_status = running` 时 `completed_at` 必须为空。
  - 流程实例必须关联有效业务对象。
  - 发起人编号必须与发起人类型匹配，客户发起时必须为有效客户号，员工发起时必须为在职员工编号，服务发起时必须为有效服务账号。
  - 同一业务对象同一流程类型同一时间只能存在一个运行中实例。
  - 贷款审批流程只能关联授信申请或贷款申请。
  - 理财复核流程只能关联理财订单或风险事件。
  - 费用减免流程只能关联费用减免申请。
  - 风控复核流程只能关联风险事件。
  - 客服工单流程只能关联客服工单。
  - `completed_at` 不为空时不得早于 `started_at`。
  - 流程实例完成后不得新增未完成任务。
  - `updated_at >= created_at`

#### `workflow_task`
流程任务表，维护流程节点、处理人、处理结果和完成时间。

- `id`：主键 ID。
- `task_no`：任务编号，业务唯一标识。
- `instance_id`：流程实例 ID，关联 `workflow_instance.id`。
- `node_code`：节点编码。
- `node_name`：节点名称。
- `assignee_id`：处理员工 ID，关联 `dim_employee.id`。
- `task_status`：任务状态。枚举值：
  - `pending`：待处理
  - `processing`：处理中
  - `approved`：通过
  - `rejected`：拒绝
  - `skipped`：跳过
  - `cancelled`：取消
- `task_result`：处理结果。
- `task_comment`：处理意见。
- `assigned_at`：分配时间。
- `completed_at`：完成时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_workflow_task_no (task_no)`
- 外键约束：
  - `fk_workflow_task_instance (instance_id -> workflow_instance.id)`
  - `fk_workflow_task_assignee (assignee_id -> dim_employee.id)`
- 业务约束：
  - 已完成任务不得重复处理。
  - `task_status IN ('approved', 'rejected', 'skipped', 'cancelled')` 时 `completed_at` 必须不为空。
  - 任务处理人必须为在职员工。
  - 任务实例必须处于运行中状态才能新增任务。
  - 同一流程实例同一节点编码不得存在多个未完成任务。
  - `completed_at` 不为空时 `assigned_at` 不得晚于 `completed_at`。
  - `task_status = pending` 时 `completed_at` 必须为空。
  - `task_status IN ('approved', 'rejected')` 时 `task_result` 必须不为空。
  - 前置节点未完成时不得处理后置节点，跳过节点除外。
  - 最后一个必需任务完成后必须回写流程实例状态。
  - `updated_at >= created_at`

#### `notification_message`
通知消息表，维护客户通知、交易通知、还款提醒和催收提醒。

- `id`：主键 ID。
- `message_no`：消息编号，业务唯一标识。
- `customer_id`：客户 ID，关联 `customer.id`。
- `related_type`：关联对象类型。枚举值：
  - `none`：无
  - `account_transaction`：账户交易
  - `repayment_bill`：还款账单
  - `wealth_order`：理财订单
  - `loan_contract`：贷款合同
  - `collection_case`：催收案件
  - `support_ticket`：客服工单
- `related_id`：关联对象 ID。
- `channel_txn_id`：渠道流水 ID，关联 `channel_transaction.id`。
- `message_type`：消息类型。枚举值：
  - `account`：账户通知
  - `transaction`：交易通知
  - `wealth`：理财通知
  - `loan`：贷款通知
  - `repayment`：还款提醒
  - `collection`：催收提醒
  - `system`：系统通知
- `send_channel`：发送渠道。枚举值：
  - `sms`：短信
  - `email`：邮件
  - `app_push`：App 推送
  - `site_message`：站内信
- `message_title`：消息标题。
- `message_content`：消息内容。
- `failure_reason`：发送失败原因。
- `send_status`：发送状态。枚举值：
  - `pending`：待发送
  - `success`：发送成功
  - `failed`：发送失败
  - `cancelled`：已取消
- `sent_at`：发送时间。
- `read_status`：阅读状态。枚举值：
  - `unread`：未读
  - `read`：已读
- `read_at`：阅读时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_notification_message_no (message_no)`
- 外键约束：
  - `fk_notification_message_customer (customer_id -> customer.id)`
  - `fk_notification_message_channel_txn (channel_txn_id -> channel_transaction.id)`
- 业务约束：
  - `send_status = success` 时 `sent_at` 必须不为空。
  - `read_status = read` 时 `read_at` 必须不为空。
  - 消息客户必须为有效客户。
  - 客户联系方式或设备信息必须支持选定发送渠道。
  - `send_status IN ('pending', 'failed', 'cancelled')` 时 `sent_at` 必须为空，重试成功场景除外。
  - `read_at` 不得早于 `sent_at`。
  - 发送失败必须保留失败原因或可追溯渠道流水。
  - 交易、还款、催收等业务通知必须关联对应业务对象。
  - 已取消消息不得再次发送。
  - 站内信成功发送后默认阅读状态为未读。
  - `updated_at >= created_at`

#### `support_ticket`
客服工单表，维护客户咨询、投诉和业务问题处理。

- `id`：主键 ID。
- `ticket_no`：工单编号，业务唯一标识。
- `customer_id`：客户 ID，关联 `customer.id`。
- `channel_id`：渠道 ID，关联 `dim_channel.id`。
- `assignee_id`：处理员工 ID，关联 `dim_employee.id`。
- `ticket_type`：工单类型。枚举值：
  - `account_issue`：账户问题
  - `transaction_issue`：交易问题
  - `wealth_issue`：理财问题
  - `loan_issue`：贷款问题
  - `repayment_issue`：还款问题
  - `complaint`：投诉
  - `other`：其他
- `related_type`：关联对象类型。枚举值：
  - `none`：无
  - `account_transaction`：账户交易
  - `wealth_order`：理财订单
  - `loan_application`：贷款申请
  - `repayment_bill`：还款账单
  - `support_ticket`：客服工单
- `related_id`：关联对象 ID。
- `ticket_title`：工单标题。
- `ticket_content`：工单内容。
- `ticket_status`：工单状态。枚举值：
  - `submitted`：已提交
  - `processing`：处理中
  - `waiting_customer`：等待客户
  - `resolved`：已解决
  - `closed`：已关闭
  - `rejected`：已拒绝
- `handle_result`：处理结果。
- `submitted_at`：提交时间。
- `handled_at`：处理时间。
- `closed_at`：关闭时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_support_ticket_no (ticket_no)`
- 外键约束：
  - `fk_support_ticket_customer (customer_id -> customer.id)`
  - `fk_support_ticket_channel (channel_id -> dim_channel.id)`
  - `fk_support_ticket_assignee (assignee_id -> dim_employee.id)`
- 业务约束：
  - `ticket_title` 和 `ticket_content` 不能为空。
  - `ticket_status IN ('resolved', 'closed', 'rejected')` 时 `handle_result` 必须不为空。
  - 工单客户必须为有效客户。
  - 工单渠道必须为启用渠道。
  - 工单处理人必须为在职客服人员或具备对应业务权限的员工。
  - `submitted_at` 不得晚于 `handled_at` 和 `closed_at`。
  - `ticket_status = waiting_customer` 时必须保留等待客户补充的处理结果。
  - 投诉类工单关闭前必须填写处理结果。
  - 交易、理财、贷款和还款问题工单必须填写 `related_type` 和 `related_id`。
  - 已关闭工单不得重新进入处理中状态，重新处理应新建工单或重开记录。
  - 工单解决后应触发通知消息或生成 `support_ticket_feedback` 客户确认记录。
  - `updated_at >= created_at`

#### `support_ticket_feedback`
客服工单反馈表，维护客户确认、满意度和反馈内容。
- `id`：主键 ID。
- `feedback_no`：反馈编号，业务唯一标识。
- `ticket_id`：工单 ID，关联 `support_ticket.id`。
- `customer_id`：客户 ID，关联 `customer.id`。
- `confirm_status`：确认状态。枚举值：
  - `confirmed`：已确认
  - `not_confirmed`：未确认
  - `disputed`：有异议
- `satisfaction_score`：满意度评分。
- `feedback_content`：反馈内容。
- `confirmed_at`：确认时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_support_ticket_feedback_no (feedback_no)`
  - `uk_support_ticket_feedback_ticket (ticket_id)`
- 外键约束：
  - `fk_support_ticket_feedback_ticket (ticket_id -> support_ticket.id)`
  - `fk_support_ticket_feedback_customer (customer_id -> customer.id)`
- 业务约束：
  - 反馈客户必须与工单客户一致。
  - `satisfaction_score` 为空或满足 `satisfaction_score >= 1 AND satisfaction_score <= 5`。
  - `confirm_status IN ('confirmed', 'disputed')` 时 `confirmed_at` 必须不为空。
  - 有异议反馈应重新打开工单或新建关联工单。
  - `updated_at >= created_at`

#### `business_metric_dict`
业务指标字典表，维护指标编码、统计口径、单位和适用统计域。
- `id`：主键 ID。
- `metric_code`：指标编码，业务唯一标识。
- `metric_name`：指标名称。
- `stat_domain`：统计域。
- `metric_type`：指标类型。枚举值：
  - `count`：数量
  - `amount`：金额
  - `rate`：比率
  - `duration`：时长
- `metric_unit`：指标单位。
- `currency_required_flag`：是否要求币种维度，`1` 表示是，`0` 表示否。
- `calculation_rule`：计算口径。
- `yn`：是否启用，`1` 表示启用，`0` 表示停用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_business_metric_code (metric_code)`
- 外键约束：
  - 无
- 业务约束：
  - 启用指标才能写入业务日统计。
  - 金额类指标必须要求币种维度，不得混合币种直接汇总。
  - `calculation_rule` 不能为空。
  - `updated_at >= created_at`

#### `business_stat_daily`
业务日统计表，维护客户、账户、交易、理财、信贷和催收日指标。

- `id`：主键 ID。
- `stat_date`：统计日期。
- `branch_id`：机构 ID，关联 `dim_branch.id`。
- `channel_id`：渠道 ID，关联 `dim_channel.id`。
- `currency_code`：统计币种，金额类指标必填，非金额类指标为空。
- `currency_code_key`：统计币种唯一键归一值，由 `currency_code` 派生，`currency_code` 为空时固定为 `__NONE__`。
- `stat_domain`：统计域。枚举值：
  - `customer`：客户
  - `account`：账户
  - `transaction`：交易
  - `wealth`：理财
  - `loan`：信贷
  - `repayment`：还款
  - `risk`：风控
  - `collection`：催收
- `metric_code`：指标编码。
- `metric_id`：指标字典 ID，关联 `business_metric_dict.id`。
- `metric_name`：指标名称。
- `metric_value`：指标值。
- `created_at`：创建时间。

- 唯一性约束：
  - `uk_business_stat_daily_key (stat_date, branch_id, channel_id, currency_code_key, stat_domain, metric_code)`
- 外键约束：
  - `fk_business_stat_daily_branch (branch_id -> dim_branch.id)`
  - `fk_business_stat_daily_channel (channel_id -> dim_channel.id)`
  - `fk_business_stat_daily_currency (currency_code -> dim_currency.currency_code)`
  - `fk_business_stat_daily_metric (metric_id -> business_metric_dict.id)`
- 业务约束：
  - 同一统计维度同一指标每天只能有一条记录。
  - 统计日期不得晚于当前日期。
  - 机构和渠道必须为统计口径内有效维度，汇总口径使用维表中的 `ALL` 汇总行。
  - `metric_code` 必须在 `business_metric_dict` 中定义。
  - `metric_code` 必须与 `metric_id` 对应的指标编码一致。
  - `metric_value` 不得为空。
  - 金额类指标 `currency_code` 必须不为空，并且必须按币种拆分，不得混合币种直接汇总。
  - 非金额类指标 `currency_code` 必须为空。
  - 日统计值必须能追溯到明细数据或上游统计批次。
  - 同一统计日重算时必须覆盖同一唯一维度记录。
  - 风控、催收和还款指标应与对应领域日统计口径保持一致。
  - 日统计记录可重算覆盖，不物理删除。

## 数据生成
### 生成原则
- 分层顺序固定为 `Layer1 -> Layer2 -> Layer3 -> Layer4 -> Layer5 -> Layer6 -> Layer7 -> Layer8 -> Layer9`，后层只能依赖前层已落库数据。
- 每个阶段的处理表包含本阶段主数据、业务明细、允许追加写入的公共资金表和最终状态快照表。
- 基础维度、产品主数据、风控规则和指标字典优先保证“稳定可回放”，编码、层级和枚举口径在不同批次之间保持一致。
- 所有编码类字段统一使用稳定规则生成，例如 `CUS00000001`、`ACC00000001`、`TXN0000000001`、`LOAN00000001`、`BILL00000001`。
- 时间字段统一遵循“主表先、子表后；创建时间先、更新时间后；业务发生时间不早于创建时间”的原则，保证外键和业务约束同时成立。
- 资金链路按业务事件同层落账，账户普通交易在 Layer3 落账，理财申赎在 Layer4 落账，贷款放款在 Layer5 落账，正常还款在 Layer6 落账，催收回款和抵押处置入账在 Layer7 落账。
- `account_transaction`、`channel_transaction`、`account_ledger`、`fund_freeze`、`fund_freeze_operation`、`reconciliation_batch`、`reconciliation_result` 和 `reconciliation_adjustment` 允许在 Layer3 之后由业务阶段追加写入，不允许 Layer3 为尚未生成的理财、信贷、还款、风控或催收对象预生成资金记录。
- Layer4 到 Layer7 追加写入账户交易时必须同步生成渠道流水、账户流水和对账结果，对账批次按 `channel_id + reconcile_date` 幂等覆盖。
- 理财、信贷、还款、逾期、催收、风控和运营支撑数据必须建立在真实客户、账户、产品和交易数据之上，不允许生成孤立业务对象。
- 日统计数据必须由明细数据或阶段性汇总结果反推生成，不直接凭空造数。

### 生成强约束
- 主体一致性：客户、账户、卡、风险测评、申请、合同、账单、逾期、催收案件、工单、流程和通知在跨表引用时必须属于同一业务主体，禁止仅按相同序号拼接。
- 派生来源：下游表必须从上游真实记录派生，贷款合同只能从终审通过的贷款申请派生，放款只能从已签约合同派生，还款只能从已出账账单派生，逾期只能从真实逾期账单派生，催收案件只能从逾期记录派生。
- 多态引用：`related_type` 和 `related_id` 必须映射到已存在、业务状态有效且主体一致的目标对象，通知、工单、流程、风控事件和人工复核任务均必须执行该规则。
- 资金一致性：业务单据金额必须作为同层追加资金记录的唯一金额来源，账户交易、渠道流水、账户流水、冻结记录、对账结果和业务单据之间的客户、账户、币种、金额、方向和业务引用必须一致。
- 审批一致性：授信、贷款、费用减免、人工复核和流程任务的审批结果、状态、完成时间和关联业务对象必须一致，审批未通过或未完成的对象不得生成通过后才能出现的合同、放款、减免或完成态流程。
- 风控与 AML 一致性：风险事件必须与关联业务对象客户一致；AML 案件、案件交易明细、复核结果和可疑交易报告的客户、交易范围、币种和金额必须一致。
- 催收处置一致性：催收动作、联系记录、承诺还款、法诉、核销、重组和抵押处置必须来自同一催收案件，并与案件对应的客户、合同、逾期记录、账单和回款金额一致。
- 时间一致性：业务发生时间必须满足上游先于下游，关闭、确认、审批、放款、还款、结案和处置完成后的 `updated_at` 必须取对应业务完成时间，不得晚于业务完成时间。
- 验收一致性：Layer9 必须覆盖规模、唯一性、外键、多态引用、主体一致性、时间顺序、金额闭环、状态流转、统计追溯和近期数据有效性，任何强约束不满足时生成任务必须失败。

### 标准规模口径
- 标准规模使用 `scale = standard`，其他规模按 `scale_factor` 等比缩放，基础配置表不低于标准规模。
- Layer1 基础配置：机构不少于 `50` 个，员工不少于 `300` 人，账户产品不少于 `10` 个，服务产品不少于 `12` 个，贷款产品不少于 `24` 个，理财产品不少于 `80` 个，风控规则不少于 `10` 条，业务指标不少于 `12` 个。
- Layer2 客户主数据：个人客户不少于 `46000` 户，企业客户不少于 `4000` 户，实名覆盖率不低于 `98%`，有效 KYC 覆盖率不低于 `95%`，客户风险测评覆盖率不低于 `85%`。
- Layer3 账户交易：账户数为有效客户数的 `1.3` 到 `1.8` 倍，银行卡数为个人有效账户数的 `0.8` 到 `1.2` 倍，账户交易不少于 `1000000` 笔，渠道流水覆盖线上交易，对账批次覆盖每个渠道每日数据。
- Layer4 理财业务：理财订单不少于 `30000` 笔，理财持仓不少于 `10000` 条，收益记录覆盖持仓自然日或交易日，净值记录覆盖最近 `12` 个月交易日。
- Layer5 信贷业务：授信申请不少于 `20000` 笔，贷款申请不少于 `15000` 笔，贷款合同不少于 `8000` 笔，放款记录覆盖所有已放款合同。
- Layer6 还款逾期：还款计划覆盖全部已放款合同期次，账单覆盖已到期计划，正常还款记录覆盖已结清账单，逾期合同占已放款合同的 `6%` 到 `12%`。
- Layer7 风控催收：风险事件覆盖客户、交易、理财、信贷、还款和催收场景，AML 案件占交易客户的 `0.05%` 到 `0.2%`，催收案件覆盖逾期中记录的 `70%` 到 `95%`。
- Layer8 运营统计：通知消息覆盖交易、理财、贷款、还款和催收关键事件，客服工单不少于客户数的 `1%`，业务日统计覆盖 `T-90` 到 `T` 的每个统计日。

### 时间跨度口径
- 时间基准：以脚本运行环境的本地时间为准，取执行当天当前日期为基准日 `T`，不使用数据库服务器时间作为生成基准。
- 基础维度与配置：`dim_branch`、`dim_channel`、`dim_currency`、`dim_risk_level`、`dim_employee`、`dim_product_category`、`account_product`、`service_product`、`loan_product`、`wealth_product`、`risk_rule`、`risk_strategy` 和 `business_metric_dict` 的创建时间覆盖 `T-1460` 到 `T-180`。
- 客户与账户域：客户开户注册、实名、KYC、联系方式、设备和账户开户时间覆盖 `T-1095` 到 `T`，最近 `30` 天新增客户和新增账户占比均不低于 `3%`。
- 账户交易域：转账、消费、充值、提现、冻结、解冻、渠道流水和对账数据覆盖 `T-365` 到 `T`。
- 理财域：产品净值覆盖最近 `12` 个月交易日；理财订单、持仓、收益和公告覆盖 `T-365` 到 `T`。
- 信贷域：授信申请、贷款申请、审批、合同、签署和放款覆盖 `T-720` 到 `T`，最近 `30` 天放款合同占比不低于 `2%`。
- 还款逾期域：还款计划、账单、还款、逾期和费用减免覆盖合同放款日至 `T`。
- 风控催收域：风险事件、反洗钱、人工复核、催收、法诉、核销、重组和抵押处置覆盖对应业务事件之后到 `T`。
- 运营支撑域：流程任务、消息通知、客服工单和业务日统计覆盖依赖业务发生日至 `T`。

### 字段分布口径
- 客户类型：个人客户占 `90%` 到 `95%`，企业客户占 `5%` 到 `10%`。
- 客户状态：正常客户占 `88%` 到 `94%`，冻结客户占 `2%` 到 `4%`，限制客户占 `2%` 到 `5%`，销户客户占 `1%` 到 `3%`。
- 渠道分布：手机银行占 `45%` 到 `60%`，网上银行占 `15%` 到 `25%`，柜面占 `10%` 到 `20%`，开放银行和合作渠道合计占 `5%` 到 `15%`。
- 交易状态：成功交易占 `92%` 到 `97%`，失败交易占 `2%` 到 `5%`，退款、撤销和冲正合计占 `0.5%` 到 `3%`。
- 交易类型：消费和转账合计占 `65%` 到 `80%`，充值和提现合计占 `10%` 到 `20%`，退款、冲正和调账合计占 `1%` 到 `5%`。
- 理财风险：低风险和中低风险产品订单占 `55%` 到 `75%`，中风险产品订单占 `15%` 到 `30%`，中高风险和高风险产品订单占 `5%` 到 `15%`。
- 贷款审批：贷款申请通过率为 `55%` 到 `75%`，拒绝率为 `15%` 到 `30%`，撤回和超时关闭合计占 `5%` 到 `10%`。
- 还款表现：正常还款占应还账单的 `82%` 到 `92%`，提前还款占 `3%` 到 `8%`，部分还款占 `2%` 到 `6%`，逾期未结清占 `3%` 到 `8%`。
- 催收阶段：早期催收占 `45%` 到 `60%`，中期催收占 `20%` 到 `35%`，后期催收占 `10%` 到 `20%`，法诉、核销和重组合计占 `2%` 到 `8%`。

### 金额计算口径
- 金额字段统一保留 `2` 位小数，利率字段统一保留 `4` 到 `6` 位小数，份额和净值字段按表定义精度保留。
- 计息天数使用 `ACT/365`，按自然日计息，节假日不停止计息。
- 等额本息月供：`payment = principal * monthly_rate * (1 + monthly_rate)^term / ((1 + monthly_rate)^term - 1)`。
- 等额本金每期本金：`principal_per_period = principal / term`，每期利息按剩余本金和月利率计算。
- 先息后本每期利息：`interest = principal * annual_interest_rate / 12`，最后一期归还全部本金。
- 一次性还本付息到期金额：`principal + principal * annual_interest_rate * actual_days / 365`。
- 罚息金额：`overdue_principal_or_interest * penalty_daily_rate * overdue_days`，`penalty_daily_rate = annual_interest_rate / 365 * penalty_multiplier`，`penalty_multiplier` 取 `1.3` 到 `1.5`。
- 手续费金额按产品费率、交易金额和封顶金额计算，减免后费用不得小于 `0`。
- 净值型理财收益：`holding_share * (current_nav - previous_nav)`，非净值型理财收益：`confirmed_amount * expected_yield_rate * holding_days / 365`。
- 账户余额按账户流水顺序反推，`balance_after = previous_balance_after + amount_delta`，`frozen_after = previous_frozen_after + frozen_delta`，冻结余额按冻结操作明细顺序反推。

### 业务统计回算口径
- `business_metric_dict` 在 Layer1 从种子导入，`business_stat_daily` 在 Layer8 由明细表回算生成。
- 日统计维度固定为 `stat_date`、`branch_id`、`channel_id`、`currency_code`、`stat_domain` 和 `metric_code`，机构和渠道必须同时生成明细维度行和 `ALL` 汇总行。
- 金额类指标必须按 `currency_code` 分币种回算，非金额类指标 `currency_code` 为空。
- `CUSTOMER_ACTIVE_COUNT`：统计日状态为正常或限制且未销户的客户数，按开户机构归属。
- `ACCOUNT_ACTIVE_COUNT`：统计日状态为正常的账户数，按账户开户机构和开户渠道归属。
- `TRANSACTION_AMOUNT`：统计日成功账户交易金额合计，不包含失败、撤销和冲正原交易。
- `TRANSACTION_COUNT`：统计日成功账户交易笔数，不包含失败、撤销和冲正原交易。
- `WEALTH_AUM`：统计日理财持仓当前金额合计，按账户机构、渠道和币种归属。
- `WEALTH_ORDER_AMOUNT`：统计日确认成功的理财订单金额合计，撤单和失败订单不计入。
- `LOAN_APPLICATION_COUNT`：统计日新提交贷款申请笔数，撤回申请计入申请数。
- `LOAN_DISBURSE_AMOUNT`：统计日成功放款金额合计，只统计放款状态为成功的记录。
- `REPAYMENT_AMOUNT`：统计日成功还款金额合计，冲正记录按负向金额计入。
- `OVERDUE_AMOUNT`：统计日未结清逾期本金、利息、罚息和费用余额合计。
- `RISK_EVENT_COUNT`：统计日新发生风险事件数量，按事件发生时间计入。
- `COLLECTION_RECOVERY_RATE`：统计日催收回收金额除以当日催收分案金额，分母为 `0` 时统计值为 `0`。
- 汇总行金额必须等于同日期、同指标下明细维度金额合计，汇总行数量必须等于去重后的明细主体数量。

### 阶段 1：Layer1 基础配置与产品主数据
- 目标：生成机构、渠道、币种、风险等级、员工、产品分类、账户产品、服务产品、贷款产品、理财产品、风控规则、风控策略和指标字典，为后续业务链路提供稳定引用。
- 处理表：`dim_branch`、`dim_channel`、`dim_currency`、`dim_risk_level`、`dim_employee`、`dim_product_category`、`account_product`、`service_product`、`loan_product`、`loan_product_eligibility_rule`、`loan_product_rate_tier`、`loan_product_required_material`、`wealth_product`、`wealth_open_period`、`wealth_trade_calendar`、`wealth_settlement_rule`、`wealth_nav`、`wealth_product_notice`、`risk_rule`、`risk_strategy`、`risk_strategy_rule_rel`、`business_metric_dict`
- 种子导入表：`dim_branch`、`dim_channel`、`dim_currency`、`dim_risk_level`、`dim_employee`、`dim_product_category`、`account_product`、`service_product`、`loan_product`、`loan_product_eligibility_rule`、`loan_product_rate_tier`、`loan_product_required_material`、`wealth_product`、`wealth_settlement_rule`、`risk_rule`、`risk_strategy`、`risk_strategy_rule_rel`、`business_metric_dict`
- 程序生成表：`wealth_open_period`、`wealth_trade_calendar`、`wealth_nav`、`wealth_product_notice`

表级说明：

- 基础维度组
  - 来源：导入 `seeds/1_foundation/dim_branch.csv`、`seeds/1_foundation/dim_channel.csv`、`seeds/1_foundation/dim_currency.csv`、`seeds/1_foundation/dim_risk_level.csv`、`seeds/1_foundation/dim_employee.csv` 和 `seeds/1_foundation/dim_product_category.csv`。
  - 生成方式：按种子导入总分支机构、业务渠道、币种、客户/产品/事件风险等级、员工和产品分类树；`dim_employee.permission_codes` 按 `employee_role` 从种子导入或派生；统计汇总口径使用种子中的 `ALL` 行或由程序补齐。
  - 关键约束：机构层级、渠道状态、币种启用状态、风险等级类型和员工归属必须闭环。
- 账户与服务产品组
  - 来源：导入 `seeds/2_product/account_product.csv` 和 `seeds/2_product/service_product.csv`。
  - 生成方式：按种子导入账户产品和服务产品，并校验产品分类和币种引用。
  - 关键约束：产品分类类型必须与产品域一致，启用产品才能被后续业务引用。
- 贷款产品组
  - 来源：导入 `seeds/2_product/loan_product.csv`、`seeds/2_product/loan_product_eligibility_rule.csv`、`seeds/2_product/loan_product_rate_tier.csv` 和 `seeds/2_product/loan_product_required_material.csv`。
  - 生成方式：按种子导入消费贷、经营贷、现金贷和分期贷，并通过抵押质押标志、保证担保标志区分信用贷、抵押贷和担保贷。
  - 关键约束：产品金额、期限、利率区间有效；启用贷款产品必须存在准入规则、利率档位和必需材料。
- 理财产品组
  - 来源：`wealth_product` 和 `wealth_settlement_rule` 导入 `seeds/2_product` 下对应 CSV，`wealth_open_period`、`wealth_trade_calendar`、`wealth_nav` 和 `wealth_product_notice` 由程序生成。
  - 生成方式：按种子导入现金管理、固定收益、混合型、权益型和结构性理财产品及清算规则，再按产品状态、运行基准日和交易日历规则生成开放期、交易日历、净值和公告。
  - 关键约束：产品风险等级、起购金额、净值日期、开放期和清算规则必须一致。
- 规则指标组
  - 来源：导入 `seeds/3_rule/risk_rule.csv`、`seeds/3_rule/risk_strategy.csv`、`seeds/3_rule/risk_strategy_rule_rel.csv` 和 `seeds/3_rule/business_metric_dict.csv`。
  - 生成方式：按种子导入风控规则、风控策略、策略规则关系和业务指标字典。
  - 关键约束：启用策略必须关联启用规则；业务指标编码、统计域、单位和计算口径必须固定。

Checklist：

- [x] 生成基础维度和统计汇总行。
- [x] 生成账户产品、服务产品、贷款产品和理财产品。
- [x] 生成贷款准入、利率和材料配置。
- [x] 生成理财开放期、交易日历、清算规则、净值和公告。
- [x] 生成风控规则、风控策略、策略规则关系和业务指标字典。
- [x] 执行 Layer1 层级、唯一性、产品启用状态、规则启用状态、指标编码和风险等级匹配校验。

### 阶段 2：Layer2 客户主数据
- 目标：生成个人客户、企业客户、实名、KYC、联系方式、设备、风险测评、标签和客户状态历史。
- 处理表：`customer`、`customer_status_history`、`customer_identity`、`customer_contact`、`customer_device`、`customer_kyc`、`enterprise_profile`、`beneficial_owner`、`customer_risk_assessment`、`customer_tag`、`customer_tag_rel`
- 程序生成表：`customer`、`customer_status_history`、`customer_identity`、`customer_contact`、`customer_device`、`customer_kyc`、`enterprise_profile`、`beneficial_owner`、`customer_risk_assessment`、`customer_tag`、`customer_tag_rel`
- 前置依赖表：`dim_branch`、`dim_channel`、`dim_currency`、`dim_risk_level`、`dim_employee`

表级说明：

- 客户主体组
  - 来源：程序生成。
  - 生成方式：按个人客户和企业客户生成客户主体，客户状态按字段分布口径覆盖正常、冻结、限制和销户。
  - 关键约束：客户编号唯一，客户类型与实名信息、企业档案和状态历史匹配。
- 实名与 KYC 组
  - 来源：程序生成。
  - 生成方式：为个人客户生成个人证件实名信息，为企业客户生成企业证件实名信息、企业档案和受益所有人，再生成 KYC 审核结果。
  - 关键约束：每个激活客户必须具备有效实名和 KYC；企业受益所有人持股比例合计不超过 `100%`。
- 联系方式与设备组
  - 来源：程序生成。
  - 生成方式：生成手机号、邮箱、地址和常用设备，线上客户必须具备登录设备。
  - 关键约束：每个有效客户至少一个已验证主手机号；设备指纹和设备状态可追溯。
- 风险测评与标签组
  - 来源：程序生成。
  - 生成方式：生成客户风险测评、客户标签和客户标签关系。
  - 关键约束：同一客户同一时间只有一条有效风险测评；规则、模型和导入来源必须保留追溯信息。

Checklist：

- [x] 生成个人客户和企业客户。
- [x] 生成实名、企业档案、受益所有人和 KYC。
- [x] 生成联系方式、设备、风险测评和标签关系。
- [x] 生成客户状态历史。
- [x] 执行 Layer2 客户规模、客户身份、联系方式唯一性、KYC 有效性、企业受益所有人和字段分布校验。

### 阶段 3：Layer3 账户、普通交易与对账
- 目标：基于客户和账户产品生成账户、银行卡、普通账户交易、渠道流水、账户流水、当前层资金冻结、冻结操作、对账和调账数据。
- 处理表：`bank_account`、`bank_account_status_history`、`bank_card`、`account_transaction`、`channel_transaction`、`account_ledger`、`fund_freeze`、`fund_freeze_operation`、`reconciliation_batch`、`reconciliation_result`、`reconciliation_adjustment`
- 程序生成表：`bank_account`、`bank_account_status_history`、`bank_card`、`account_transaction`、`channel_transaction`、`account_ledger`、`fund_freeze`、`fund_freeze_operation`、`reconciliation_batch`、`reconciliation_result`、`reconciliation_adjustment`
- 前置依赖表：`customer`、`account_product`、`dim_branch`、`dim_channel`、`dim_currency`、`dim_employee`

表级说明：

- 账户与银行卡组
  - 来源：程序生成。
  - 生成方式：为有效客户生成银行账户和借记卡或虚拟卡，并写入账户状态历史。
  - 关键约束：账户客户、账户产品、币种和机构必须匹配；卡片客户必须与绑定账户客户一致。
- 普通交易与流水组
  - 来源：程序生成。
  - 生成方式：生成转账、消费、充值、提现、退款和冲正等普通账户交易，成功交易同步生成账户流水。
  - 关键约束：交易金额、手续费、账户余额、冻结金额和账户流水必须形成借贷闭环。
- 渠道与对账组
  - 来源：程序生成。
  - 生成方式：为线上交易、开放银行交易和合作渠道交易生成渠道流水，再按渠道和日期生成对账批次、结果和调账记录。
  - 关键约束：渠道订单号、请求号和交易号在同一渠道下唯一；对账差错必须能追溯处理结果或调账交易。
- 当前层资金冻结组
  - 来源：程序生成。
  - 生成方式：仅为普通账户交易和司法冻结生成冻结记录和操作明细。
  - 关键约束：冻结金额不得超过可用余额；冻结关联对象必须在 Layer3 已生成；每次冻结状态或金额变化必须写入操作明细。

Checklist：

- [x] 生成账户、账户状态历史和银行卡。
- [x] 生成普通账户交易、渠道流水和账户流水。
- [x] 生成当前层资金冻结和冻结操作明细。
- [x] 生成对账批次、对账结果和调账记录。
- [x] 执行 Layer3 账户余额、流水借贷、冻结金额、渠道唯一性、对账闭环和字段分布校验。

### 阶段 4：Layer4 理财业务闭环
- 目标：基于客户风险测评、银行账户和理财产品生成理财申购、赎回、撤单、持仓、收益和理财资金流水。
- 处理表：`wealth_order`、`wealth_position`、`wealth_income`、`account_transaction`、`channel_transaction`、`account_ledger`、`fund_freeze`、`fund_freeze_operation`、`reconciliation_batch`、`reconciliation_result`、`reconciliation_adjustment`、`bank_account`
- 追加写入表：`account_transaction`、`channel_transaction`、`account_ledger`、`fund_freeze`、`fund_freeze_operation`、`reconciliation_batch`、`reconciliation_result`、`reconciliation_adjustment`
- 状态快照表：`bank_account`、`wealth_order`、`wealth_income`
- 程序生成表：`wealth_order`、`wealth_position`、`wealth_income`
- 程序追加写入表：`account_transaction`、`channel_transaction`、`account_ledger`、`fund_freeze`、`fund_freeze_operation`、`reconciliation_batch`、`reconciliation_result`、`reconciliation_adjustment`
- 程序状态快照表：`bank_account`、`wealth_order`、`wealth_income`
- 前置依赖表：`customer`、`customer_identity`、`customer_kyc`、`customer_risk_assessment`、`bank_account`、`wealth_product`、`wealth_open_period`、`wealth_trade_calendar`、`wealth_settlement_rule`、`wealth_nav`、`dim_channel`、`dim_currency`、`dim_employee`

表级说明：

- 理财订单组
  - 来源：程序生成。
  - 生成方式：按客户风险等级、产品风险等级、开放期和交易日历生成申购、赎回和撤单订单。
  - 关键约束：订单客户风险等级必须满足产品适当性要求；申购金额必须满足起购和递增金额规则。
- 理财资金组
  - 来源：程序生成。
  - 生成方式：申购提交时生成理财申购冻结，确认成功时生成账户扣款交易、渠道流水、账户流水、冻结释放操作和对账结果；申购失败或撤单时生成冻结释放或取消操作；赎回确认时生成到账交易、渠道流水、账户流水和对账结果。
  - 关键约束：`wealth_order.transaction_id` 和 `wealth_order.freeze_id` 必须引用同层追加写入的资金记录；冻结、交易、渠道流水和对账结果的客户、账户、币种、金额必须与订单一致，失败或撤单订单不得残留有效冻结金额。
- 理财持仓组
  - 来源：程序生成。
  - 生成方式：申购确认后生成或更新持仓，赎回确认后扣减持仓份额。
  - 关键约束：可用份额等于总份额减冻结份额；赎回份额不得超过可用份额。
- 理财收益组
  - 来源：程序生成。
  - 生成方式：按持仓、净值和收益计算口径生成每日收益，已结转收益生成账户交易、渠道流水、账户流水和对账结果。
  - 关键约束：收益日期不得早于持仓确认日期；已结转收益必须能追溯到账户资金变化和对账结果。

Checklist：

- [x] 生成理财申购、赎回和撤单订单。
- [x] 生成理财申购冻结、扣款交易、赎回到账交易、渠道流水、账户流水和对账结果。
- [x] 生成理财持仓和收益记录。
- [x] 执行 Layer4 适当性、开放期、确认日、持仓份额、收益结转、资金流水和理财风险分布校验。

### 阶段 5：Layer5 信贷授信与放款
- 目标：基于客户、贷款产品和账户生成授信、贷款申请、审批、合同、签署、担保、抵押、放款和放款资金流水。
- 处理表：`credit_application`、`credit_application_material`、`credit_approval_record`、`credit_limit`、`credit_limit_change_log`、`loan_application`、`loan_application_material`、`credit_assessment`、`loan_approval_record`、`loan_contract`、`loan_contract_document`、`contract_sign_record`、`collateral_asset`、`guarantee_record`、`loan_disbursement`、`account_transaction`、`channel_transaction`、`account_ledger`、`reconciliation_batch`、`reconciliation_result`、`reconciliation_adjustment`、`bank_account`
- 追加写入表：`account_transaction`、`channel_transaction`、`account_ledger`、`reconciliation_batch`、`reconciliation_result`、`reconciliation_adjustment`
- 状态快照表：`bank_account`、`credit_limit`、`loan_contract`
- 程序生成表：`credit_application`、`credit_application_material`、`credit_approval_record`、`credit_limit`、`credit_limit_change_log`、`loan_application`、`loan_application_material`、`credit_assessment`、`loan_approval_record`、`loan_contract`、`loan_contract_document`、`contract_sign_record`、`collateral_asset`、`guarantee_record`、`loan_disbursement`
- 程序追加写入表：`account_transaction`、`channel_transaction`、`account_ledger`、`reconciliation_batch`、`reconciliation_result`、`reconciliation_adjustment`
- 程序状态快照表：`bank_account`、`credit_limit`、`loan_contract`
- 前置依赖表：`customer`、`customer_identity`、`customer_contact`、`customer_kyc`、`enterprise_profile`、`beneficial_owner`、`bank_account`、`loan_product`、`loan_product_eligibility_rule`、`loan_product_rate_tier`、`loan_product_required_material`、`dim_employee`、`dim_channel`、`dim_currency`、`dim_risk_level`

表级说明：

- 授信组
  - 来源：程序生成。
  - 生成方式：为完成实名和 KYC 的客户生成授信申请、授信申请材料、征信评估、授信审批、授信额度和授予类额度流水。
  - 关键约束：授信征信授权材料必须早于授信评估；授信审批通过后必须生成或更新授信额度；额度可用金额必须等于总额度减已用额度减冻结额度。
- 贷款申请组
  - 来源：程序生成。
  - 生成方式：基于有效授信额度生成贷款申请、申请材料、征信评估和贷款审批记录，申请受理后生成额度冻结流水。
  - 关键约束：贷款申请金额、期限、利率和材料必须满足贷款产品规则；额度冻结流水必须关联已生成贷款申请；申请取消、拒绝或过期后必须生成额度解冻流水或最终额度状态。
- 合同签署组
  - 来源：程序生成。
  - 生成方式：为终审通过申请生成贷款合同、合同文件和签署记录。
  - 关键约束：合同客户、产品、币种、期限、利率和最终审批结果一致；签署完成后不得提前占用额度。
- 担保抵押与放款组
  - 来源：程序生成。
  - 生成方式：为抵押贷生成抵押质押资产，为担保贷生成担保记录，为已签约合同生成放款记录、额度占用流水、账户交易、渠道流水、账户流水和对账结果。
  - 关键约束：放款金额不得超过合同本金；放款成功必须生成额度占用流水、账户交易、渠道流水、账户流水、对账结果并更新合同状态。

Checklist：

- [x] 生成授信申请、授信材料、授信评估、审批、授信额度和授予类额度流水。
- [x] 生成贷款申请、材料、征信评估、审批记录和额度冻结流水。
- [x] 生成贷款合同、合同文件和签署记录。
- [x] 生成担保、抵押质押、放款记录、额度占用流水、放款交易、渠道流水、账户流水和对账结果。
- [x] 执行 Layer5 准入规则、额度流水、审批链路、签署状态、放款资金和审批分布校验。

### 阶段 6：Layer6 正常还款、逾期与费用减免
- 目标：基于已放款合同生成还款计划、账单、还款授权、正常还款记录、分配明细、逾期记录、费用减免和正常还款资金流水。
- 处理表：`repayment_schedule`、`repayment_bill`、`repayment_authorization`、`repayment_record`、`repayment_allocation`、`overdue_record`、`fee_reduction`、`account_transaction`、`channel_transaction`、`account_ledger`、`reconciliation_batch`、`reconciliation_result`、`reconciliation_adjustment`、`credit_limit_change_log`、`bank_account`、`loan_contract`、`credit_limit`
- 追加写入表：`account_transaction`、`channel_transaction`、`account_ledger`、`reconciliation_batch`、`reconciliation_result`、`reconciliation_adjustment`、`credit_limit_change_log`
- 状态快照表：`bank_account`、`loan_contract`、`credit_limit`、`repayment_bill`
- 程序生成表：`repayment_schedule`、`repayment_bill`、`repayment_authorization`、`repayment_record`、`repayment_allocation`、`overdue_record`、`fee_reduction`
- 程序追加写入表：`account_transaction`、`channel_transaction`、`account_ledger`、`reconciliation_batch`、`reconciliation_result`、`reconciliation_adjustment`、`credit_limit_change_log`
- 程序状态快照表：`bank_account`、`loan_contract`、`credit_limit`、`repayment_bill`
- 前置依赖表：`customer`、`loan_contract`、`loan_disbursement`、`credit_limit`、`bank_account`、`account_transaction`、`dim_channel`、`dim_employee`、`dim_currency`

表级说明：

- 还款计划与账单组
  - 来源：程序生成。
  - 生成方式：按合同期限、还款方式、放款日期和金额计算口径生成还款计划，再按出账日生成账单。
  - 关键约束：还款计划本金合计必须等于合同已放款本金或重组后剩余本金；账单金额必须与还款计划一致。
- 正常还款组
  - 来源：程序生成。
  - 生成方式：为自动扣款和代扣合同生成授权记录，再生成正常还款、自动扣款、提前还款、部分还款和冲正记录。
  - 关键约束：成功还款必须生成账户交易、渠道流水、账户流水和对账结果；还款金额必须等于分项金额合计；催收回款只在 Layer7 生成。
- 还款分配组
  - 来源：程序生成。
  - 生成方式：将还款金额分配到账单、期次、本金、利息、费用和罚息。
  - 关键约束：同一还款记录的分配总额必须等于还款金额。
- 逾期与减免组
  - 来源：程序生成。
  - 生成方式：对超过到期日且未结清账单生成逾期记录，并为部分逾期账单生成费用减免。
  - 关键约束：逾期金额、逾期天数、逾期阶段和账单状态必须一致；减免审批通过后必须形成账单最终金额口径。
- 合同与额度状态组
  - 来源：程序生成。
  - 生成方式：还款成功后生成合同剩余本金、合同状态、逾期状态和授信额度释放流水的最终状态口径。
  - 关键约束：合同剩余本金不得小于 `0`；额度释放流水必须关联对应还款和合同。

Checklist：

- [x] 生成还款计划和还款账单。
- [x] 生成还款授权、正常还款记录、还款交易、渠道流水、账户流水和对账结果。
- [x] 生成还款分配明细、逾期记录和费用减免。
- [x] 生成合同余额、合同状态、账单金额、逾期状态和授信额度释放流水。
- [x] 执行 Layer6 计划本金、账单金额、还款入账、分配总额、逾期状态、合同余额和还款表现分布校验。

### 阶段 7：Layer7 风控、反洗钱与催收处置
- 目标：基于客户、交易、理财、信贷、还款和逾期数据生成风险事件、命中记录、黑名单、反洗钱、人工复核、催收、催收回款和处置结果。
- 处理表：`risk_event`、`risk_hit_record`、`blacklist_record`、`aml_case`、`aml_case_transaction`、`suspicious_transaction_report`、`aml_review_result`、`manual_review_task`、`collection_case`、`collection_action`、`collection_contact_record`、`repayment_promise`、`legal_case`、`loan_write_off`、`loan_restructure`、`collateral_disposal`、`collection_performance_daily`、`customer_status_history`、`bank_account_status_history`、`fund_freeze`、`fund_freeze_operation`、`repayment_record`、`repayment_allocation`、`repayment_schedule`、`account_transaction`、`channel_transaction`、`account_ledger`、`reconciliation_batch`、`reconciliation_result`、`reconciliation_adjustment`、`credit_limit_change_log`、`customer`、`bank_account`、`loan_contract`、`repayment_bill`、`overdue_record`、`credit_limit`、`collateral_asset`
- 追加写入表：`customer_status_history`、`bank_account_status_history`、`fund_freeze`、`fund_freeze_operation`、`repayment_record`、`repayment_allocation`、`repayment_schedule`、`account_transaction`、`channel_transaction`、`account_ledger`、`reconciliation_batch`、`reconciliation_result`、`reconciliation_adjustment`、`credit_limit_change_log`
- 状态快照表：`customer`、`bank_account`、`loan_contract`、`repayment_bill`、`overdue_record`、`credit_limit`、`collateral_asset`、`repayment_promise`、`collection_case`、`repayment_schedule`
- 程序生成表：`risk_event`、`risk_hit_record`、`blacklist_record`、`aml_case`、`aml_case_transaction`、`suspicious_transaction_report`、`aml_review_result`、`manual_review_task`、`collection_case`、`collection_action`、`collection_contact_record`、`repayment_promise`、`legal_case`、`loan_write_off`、`loan_restructure`、`collateral_disposal`
- 明细回算表：`collection_performance_daily`
- 程序追加写入表：`customer_status_history`、`bank_account_status_history`、`fund_freeze`、`fund_freeze_operation`、`repayment_record`、`repayment_allocation`、`repayment_schedule`、`account_transaction`、`channel_transaction`、`account_ledger`、`reconciliation_batch`、`reconciliation_result`、`reconciliation_adjustment`、`credit_limit_change_log`
- 程序状态快照表：`customer`、`bank_account`、`loan_contract`、`repayment_bill`、`overdue_record`、`credit_limit`、`collateral_asset`、`repayment_promise`、`collection_case`、`repayment_schedule`
- 前置依赖表：`customer`、`bank_account`、`account_transaction`、`wealth_order`、`loan_application`、`loan_contract`、`repayment_schedule`、`repayment_bill`、`overdue_record`、`credit_limit`、`risk_rule`、`risk_strategy`、`dim_branch`、`dim_employee`、`dim_channel`、`dim_currency`、`dim_risk_level`、`collateral_asset`

表级说明：

- 风险事件组
  - 来源：程序生成。
  - 生成方式：从开户、交易、贷款申请、理财订单、反洗钱、可疑交易和催收场景抽样生成风险事件和命中记录。
  - 关键约束：风险事件客户必须与关联业务对象客户一致；命中规则必须引用 Layer1 已启用规则；人工复核决策必须生成复核任务；冻结决策必须追加状态历史或资金冻结操作。
- 反洗钱组
  - 来源：程序生成。
  - 生成方式：为可疑交易、名单命中、大额交易和异常行为生成 AML 案件、案件交易明细、复核结果和可疑交易报告。
  - 关键约束：需报送复核结果必须生成可疑交易报告；报告客户、交易范围、币种和金额必须与 AML 案件及交易明细一致。
- 催收处置组
  - 来源：程序生成。
  - 生成方式：为逾期中记录生成催收案件、催收动作、联系记录、承诺还款、法诉、核销、重组和抵押处置。
  - 关键约束：催收案件必须来自逾期中记录；处置结果必须与合同、客户、逾期和回款金额一致。
- 催收回款组
  - 来源：程序生成。
  - 生成方式：基于催收案件或承诺还款生成催收还款记录、还款分配、账户交易、渠道流水、账户流水和对账结果。
  - 关键约束：催收还款必须关联有效催收案件或承诺还款；催收回款后必须形成账单、逾期、合同和催收案件最终状态口径。
- 处置状态组
  - 来源：程序生成。
  - 生成方式：核销审批后生成逾期、合同和额度处置状态；重组生效后生成新版本还款计划；抵押处置完成后生成抵押资产状态和逾期回收金额。
  - 关键约束：状态对象必须与处置记录的合同、客户和币种一致；核销不生成账户资金交易；重组后新计划本金合计必须等于重组后剩余本金。
- 催收绩效组
  - 来源：明细回算。
  - 生成方式：按统计日、催收员、催收阶段和币种，从催收案件、联系记录、承诺还款和催收还款明细回算催收绩效日表。
  - 关键约束：绩效金额和数量必须能回溯到同日同催收员同阶段明细。

Checklist：

- [x] 生成风险事件、命中记录、黑名单和人工复核任务。
- [x] 生成 AML 案件、复核结果和可疑交易报告。
- [x] 生成催收案件、联系记录、承诺还款和处置结果。
- [x] 生成催收还款、还款分配、账户交易、渠道流水、账户流水和对账结果。
- [x] 生成合同、账单、还款计划、逾期、额度、催收案件和抵押资产处置状态。
- [x] 生成催收绩效日表。
- [x] 执行 Layer7 风险对象、命中规则、AML 报送、催收来源、处置金额、状态一致性和催收分布校验。

### 阶段 8：Layer8 运营支撑与日统计
- 目标：基于业务链路生成通知消息、客服工单、流程实例、流程任务、客户反馈和业务日统计。
- 处理表：`notification_message`、`support_ticket`、`support_ticket_feedback`、`workflow_instance`、`workflow_task`、`business_stat_daily`、`customer_status_history`、`bank_account_status_history`、`customer`、`bank_account`
- 追加写入表：`customer_status_history`、`bank_account_status_history`
- 状态快照表：`customer`、`bank_account`
- 程序生成表：`notification_message`、`support_ticket`、`support_ticket_feedback`、`workflow_instance`、`workflow_task`
- 程序回算生成表：`business_stat_daily`
- 程序追加写入表：`customer_status_history`、`bank_account_status_history`
- 程序状态快照表：`customer`、`bank_account`
- 前置依赖表：`customer`、`customer_contact`、`customer_device`、`bank_account`、`account_transaction`、`channel_transaction`、`wealth_order`、`wealth_position`、`credit_application`、`loan_application`、`loan_contract`、`loan_disbursement`、`repayment_bill`、`repayment_record`、`overdue_record`、`risk_event`、`collection_case`、`fee_reduction`、`manual_review_task`、`aml_review_result`、`business_metric_dict`、`dim_employee`、`dim_branch`、`dim_channel`、`dim_currency`

表级说明：

- 消息与工单组
  - 来源：程序生成。
  - 生成方式：为交易、理财、贷款、还款、催收和系统事件生成通知消息，并生成客服工单。
  - 关键约束：业务通知必须关联对应业务对象；客服工单必须关联已存在客户和业务对象；客服工单触发客户或账户状态变更时必须追加状态历史并形成当前状态口径。
- 流程组
  - 来源：程序生成。
  - 生成方式：为贷款审批、理财复核、费用减免、风控复核和已生成客服工单生成流程实例和流程任务。
  - 关键约束：流程实例必须关联有效业务对象；客服工单流程实例必须在客服工单生成后创建；流程任务完成时间不得晚于对应审批、复核或减免结果时间；任务完成后必须形成流程实例最终状态。
- 反馈组
  - 来源：程序生成。
  - 生成方式：为已解决或关闭工单生成通知消息或客户反馈。
  - 关键约束：工单解决后必须存在通知消息或 `support_ticket_feedback` 客户确认记录。
- 日统计组
  - 来源：程序回算生成。
  - 生成方式：按业务统计回算口径生成客户、账户、交易、理财、信贷、还款、风控和催收业务日统计。
  - 关键约束：统计指标必须在 Layer1 指标字典中定义；统计值必须能按同一日期、维度和过滤条件从明细数据重算。

Checklist：

- [x] 生成通知消息、客服工单和客户反馈。
- [x] 生成流程实例和流程任务。
- [x] 回算生成业务日统计。
- [x] 执行 Layer8 流程状态、消息关联、工单闭环、指标字典、统计追溯和汇总行校验。

### 阶段 9：最终验收
- 目标：对全量生成数据进行最终验收，覆盖规模、分布、唯一性、引用、时间、金额、状态、统计和近期数据有效性。
- 验收范围：全库数据。
- 生成表：无。

最终验收项：

- 关键表非空：确认客户、账户、交易、理财、信贷、还款、风控、催收和运营支撑核心表均非空。
- 规模达标：确认各层数据量满足标准规模口径或指定 `scale_factor` 后的目标规模。
- 字段分布达标：确认客户状态、渠道、交易状态、交易类型、贷款审批、还款表现、逾期和催收阶段满足字段分布口径。
- 全局唯一性：确认客户号、账户号、交易号、订单号、申请号、合同号、账单号、案件号、任务号等业务唯一键无重复。
- 跨域外键完整性：确认客户、账户、产品、交易、理财、信贷、还款、风控、催收和运营之间的外键引用全部闭环。
- 跨层追加写入一致：确认 Layer4 到 Layer7 追加写入的资金记录均引用同层已生成业务对象，不存在未来对象占位资金记录，渠道流水和对账结果覆盖所有成功账户交易。
- 时间顺序正确：确认开户注册、交易、订单、审批、签署、放款、出账、还款、逾期、催收和统计时间整体有序。
- 金额闭环成立：确认账户余额、冻结金额、交易流水、授信额度、放款、账单、还款、逾期、核销、重组、抵押处置和调账金额全部成立。
- 状态流转正确：确认客户、账户、交易、理财订单、贷款申请、合同、账单、逾期、催收和工单状态符合业务约束。
- 业务统计可追溯：确认日统计指标能按业务统计回算口径回溯到明细数据、阶段汇总或固定指标字典。
- 近期指标有效：确认最近 `30` 天存在新增客户、新增账户、新放款、交易、还款、风控、催收和客服工单数据。

Checklist：

- [x] 执行关键表非空校验。
- [x] 执行规模达标校验。
- [x] 执行字段分布校验。
- [x] 执行业务唯一键校验。
- [x] 执行跨域外键完整性校验。
- [x] 执行跨层追加写入一致性校验。
- [x] 执行全局时间顺序校验。
- [x] 执行金额闭环校验。
- [x] 执行状态流转一致性校验。
- [x] 执行业务统计追溯校验。
- [x] 执行近期指标有效性校验。

## 接口定义
本节定义金融业务系统对外部渠道、内部运营、风控审批、对账清算和数据分析暴露的业务接口。

### 1. 通用接口约定
| 项目         | 约定                                                                                   |
| ------------ | -------------------------------------------------------------------------------------- |
| 数据格式     | 请求和响应均使用 `application/json`，文件上传使用 `multipart/form-data`                |
| 字符编码     | `UTF-8`                                                                                |
| 金额格式     | 金额字段使用字符串传输，保留币种对应小数位，例如 `"1000.00"`                           |
| 日期时间格式 | 日期使用 `YYYY-MM-DD`，时间使用 ISO 8601 本地时间格式                                  |
| 认证方式     | 所有接口必须传 `Authorization`，客户端、员工端和系统间接口均从 Bearer token 解析调用身份 |
| 幂等控制     | 资金、订单、申请、审批、还款和调账类写接口必须传入 `request_no`                        |
| 分页参数     | 业务列表接口使用 `page_no`、`page_size`，基础配置、枚举、详情下钻和小结果集接口可不分页 |
| 追踪字段     | `X-Request-Id` 为请求追踪号，`X-Channel-Code` 为渠道编码，`X-Operator-No` 为人工操作人编号 |
| 响应结构     | `code`、`message`、`request_id`、`data`                                                |
| 关联表范围   | 接口总览的关联表列只列业务读写表，通用认证、权限和接口幂等记录不进入业务数据模型 |

身份确认约定：

- 客户端接口使用请求头 `Authorization: Bearer <customer_no>` 作为客户登录态，当前 `access_token` 直接使用客户号，客户号必须对应 `customer.customer_no` 且客户状态允许办理当前业务。
- 员工端接口使用请求头 `Authorization: Bearer <employee_no>` 作为员工登录态，当前 `access_token` 直接使用员工编号，员工编号必须对应 `dim_employee.employee_no` 且员工具备对应岗位角色和权限编码。
- 系统间接口使用请求头 `Authorization: Bearer <employee_no>` 作为调用方登录态，系统服务账号以员工编号维护在 `dim_employee.employee_no` 中，员工状态和岗位权限必须允许访问对应渠道、接口范围和业务。
- 请求头或请求体中的客户号、员工编号、账户号、订单号、合同号、账单号和案件号只作为业务参数使用，不能替代登录态。
- `X-Operator-No` 仅在员工端人工操作时必填，用于操作审计和业务留痕，不作为客户身份的唯一来源；客户身份以 `Authorization` 解析结果和请求体中的业务客户号校验结果为准。
- 涉及客户业务对象的接口必须校验登录客户、请求客户号、账户、订单、合同、账单或案件归属一致。
- 服务层必须按 `request_no`、渠道和业务类型维护接口幂等结果，记录请求摘要、业务编号和回放响应；接口幂等记录不进入本业务库表结构，重复请求时必须返回首次处理结果。

### 2. 接口业务约束
- 写接口必须校验渠道、机构、币种、产品、员工和客户状态有效性，停用或关闭对象不得承接新增业务。
- 客户、账户、订单、合同、账单、逾期、催收案件、工单和流程之间的引用必须满足数据定义中的主体一致性约束。
- 余额类资金交易写接口必须同步形成账户交易、渠道流水、账户流水和对账结果；生成对账结果前必须按渠道和交易日读取或创建 `reconciliation_batch`；失败交易不得生成账户流水。
- 冻结类资金变动写接口只生成资金冻结、冻结操作和账户冻结流水，不生成账户交易、渠道流水和对账结果。
- 贷款放款必须使用 `loan_disbursement.disbursement_amount` 作为金额来源；正常还款和催收回款必须使用 `repayment_bill`、`repayment_record` 和 `repayment_allocation` 金额作为来源；理财申购扣款、理财赎回到账和理财收益结转必须使用 `wealth_order.order_amount`、`wealth_position` 和 `wealth_income` 金额作为来源。
- 审批、复核、减免和流程任务接口必须保证处理结果、业务对象状态和完成时间一致。
- 幂等接口在相同 `request_no`、渠道和业务类型下重复提交时必须返回同一业务结果，不得重复生成 `account_transaction`、`channel_transaction`、`account_ledger`、业务订单、合同、账单或流程任务。
- 查询接口返回的多态业务对象必须包含 `related_type`、`related_id` 和可读业务编号。
- 统计接口返回值必须能按数据定义中的业务统计回算口径追溯到明细数据。

### 3. 基础配置接口
| 方法  | 路径                       | 接口说明         | 主要入参                                          | 主要出参                               | 关联表            |
| ----- | -------------------------- | ---------------- | ------------------------------------------------- | -------------------------------------- | ----------------- |
| `GET` | `/api/v1/branches`         | 查询可用机构树   | `branch_status`、`province`、`city`               | 机构层级、机构编码、机构名称、服务电话 | `dim_branch`      |
| `GET` | `/api/v1/channels`         | 查询可用业务渠道 | `channel_type`、`channel_status`                  | 渠道编码、渠道名称、渠道类型、启用状态 | `dim_channel`     |
| `GET` | `/api/v1/currencies`       | 查询可用币种     | `yn`                                              | 币种代码、币种名称、金额精度           | `dim_currency`    |
| `GET` | `/api/v1/risk-levels`      | 查询风险等级     | `risk_level_type`                                 | 等级编码、等级名称、评分区间、排序号   | `dim_risk_level`  |
| `GET` | `/api/v1/account-products` | 查询账户产品     | `account_type`、`currency_code`                   | 产品编码、账户类型、开户条件、限额     | `account_product` |
| `GET` | `/api/v1/service-products` | 查询服务产品     | `service_type`、`service_status`                  | 服务编码、服务费用、服务状态           | `service_product` |
| `GET` | `/api/v1/employees`        | 查询员工基础信息 | `employee_role`、`branch_code`、`employee_status` | 员工编号、姓名、机构、角色、权限编码   | `dim_employee`、`dim_branch` |

接口明细：

#### 3.1. `GET /api/v1/branches`
说明：查询可用于开户注册、账户管理、信贷审批和催收分案的机构树。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Query：`branch_status`、`province`、`city`
- Body：无

响应：

- `data.list[].branch_code`：机构编码
- `data.list[].branch_name`：机构名称
- `data.list[].branch_level`：机构层级
- `data.list[].province`：所在省份
- `data.list[].city`：所在城市
- `data.list[].service_phone`：客服电话
- `data.list[].branch_status`：机构状态
- `data.list[].children`：下级机构列表

内部步骤：

- 校验请求头中的渠道和操作员。
- 按机构状态、省份和城市过滤 `dim_branch`。
- 排除 `branch_code = ALL` 的统计汇总行。
- 按 `parent_id` 组装机构树。
- 返回机构编码、名称、层级、地区、客服电话和状态。

#### 3.2. `GET /api/v1/channels`
说明：查询开户、交易、贷款、理财和客服工单可使用的业务渠道。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Query：`channel_type`、`channel_status`
- Body：无

响应：

- `data.list[].channel_code`：渠道编码
- `data.list[].channel_name`：渠道名称
- `data.list[].channel_type`：渠道类型
- `data.list[].channel_status`：渠道状态
- `data.list[].yn`：启用标识

内部步骤：

- 校验请求头中的请求流水和操作员。
- 按渠道类型和渠道状态过滤 `dim_channel`。
- 排除 `channel_code = ALL` 的统计汇总行。
- 返回渠道编码、名称、类型、状态和启用标识。

#### 3.3. `GET /api/v1/currencies`
说明：查询账户、交易、贷款和理财产品可使用的币种。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Query：`yn`
- Body：无

响应：

- `data.list[].currency_code`：币种代码
- `data.list[].currency_name`：币种名称
- `data.list[].symbol`：币种符号
- `data.list[].precision_scale`：金额精度位数
- `data.list[].yn`：启用标识

内部步骤：

- 校验请求头中的渠道和操作员。
- 按启用标识过滤 `dim_currency`。
- 返回币种代码、名称、符号、金额精度和启用标识。
- 下游金额类接口按返回的 `precision_scale` 校验金额小数位。

#### 3.4. `GET /api/v1/risk-levels`
说明：查询客户风险等级、产品风险等级和风控事件风险等级。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Query：`risk_level_type`
- Body：无

响应：

- `data.list[].risk_level_code`：风险等级编码
- `data.list[].risk_level_name`：风险等级名称
- `data.list[].risk_level_type`：等级类型
- `data.list[].risk_score_min`：评分下限
- `data.list[].risk_score_max`：评分上限
- `data.list[].sort_no`：排序号
- `data.list[].yn`：启用标识

内部步骤：

- 校验请求头中的渠道和操作员。
- 按风险等级类型过滤 `dim_risk_level`。
- 仅返回启用或符合查询条件的风险等级。
- 按 `risk_level_type` 和 `sort_no` 排序返回。

#### 3.5. `GET /api/v1/account-products`
说明：查询可用于新开账户和账户变更的账户产品。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Query：`account_type`、`currency_code`
- Body：无

响应：

- `data.list[].product_code`：账户产品编码
- `data.list[].product_name`：账户产品名称
- `data.list[].account_type`：账户类型
- `data.list[].currency_code`：币种代码
- `data.list[].min_open_amount`：最低开户金额
- `data.list[].daily_transfer_limit`：日转账限额
- `data.list[].daily_withdraw_limit`：日提现限额
- `data.list[].product_status`：产品状态

内部步骤：

- 校验请求头中的渠道和操作员。
- 按账户类型和币种过滤 `account_product`。
- 校验产品关联的币种和产品分类处于有效状态。
- 仅返回可用于新增开户或账户变更的产品。

#### 3.6. `GET /api/v1/service-products`
说明：查询账户服务包、手续费服务和增值服务产品。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Query：`service_type`、`service_status`
- Body：无

响应：

- `data.list[].service_code`：服务产品编码
- `data.list[].service_name`：服务产品名称
- `data.list[].service_type`：服务类型
- `data.list[].fee_amount`：服务费用金额
- `data.list[].service_status`：服务状态

内部步骤：

- 校验请求头中的渠道和操作员。
- 按服务类型和服务状态过滤 `service_product`。
- 校验服务产品状态。
- 返回服务编码、名称、类型、服务费用和服务状态。

#### 3.7. `GET /api/v1/employees`
说明：查询审批、风控、催收、客服和运营处理人基础信息。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Query：`employee_role`、`branch_code`、`employee_status`
- Body：无

响应：

- `data.list[].employee_no`：员工编号
- `data.list[].employee_name`：员工姓名
- `data.list[].branch_code`：所属机构编码
- `data.list[].branch_name`：所属机构名称
- `data.list[].employee_role`：岗位角色
- `data.list[].permission_codes`：权限编码列表
- `data.list[].employee_status`：员工状态

内部步骤：

- 校验请求头中的渠道和操作员。
- 按员工角色、机构和员工状态过滤 `dim_employee`。
- 关联 `dim_branch` 补充所属机构名称和机构状态。
- 仅返回当前操作员有权查看的员工信息。

### 4. 客户接口
| 方法    | 路径                                               | 接口说明           | 主要入参                                                                   | 主要出参                               | 关联表                                                 |
| ------- | -------------------------------------------------- | ------------------ | -------------------------------------------------------------------------- | -------------------------------------- | ------------------------------------------------------ |
| `POST`  | `/api/v1/customers`                                | 创建个人或企业客户 | `request_no`、`customer_type`、客户基础信息、`branch_code`、`channel_code` | 客户号、客户状态、客户创建时间         | `customer`、`enterprise_profile`、`dim_branch`、`dim_channel` |
| `GET`   | `/api/v1/customers/{customer_no}`                  | 查询客户档案       | `customer_no`                                                              | 客户基础信息、状态、风险等级、KYC 状态 | `customer`、`customer_kyc`、`customer_risk_assessment` |
| `PATCH` | `/api/v1/customers/{customer_no}`                  | 更新客户基础信息   | `request_no`、`customer_no`、客户基础字段                                                 | 客户号、更新时间                       | `customer`                                             |
| `POST`  | `/api/v1/customers/{customer_no}/identities`       | 提交实名认证信息   | `request_no`、`customer_no`、证件类型、证件号、姓名、有效期                               | 证件号码、认证状态                     | `customer`、`customer_identity`                        |
| `POST`  | `/api/v1/customers/{customer_no}/contacts`         | 新增客户联系方式   | `request_no`、`customer_no`、联系方式类型、联系方式、是否默认                             | 联系方式 ID、验证标识                  | `customer`、`customer_contact`                         |
| `POST`  | `/api/v1/customers/{customer_no}/devices`          | 绑定客户设备       | `request_no`、`customer_no`、设备编号、设备类型、设备指纹、推送令牌                       | 设备编号、可信标识、风险状态           | `customer`、`customer_device`                          |
| `POST`  | `/api/v1/customers/{customer_no}/kyc`              | 提交 KYC 信息      | `request_no`、`customer_no`、职业、行业、年收入、收入币种、资金来源、就业状态             | KYC ID、KYC 状态、合规状态             | `customer`、`customer_kyc`                             |
| `POST`  | `/api/v1/customers/{customer_no}/beneficial-owners` | 维护企业受益人     | `request_no`、`customer_no`、受益人类型、姓名、证件信息、持股比例、控制关系、授权有效期   | 受益人 ID、核验状态                    | `customer`、`beneficial_owner`                         |
| `POST`  | `/api/v1/customers/{customer_no}/risk-assessments` | 提交客户风险测评   | `request_no`、`customer_no`、测评类型、评分、生效时间、失效时间                           | 测评编号、评分、风险等级               | `customer`、`customer_risk_assessment`、`dim_risk_level` |
| `POST`  | `/api/v1/customers/{customer_no}/tags`             | 维护客户标签       | `request_no`、`customer_no`、标签编码、标签来源                                           | 标签关系 ID、标签编码                  | `customer`、`customer_tag`、`customer_tag_rel`         |
| `GET`   | `/api/v1/customers/{customer_no}/status-history`   | 查询客户状态历史   | `customer_no`、时间范围                                                    | 状态变更记录列表                       | `customer_status_history`                              |

接口明细：

#### 4.1. `POST /api/v1/customers`
说明：创建个人或企业客户。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Body：`request_no`、`customer_type`、客户基础信息、`branch_code`、`channel_code`

响应：

- `data.customer_no`：客户号
- `data.customer_status`：客户状态
- `data.created_at`：客户创建时间
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、客户创建权限和请求字段格式。
- 读取并校验 `dim_branch`、`dim_channel` 和客户唯一性。
- 校验客户主体、机构、渠道、客户类型和创建时间一致。
- 在同一事务内写入 `customer`；企业客户同步写入 `enterprise_profile`。
- 返回客户号、客户状态、客户创建时间。

#### 4.2. `GET /api/v1/customers/{customer_no}`
说明：查询客户档案。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`customer_no`
- Query：无
- Body：无

响应：

- `data.customer_profile`：客户基础信息
- `data.customer_status`：客户状态
- `data.risk_level`：风险等级
- `data.kyc_status`：KYC 状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 customer、customer_kyc、customer_risk_assessment。
- 校验返回对象在当前渠道和操作员权限范围内。
- 组装客户基础信息、客户状态、风险等级、KYC 状态并返回。

#### 4.3. `PATCH /api/v1/customers/{customer_no}`
说明：更新客户基础信息。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`customer_no`
- Body：`request_no`、客户基础字段

响应：

- `data.customer_no`：客户号
- `data.updated_at`：更新时间
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、客户资料维护权限和请求字段格式。
- 读取并锁定 `customer`。
- 校验客户状态、主体一致性、资料更新时间和业务权限。
- 在同一事务内更新 `customer` 基础字段和更新时间。
- 返回客户号、更新时间。

#### 4.4. `POST /api/v1/customers/{customer_no}/identities`
说明：提交实名认证信息。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`customer_no`
- Body：`request_no`、证件类型、证件号、姓名、有效期

响应：

- `data.identity_no`：证件号码
- `data.verification_status`：认证状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、实名认证提交权限和请求字段格式。
- 读取并锁定 `customer` 和既有 `customer_identity`。
- 校验客户状态、证件主体、证件有效期和实名认证权限。
- 在同一事务内写入或更新 `customer_identity`。
- 返回证件号码、认证状态。

#### 4.5. `POST /api/v1/customers/{customer_no}/contacts`
说明：新增客户联系方式。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`customer_no`
- Body：`request_no`、联系方式类型、联系方式、是否默认

响应：

- `data.contact_id`：联系方式 ID
- `data.verified_flag`：验证标识
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号和请求字段格式。
- 读取并锁定 `customer` 和既有 `customer_contact`。
- 校验客户状态、联系方式格式、默认联系方式唯一性和维护权限。
- 在同一事务内写入或更新 `customer_contact`。
- 返回联系方式 ID、验证标识。

#### 4.6. `POST /api/v1/customers/{customer_no}/devices`
说明：绑定客户设备。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`customer_no`
- Body：`request_no`、设备编号、设备类型、设备指纹、推送令牌

响应：

- `data.device_no`：设备编号
- `data.trusted_flag`：可信设备标识
- `data.risk_status`：设备风险状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号和请求字段格式。
- 读取并锁定 `customer` 和既有 `customer_device`。
- 校验客户状态、设备编号、设备指纹唯一性和绑定权限。
- 在同一事务内写入或更新 `customer_device`。
- 返回设备编号、可信设备标识、设备风险状态。

#### 4.7. `POST /api/v1/customers/{customer_no}/kyc`
说明：提交 KYC 信息。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`customer_no`
- Body：`request_no`、职业、行业、年收入、收入币种、资金来源、就业状态

响应：

- `data.kyc_id`：KYC ID
- `data.kyc_status`：KYC 状态
- `data.compliance_status`：合规状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号和请求字段格式。
- 读取并锁定 `customer` 和既有 `customer_kyc`。
- 校验客户状态、KYC 字段完整性、收入币种和提交权限。
- 在同一事务内写入或更新 `customer_kyc`。
- 返回 KYC ID、KYC 状态、合规状态。

#### 4.8. `POST /api/v1/customers/{customer_no}/beneficial-owners`
说明：维护企业受益人。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`customer_no`
- Body：`request_no`、受益人类型、姓名、证件信息、持股比例、控制关系、授权有效期

响应：

- `data.beneficial_owner_id`：受益人 ID
- `data.verification_status`：核验状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、企业受益人维护权限和请求字段格式。
- 校验客户为企业客户，且企业主体、证件信息和受益人类型符合企业 KYC 要求。
- 授权经办人必须校验授权有效期开始日期和结束日期。
- 在同一事务内写入或更新 `beneficial_owner`，并校验企业客户至少存在一名法定代表人，且至少存在一名实际控制人或持股比例大于等于 25 的股东。
- 返回受益人 ID、核验状态。

#### 4.9. `POST /api/v1/customers/{customer_no}/risk-assessments`
说明：提交客户风险测评。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`customer_no`
- Body：`request_no`、测评类型、评分、生效时间、失效时间

响应：

- `data.assessment_no`：测评编号
- `data.score`：评分
- `data.risk_level`：风险等级
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号和请求字段格式。
- 读取并锁定 `customer`、既有 `customer_risk_assessment` 和 `dim_risk_level`。
- 校验客户状态、评分区间、生效时间、失效时间和测评权限。
- 在同一事务内写入 `customer_risk_assessment` 并更新客户风险等级。
- 返回测评编号、评分、风险等级。

#### 4.10. `POST /api/v1/customers/{customer_no}/tags`
说明：维护客户标签。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`customer_no`
- Body：`request_no`、标签编码、标签来源

响应：

- `data.tag_rel_id`：标签关系 ID
- `data.tag_code`：标签编码
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号和请求字段格式。
- 读取并锁定 `customer`、`customer_tag` 和既有 `customer_tag_rel`。
- 校验客户状态、标签状态、标签来源和维护权限。
- 在同一事务内写入或更新 `customer_tag_rel`。
- 返回标签关系 ID、标签编码。

#### 4.11. `GET /api/v1/customers/{customer_no}/status-history`
说明：查询客户状态历史。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`customer_no`
- Query：时间范围
- Body：无

响应：

- `data.list[]`：状态变更记录列表
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 customer_status_history。
- 校验返回对象在当前渠道和操作员权限范围内。
- 组装状态变更记录列表并返回。

### 5. 账户与交易接口
| 方法   | 路径                                           | 接口说明         | 主要入参                                                                                    | 主要出参                           | 关联表                                                                |
| ------ | ---------------------------------------------- | ---------------- | ------------------------------------------------------------------------------------------- | ---------------------------------- | --------------------------------------------------------------------- |
| `POST` | `/api/v1/accounts`                             | 开立银行账户     | `request_no`、`customer_no`、`product_code`、`currency_code`、`branch_code`、`channel_code` | 账户号、账户状态、开户时间         | `bank_account`、`bank_account_status_history`、`customer`、`account_product`、`dim_currency`、`dim_branch`、`dim_channel` |
| `GET`  | `/api/v1/accounts/{account_no}`                | 查询账户详情     | `account_no`                                                                                | 账户状态、余额、冻结金额、开户产品 | `bank_account`、`account_product`                                     |
| `GET`  | `/api/v1/customers/{customer_no}/accounts`     | 查询客户账户列表 | `customer_no`、`account_status`                                                             | 账户列表、余额、币种、产品         | `bank_account`、`account_product`                                     |
| `POST` | `/api/v1/accounts/{account_no}/cards`          | 绑定银行卡       | `request_no`、`account_no`、卡类型、卡介质                                                  | 卡号、卡状态、发卡时间             | `bank_card`、`bank_account`                                           |
| `POST` | `/api/v1/accounts/{account_no}/status-changes` | 变更账户状态     | `request_no`、`account_no`、目标状态、原因                                                              | 状态变更记录号、当前状态           | `bank_account_status_history`、`bank_account`                         |
| `POST` | `/api/v1/transactions`                         | 发起普通账户交易 | `request_no`、`customer_no`、`account_no`、交易类型、金额、币种、收付款信息、关联对象类型、关联对象编号 | 交易编号、交易状态、渠道流水号、关联对象 | `account_transaction`、`channel_transaction`、`account_ledger`、`reconciliation_batch`、`reconciliation_result`、`customer`、`bank_account`、`loan_contract`、`repayment_bill`、`wealth_order`、`wealth_income`、`risk_event` |
| `GET`  | `/api/v1/transactions/{transaction_no}`        | 查询账户交易详情 | `transaction_no`                                                                            | 交易状态、金额、渠道流水、对账状态 | `account_transaction`、`channel_transaction`、`reconciliation_result` |
| `GET`  | `/api/v1/accounts/{account_no}/transactions`   | 查询账户交易明细 | `account_no`、时间范围、交易类型、交易状态、`page_no`、`page_size`                           | 交易明细列表                       | `account_transaction`                                                 |
| `GET`  | `/api/v1/accounts/{account_no}/ledgers`        | 查询账户资金流水 | `account_no`、时间范围、流水类型、`page_no`、`page_size`                                     | 账户流水列表、交易后余额           | `account_ledger`                                                      |
| `POST` | `/api/v1/fund-freezes`                         | 新增资金冻结     | `request_no`、`account_no`、冻结金额、冻结原因、冻结关联对象类型、冻结关联对象编号          | 冻结编号、冻结状态                 | `fund_freeze`、`fund_freeze_operation`、`account_ledger`、`bank_account`、`customer`、`account_transaction`、`wealth_order`、`loan_contract`、`repayment_bill`、`risk_event` |
| `POST` | `/api/v1/fund-freezes/{freeze_no}/operations`  | 解冻或释放冻结   | `request_no`、`freeze_no`、操作类型、金额、原因                                             | 操作编号、冻结余额、冻结状态       | `fund_freeze_operation`、`fund_freeze`、`account_ledger`、`bank_account`、`account_transaction`、`wealth_order`、`loan_contract`、`repayment_bill`、`risk_event` |
| `POST` | `/api/v1/reconciliation/batches`               | 创建对账批次     | `request_no`、`channel_code`、`reconcile_date`                                              | 批次号、批次状态                   | `reconciliation_batch`、`dim_channel`                                 |
| `POST` | `/api/v1/reconciliation/results`               | 写入对账结果     | `request_no`、批次号、账户交易号、渠道流水号、匹配结果                                      | 对账结果编号、处理状态             | `reconciliation_batch`、`account_transaction`、`channel_transaction`、`reconciliation_result` |
| `POST` | `/api/v1/reconciliation/adjustments`           | 发起调账         | `request_no`、对账结果编号、调账金额、调账原因                                              | 调账编号、调账状态                 | `reconciliation_adjustment`、`reconciliation_result`、`account_transaction`、`channel_transaction` |
| `POST` | `/api/v1/reconciliation/adjustments/{adjustment_no}/approval` | 审批调账 | `request_no`、`adjustment_no`、审批结果、审批金额、审批意见                                    | 调账编号、调账状态                 | `reconciliation_adjustment`                                           |
| `POST` | `/api/v1/reconciliation/adjustments/{adjustment_no}/post` | 调账入账 | `request_no`、`adjustment_no`、入账账户、入账金额、入账日期                                      | 调账编号、调账状态、交易编号       | `reconciliation_adjustment`、`account_transaction`、`channel_transaction`、`account_ledger`、`reconciliation_batch`、`reconciliation_result` |

接口明细：

#### 5.1. `POST /api/v1/accounts`
说明：开立银行账户。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Body：`request_no`、`customer_no`、`product_code`、`currency_code`、`branch_code`、`channel_code`

响应：

- `data.account_no`：账户号
- `data.account_status`：账户状态
- `data.opened_at`：开户时间
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、开户权限和请求字段格式。
- 读取并锁定 `customer`、`account_product`、`dim_currency`、`dim_branch` 和 `dim_channel`。
- 校验客户、产品、币种、机构、渠道、账户类型和开户时间一致。
- 在同一事务内写入 `bank_account` 和初始 `bank_account_status_history`。
- 返回账户号、账户状态、开户时间。

#### 5.2. `GET /api/v1/accounts/{account_no}`
说明：查询账户详情。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`account_no`
- Query：无
- Body：无

响应：

- `data.account_status`：账户状态
- `data.balance_amount`：余额
- `data.frozen_amount`：冻结金额
- `data.account_product`：开户产品
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 bank_account、account_product。
- 校验返回对象在当前渠道和操作员权限范围内。
- 组装账户状态、余额、冻结金额、开户产品并返回。

#### 5.3. `GET /api/v1/customers/{customer_no}/accounts`
说明：查询客户账户列表。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`customer_no`
- Query：`account_status`
- Body：无

响应：

- `data.list[].account_no`：账户号
- `data.list[].balance_amount`：余额
- `data.list[].currency_code`：币种
- `data.list[].account_product`：产品
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 bank_account、account_product。
- 校验返回对象在当前渠道和操作员权限范围内。
- 组装账户号、余额、币种、产品并返回。

#### 5.4. `POST /api/v1/accounts/{account_no}/cards`
说明：绑定银行卡。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`account_no`
- Body：`request_no`、卡类型、卡介质

响应：

- `data.card_no`：卡号
- `data.card_status`：卡状态
- `data.issued_at`：发卡时间
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、绑卡权限和请求字段格式。
- 读取并锁定 `bank_account` 和既有 `bank_card`。
- 校验账户状态、卡介质、卡号唯一性和绑定权限。
- 在同一事务内写入 `bank_card`。
- 返回卡号、卡状态、发卡时间。

#### 5.5. `POST /api/v1/accounts/{account_no}/status-changes`
说明：变更账户状态。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`account_no`
- Body：`request_no`、目标状态、原因

响应：

- `data.status_history_id`：状态变更记录 ID
- `data.change_seq`：状态变更序号
- `data.current_status`：当前状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、账户状态变更权限和请求字段格式。
- 读取并锁定 `bank_account` 和既有 `bank_account_status_history`。
- 校验目标状态、状态流转、变更原因和操作权限。
- 在同一事务内写入 `bank_account_status_history` 并同步更新 `bank_account.account_status`。
- 返回状态变更记录 ID、状态变更序号、当前状态。

#### 5.6. `POST /api/v1/transactions`
说明：发起普通账户交易。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Body：`request_no`、`customer_no`、`account_no`、交易类型、金额、币种、收付款信息、关联对象类型、关联对象编号

响应：

- `data.transaction_no`：交易编号
- `data.transaction_status`：交易状态
- `data.channel_txn_no`：渠道流水号
- `data.related_type`：关联对象类型
- `data.related_no`：关联对象编号
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、交易权限和金额精度。
- 读取并锁定 `customer`、`bank_account`，以及关联对象类型和关联对象编号指向的 `loan_contract`、`repayment_bill`、`wealth_order`、`wealth_income` 或 `risk_event`。
- 校验主体、账户、币种、金额、业务状态和关联对象一致性。
- 在同一事务内写入账户交易；交易成功时读取或创建同渠道同交易日对账批次，并生成渠道流水、账户流水和对账结果；交易失败时仅记录失败状态和失败原因，不生成账户流水或余额变动。
- 返回交易编号、交易状态、渠道流水号、关联对象类型和关联对象编号。

#### 5.7. `GET /api/v1/transactions/{transaction_no}`
说明：查询账户交易详情。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`transaction_no`
- Query：无
- Body：无

响应：

- `data.transaction_status`：交易状态
- `data.amount`：金额
- `data.channel_transaction`：渠道流水
- `data.reconcile_status`：对账状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 account_transaction、channel_transaction、reconciliation_result。
- 校验返回对象在当前渠道和操作员权限范围内。
- 组装交易状态、金额、渠道流水、对账状态并返回。

#### 5.8. `GET /api/v1/accounts/{account_no}/transactions`
说明：查询账户交易明细。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`account_no`
- Query：时间范围、交易类型、交易状态、`page_no`、`page_size`
- Body：无

响应：

- `data.list[]`：交易明细列表
- `data.page_no`：当前页码
- `data.page_size`：每页条数
- `data.total_count`：总记录数
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 account_transaction。
- 校验返回对象在当前渠道和操作员权限范围内。
- 分页组装交易明细列表并返回。

#### 5.9. `GET /api/v1/accounts/{account_no}/ledgers`
说明：查询账户资金流水。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`account_no`
- Query：时间范围、流水类型、`page_no`、`page_size`
- Body：无

响应：

- `data.list[]`：账户流水列表
- `data.list[].balance_after`：交易后余额
- `data.page_no`：当前页码
- `data.page_size`：每页条数
- `data.total_count`：总记录数
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 account_ledger。
- 校验返回对象在当前渠道和操作员权限范围内。
- 分页组装账户流水列表、交易后余额并返回。

#### 5.10. `POST /api/v1/fund-freezes`
说明：新增资金冻结。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Body：`request_no`、`account_no`、冻结金额、冻结原因、冻结关联对象类型、冻结关联对象编号

响应：

- `data.freeze_no`：冻结编号
- `data.freeze_status`：冻结状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、冻结权限、冻结金额精度和账户可用余额。
- 读取并锁定 `customer`、`bank_account`，以及 `account_transaction`、`wealth_order`、`loan_contract`、`repayment_bill` 或 `risk_event` 对应冻结关联对象。
- 在同一事务内写入 `fund_freeze` 和冻结类 `fund_freeze_operation`，同步更新账户冻结余额，追加 `account_ledger` 冻结流水，不生成账户交易和对账结果。
- 返回冻结编号、冻结状态。

#### 5.11. `POST /api/v1/fund-freezes/{freeze_no}/operations`
说明：解冻或释放冻结。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`freeze_no`
- Body：`request_no`、操作类型、金额、原因

响应：

- `data.operation_no`：操作编号
- `data.frozen_balance`：冻结余额
- `data.freeze_status`：冻结状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、冻结操作权限、操作类型、操作金额和冻结余额。
- 读取并锁定 `fund_freeze`、`bank_account`，以及 `account_transaction`、`wealth_order`、`loan_contract`、`repayment_bill` 或 `risk_event` 对应冻结关联对象。
- 在同一事务内写入解冻、释放或取消类 `fund_freeze_operation`，同步更新账户冻结余额，追加 `account_ledger` 冻结变动流水，不生成账户交易和对账结果。
- 返回操作编号、冻结余额、冻结状态。

#### 5.12. `POST /api/v1/reconciliation/batches`
说明：创建对账批次。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Body：`request_no`、`channel_code`、`reconcile_date`

响应：

- `data.batch_no`：批次号
- `data.batch_status`：批次状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、对账批次创建权限和请求字段格式。
- 读取并校验 `dim_channel` 和既有 `reconciliation_batch`。
- 校验渠道、对账日期、有效批次唯一性和创建权限；同渠道同日已失败或已取消批次不阻止重新创建。
- 在同一事务内写入 `reconciliation_batch`。
- 返回批次号、批次状态。

#### 5.13. `POST /api/v1/reconciliation/results`
说明：写入对账结果。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Body：`request_no`、批次号、账户交易号、渠道流水号、匹配结果

响应：

- `data.result_no`：对账结果编号
- `data.process_status`：处理状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、操作权限、幂等号和请求字段格式。
- 读取并校验对账批次，以及账户交易号或渠道流水号对应记录；`matched`、`amount_mismatch` 和 `status_mismatch` 结果必须同时提供账户交易号和渠道流水号，`bank_only` 结果只要求账户交易号，`channel_only` 结果只要求渠道流水号。
- 按账户交易、渠道流水、订单号、金额、币种、请求状态、回调状态和对账状态计算匹配结果；`matched` 的差错金额必须为 `0` 且处理状态为 `closed`，`amount_mismatch` 的差错金额必须等于银行侧交易金额与渠道侧流水金额差额的绝对值且处理状态为 `pending`，`status_mismatch` 的差错金额为 `0` 且处理状态为 `pending`，`bank_only` 的差错金额为银行侧交易金额且处理状态为 `pending`，`channel_only` 的差错金额为渠道侧流水金额且处理状态为 `pending`。
- 在同一事务内写入或幂等返回 `reconciliation_result`。
- 返回对账结果编号、处理状态。

#### 5.14. `POST /api/v1/reconciliation/adjustments`
说明：发起调账。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Body：`request_no`、对账结果编号、调账金额、调账原因

响应：

- `data.adjustment_no`：调账编号
- `data.adjustment_status`：调账状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、调账权限、对账结果编号、调账金额和调账原因。
- 读取并锁定对账结果、账户交易和渠道流水。
- 校验对账结果处于可调账状态，调账金额不超过差错金额。
- 在同一事务内写入 `reconciliation_adjustment`，初始状态为 `submitted`，不生成账户交易和账户流水。
- 返回调账编号、调账状态。

#### 5.15. `POST /api/v1/reconciliation/adjustments/{adjustment_no}/approval`
说明：审批调账。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`adjustment_no`
- Body：`request_no`、审批结果、审批金额、审批意见

响应：

- `data.adjustment_no`：调账编号
- `data.adjustment_status`：调账状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号和调账审批权限。
- 读取并锁定调账申请。
- 校验调账状态、审批结果、审批金额和审批时间。
- 在同一事务内更新 `reconciliation_adjustment` 审批状态和审批信息。
- 返回调账编号、调账状态。

#### 5.16. `POST /api/v1/reconciliation/adjustments/{adjustment_no}/post`
说明：调账入账。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`adjustment_no`
- Body：`request_no`、入账账户、入账金额、入账日期

响应：

- `data.adjustment_no`：调账编号
- `data.adjustment_status`：调账状态
- `data.transaction_no`：交易编号
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、入账权限、入账账户和入账金额。
- 读取并锁定已审批调账申请、对账结果和入账账户。
- 校验入账金额等于审批调账金额，账户、币种和对账差错主体一致。
- 在同一事务内写入账户交易、渠道流水、账户流水，读取或创建同渠道同入账日对账批次，更新 `reconciliation_adjustment` 为 `posted`，并回写 `reconciliation_result` 处理状态。
- 返回调账编号、调账状态、交易编号。

### 6. 理财接口
| 方法   | 路径                                               | 接口说明         | 主要入参                                                            | 主要出参                                           | 关联表                                                                                    |
| ------ | -------------------------------------------------- | ---------------- | ------------------------------------------------------------------- | -------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `GET`  | `/api/v1/wealth/products`                          | 查询可售理财产品 | `risk_level_code`、`currency_code`、`product_status`                | 理财产品列表                                       | `wealth_product`、`wealth_nav`、`dim_risk_level`                                           |
| `GET`  | `/api/v1/wealth/products/{product_code}`           | 查询理财产品详情 | `product_code`                                                      | 产品详情、开放期、结算规则、最新净值、公告         | `wealth_product`、`wealth_nav`、`wealth_open_period`、`wealth_settlement_rule`、`wealth_product_notice` |
| `GET`  | `/api/v1/wealth/products/{product_code}/navs`      | 查询理财净值     | `product_code`、日期范围、`page_no`、`page_size`                    | 净值列表                                           | `wealth_nav`                                                                              |
| `POST` | `/api/v1/wealth/orders/purchase`                   | 发起理财申购     | `request_no`、`customer_no`、`account_no`、`product_code`、申购金额 | 订单号、订单状态、冻结编号                         | `wealth_order`、`wealth_product`、`wealth_open_period`、`fund_freeze`、`fund_freeze_operation`、`account_ledger`、`customer`、`bank_account` |
| `POST` | `/api/v1/wealth/orders/redeem`                     | 发起理财赎回     | `request_no`、`customer_no`、`account_no`、`position_id`、赎回份额  | 订单号、订单状态、预计到账日                       | `wealth_order`、`wealth_position`、`wealth_product`、`wealth_open_period`、`wealth_trade_calendar`、`wealth_settlement_rule`、`customer`、`bank_account` |
| `POST` | `/api/v1/wealth/orders/{order_no}/confirm`         | 确认理财订单     | `request_no`、`order_no`、确认金额、确认份额、确认净值、确认日期                | 订单号、订单状态、持仓状态、交易编号               | `wealth_order`、`wealth_product`、`wealth_position`、`fund_freeze`、`fund_freeze_operation`、`account_transaction`、`customer`、`bank_account`、`channel_transaction`、`account_ledger`、`reconciliation_batch`、`reconciliation_result` |
| `POST` | `/api/v1/wealth/orders/{order_no}/cancel`          | 撤销理财订单     | `request_no`、`order_no`、撤销原因                                  | 订单号、订单状态、解冻状态                         | `wealth_order`、`wealth_position`、`fund_freeze`、`fund_freeze_operation`、`account_ledger`、`customer`、`bank_account` |
| `GET`  | `/api/v1/wealth/orders/{order_no}`                 | 查询理财订单详情 | `order_no`                                                          | 订单状态、确认份额、交易流水、对账状态             | `wealth_order`、`account_transaction`、`reconciliation_result`                            |
| `GET`  | `/api/v1/customers/{customer_no}/wealth/positions` | 查询客户理财持仓 | `customer_no`、`product_code`                                       | 持仓列表                                           | `wealth_position`、`wealth_product`、`wealth_income`                                      |
| `GET`  | `/api/v1/customers/{customer_no}/wealth/incomes`   | 查询客户理财收益 | `customer_no`、收益日期范围、`page_no`、`page_size`                 | 收益列表                                           | `wealth_income`、`wealth_product`                                                        |
| `POST` | `/api/v1/wealth/incomes/{income_no}/settle`        | 结转理财收益     | `request_no`、`income_no`、结转金额、结转日期                                    | 收益编号、结转状态、交易编号                       | `wealth_income`、`wealth_position`、`account_transaction`、`channel_transaction`、`account_ledger`、`reconciliation_batch`、`reconciliation_result` |

接口明细：

#### 6.1. `GET /api/v1/wealth/products`
说明：查询可售理财产品。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Query：`risk_level_code`、`currency_code`、`product_status`
- Body：无

响应：

- `data.list[].product_code`：产品编码
- `data.list[].product_name`：产品名称
- `data.list[].risk_level`：风险等级
- `data.list[].expected_yield_rate`：预期收益率
- `data.list[].open_status`：开放状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 wealth_product、wealth_nav、dim_risk_level。
- 校验返回对象在当前渠道和操作员权限范围内。
- 组装产品编码、产品名称、风险等级、预期收益率、开放状态列表并返回。

#### 6.2. `GET /api/v1/wealth/products/{product_code}`
说明：查询理财产品详情。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`product_code`
- Query：无
- Body：无

响应：

- `data.product_detail`：产品详情
- `data.open_periods`：开放期
- `data.settlement_rule`：结算规则
- `data.latest_nav`：最新净值
- `data.notices`：公告
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 wealth_product、wealth_nav、wealth_open_period、wealth_settlement_rule、wealth_product_notice。
- 校验返回对象在当前渠道和操作员权限范围内。
- 组装产品详情、开放期、结算规则、最新净值、公告并返回。

#### 6.3. `GET /api/v1/wealth/products/{product_code}/navs`
说明：查询理财净值。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`product_code`
- Query：日期范围、`page_no`、`page_size`
- Body：无

响应：

- `data.list[].nav_date`：净值日期
- `data.list[].unit_nav`：单位净值
- `data.list[].accumulated_nav`：累计净值
- `data.page_no`：当前页码
- `data.page_size`：每页条数
- `data.total_count`：总记录数
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 wealth_nav。
- 校验返回对象在当前渠道和操作员权限范围内。
- 分页组装净值日期、单位净值、累计净值并返回。

#### 6.4. `POST /api/v1/wealth/orders/purchase`
说明：发起理财申购。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Body：`request_no`、`customer_no`、`account_no`、`product_code`、申购金额

响应：

- `data.order_no`：订单号
- `data.order_status`：订单状态
- `data.freeze_no`：冻结编号
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、申购权限、申购金额精度、客户风险等级和产品开放期。
- 读取并锁定客户、账户、理财产品、开放期和账户余额。
- 在同一事务内写入申购 `wealth_order`，生成申购冻结 `fund_freeze` 和 `fund_freeze_operation`，追加 `account_ledger` 冻结流水，申购确认扣款时再生成账户交易、对账批次和对账结果。
- 返回订单号、订单状态、冻结编号。

#### 6.5. `POST /api/v1/wealth/orders/redeem`
说明：发起理财赎回。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Body：`request_no`、`customer_no`、`account_no`、`position_id`、赎回份额

响应：

- `data.order_no`：订单号
- `data.order_status`：订单状态
- `data.expected_arrival_date`：预计到账日
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、赎回权限、赎回份额精度、产品开放期和持仓可用份额。
- 读取并锁定客户、账户、理财持仓、理财产品、开放期、交易日历和结算规则。
- 在同一事务内写入赎回 `wealth_order`，冻结持仓可用份额。
- 赎回确认到账时再生成账户交易、账户流水、渠道流水、对账批次和对账结果。
- 返回订单号、订单状态、预计到账日。

#### 6.6. `POST /api/v1/wealth/orders/{order_no}/confirm`
说明：确认理财订单。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`order_no`
- Body：`request_no`、确认金额、确认份额、确认净值、确认日期

响应：

- `data.order_no`：订单号
- `data.order_status`：订单状态
- `data.position_status`：持仓状态
- `data.transaction_no`：交易编号
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、确认权限、订单状态、确认金额、确认份额和确认净值。
- 读取并锁定理财订单、客户、结算账户、产品、冻结记录和既有持仓。
- 申购确认时按冻结金额释放冻结并扣款，写入或更新 `wealth_position`。
- 赎回确认时按确认金额入账，扣减冻结份额并更新 `wealth_position`。
- 在同一事务内写入账户交易、渠道流水、账户流水，读取或创建同渠道同确认日对账批次，并生成对账结果。
- 返回订单号、订单状态、持仓状态、交易编号。

#### 6.7. `POST /api/v1/wealth/orders/{order_no}/cancel`
说明：撤销理财订单。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`order_no`
- Body：`request_no`、撤销原因

响应：

- `data.order_no`：订单号
- `data.order_status`：订单状态
- `data.unfreeze_status`：解冻状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、撤销原因和订单可撤销状态。
- 读取并锁定理财订单、客户、账户、冻结记录或持仓份额。
- 校验订单、客户、账户、产品和撤销权限一致。
- 在同一事务内更新订单状态；申购订单写入取消类 `fund_freeze_operation` 并追加账户冻结流水，赎回订单释放冻结份额。
- 返回订单号、订单状态、解冻状态。

#### 6.8. `GET /api/v1/wealth/orders/{order_no}`
说明：查询理财订单详情。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`order_no`
- Query：无
- Body：无

响应：

- `data.order_status`：订单状态
- `data.confirmed_share`：确认份额
- `data.transaction`：交易流水
- `data.reconcile_status`：对账状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 wealth_order、account_transaction、reconciliation_result。
- 校验返回对象在当前渠道和操作员权限范围内。
- 组装订单状态、确认份额、交易流水、对账状态并返回。

#### 6.9. `GET /api/v1/customers/{customer_no}/wealth/positions`
说明：查询客户理财持仓。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`customer_no`
- Query：`product_code`
- Body：无

响应：

- `data.list[].holding_share`：持仓份额
- `data.list[].available_share`：可用份额
- `data.list[].market_value_amount`：持仓市值
- `data.list[].income`：收益
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 wealth_position、wealth_product、wealth_income。
- 校验返回对象在当前渠道和操作员权限范围内。
- 组装持仓份额、可用份额、持仓市值、收益列表并返回。

#### 6.10. `GET /api/v1/customers/{customer_no}/wealth/incomes`
说明：查询客户理财收益。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`customer_no`
- Query：收益日期范围、`page_no`、`page_size`
- Body：无

响应：

- `data.list[].income_date`：收益日期
- `data.list[].product`：产品
- `data.list[].income_amount`：收益金额
- `data.list[].settled_flag`：结转标识
- `data.page_no`：当前页码
- `data.page_size`：每页条数
- `data.total_count`：总记录数
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 wealth_income、wealth_product。
- 校验返回对象在当前渠道和操作员权限范围内。
- 分页组装收益日期、产品、收益金额、结转标识并返回。

#### 6.11. `POST /api/v1/wealth/incomes/{income_no}/settle`
说明：结转理财收益。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`income_no`
- Body：`request_no`、结转金额、结转日期

响应：

- `data.income_no`：收益编号
- `data.settled_flag`：结转标识
- `data.transaction_no`：交易编号
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、收益结转权限、收益状态、结转金额和结转日期。
- 读取并锁定理财收益、理财持仓、客户和结算账户。
- 校验结转金额等于待结转收益金额，且持仓、账户和产品主体一致。
- 在同一事务内更新 `wealth_income` 结转状态，写入账户交易、渠道流水、账户流水，读取或创建同渠道同结转日对账批次，并生成对账结果。
- 返回收益编号、结转标识、交易编号。

### 7. 信贷接口
| 方法   | 路径                                                                   | 接口说明         | 主要入参                                                                       | 主要出参                                     | 关联表                                                                            |
| ------ | ---------------------------------------------------------------------- | ---------------- | ------------------------------------------------------------------------------ | -------------------------------------------- | --------------------------------------------------------------------------------- |
| `GET`  | `/api/v1/loan/products`                                                | 查询贷款产品     | `loan_type`、`currency_code`、`product_status`                                 | 贷款产品列表                                 | `loan_product`、`loan_product_eligibility_rule`、`loan_product_rate_tier`          |
| `GET`  | `/api/v1/loan/products/{product_code}`                                 | 查询贷款产品详情 | `product_code`                                                                 | 产品详情、准入规则、费率档位、材料要求       | `loan_product`、`loan_product_eligibility_rule`、`loan_product_rate_tier`、`loan_product_required_material` |
| `POST` | `/api/v1/credit/applications`                                          | 提交授信申请     | `request_no`、`customer_no`、`product_code`、申请额度、材料                    | 授信申请编号、申请状态                       | `credit_application`、`credit_application_material`、`customer`、`loan_product`、`loan_product_eligibility_rule`、`loan_product_rate_tier` |
| `GET`  | `/api/v1/credit/applications/{credit_application_no}`                  | 查询授信申请详情 | `credit_application_no`                                                        | 申请信息、材料、审批记录、授信结果           | `credit_application`、`credit_application_material`、`credit_approval_record`、`credit_limit` |
| `POST` | `/api/v1/credit/applications/{credit_application_no}/approval-records` | 提交授信审批结果 | `request_no`、`credit_application_no`、审批节点、审批结果、额度、原因                                   | 审批记录编号、授信状态                       | `credit_application`、`credit_assessment`、`credit_approval_record`、`credit_limit`、`credit_limit_change_log`、`customer` |
| `GET`  | `/api/v1/customers/{customer_no}/credit-limits`                        | 查询客户授信额度 | `customer_no`、`product_code`                                                  | 授信额度列表                                 | `credit_limit`、`loan_product`                                                     |
| `POST` | `/api/v1/loan/applications`                                            | 提交贷款申请     | `request_no`、`customer_no`、`limit_no`、申请金额、期限、还款方式、材料        | 贷款申请编号、申请状态                       | `loan_application`、`loan_application_material`、`credit_limit`、`credit_limit_change_log`、`customer`、`loan_product` |
| `GET`  | `/api/v1/loan/applications/{application_no}`                           | 查询贷款申请详情 | `application_no`                                                               | 申请信息、评估结果、审批记录、合同信息       | `loan_application`、`credit_assessment`、`loan_approval_record`、`loan_contract`  |
| `POST` | `/api/v1/loan/applications/{application_no}/status-changes`            | 变更贷款申请状态 | `request_no`、`application_no`、目标状态、原因                                                   | 贷款申请编号、申请状态、额度释放状态         | `loan_application`、`credit_limit`、`credit_limit_change_log`                    |
| `POST` | `/api/v1/loan/applications/{application_no}/approval-records`          | 提交贷款审批结果 | `request_no`、`application_no`、审批节点、审批结果、审批金额、审批利率                           | 审批记录编号、申请状态                       | `loan_approval_record`、`loan_application`、`credit_assessment`、`loan_contract`、`credit_limit`、`credit_limit_change_log` |
| `POST` | `/api/v1/loan/contracts/{contract_no}/sign-records`                    | 提交合同签署记录 | `request_no`、`contract_no`、`document_no`、签署方、签署方式、签署结果                         | 签署记录编号、合同状态                       | `contract_sign_record`、`loan_contract`、`loan_contract_document`                  |
| `POST` | `/api/v1/loan/contracts/{contract_no}/disbursements`                   | 发起贷款放款     | `request_no`、`contract_no`、`account_no`、放款金额                            | 放款编号、放款状态、交易编号                 | `loan_contract`、`loan_disbursement`、`account_transaction`、`channel_transaction`、`bank_account`、`account_ledger`、`reconciliation_batch`、`reconciliation_result`、`credit_limit`、`credit_limit_change_log`、`repayment_schedule` |
| `GET`  | `/api/v1/loan/contracts/{contract_no}`                                 | 查询合同借据详情 | `contract_no`                                                                  | 合同信息、剩余本金、还款状态、放款记录       | `loan_contract`、`loan_disbursement`                                              |

接口明细：

#### 7.1. `GET /api/v1/loan/products`
说明：查询贷款产品。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Query：`loan_type`、`currency_code`、`product_status`
- Body：无

响应：

- `data.list[].product_code`：产品编码
- `data.list[].eligibility_rules`：准入条件
- `data.list[].rate_range`：利率区间
- `data.list[].term_range`：期限范围
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 loan_product、loan_product_eligibility_rule、loan_product_rate_tier。
- 校验返回对象在当前渠道和操作员权限范围内。
- 组装产品编码、准入条件、利率区间、期限范围列表并返回。

#### 7.2. `GET /api/v1/loan/products/{product_code}`
说明：查询贷款产品详情。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`product_code`
- Query：无
- Body：无

响应：

- `data.product_detail`：产品详情
- `data.eligibility_rules`：准入规则
- `data.rate_tiers`：费率档位
- `data.required_materials`：材料要求
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 loan_product、loan_product_eligibility_rule、loan_product_rate_tier、loan_product_required_material。
- 校验返回对象在当前渠道和操作员权限范围内。
- 组装产品详情、准入规则、费率档位、材料要求并返回。

#### 7.3. `POST /api/v1/credit/applications`
说明：提交授信申请。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Body：`request_no`、`customer_no`、`product_code`、申请额度、材料

响应：

- `data.credit_application_no`：授信申请编号
- `data.application_status`：申请状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、授信申请权限和请求字段格式。
- 读取并校验 `customer`、`loan_product`、`loan_product_eligibility_rule`、`loan_product_rate_tier` 和申请材料。
- 校验客户状态、产品准入、申请额度、币种、材料和业务权限。
- 在同一事务内写入 `credit_application` 和 `credit_application_material`。
- 返回授信申请编号、申请状态。

#### 7.4. `GET /api/v1/credit/applications/{credit_application_no}`
说明：查询授信申请详情。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`credit_application_no`
- Query：无
- Body：无

响应：

- `data.application_info`：申请信息
- `data.materials`：材料
- `data.approval_records`：审批记录
- `data.credit_result`：授信结果
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 credit_application、credit_application_material、credit_approval_record、credit_limit。
- 校验返回对象在当前渠道和操作员权限范围内。
- 组装申请信息、材料、审批记录、授信结果并返回。

#### 7.5. `POST /api/v1/credit/applications/{credit_application_no}/approval-records`
说明：提交授信审批结果。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`credit_application_no`
- Body：`request_no`、审批节点、审批结果、额度、原因

响应：

- `data.approval_record_id`：审批记录 ID
- `data.application_status`：授信申请状态
- `data.limit_status`：额度状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号和授信审批权限。
- 读取并锁定授信申请、授信评估、审批记录和客户信息。
- 校验审批节点、审批结果、额度、风险等级和完成时间。
- 在同一事务内写入审批记录并回写授信申请状态；审批通过时生成或更新 `credit_limit`，并写入授予类 `credit_limit_change_log`。
- 返回审批记录 ID、授信申请状态、额度状态。

#### 7.6. `GET /api/v1/customers/{customer_no}/credit-limits`
说明：查询客户授信额度。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`customer_no`
- Query：`product_code`
- Body：无

响应：

- `data.list[].limit_no`：授信编号
- `data.list[].total_limit_amount`：总额度
- `data.list[].available_limit_amount`：可用额度
- `data.list[].frozen_limit_amount`：冻结额度
- `data.list[].valid_to`：失效时间
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 credit_limit、loan_product。
- 校验返回对象在当前渠道和操作员权限范围内。
- 组装授信编号、总额度、可用额度、冻结额度、失效时间列表并返回。

#### 7.7. `POST /api/v1/loan/applications`
说明：提交贷款申请。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Body：`request_no`、`customer_no`、`limit_no`、申请金额、期限、还款方式、材料

响应：

- `data.application_no`：贷款申请编号
- `data.application_status`：申请状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、贷款申请权限、申请金额、期限、还款方式和材料完整性。
- 读取并锁定客户、授信额度、贷款产品和申请材料。
- 校验客户、授信额度、币种、产品准入和申请金额一致。
- 在同一事务内写入贷款申请和申请材料，写入冻结类 `credit_limit_change_log`，并同步更新 `credit_limit.frozen_limit_amount` 和 `available_limit_amount`。
- 返回贷款申请编号、申请状态。

#### 7.8. `GET /api/v1/loan/applications/{application_no}`
说明：查询贷款申请详情。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`application_no`
- Query：无
- Body：无

响应：

- `data.application_info`：申请信息
- `data.assessment_result`：评估结果
- `data.approval_records`：审批记录
- `data.contract_info`：合同信息
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 loan_application、credit_assessment、loan_approval_record、loan_contract。
- 校验返回对象在当前渠道和操作员权限范围内。
- 组装申请信息、评估结果、审批记录、合同信息并返回。

#### 7.9. `POST /api/v1/loan/applications/{application_no}/status-changes`
说明：变更贷款申请状态。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`application_no`
- Body：`request_no`、目标状态、原因

响应：

- `data.application_no`：贷款申请编号
- `data.application_status`：申请状态
- `data.limit_release_status`：额度释放状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、目标状态和状态变更权限。
- 读取并锁定贷款申请和授信额度冻结流水。
- 校验目标状态只能为取消或过期，且申请未审批通过、未生成有效合同。
- 在同一事务内更新贷款申请状态，写入释放冻结类 `credit_limit_change_log`，并同步更新 `credit_limit.frozen_limit_amount` 和 `available_limit_amount`。
- 返回贷款申请编号、申请状态、额度释放状态。

#### 7.10. `POST /api/v1/loan/applications/{application_no}/approval-records`
说明：提交贷款审批结果。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`application_no`
- Body：`request_no`、审批节点、审批结果、审批金额、审批利率

响应：

- `data.approval_record_id`：审批记录 ID
- `data.application_status`：申请状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号和贷款审批权限。
- 读取并锁定贷款申请、授信额度、征信评估和审批记录。
- 校验审批金额、审批利率、期限、产品规则和额度占用状态。
- 在同一事务内写入贷款审批记录并回写贷款申请状态；审批通过时生成或关联 `loan_contract`，审批拒绝时写入释放冻结类 `credit_limit_change_log`，并同步更新 `credit_limit.frozen_limit_amount` 和 `available_limit_amount`。
- 返回审批记录 ID、申请状态。

#### 7.11. `POST /api/v1/loan/contracts/{contract_no}/sign-records`
说明：提交合同签署记录。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`contract_no`
- Body：`request_no`、`document_no`、签署方、签署方式、签署结果

响应：

- `data.sign_no`：签署记录编号
- `data.contract_status`：合同状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、合同签署权限和合同文件编号。
- 读取并锁定贷款合同、合同文件和签署记录。
- 校验合同文件有效、签署方一致、签署方式和签署结果。
- 在同一事务内写入 `contract_sign_record`，同步更新 `loan_contract_document` 签署状态和 `loan_contract` 签署状态。
- 返回签署记录编号、合同状态。

#### 7.12. `POST /api/v1/loan/contracts/{contract_no}/disbursements`
说明：发起贷款放款。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`contract_no`
- Body：`request_no`、`account_no`、放款金额

响应：

- `data.disbursement_no`：放款编号
- `data.disbursement_status`：放款状态
- `data.transaction_no`：交易编号
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、放款金额精度和放款权限。
- 读取并锁定贷款合同、授信额度、收款账户和放款记录。
- 校验合同已签署、合同对应冻结额度、账户币种和放款金额一致。
- 在同一事务内写入放款记录；放款成功时生成账户交易、渠道流水、账户流水，读取或创建同渠道同放款日对账批次，生成对账结果、额度冻结转占用流水和初始还款计划，并同步更新合同已放款本金、未放款本金、剩余本金、放款时间和合同状态；放款失败时仅记录失败状态和失败原因，不生成资金流水、还款计划或合同金额变动。
- 返回放款编号、放款状态、交易编号。

#### 7.13. `GET /api/v1/loan/contracts/{contract_no}`
说明：查询合同借据详情。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`contract_no`
- Query：无
- Body：无

响应：

- `data.contract_info`：合同信息
- `data.outstanding_principal_amount`：剩余本金
- `data.repayment_status`：还款状态
- `data.disbursements`：放款记录
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 loan_contract、loan_disbursement。
- 校验返回对象在当前渠道和操作员权限范围内。
- 组装合同信息、剩余本金、还款状态、放款记录并返回。

### 8. 还款与逾期接口
| 方法   | 路径                                                       | 接口说明         | 主要入参                                                           | 主要出参                                   | 关联表                                                              |
| ------ | ---------------------------------------------------------- | ---------------- | ------------------------------------------------------------------ | ------------------------------------------ | ------------------------------------------------------------------- |
| `GET`  | `/api/v1/loan/contracts/{contract_no}/repayment-schedules` | 查询还款计划     | `contract_no`                                                      | 还款计划列表                               | `repayment_schedule`                                                |
| `POST` | `/api/v1/repayment/bills/generate`                         | 生成还款账单     | `request_no`、`contract_no`、出账日期、期次范围                    | 账单数量                                   | `loan_contract`、`repayment_schedule`、`repayment_bill`             |
| `GET`  | `/api/v1/repayment/bills`                                  | 查询还款账单     | `customer_no`、`contract_no`、账单状态、时间范围、`page_no`、`page_size` | 账单编号、未还金额、已还金额、账单状态     | `repayment_bill`                                                    |
| `POST` | `/api/v1/repayment/authorizations`                         | 创建自动还款授权 | `request_no`、`customer_no`、`contract_no`、`account_no`、授权方式 | 授权编号、授权状态                         | `repayment_authorization`、`customer`、`loan_contract`、`bank_account`       |
| `POST` | `/api/v1/repayments`                                       | 发起正常还款     | `request_no`、`bill_no`、`account_no`、还款金额、还款方式          | 还款编号、还款状态、交易编号               | `repayment_record`、`repayment_allocation`、`account_transaction`、`channel_transaction`、`bank_account`、`account_ledger`、`reconciliation_batch`、`reconciliation_result`、`repayment_bill`、`repayment_schedule`、`overdue_record`、`loan_contract`、`credit_limit`、`credit_limit_change_log` |
| `GET`  | `/api/v1/repayments/{repayment_no}`                        | 查询还款详情     | `repayment_no`                                                     | 还款状态、分配明细、交易流水、对账状态     | `repayment_record`、`repayment_allocation`、`account_transaction`、`reconciliation_result` |
| `GET`  | `/api/v1/overdues`                                         | 查询逾期记录     | `customer_no`、`contract_no`、逾期阶段、逾期状态、`page_no`、`page_size` | 逾期编号、逾期天数、逾期总金额、催收状态   | `overdue_record`、`collection_case`                                 |
| `POST` | `/api/v1/overdues/refresh`                                 | 刷新逾期记录     | `request_no`、`contract_no`、逾期计算日期                           | 逾期记录数                                 | `loan_contract`、`repayment_bill`、`repayment_schedule`、`overdue_record`、`collection_case` |
| `POST` | `/api/v1/fee-reductions`                                   | 发起费用减免申请 | `request_no`、`bill_no`、减免类型、减免金额、原因                  | 减免编号、减免状态                         | `fee_reduction`、`workflow_instance`、`workflow_task`、`repayment_bill`、`loan_contract`、`overdue_record` |
| `POST` | `/api/v1/fee-reductions/{reduction_no}/approval`           | 提交费用减免审批 | `request_no`、`reduction_no`、审批结果、审批金额、原因                             | 减免编号、减免状态、账单金额               | `fee_reduction`、`repayment_bill`、`overdue_record`、`workflow_task`、`workflow_instance` |

接口明细：

#### 8.1. `GET /api/v1/loan/contracts/{contract_no}/repayment-schedules`
说明：查询还款计划。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`contract_no`
- Query：无
- Body：无

响应：

- `data.list[].period_no`：期次
- `data.list[].principal_amount`：应还本金
- `data.list[].interest_amount`：应还利息
- `data.list[].due_date`：应还日
- `data.list[].schedule_status`：计划状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 repayment_schedule。
- 校验返回对象在当前渠道和操作员权限范围内。
- 组装期次、应还本金、应还利息、应还日、计划状态列表并返回。

#### 8.2. `POST /api/v1/repayment/bills/generate`
说明：生成还款账单。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Body：`request_no`、`contract_no`、出账日期、期次范围

响应：

- `data.bill_count`：账单数量
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、账单生成权限、合同状态、出账日期和期次范围。
- 读取并锁定贷款合同、还款计划和既有账单。
- 校验还款计划已生效，目标期次未重复出账。
- 在同一事务内按还款计划生成 `repayment_bill`，并同步计划出账状态。
- 返回账单数量。

#### 8.3. `GET /api/v1/repayment/bills`
说明：查询还款账单。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Query：`customer_no`、`contract_no`、账单状态、时间范围、`page_no`、`page_size`
- Body：无

响应：

- `data.list[].bill_no`：账单编号
- `data.list[].outstanding_amount`：未还金额
- `data.list[].paid_amount`：已还金额
- `data.list[].bill_status`：账单状态
- `data.page_no`：当前页码
- `data.page_size`：每页条数
- `data.total_count`：总记录数
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 repayment_bill。
- 校验返回对象在当前渠道和操作员权限范围内。
- 分页组装账单编号、未还金额、已还金额、账单状态并返回。

#### 8.4. `POST /api/v1/repayment/authorizations`
说明：创建自动还款授权。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Body：`request_no`、`customer_no`、`contract_no`、`account_no`、授权方式

响应：

- `data.authorization_no`：授权编号
- `data.authorization_status`：授权状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、自动还款授权权限和授权字段格式。
- 读取并校验客户、合同、还款账户和授权方式。
- 校验账户归属、合同状态、授权有效期和重复授权规则。
- 在同一事务内写入 `repayment_authorization`，不生成资金流水和对账结果。
- 返回授权编号、授权状态。

#### 8.5. `POST /api/v1/repayments`
说明：发起正常还款。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Body：`request_no`、`bill_no`、`account_no`、还款金额、还款方式

响应：

- `data.repayment_no`：还款编号
- `data.repayment_status`：还款状态
- `data.transaction_no`：交易编号
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、还款权限、还款金额精度和账户余额。
- 读取并锁定账单、还款账户、合同、还款计划、逾期记录和既有还款记录。
- 校验主体、账户、币种、金额、账单状态和分配规则一致。
- 在同一事务内写入还款记录；还款成功时生成分配明细、账户交易、渠道流水、账户流水，读取或创建同渠道同还款日对账批次，生成对账结果和额度释放流水，并同步账单、计划、逾期记录、合同余额、合同状态和授信额度；还款失败时仅记录失败状态和失败原因，不生成分配明细、资金流水或业务余额变动。
- 返回还款编号、还款状态、交易编号。

#### 8.6. `GET /api/v1/repayments/{repayment_no}`
说明：查询还款详情。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`repayment_no`
- Query：无
- Body：无

响应：

- `data.repayment_status`：还款状态
- `data.allocations`：分配明细
- `data.transaction`：交易流水
- `data.reconcile_status`：对账状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 repayment_record、repayment_allocation、account_transaction、reconciliation_result。
- 校验返回对象在当前渠道和操作员权限范围内。
- 组装还款状态、分配明细、交易流水、对账状态并返回。

#### 8.7. `GET /api/v1/overdues`
说明：查询逾期记录。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Query：`customer_no`、`contract_no`、逾期阶段、逾期状态、`page_no`、`page_size`
- Body：无

响应：

- `data.list[].overdue_no`：逾期编号
- `data.list[].overdue_days`：逾期天数
- `data.list[].overdue_total_amount`：逾期总金额
- `data.list[].collection_status`：催收状态
- `data.page_no`：当前页码
- `data.page_size`：每页条数
- `data.total_count`：总记录数
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 overdue_record、collection_case。
- 校验返回对象在当前渠道和操作员权限范围内。
- 分页组装逾期编号、逾期天数、逾期总金额、催收状态并返回。

#### 8.8. `POST /api/v1/overdues/refresh`
说明：刷新逾期记录。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Body：`request_no`、`contract_no`、逾期计算日期

响应：

- `data.overdue_count`：逾期记录数
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、逾期刷新权限、合同状态和逾期计算日期。
- 读取并锁定合同、还款计划、还款账单和既有逾期记录。
- 按逾期计算日期识别未结清且超过应还日的账单。
- 在同一事务内生成或更新 `overdue_record`，同步账单逾期状态、计划逾期状态、合同逾期状态和催收案件状态。
- 返回逾期记录数。

#### 8.9. `POST /api/v1/fee-reductions`
说明：发起费用减免申请。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Body：`request_no`、`bill_no`、减免类型、减免金额、原因

响应：

- `data.reduction_no`：减免编号
- `data.reduction_status`：减免状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、费用减免申请权限和请求字段格式。
- 读取并锁定 `repayment_bill`、`loan_contract`、`overdue_record` 和既有 `fee_reduction`。
- 校验账单状态、逾期状态、减免类型、减免金额和业务权限。
- 在同一事务内写入 `fee_reduction`，并创建费用减免审批流程实例和待审批任务。
- 返回减免编号、减免状态。

#### 8.10. `POST /api/v1/fee-reductions/{reduction_no}/approval`
说明：提交费用减免审批。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`reduction_no`
- Body：`request_no`、审批结果、审批金额、原因

响应：

- `data.reduction_no`：减免编号
- `data.reduction_status`：减免状态
- `data.bill_amount`：账单金额
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号和费用减免审批权限。
- 读取并锁定减免申请、还款账单、逾期记录和审批任务。
- 校验审批结果、审批金额、账单状态、逾期状态和完成时间。
- 在同一事务内更新 `fee_reduction` 审批结果；审批通过时同步更新 `repayment_bill` 未还金额和减免金额，存在逾期记录时同步更新 `overdue_record.reduced_amount` 和未结清金额；审批拒绝时保持账单和逾期金额不变；完成审批任务并同步流程实例状态。
- 返回减免编号、减免状态、账单金额。

### 9. 风控与反洗钱接口
| 方法   | 路径                                             | 接口说明          | 主要入参                                                                      | 主要出参                                   | 关联表                                                |
| ------ | ------------------------------------------------ | ----------------- | ----------------------------------------------------------------------------- | ------------------------------------------ | ----------------------------------------------------- |
| `POST` | `/api/v1/risk/events`                            | 创建风险事件      | `request_no`、`customer_no`、`related_type`、`related_id`、事件类型、风险评分 | 风险事件编号、决策动作、命中规则           | `risk_event`、`risk_rule`、`risk_strategy`、`risk_hit_record`、`manual_review_task`、`fund_freeze`、`fund_freeze_operation`、`account_ledger`、`customer_status_history`、`bank_account_status_history`、`customer`、`bank_account`、`account_transaction`、`credit_application`、`loan_application`、`wealth_order`、`collection_case` |
| `GET`  | `/api/v1/risk/events/{event_no}`                 | 查询风险事件详情  | `event_no`                                                                    | 事件信息、命中记录、处置结果、人工复核任务 | `risk_event`、`risk_hit_record`、`manual_review_task` |
| `POST` | `/api/v1/manual-review/tasks/{task_no}/complete` | 完成人工复核任务  | `request_no`、`task_no`、复核结果、复核意见                                   | 任务编号、任务状态、业务对象类型、业务对象编号、业务对象状态 | `manual_review_task`、`risk_event`、`credit_application`、`loan_application`、`wealth_order`、`fee_reduction`、`aml_case` |
| `GET`  | `/api/v1/blacklists`                             | 查询黑名单记录    | `customer_no`、证件号、手机号、黑名单状态、`page_no`、`page_size`             | 黑名单编号、风险等级、黑名单状态           | `blacklist_record`                                    |
| `POST` | `/api/v1/blacklists`                             | 新增黑名单记录    | `request_no`、客户或证件信息、风险等级、原因、有效期                          | 黑名单编号、黑名单状态                     | `blacklist_record`、`customer`、`dim_risk_level`      |
| `POST` | `/api/v1/aml/cases`                              | 创建 AML 案件     | `request_no`、`customer_no`、风险事件编号、案件类型、可疑原因、涉案交易列表   | AML 案件编号、案件状态                     | `risk_event`、`aml_case`、`aml_case_transaction`、`customer`、`account_transaction` |
| `POST` | `/api/v1/aml/cases/{case_no}/review-results`     | 提交 AML 复核结果 | `request_no`、`case_no`、复核结果、是否报送、复核意见                         | 复核编号、案件状态、报告编号               | `aml_case`、`aml_review_result`、`suspicious_transaction_report` |
| `GET`  | `/api/v1/aml/reports/{report_no}`                | 查询可疑交易报告  | `report_no`                                                                   | 报告状态、报送交易总金额、报送时间、案件信息 | `suspicious_transaction_report`、`aml_case`           |

接口明细：

#### 9.1. `POST /api/v1/risk/events`
说明：创建风险事件。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Body：`request_no`、`customer_no`、`related_type`、`related_id`、事件类型、风险评分

响应：

- `data.event_no`：风险事件编号
- `data.decision_action`：决策动作
- `data.hit_rules`：命中规则
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、风险事件字段和命中规则。
- 读取并校验 `customer`、`risk_rule`、`risk_strategy`，以及 `bank_account`、`account_transaction`、`credit_application`、`loan_application`、`wealth_order` 或 `collection_case` 对应风险关联对象。
- 校验主体一致性、状态流转、时间顺序和风险决策权限。
- 在同一事务内写入风险事件和命中记录；决策为人工复核时生成 `manual_review_task`，决策为冻结时生成资金冻结、冻结操作、账户冻结流水、客户状态历史或账户状态历史，并同步更新客户或账户当前状态和账户冻结金额。
- 返回风险事件编号、决策动作、命中规则。

#### 9.2. `GET /api/v1/risk/events/{event_no}`
说明：查询风险事件详情。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`event_no`
- Query：无
- Body：无

响应：

- `data.event_info`：事件信息
- `data.hit_records`：命中记录
- `data.disposal_result`：处置结果
- `data.manual_review_task`：人工复核任务
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 risk_event、risk_hit_record、manual_review_task。
- 校验返回对象在当前渠道和操作员权限范围内。
- 组装事件信息、命中记录、处置结果、人工复核任务并返回。

#### 9.3. `POST /api/v1/manual-review/tasks/{task_no}/complete`
说明：完成人工复核任务。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`task_no`
- Body：`request_no`、复核结果、复核意见

响应：

- `data.task_no`：任务编号
- `data.task_status`：任务状态
- `data.related_type`：业务对象类型
- `data.related_no`：业务对象编号
- `data.business_status`：业务对象状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号和处理权限。
- 读取并锁定人工复核任务；`risk_event_id` 不为空时读取并锁定风险事件；`task_type = risk_review` 时 `related_type` 必须为 `risk_event` 且 `related_id` 必须等于风险事件 ID；`task_type = aml_review` 时 `related_type` 必须为 `aml_case`；其他复核任务按 `related_type` 读取并锁定 `credit_application`、`loan_application`、`wealth_order` 或 `fee_reduction` 对应复核业务对象。
- 校验复核任务当前状态必须为 `pending` 或 `processing`，复核结果必须为 `approved` 或 `rejected`，已 `approved`、`rejected` 或 `cancelled` 的任务不得重复处理；校验业务状态、处理人角色、权限编码和完成时间。
- 在同一事务内更新 `manual_review_task.review_result`、`review_comment`、`task_status`、`completed_at`；存在风险事件时同步风险事件处置状态；不存在风险事件时按 `related_type` 同步回写授信申请、贷款申请、理财订单、费用减免或 AML 案件状态。
- 返回任务编号、任务状态、业务对象类型、业务对象编号、业务对象状态。

#### 9.4. `GET /api/v1/blacklists`
说明：查询黑名单记录。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Query：`customer_no`、证件号、手机号、黑名单状态、`page_no`、`page_size`
- Body：无

响应：

- `data.list[].blacklist_no`：黑名单编号
- `data.list[].risk_level`：风险等级
- `data.list[].blacklist_status`：黑名单状态
- `data.page_no`：当前页码
- `data.page_size`：每页条数
- `data.total_count`：总记录数
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 blacklist_record。
- 校验返回对象在当前渠道和操作员权限范围内。
- 分页组装黑名单编号、风险等级、黑名单状态并返回。

#### 9.5. `POST /api/v1/blacklists`
说明：新增黑名单记录。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Body：`request_no`、客户或证件信息、风险等级、原因、有效期

响应：

- `data.blacklist_no`：黑名单编号
- `data.blacklist_status`：黑名单状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、黑名单维护权限和请求字段格式。
- 读取并校验 `customer`、`dim_risk_level` 和既有 `blacklist_record`。
- 校验客户或证件主体、风险等级、有效期、黑名单状态和业务权限。
- 在同一事务内写入或更新 `blacklist_record`。
- 返回黑名单编号、黑名单状态。

#### 9.6. `POST /api/v1/aml/cases`
说明：创建 AML 案件。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Body：`request_no`、`customer_no`、风险事件编号、案件类型、可疑原因、涉案交易列表

响应：

- `data.case_no`：AML 案件编号
- `data.case_status`：案件状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、AML 建案权限和请求字段格式。
- 读取并校验客户、风险事件和涉案交易列表；涉案交易列表必须包含账户交易编号、是否纳入案件统计和纳入原因。
- 校验 AML 案件客户、风险事件和交易主体一致，且风险事件状态允许创建 AML 案件。
- 在同一事务内写入 `aml_case` 和 `aml_case_transaction`。
- 返回AML 案件编号、案件状态。

#### 9.7. `POST /api/v1/aml/cases/{case_no}/review-results`
说明：提交 AML 复核结果。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`case_no`
- Body：`request_no`、复核结果、是否报送、复核意见

响应：

- `data.review_no`：复核编号
- `data.case_status`：案件状态
- `data.report_no`：报告编号
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号和处理权限。
- 读取并锁定 AML 案件、复核记录和可疑交易报告。
- 校验复核结果、案件状态、处理人角色和完成时间。
- 在同一事务内写入 `aml_review_result` 并同步更新 AML 案件状态；需要报送时生成 `suspicious_transaction_report`。
- 返回复核编号、案件状态、报告编号。

#### 9.8. `GET /api/v1/aml/reports/{report_no}`
说明：查询可疑交易报告。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`report_no`
- Query：无
- Body：无

响应：

- `data.report_status`：报告状态
- `data.total_transaction_amount`：报送交易总金额
- `data.reported_at`：报送时间
- `data.case_info`：案件信息
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 suspicious_transaction_report、aml_case。
- 校验返回对象在当前渠道和操作员权限范围内。
- 组装报告状态、报送交易总金额、报送时间、案件信息并返回。

### 10. 催收接口
| 方法   | 路径                                                      | 接口说明           | 主要入参                                               | 主要出参                               | 关联表                                                              |
| ------ | --------------------------------------------------------- | ------------------ | ------------------------------------------------------ | -------------------------------------- | ------------------------------------------------------------------- |
| `POST` | `/api/v1/collection/cases`                                | 创建催收案件       | `request_no`、`overdue_no`、催收阶段、分案金额、催收员 | 催收案件编号、案件状态                 | `collection_case`、`overdue_record`、`loan_contract`                |
| `GET`  | `/api/v1/collection/cases/{case_no}`                      | 查询催收案件详情   | `case_no`                                              | 案件信息、联系记录、承诺还款、处置结果 | `collection_case`、`collection_contact_record`、`repayment_promise`、`collection_action`、`legal_case`、`loan_write_off`、`loan_restructure`、`collateral_disposal` |
| `POST` | `/api/v1/collection/cases/{case_no}/actions`              | 记录催收动作       | `request_no`、`case_no`、动作类型、动作结果               | 动作编号、案件状态                     | `collection_action`、`collection_case`、`customer`、`loan_contract`、`overdue_record` |
| `POST` | `/api/v1/collection/cases/{case_no}/contacts`             | 记录催收联系       | `request_no`、`case_no`、联系方法、联系结果、联系内容、下次跟进时间、承诺日期、承诺金额 | 联系记录编号、案件状态                 | `collection_contact_record`、`collection_case`、`repayment_promise`、`repayment_record`、`customer`、`loan_contract`、`overdue_record` |
| `POST` | `/api/v1/collection/cases/{case_no}/promises`             | 记录承诺还款       | `request_no`、`case_no`、承诺日期、承诺金额                       | 承诺编号、承诺状态                     | `repayment_promise`、`collection_case`、`customer`、`loan_contract`、`overdue_record` |
| `POST` | `/api/v1/collection/cases/{case_no}/repayments`           | 记录催收回款       | `request_no`、`case_no`、`bill_no`、`account_no`、回款金额、`promise_no` | 还款编号、还款状态、交易编号、案件状态 | `repayment_record`、`repayment_allocation`、`account_transaction`、`channel_transaction`、`account_ledger`、`reconciliation_batch`、`reconciliation_result`、`collection_case`、`repayment_bill`、`overdue_record`、`loan_contract`、`repayment_promise`、`credit_limit`、`credit_limit_change_log` |
| `POST` | `/api/v1/collection/cases/{case_no}/legal-cases`          | 创建法诉案件       | `request_no`、`case_no`、法务类型、诉请金额、受理时间             | 法诉案件编号、法诉状态                 | `collection_action`、`legal_case`、`collection_case`、`loan_contract`、`overdue_record` |
| `POST` | `/api/v1/collection/cases/{case_no}/write-offs`           | 发起贷款核销       | `request_no`、`case_no`、核销本金、核销利息、核销原因             | 核销编号、核销状态                     | `collection_action`、`loan_write_off`、`loan_contract`、`repayment_bill`、`overdue_record`、`collection_case` |
| `POST` | `/api/v1/collection/write-offs/{write_off_no}/approval`   | 审批贷款核销       | `request_no`、`write_off_no`、审批结果、审批金额、审批意见             | 核销编号、核销状态                     | `loan_write_off`、`collection_case`                                    |
| `POST` | `/api/v1/collection/write-offs/{write_off_no}/post`       | 核销入账           | `request_no`、`write_off_no`、入账日期                                | 核销编号、核销状态、合同状态           | `loan_write_off`、`loan_contract`、`repayment_bill`、`overdue_record`、`collection_case` |
| `POST` | `/api/v1/collection/cases/{case_no}/restructures`         | 发起贷款重组       | `request_no`、`case_no`、重组本金、重组期限、重组利率             | 重组编号、重组状态                     | `collection_action`、`loan_restructure`、`loan_contract`、`repayment_schedule`、`repayment_bill`、`overdue_record`、`collection_case` |
| `POST` | `/api/v1/collection/restructures/{restructure_no}/approval` | 审批贷款重组     | `request_no`、`restructure_no`、审批结果、审批意见                       | 重组编号、重组状态                     | `loan_restructure`、`collection_case`                                  |
| `POST` | `/api/v1/collection/restructures/{restructure_no}/effective` | 重组生效        | `request_no`、`restructure_no`、生效日期                                 | 重组编号、重组状态、新还款计划         | `loan_restructure`、`loan_contract`、`repayment_schedule`、`repayment_bill`、`overdue_record`、`collection_case` |
| `POST` | `/api/v1/collection/cases/{case_no}/collateral-disposals` | 记录抵押物处置     | `request_no`、`case_no`、抵押物编号、处置金额、回款金额、回款账户、处置方式 | 处置编号、抵押物状态、回款金额         | `collection_action`、`collection_case`、`collateral_disposal`、`bank_account`、`collateral_asset`、`repayment_record`、`repayment_allocation`、`account_transaction`、`channel_transaction`、`account_ledger`、`reconciliation_batch`、`reconciliation_result`、`repayment_bill`、`overdue_record`、`loan_contract`、`credit_limit`、`credit_limit_change_log` |
| `GET`  | `/api/v1/collection/performance-daily`                    | 查询催收绩效日统计 | `stat_date`、`employee_no`、催收阶段、币种、`page_no`、`page_size` | 催收绩效日统计列表                     | `collection_performance_daily`、`dim_employee`                      |

接口明细：

#### 10.1. `POST /api/v1/collection/cases`
说明：创建催收案件。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Body：`request_no`、`overdue_no`、催收阶段、分案金额、催收员

响应：

- `data.case_no`：催收案件编号
- `data.case_status`：案件状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、催收案件创建权限和请求字段格式。
- 读取并锁定 `overdue_record`、`loan_contract` 和既有 `collection_case`。
- 校验逾期状态、合同状态、催收阶段、分案金额、催收员和业务权限。
- 在同一事务内写入 `collection_case`。
- 返回催收案件编号、案件状态。

#### 10.2. `GET /api/v1/collection/cases/{case_no}`
说明：查询催收案件详情。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`case_no`
- Query：无
- Body：无

响应：

- `data.case_info`：案件信息
- `data.contact_records`：联系记录
- `data.repayment_promises`：承诺还款
- `data.disposal_result`：处置结果
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 collection_case、collection_contact_record、repayment_promise、collection_action、legal_case、loan_write_off、loan_restructure、collateral_disposal。
- 校验返回对象在当前渠道和操作员权限范围内。
- 组装案件信息、联系记录、承诺还款、处置结果并返回。

#### 10.3. `POST /api/v1/collection/cases/{case_no}/actions`
说明：记录催收动作。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`case_no`
- Body：`request_no`、动作类型、动作结果

响应：

- `data.action_no`：动作编号
- `data.case_status`：案件状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、催收动作记录权限和请求字段格式。
- 读取并锁定 `collection_case` 和既有 `collection_action`。
- 校验案件状态、动作类型、动作结果、时间顺序和业务权限。
- 在同一事务内写入 `collection_action` 并同步案件处置状态。
- 返回动作编号、案件状态。

#### 10.4. `POST /api/v1/collection/cases/{case_no}/contacts`
说明：记录催收联系。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`case_no`
- Body：`request_no`、联系方法、联系结果、联系内容、下次跟进时间、承诺日期、承诺金额

响应：

- `data.contact_record_id`：联系记录 ID
- `data.case_status`：案件状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、催收联系记录权限和请求字段格式。
- 读取并锁定 `collection_case`、既有 `collection_contact_record`、`repayment_promise` 和 `repayment_record`。
- 校验案件状态、联系结果、承诺要素、已还款记录和业务权限。
- 在同一事务内写入联系记录；联系结果为承诺还款时同步写入 `repayment_promise`；联系结果为已还款时必须校验存在对应成功 `repayment_record`。
- 返回联系记录 ID、案件状态。

#### 10.5. `POST /api/v1/collection/cases/{case_no}/promises`
说明：记录承诺还款。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`case_no`
- Body：`request_no`、承诺日期、承诺金额

响应：

- `data.promise_no`：承诺编号
- `data.promise_status`：承诺状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号和承诺还款字段格式。
- 读取并校验催收案件、客户、合同、逾期记录和催收员权限。
- 校验承诺日期、承诺金额和案件状态。
- 在同一事务内写入 `repayment_promise`，不生成资金流水和对账结果。
- 返回承诺编号、承诺状态。

#### 10.6. `POST /api/v1/collection/cases/{case_no}/repayments`
说明：记录催收回款。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`case_no`
- Body：`request_no`、`bill_no`、`account_no`、回款金额、`promise_no`

响应：

- `data.repayment_no`：还款编号
- `data.repayment_status`：还款状态
- `data.transaction_no`：交易编号
- `data.case_status`：案件状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、催收回款权限、回款金额精度和催收案件状态。
- 读取并锁定催收案件、账单、还款账户、合同、逾期记录、承诺还款和既有回款记录。
- 校验主体、账户、币种、金额、案件和逾期状态一致。
- 在同一事务内写入催收回款记录；回款成功时生成分配明细、账户交易、渠道流水、账户流水，读取或创建同渠道同回款日对账批次，生成对账结果和额度释放流水，并同步账单、逾期、合同剩余本金、合同状态、授信额度、承诺还款履约状态和催收案件状态；回款失败时仅记录失败状态和失败原因，不生成分配明细、资金流水或业务余额变动。
- 返回还款编号、还款状态、交易编号、案件状态。

#### 10.7. `POST /api/v1/collection/cases/{case_no}/legal-cases`
说明：创建法诉案件。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`case_no`
- Body：`request_no`、法务类型、诉请金额、受理时间

响应：

- `data.legal_case_no`：法诉案件编号
- `data.legal_status`：法诉状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号和处置权限。
- 读取并锁定催收案件、合同、逾期记录和催收动作。
- 先生成或校验对应 `collection_action`，保证处置动作与案件断点可追溯。
- 在同一事务内写入 `legal_case` 并同步案件法务处置状态。
- 返回法诉案件编号、法诉状态。

#### 10.8. `POST /api/v1/collection/cases/{case_no}/write-offs`
说明：发起贷款核销。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`case_no`
- Body：`request_no`、核销本金、核销利息、核销原因

响应：

- `data.write_off_no`：核销编号
- `data.write_off_status`：核销状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号和处置权限。
- 读取并锁定催收案件、合同、账单、逾期记录和催收动作。
- 先生成或校验对应 `collection_action`，保证处置动作与案件断点可追溯。
- 在同一事务内写入 `loan_write_off`，初始状态为 `submitted`，并同步案件处置状态。
- 返回核销编号、核销状态。

#### 10.9. `POST /api/v1/collection/write-offs/{write_off_no}/approval`
说明：审批贷款核销。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`write_off_no`
- Body：`request_no`、审批结果、审批金额、审批意见

响应：

- `data.write_off_no`：核销编号
- `data.write_off_status`：核销状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号和核销审批权限。
- 读取并锁定核销申请和催收案件。
- 校验核销状态、审批金额、审批分项和审批时间。
- 在同一事务内更新 `loan_write_off` 审批状态和审批信息。
- 返回核销编号、核销状态。

#### 10.10. `POST /api/v1/collection/write-offs/{write_off_no}/post`
说明：核销入账。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`write_off_no`
- Body：`request_no`、入账日期

响应：

- `data.write_off_no`：核销编号
- `data.write_off_status`：核销状态
- `data.contract_status`：合同状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、入账权限和入账日期。
- 读取并锁定已审批核销、合同、账单、逾期记录和催收案件。
- 校验核销金额不超过未结清金额，核销本金不超过合同剩余本金。
- 在同一事务内更新 `loan_write_off` 为 `posted`，并同步合同核销本金、合同剩余本金、合同状态、账单核销金额、账单未还金额、账单状态、逾期核销金额、逾期状态和案件状态。
- 返回核销编号、核销状态、合同状态。

#### 10.11. `POST /api/v1/collection/cases/{case_no}/restructures`
说明：发起贷款重组。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`case_no`
- Body：`request_no`、重组本金、重组期限、重组利率

响应：

- `data.restructure_no`：重组编号
- `data.restructure_status`：重组状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号和处置权限。
- 读取并锁定催收案件、合同、原还款计划、账单、逾期记录和催收动作。
- 先生成或校验对应 `collection_action`，保证处置动作与案件断点可追溯。
- 在同一事务内写入 `loan_restructure`，初始状态为 `submitted`，并同步案件处置状态。
- 返回重组编号、重组状态。

#### 10.12. `POST /api/v1/collection/restructures/{restructure_no}/approval`
说明：审批贷款重组。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`restructure_no`
- Body：`request_no`、审批结果、审批意见

响应：

- `data.restructure_no`：重组编号
- `data.restructure_status`：重组状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号和重组审批权限。
- 读取并锁定重组申请和催收案件。
- 校验重组状态、审批结果、重组本金、重组期限、重组利率和审批时间。
- 在同一事务内更新 `loan_restructure` 审批状态和审批信息。
- 返回重组编号、重组状态。

#### 10.13. `POST /api/v1/collection/restructures/{restructure_no}/effective`
说明：重组生效。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`restructure_no`
- Body：`request_no`、生效日期

响应：

- `data.restructure_no`：重组编号
- `data.restructure_status`：重组状态
- `data.new_repayment_schedule`：新还款计划
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、生效权限和生效日期。
- 读取并锁定已审批重组、合同、原还款计划、账单、逾期记录和催收案件。
- 校验重组后本金、资本化金额、减免金额和新计划版本。
- 在同一事务内更新 `loan_restructure` 为 `effective`，同步合同重组本金、剩余本金和合同状态，关闭、调整或迁移原未结清账单、逾期记录和催收案件，并生成新版本还款计划。
- 返回重组编号、重组状态、新还款计划。

#### 10.14. `POST /api/v1/collection/cases/{case_no}/collateral-disposals`
说明：记录抵押物处置。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`case_no`
- Body：`request_no`、抵押物编号、处置金额、回款金额、回款账户、处置方式

响应：

- `data.disposal_no`：处置编号
- `data.collateral_status`：抵押物状态
- `data.received_amount`：回款金额
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、处置权限、处置金额、回款金额和回款账户。
- 读取并锁定催收案件、催收动作、抵押物、合同和逾期记录。
- 先生成或校验对应 `collection_action`，保证处置动作与案件断点可追溯。
- 在同一事务内写入抵押物处置记录；存在现金回收时同步生成还款记录、分配明细、账户交易、渠道流水、账户流水，读取或创建同渠道同回款日对账批次，生成对账结果和额度释放流水，并同步账单已还金额、账单未还金额、账单状态、逾期已还金额、逾期未结清金额、逾期状态、合同剩余本金、合同状态、逾期回收金额和催收案件状态。
- 返回处置编号、抵押物状态、回款金额。

#### 10.15. `GET /api/v1/collection/performance-daily`
说明：查询催收绩效日统计。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Query：`stat_date`、`employee_no`、催收阶段、币种、`page_no`、`page_size`
- Body：无

响应：

- `data.list[].stat_date`：统计日期
- `data.list[].employee_no`：催收员工编号
- `data.list[].collection_stage`：催收阶段
- `data.list[].currency_code`：币种
- `data.list[].assigned_amount`：分案金额
- `data.list[].recovered_amount`：回收金额
- `data.list[].recovery_rate`：回收率
- `data.page_no`：当前页码
- `data.page_size`：每页条数
- `data.total_count`：总记录数
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 collection_performance_daily、dim_employee。
- 校验返回对象在当前渠道和操作员权限范围内。
- 分页组装分案金额、回收金额、回收率并返回。

### 11. 运营支撑接口
| 方法   | 路径                                            | 接口说明         | 主要入参                                                                                  | 主要出参                             | 关联表                                        |
| ------ | ----------------------------------------------- | ---------------- | ----------------------------------------------------------------------------------------- | ------------------------------------ | --------------------------------------------- |
| `POST` | `/api/v1/workflow/instances`                    | 创建流程实例     | `request_no`、流程类型、`related_type`、`related_id`、`initiator_type`、`initiator_no`     | 流程实例编号、实例状态               | `workflow_instance`、`workflow_task`、`credit_application`、`loan_application`、`wealth_order`、`fee_reduction`、`risk_event`、`support_ticket` |
| `GET`  | `/api/v1/workflow/instances/{instance_no}`      | 查询流程实例详情 | `instance_no`                                                                             | 实例状态、任务列表、任务处理记录     | `workflow_instance`、`workflow_task`          |
| `POST` | `/api/v1/workflow/tasks/{task_no}/complete`     | 完成流程任务     | `request_no`、`task_no`、处理结果、处理意见                                               | 任务编号、任务状态、实例状态、业务对象类型、业务对象编号、业务对象状态 | `workflow_task`、`workflow_instance`、`credit_application`、`loan_application`、`wealth_order`、`fee_reduction`、`risk_event`、`support_ticket` |
| `POST` | `/api/v1/notifications`                         | 发送业务通知     | `request_no`、`customer_no`、通知类型、通知渠道、通知关联对象类型、通知关联对象编号可为空 | 消息编号、发送状态                   | `notification_message`、`customer`、`customer_contact`、`customer_device`、`account_transaction`、`wealth_order`、`loan_contract`、`repayment_bill`、`collection_case`、`support_ticket` |
| `GET`  | `/api/v1/customers/{customer_no}/notifications` | 查询客户通知     | `customer_no`、通知类型、发送状态、`page_no`、`page_size`                                  | 通知消息列表                         | `notification_message`                        |
| `POST` | `/api/v1/support/tickets`                       | 创建客服工单     | `request_no`、`customer_no`、工单类型、工单标题、工单内容、工单关联对象类型、工单关联对象编号 | 工单编号、工单状态                   | `support_ticket`、`workflow_instance`、`workflow_task`、`customer`、`account_transaction`、`wealth_order`、`loan_application`、`repayment_bill` |
| `GET`  | `/api/v1/support/tickets/{ticket_no}`           | 查询客服工单详情 | `ticket_no`                                                                               | 工单信息、处理人、处理结果、客户反馈 | `support_ticket`、`support_ticket_feedback`、`dim_employee` |
| `POST` | `/api/v1/support/tickets/{ticket_no}/feedback`  | 提交工单反馈     | `request_no`、`ticket_no`、确认结果、满意度评分、反馈内容                                              | 反馈编号、确认状态                   | `support_ticket_feedback`、`support_ticket`  |
| `GET`  | `/api/v1/metrics/daily`                         | 查询业务日统计   | `stat_date`、`stat_domain`、`metric_code`、`branch_code`、`channel_code`、`currency_code`、`page_no`、`page_size` | 业务日统计列表                       | `business_stat_daily`、`business_metric_dict` |

接口明细：

#### 11.1. `POST /api/v1/workflow/instances`
说明：创建流程实例。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Body：`request_no`、流程类型、`related_type`、`related_id`、`initiator_type`、`initiator_no`

响应：

- `data.instance_no`：流程实例编号
- `data.instance_status`：流程实例状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、流程发起权限和请求字段格式。
- 读取并校验 `related_type` 指向的授信申请、贷款申请、理财订单、费用减免、风险事件或客服工单；`loan_approval` 只能关联 `credit_application` 或 `loan_application`，`wealth_review` 只能关联 `wealth_order` 或 `risk_event`，`fee_reduction` 只能关联 `fee_reduction`，`risk_review` 只能关联 `risk_event`，`support_ticket` 只能关联 `support_ticket`。
- 校验关联对象状态、流程类型、发起人类型、发起人编号、时间顺序和业务权限。
- 在同一事务内写入 `workflow_instance` 和初始 `workflow_task`。
- 返回流程实例编号、流程实例状态。

#### 11.2. `GET /api/v1/workflow/instances/{instance_no}`
说明：查询流程实例详情。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`instance_no`
- Query：无
- Body：无

响应：

- `data.instance_status`：流程实例状态
- `data.tasks`：任务列表
- `data.task_records`：任务处理记录
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 workflow_instance、workflow_task。
- 校验返回对象在当前渠道和操作员权限范围内。
- 组装流程实例状态、任务列表、任务处理记录并返回。

#### 11.3. `POST /api/v1/workflow/tasks/{task_no}/complete`
说明：完成流程任务。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`task_no`
- Body：`request_no`、处理结果、处理意见

响应：

- `data.task_no`：任务编号
- `data.task_status`：任务状态
- `data.instance_status`：流程实例状态
- `data.related_type`：业务对象类型
- `data.related_no`：业务对象编号
- `data.business_status`：业务对象状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号和处理权限。
- 读取并锁定 `credit_application`、`loan_application`、`wealth_order`、`fee_reduction`、`risk_event` 或 `support_ticket` 对应流程业务对象，以及流程实例和流程任务。
- 校验流程实例状态必须为 `running`，流程任务当前状态必须为 `pending` 或 `processing`，已 `approved`、`rejected`、`skipped` 或 `cancelled` 的任务不得重复处理；校验处理结果、业务状态、处理人角色和完成时间。
- 在同一事务内更新 `workflow_task.task_status`、`task_result`、`task_comment` 和 `completed_at`；最后一个必需任务完成后更新 `workflow_instance.instance_status`，并同步更新授信申请、贷款申请、理财订单、费用减免、风险事件或客服工单最终状态。
- 返回任务编号、任务状态、流程实例状态、业务对象类型、业务对象编号、业务对象状态。

#### 11.4. `POST /api/v1/notifications`
说明：发送业务通知。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Body：`request_no`、`customer_no`、通知类型、通知渠道、通知关联对象类型、通知关联对象编号可为空；无关联系统通知使用 `related_type = none` 且不传通知关联对象编号

响应：

- `data.message_no`：消息编号
- `data.send_status`：发送状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、通知发送权限和请求字段格式。
- 读取并校验 `customer`、`customer_contact`、`customer_device`，以及 `account_transaction`、`wealth_order`、`loan_contract`、`repayment_bill`、`collection_case`、`support_ticket` 或 `none` 对应通知关联对象。
- 校验客户状态、通知类型、通知渠道、手机号、邮箱、站内信账户、App 设备可达性、关联对象状态和业务权限；`app_push` 必须存在 `device_type IN ('ios', 'android')` 且 `push_token` 不为空的非黑名单设备。
- 在同一事务内写入 `notification_message`；可立即发送时状态为 `success` 或 `failed`，异步发送时状态为 `pending`，取消发送时状态为 `cancelled`。
- 返回消息编号、发送状态。

#### 11.5. `GET /api/v1/customers/{customer_no}/notifications`
说明：查询客户通知。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`customer_no`
- Query：通知类型、发送状态、`page_no`、`page_size`
- Body：无

响应：

- `data.list[]`：通知消息列表
- `data.page_no`：当前页码
- `data.page_size`：每页条数
- `data.total_count`：总记录数
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 notification_message。
- 校验返回对象在当前渠道和操作员权限范围内。
- 分页组装通知消息列表并返回。

#### 11.6. `POST /api/v1/support/tickets`
说明：创建客服工单。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Body：`request_no`、`customer_no`、工单类型、工单标题、工单内容、工单关联对象类型、工单关联对象编号

响应：

- `data.ticket_no`：工单编号
- `data.ticket_status`：工单状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、工单创建权限和请求字段格式。
- 读取并校验 `customer`，以及 `account_transaction`、`wealth_order`、`loan_application`、`repayment_bill` 或 `support_ticket` 对应工单关联对象。
- 校验客户状态、工单类型、关联对象状态、时间顺序和业务权限。
- 在同一事务内写入 `support_ticket.ticket_title`、`ticket_content` 和其他工单字段，并创建客服工单流程实例和待处理任务。
- 返回工单编号、工单状态。

#### 11.7. `GET /api/v1/support/tickets/{ticket_no}`
说明：查询客服工单详情。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`ticket_no`
- Query：无
- Body：无

响应：

- `data.ticket_info`：工单信息
- `data.handler`：处理人
- `data.process_result`：处理结果
- `data.feedback`：客户反馈
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 support_ticket、support_ticket_feedback、dim_employee。
- 校验返回对象在当前渠道和操作员权限范围内。
- 组装工单信息、处理人、处理结果、客户反馈并返回。

#### 11.8. `POST /api/v1/support/tickets/{ticket_no}/feedback`
说明：提交工单反馈。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Path：`ticket_no`
- Body：`request_no`、确认结果、满意度评分、反馈内容

响应：

- `data.feedback_no`：反馈编号
- `data.confirm_status`：确认状态
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息、幂等号、工单反馈权限和请求字段格式。
- 读取并锁定 `support_ticket` 和既有 `support_ticket_feedback`。
- 校验工单状态、确认结果、满意度评分、反馈内容和业务权限。
- 在同一事务内写入 `support_ticket_feedback` 并同步工单确认状态。
- 返回反馈编号、确认状态。

#### 11.9. `GET /api/v1/metrics/daily`
说明：查询业务日统计。

请求：

- Header：`Authorization`、`X-Request-Id`、`X-Channel-Code`、`X-Operator-No`
- Query：`stat_date`、`stat_domain`、`metric_code`、`branch_code`、`channel_code`、`currency_code`、`page_no`、`page_size`
- Body：无

响应：

- `data.list[].stat_date`：统计日期
- `data.list[].stat_domain`：统计域
- `data.list[].metric_code`：指标编码
- `data.list[].branch_code`：机构编码
- `data.list[].channel_code`：渠道编码
- `data.list[].currency_code`：币种
- `data.list[].metric_value`：指标值
- `data.page_no`：当前页码
- `data.page_size`：每页条数
- `data.total_count`：总记录数
- `request_id`：请求追踪编号

内部步骤：

- 校验请求头、鉴权信息和查询参数格式。
- 按查询条件读取 business_stat_daily、business_metric_dict。
- 校验返回对象在当前渠道和操作员权限范围内。
- 分页组装统计日期、统计域、指标编码、机构、渠道、币种和指标值并返回。
