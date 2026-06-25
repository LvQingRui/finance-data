# finance-data · 金融问数系统

面向零售银行、消费信贷和财富管理场景的智能问数项目。业务人员用自然语言提问，系统自动理解意图、生成 SQL、查询数据并返回结果，无需手写 SQL。

基于尚硅谷「掌柜问数」课程架构，在完整金融业务数据之上扩展 NL2SQL 能力。

---

## 项目亮点

- **92 张金融业务表**：覆盖客户、账户、交易、理财、信贷、还款、风控、催收全链路
- **NL2SQL 问数**：LangGraph 编排 13 节点智能体，支持指标查询、维度分析、趋势对比
- **RAG 元数据知识库**：MySQL 语义层 + Qdrant 向量召回 + Elasticsearch 维度值匹配
- **流式交互**：SSE 实时推送执行进度与查询结果
- **开箱即用**：数据生成脚本 + 调试页面 + 16 条验收用例

---

## 系统架构

```
用户提问 → POST /api/query (SSE)
              ↓
         LangGraph 问数智能体
              ↓
    关键词提取 → 三路召回（字段 / 指标 / 维度值）
              ↓
    过滤合并 → SQL 生成 → 校验 → 执行
              ↓
         返回查询结果
```

| 组件 | 作用 |
|------|------|
| MySQL `finance` | 业务数据仓库（92 表） |
| MySQL `meta` | 表/字段/指标语义元数据 |
| Qdrant | 字段与指标的向量语义召回 |
| Elasticsearch | 维度字段取值全文匹配 |
| TEI | 文本向量化（bge-large-zh-v1.5） |
| DeepSeek | 大模型 SQL 生成与修正 |

---

## 快速开始

### 1. 环境要求

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) 包管理器
- MySQL 8.0
- Qdrant、Elasticsearch（IK 分词）、TEI、DeepSeek API

### 2. 安装与配置

```bash
git clone git@github.com:LvQingRui/finance-data.git
cd finance-data

cp .env.example .env   # 填写数据库、API Key 等配置
uv sync
```

### 3. 初始化业务数据

```bash
uv run init_db.py                        # 创建 finance 库
uv run -m generate.main --profile full   # 生成模拟业务数据
```

### 4. 构建问数知识库

```bash
uv run init_meta.py                      # 创建 meta 元数据库
uv run -m app.scripts.build_meta_knowledge -c conf/meta_config.yaml
```

### 5. 启动服务

```bash
uv run -m app.main
```

| 入口 | 地址 |
|------|------|
| 问数调试页 | http://127.0.0.1:8000/static/query.html |
| Swagger 文档 | http://127.0.0.1:8000/docs |
| 问数 API | `POST /api/query` |

---

## 问数示例

```bash
curl -N -X POST http://127.0.0.1:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query":"最近30天交易金额是多少"}'
```

| 场景 | 示例问题 |
|------|----------|
| 客户 | 本月新增客户数是多少 |
| 账户 | 当前正常账户数是多少 |
| 交易 | 哪个渠道交易金额最高 |
| 理财 | 当前理财持仓规模是多少 |
| 信贷 | 本月放款金额是多少 |
| 还款 | 当前逾期余额是多少 |
| 风控 | 最近7天风险事件有多少 |
| 催收 | 催收回收率是多少 |

---

## 项目结构

```
finance-data/
├── app/
│   ├── agent/          # LangGraph 问数智能体
│   ├── api/            # 问数 API
│   ├── clients/        # MySQL / Qdrant / ES / TEI 客户端
│   ├── repositories/   # 数据访问层
│   └── routers/        # 业务 REST API
├── conf/
│   ├── app_config.yaml # 服务配置（敏感项走 .env）
│   └── meta_config.yaml# 18 张核心表 + 22 个指标定义
├── generate/           # 分层数据生成器
├── prompts/            # LLM 提示词
├── sql/                # 数据库 DDL
├── static/query.html   # 问数调试页
└── tests/              # API 与问数测试
```

---

## 配置说明

所有敏感信息通过 `.env` 管理，参考 [`.env.example`](./.env.example)：

| 变量 | 说明 |
|------|------|
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` | MySQL 连接 |
| `DB_NAME` | 业务库名（默认 `finance`） |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 |
| `QDRANT_HOST` / `QDRANT_PORT` | 向量数据库 |
| `ES_HOST` / `ES_PORT` | Elasticsearch |
| `TEI_HOST` / `TEI_PORT` | Embedding 推理服务 |

---

## 文档

- [业务表结构详细说明](./docs/DATA_SCHEMA.md) — 92 张表的字段、约束与 API 清单

---

## 技术栈

Python · FastAPI · LangGraph · LangChain · DeepSeek · Qdrant · Elasticsearch · MySQL · SQLAlchemy · uv

---

## License

MIT
