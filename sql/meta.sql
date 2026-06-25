SET NAMES utf8mb4;

DROP TABLE IF EXISTS column_metric;
DROP TABLE IF EXISTS metric_info;
DROP TABLE IF EXISTS column_info;
DROP TABLE IF EXISTS table_info;

CREATE TABLE table_info (
    id VARCHAR(64) PRIMARY KEY COMMENT '表编号',
    name VARCHAR(128) COMMENT '表名称',
    role VARCHAR(32) COMMENT '表类型(fact/dim)',
    description TEXT COMMENT '表描述'
);

CREATE TABLE column_info (
    id VARCHAR(64) PRIMARY KEY COMMENT '列编号',
    name VARCHAR(128) COMMENT '列名称',
    type VARCHAR(64) COMMENT '数据类型',
    role VARCHAR(32) COMMENT '列类型(primary_key,foreign_key,measure,dimension)',
    examples JSON COMMENT '数据示例',
    description TEXT COMMENT '列描述',
    alias JSON COMMENT '列别名',
    table_id VARCHAR(64) COMMENT '所属表编号'
);

CREATE TABLE metric_info (
    id VARCHAR(64) PRIMARY KEY COMMENT '指标编码',
    name VARCHAR(128) COMMENT '指标名称',
    description TEXT COMMENT '指标描述',
    relevant_columns JSON COMMENT '关联的列',
    alias JSON COMMENT '指标别名'
);

CREATE TABLE column_metric (
    column_id VARCHAR(64) COMMENT '列编号',
    metric_id VARCHAR(64) COMMENT '指标编号',
    PRIMARY KEY (column_id, metric_id)
);
