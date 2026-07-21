SET NAMES utf8mb4;
CREATE DATABASE meta DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
GRANT ALL PRIVILEGES ON meta.* TO 'didilili'@'%';

USE meta;

DROP TABLE IF EXISTS table_info;
CREATE TABLE table_info
(
    id          VARCHAR(64) PRIMARY KEY COMMENT '表编号',
    name        VARCHAR(128) COMMENT '表名称',
    role        VARCHAR(32) COMMENT '表类型(fact/dim)',
    description TEXT COMMENT '表描述'
);



DROP TABLE IF EXISTS column_info;
CREATE TABLE column_info
(
    id          VARCHAR(64) PRIMARY KEY COMMENT '列编号',
    name        VARCHAR(128) COMMENT '列名称',
    type        VARCHAR(64) COMMENT '数据类型',
    role        VARCHAR(32) COMMENT '列类型(primary_key,foreign_key,measure,dimension)',
    examples    JSON COMMENT '数据示例',
    description TEXT COMMENT '列描述',
    alias       JSON COMMENT '列别名',
    table_id    VARCHAR(64) COMMENT '所属表编号'
);

DROP TABLE IF EXISTS metric_info;
CREATE TABLE metric_info
(
    id               VARCHAR(64) PRIMARY KEY COMMENT '指标编码',
    name             VARCHAR(128) COMMENT '指标名称',
    description      TEXT COMMENT '指标描述',
    relevant_columns JSON COMMENT '关联的列',
    alias            JSON COMMENT '指标别名'
);


DROP TABLE IF EXISTS column_metric;
CREATE TABLE column_metric
(
    column_id VARCHAR(64) COMMENT '列编号',
    metric_id VARCHAR(64) COMMENT '指标编号',
    PRIMARY KEY (column_id, metric_id)
);

DROP TABLE IF EXISTS query_history;
DROP TABLE IF EXISTS chat_session;

CREATE TABLE chat_session
(
    session_id VARCHAR(64) PRIMARY KEY COMMENT '会话 ID',
    title      VARCHAR(255) NULL COMMENT '会话标题',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) COMMENT='问数会话表';

CREATE TABLE query_history
(
    id             BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '历史记录 ID',
    session_id     VARCHAR(64) NOT NULL COMMENT '会话 ID',
    query          TEXT NOT NULL COMMENT '用户原始问题',
    resolved_query TEXT NULL COMMENT '结合上下文后的完整问题',
    sql_text       TEXT NULL COMMENT '本次生成或预览用 SQL',
    result_summary TEXT NULL COMMENT '结果摘要',
    result_data    JSON NULL COMMENT '查询结果数据，用于历史回看表格',
    context_trace  JSON NULL COMMENT '上下文改写轨迹，用于解释系统如何理解多轮追问',
    semantic_slots JSON NULL COMMENT '结构化语义槽位，用于多轮上下文继承',
    rewrite_confidence DECIMAL(5,4) NULL COMMENT '上下文改写置信度',
    status         VARCHAR(32) NOT NULL COMMENT '查询状态',
    error_message  TEXT NULL COMMENT '错误信息',
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_query_history_session_time (session_id, created_at),
    CONSTRAINT fk_query_history_session
        FOREIGN KEY (session_id) REFERENCES chat_session(session_id)
) COMMENT='问数查询历史表';
