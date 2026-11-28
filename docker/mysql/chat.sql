/**
  chat 库：多轮问数的会话记录

  单独成库而不是放进 meta，原因是数据性质完全不同：
    meta 是“描述层”，表结构由 meta.sql 定义、内容由 build 脚本生成，
    整库可以随时 DROP 后原样重建，丢了不会有任何损失；
    chat_turn 是用户真实问答留下的记录，重建不出来，丢了就永久丢失。

  放在同一个库里，重建元数据时就必须连聊天记录一起清掉，
  反过来也因为怕误删而不敢重建元数据。分开之后两边各自独立。

  同一份数据的两种用法也在这里体现：
    落库存“全量档案”（原话、改写后的问题、槽位、SQL、结果快照），用于回放和排查；
    但进提示词的只有 slots 这一层小对象，SQL 和结果不会塞回上下文。
 */

SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS chat DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
GRANT ALL PRIVILEGES ON chat.* TO 'didilili'@'%';

USE chat;


/**
  多轮会话记录表
  一次问答一行，业务上靠 session_id + seq 定位
 */
DROP TABLE IF EXISTS chat_turn;
CREATE TABLE chat_turn
(
    id              BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    session_id      VARCHAR(64) NOT NULL COMMENT '会话编号',
    seq             INT         NOT NULL COMMENT '会话内轮次',
    user_query      TEXT COMMENT '用户原话',
    rewritten_query TEXT COMMENT '改写后的完整问题',
    slots           JSON COMMENT '结构化槽位',
    sql_text        TEXT COMMENT '本轮生成的SQL',
    row_count       INT COMMENT '结果行数',
    result          JSON COMMENT '结果集快照',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    KEY idx_session_seq (session_id, seq)
);


/**
  会话索引表
  左侧会话列表只查这张表，不用每次把历史轮次全读一遍
  标题取首轮改写后的问题，不额外调用大模型
 */
DROP TABLE IF EXISTS chat_session;
CREATE TABLE chat_session
(
    session_id VARCHAR(64) PRIMARY KEY COMMENT '会话编号',
    title      VARCHAR(120) NOT NULL COMMENT '会话标题',
    turn_count INT DEFAULT 0 COMMENT '问答轮数',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
    remark     TEXT COMMENT '备注',
    KEY idx_updated_at (updated_at)
);
