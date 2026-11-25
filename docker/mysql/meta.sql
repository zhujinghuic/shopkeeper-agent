
/**
  meta 库的定位是“描述层”，不是“建模层”。它要能把四件事说清楚就行：

    1.这张表是事实表还是维度表（table_info.role）
    2.这个字段是度量、维度还是主外键（column_info.role）
    3.指标依赖哪些字段（column_metric）
    4.字段怎么描述、有哪些别名、有什么示例值

    这四件事有地方放，表设计就“够用”了。项目这四张表也确实很朴素——alias 直接存 JSON 数组，没做严格范式化。
    对 RAG 场景这样反而更好：一次查询就能拿到完整对象，不用 join 一堆表。

 */
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



/**
  primary_key - 主键
  foreign_key - 外键
  measure - 度量 （例如-amount,quantity等）
  dimension - 维度 （普通信息字段-如 product_name,year,brand等）
 */
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
