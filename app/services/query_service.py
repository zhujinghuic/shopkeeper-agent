"""
问数查询服务

负责把 API 层传入的自然语言问题转换成一次 LangGraph 工作流执行：
先按 session_id 读会话历史并压成上下文，再创建初始 State、组装 Runtime Context，
消费 graph.astream 的流式输出并统一包装成 SSE 文本，最后把本轮问答落库。
"""

import json
import uuid

import jieba.analyse
from langchain_huggingface import HuggingFaceEndpointEmbeddings

from app.agent.context import DataAgentContext
from app.agent.graph import graph
from app.agent.memory import (
    TURN_FETCH_LIMIT,
    build_column_history,
    build_memory_text,
    build_sql_baseline,
    needs_recall,
)
from app.agent.state import DataAgentState
from app.core.log import logger
from app.core.serialization import rows_to_jsonable
from app.entities.chat_turn import ChatTurn
from app.entities.sql_audit import SQLAudit
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.chat.chat_memory_mysql_repository import (
    ChatMemoryMySQLRepository,
)
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository


class QueryService:
    """封装一次问数查询所需的业务编排逻辑"""

    def __init__(
        self,
        meta_mysql_repository: MetaMySQLRepository,
        embedding_client: HuggingFaceEndpointEmbeddings,
        dw_mysql_repository: DWMySQLRepository,
        column_qdrant_repository: ColumnQdrantRepository,
        metric_qdrant_repository: MetricQdrantRepository,
        value_es_repository: ValueESRepository,
        chat_memory_repository: ChatMemoryMySQLRepository,
    ):
        # MySQL 仓储分别负责元数据补全和真实数仓环境信息读取
        self.meta_mysql_repository = meta_mysql_repository
        self.dw_mysql_repository = dw_mysql_repository
        # 会话仓储负责多轮问答记录的读写，上下文压缩交给 agent.memory
        self.chat_memory_repository = chat_memory_repository

        # 召回链路依赖的向量检索、Embedding 和全文检索能力由依赖层注入
        self.embedding_client = embedding_client
        self.column_qdrant_repository = column_qdrant_repository
        self.metric_qdrant_repository = metric_qdrant_repository
        self.value_es_repository = value_es_repository

    async def query(self, query: str, session_id: str | None = None):
        """执行一次问数工作流，并逐段产出 SSE 消息"""

        # 前端没带 session_id 时生成一个，保证多轮记录始终有归属
        session_id = session_id or f"s-{uuid.uuid4().hex[:12]}"
        # 异步生成器。非阻塞IO，完美实现了后端在耗时处理的同时，还能实时、片段式地（流式）把进度和结果推送给前端
        yield self._sse({"type": "session", "session_id": session_id})

        # 会话记忆属于增强能力，读写失败不应该让整次问数失败
        history_text = ""
        sql_baseline = ""
        column_history = ""
        try:
            history_text, sql_baseline, column_history = await self._load_context(
                session_id, query
            )
        except Exception as e:
            logger.warning(f"加载会话历史失败，按单轮处理：{e}")

        # State 只放会被图节点读写和合并的业务数据，外部工具对象不塞进 State
        state = DataAgentState(
            query=query,
            session_id=session_id,
            history_text=history_text,
            sql_baseline=sql_baseline,
            column_history=column_history,
        )
        # Context 保存本次图执行需要复用的外部依赖，节点通过 runtime.context 读取
        context = DataAgentContext(
            column_qdrant_repository=self.column_qdrant_repository,
            embedding_client=self.embedding_client,
            metric_qdrant_repository=self.metric_qdrant_repository,
            value_es_repository=self.value_es_repository,
            meta_mysql_repository=self.meta_mysql_repository,
            dw_mysql_repository=self.dw_mysql_repository,
        )

        # values 模式会在每一步之后给出完整状态快照，用来拿到最终 SQL 和槽位落库
        final_state: dict = {}
        row_count: int | None = None
        result_rows: list | None = None

        try:
            async for mode, chunk in graph.astream(
                input=state,
                context=context,
                stream_mode=["custom", "values"],
            ):
                if mode == "values":
                    final_state = chunk
                    continue

                # custom 模式对应节点内部 writer(...) 写出的进度消息
                if chunk.get("type") == "result":
                    data = chunk.get("data")
                    if isinstance(data, list):
                        row_count = len(data)
                        # 留一份快照，切回这个会话时前端要能重绘表格；只存前 200 行
                        result_rows = data[:200]
                yield self._sse(chunk)
        except Exception as e:
            # 流式接口已经开始返回后不能再改 HTTP 状态码，因此把异常也包装成一条 SSE 消息
            yield self._sse({"type": "error", "message": str(e)})

        # 落库放在响应之后：即使写历史失败，用户也已经拿到结果
        seq: int | None = None
        try:
            seq = await self._save_turn(
                session_id, query, final_state, row_count, result_rows
            )
        except Exception as e:
            # 用 exception 打出堆栈：之前只打 warning，Decimal 序列化失败这类问题很难被发现
            logger.exception(f"保存会话记录失败：{e}")

        # 审计独立于会话记录：会话写失败也要留下这次 SQL 执行痕迹
        try:
            await self._save_audit(session_id, seq, query, final_state, row_count)
        except Exception as e:
            logger.warning(f"保存 SQL 审计记录失败：{e}")

    async def _load_context(self, session_id: str, query: str) -> tuple[str, str, str]:
        """读取并压缩会话历史；出现强指代时额外按关键词回捞更早的轮次

        除了给改写节点用的 history_text，还单独给 SQL 生成准备两样东西：
        最近一次产出 SQL 的那一轮（增量基线）和最近几轮展示过的列清单。
        """

        turns = await self.chat_memory_repository.list_turns(
            session_id, TURN_FETCH_LIMIT
        )
        if not turns:
            return "", "", ""

        """
        如果 query 里出现 ANAPHORA_MARKERS 中的任何一个词，就用 jieba 抽出前 4 个词，每个词分别查一次。
        build_memory_text 在末尾用 exist_seqs 去重，只有 12 轮以外的才会真正以 【按指代回捞的历史轮次】 的形式补进上下文。
        举例：会话 20 轮，第 3 轮问过“华北地区销售额”，现在说“回到华北那个口径”：
        turns = 第 9~20 轮
        jieba 抽出 华北、口径（那个、回到 这类词不够表意，或者 <2 字会被过滤）
        用 华北 查到第 3 轮 → 不在 turns 里 → 补进去
        """
        recalled: list[ChatTurn] = []
        if needs_recall(query):
            # 回捞取的是历史记录里的 slots，不会把 SQL 和结果集带进上下文
            tokens = jieba.analyse.extract_tags(query, topK=4)
            for token in tokens:
                if len(token) < 2:
                    continue
                found = await self.chat_memory_repository.search_turns(
                    session_id, token
                )
                recalled.extend(found)

        return (
            build_memory_text(turns, recalled),
            build_sql_baseline(turns),
            build_column_history(turns),
        )

    async def _save_turn(
        self,
        session_id: str,
        query: str,
        final_state: dict,
        row_count: int | None,
        result_rows: list | None,
    ) -> int | None:
        """把本轮问答落库，供下一轮继承，同时刷新左侧会话列表

        返回本轮 seq，供审计记录关联；没有落库时返回 None。
        """

        rewritten_query = final_state.get("rewritten_query")
        if not rewritten_query:
            # 改写节点既没产出也没降级结果时不落库，避免污染历史
            return None

        slots = dict(final_state.get("slots") or {})
        missing = final_state.get("missing_slots") or []
        if missing:
            # 澄清轮也落库：用户下一句“2025 年”要接着这一轮才能补全
            slots["missing"] = [item.get("question") for item in missing]

        if final_state.get("intent") == "unsupported":
            # 拒绝轮同样落库：会话列表要看到这条记录，下一轮改写也要知道上一轮被拒过，
            # 否则用户紧接着说“那查一下呢”，历史里只留下一条“删除……”把它带偏
            slots["rejected"] = final_state.get("reject_reason") or "不支持的请求"

        # 结果集里的列名是事实，比模型自述的槽位可靠：
        # 改写模型漏抽 select_columns 时用实际返回的列兜底，否则下一轮继承不到“上一轮展示了哪些列”
        if result_rows:
            slots["select_columns"] = list(result_rows[0].keys())

        seq = await self.chat_memory_repository.next_seq(session_id)
        turn = ChatTurn(
            session_id=session_id,
            seq=seq,
            user_query=query,
            rewritten_query=rewritten_query,
            slots=slots,
            sql=final_state.get("sql"),
            row_count=row_count,
            # 再兜一次底：结果集来自数仓，里面有 Decimal 时 JSON 列会写入失败
            result=rows_to_jsonable(result_rows) if result_rows is not None else None,
        )
        # 会话标题只在首次创建时生效，后续轮次会被仓储层忽略
        await self.chat_memory_repository.append_turn(
            turn, session_title=self._make_title(rewritten_query)
        )
        return seq

    async def _save_audit(
        self,
        session_id: str,
        seq: int | None,
        query: str,
        final_state: dict,
        row_count: int | None,
    ) -> None:
        """把本轮的安全判定与执行情况落审计表

        两类都要写：
        1. 走到 SQL 的轮次，记放行还是被白名单拦下；
        2. 被意图判断直接拒绝的轮次（没有 SQL），记“用户要求做了什么”——
           这一类比白名单拦截更值得留痕：它是唯一能看出有人在试图删改数据的线索。

        澄清轮和召回阶段就失败的情况既没有 sql_guard 也没有 sql，不写审计。
        """

        guard = final_state.get("sql_guard") or {}
        sql = final_state.get("sql")
        rejected = final_state.get("intent") == "unsupported"
        if not guard and not sql and not rejected:
            return

        if rejected:
            # 拒绝发生在改写阶段，此时还没有 SQL，所以 sql 留空，
            # 用 guard_rule 标记拒绝原因，方便和"白名单拦截"区分开
            allowed = False
            rule = "intent_unsupported"
            reason = final_state.get("reject_reason") or "超出只读范围的请求"
        else:
            allowed = bool(guard.get("allowed", True))
            rule = guard.get("rule") or None
            reason = guard.get("reason") or None

        audit = SQLAudit(
            session_id=session_id,
            seq=seq,
            user_query=query,
            rewritten_query=final_state.get("rewritten_query"),
            sql=sql,
            allowed=allowed,
            guard_rule=rule,
            guard_reason=reason,
            # 被拦截时没有结果集，别把上一轮或本轮的残留行数记到这条审计上
            row_count=row_count if allowed else None,
            elapsed_ms=final_state.get("sql_elapsed_ms"),
        )
        await self.chat_memory_repository.append_audit(audit)

    @staticmethod
    def _make_title(rewritten_query: str) -> str:
        """用首轮改写后的问题当会话标题，不额外调一次大模型"""

        title = " ".join(rewritten_query.split())
        return title[:40] or "未命名会话"

    @staticmethod
    def _sse(payload: dict) -> str:
        """把一条事件包装成 SSE 文本

        ensure_ascii=False 保留中文进度文案，default=str 兜底处理日期等非 JSON 类型
        """

        return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
