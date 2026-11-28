"""
会话记忆组装

把落库的多轮历史压成“够用但不膨胀”的上下文，核心原则有三条：

1. 历史正文只保留“问题 + 槽位”，结果集不进提示词；
   唯一的例外是最近一次产出结果的 SQL，它作为本轮增量修改的基线单独注入。
2. 最近若干轮保留完整信息，更早的轮次压成一行结构化事实，按 token 预算从最旧的开始丢。
3. 摘要是“重建”而不是“追加”，每轮都用结构化槽位重新拼一遍，
   避免摘要自身滚雪球，也避免 LLM 改写把“华东”“2025Q1”这类枚举和数字说跑偏。
"""

from app.entities.chat_turn import ChatTurn

# 最近几轮保留完整槽位
RECENT_TURN_LIMIT = 3
# 一次性从库里取多少轮，够 recent + 摘要 + 少量回捞使用
TURN_FETCH_LIMIT = 12
# 历史上下文的 token 预算，按预算裁剪而不是按固定轮数
MEMORY_TOKEN_BUDGET = 900
# 单轮渲染出来的最大长度，防止某一轮问题特别长把预算吃光
TURN_LINE_MAX_CHARS = 220

# 出现这些说法，说明本轮大概率依赖上文，需要扩大回捞范围
ANAPHORA_MARKERS = (
    "刚才",
    "刚刚",
    "上次",
    "之前",
    "那个",
    "这条",
    "这批",
    "回到",
    "沿用",
    "还是按",
    "它的",
    "这个口径",
)


def estimate_tokens(text: str) -> int:
    """粗估 token 数。中文大约 1.5 字一个 token，只用于预算裁剪，不追求精确"""

    return max(1, int(len(text) / 1.5))


def needs_recall(query: str) -> bool:
    """判断本轮是否出现强指代，需要回捞更早的轮次"""

    return any(marker in query for marker in ANAPHORA_MARKERS)


def format_turn(turn: ChatTurn, compact: bool = False) -> str:
    """把一轮问答渲染成一行结构化事实，不含 SQL 和结果"""

    slots = turn.slots or {}
    parts: list[str] = [f"第{turn.seq}轮"]

    if compact:
        # 旧轮次只保留“理解后的完整问题 + 槽位”，原话价值低且占地方
        if turn.rewritten_query:
            parts.append(f"理解：{turn.rewritten_query}")
    else:
        parts.append(f"用户：{turn.user_query}")
        # 改写结果和原话一致时不必重复展示
        if turn.rewritten_query and turn.rewritten_query != turn.user_query:
            parts.append(f"理解：{turn.rewritten_query}")

    tables = [str(item) for item in slots.get("tables") or []]
    if tables:
        parts.append(f"表：{'、'.join(tables)}")

    metrics = [str(item) for item in slots.get("metrics") or []]
    if metrics:
        parts.append(f"指标：{'、'.join(metrics)}")

    filters = [str(item) for item in slots.get("filters") or []]
    if filters:
        parts.append(f"过滤：{'；'.join(filters)}")

    if slots.get("time_range"):
        parts.append(f"时间：{slots['time_range']}")

    if slots.get("granularity"):
        parts.append(f"粒度：{slots['granularity']}")

    # 展示列是最容易被下一轮继承错的一维：只写“本轮新提到的列”会让上一轮的结果被整体覆盖
    columns = [str(item) for item in slots.get("select_columns") or []]
    if columns:
        parts.append(f"列：{'、'.join(columns)}")

    # 上一轮如果是澄清轮，把待确认内容也带下去，用户回答后能直接补全
    missing = [str(item) for item in slots.get("missing") or []]
    if missing:
        parts.append(f"待确认：{'；'.join(missing)}")

    # 被拒绝的轮次要标明，否则下一句“那查一下呢”会让改写把被拒的意图当成新需求继承
    if slots.get("rejected"):
        parts.append(f"已拒绝：{slots['rejected']}")

    line = "｜".join(parts)
    if len(line) > TURN_LINE_MAX_CHARS:
        line = line[:TURN_LINE_MAX_CHARS] + "…"
    return line


def build_memory_text(
    turns: list[ChatTurn], recalled: list[ChatTurn] | None = None
) -> str:
    """把历史轮次拼成提示词里的会话上下文文本"""

    if not turns:
        return ""

    recent = turns[-RECENT_TURN_LIMIT:]
    older = turns[:-RECENT_TURN_LIMIT]

    recent_lines = [format_turn(turn) for turn in recent]
    # 最近轮次先占预算，剩下的才给摘要，保证“最近的记忆”一定在
    used = sum(estimate_tokens(line) for line in recent_lines)
    remaining = max(0, MEMORY_TOKEN_BUDGET - used)

    # 摘要从最近的老轮次往更早的方向填，超预算就停，也就是丢掉最旧的
    summary_lines: list[str] = []
    for turn in reversed(older):
        line = format_turn(turn, compact=True)
        cost = estimate_tokens(line)
        if cost > remaining:
            break
        summary_lines.append(line)
        remaining -= cost
    summary_lines.reverse()

    sections: list[str] = []

    if summary_lines:
        omitted = len(older) - len(summary_lines)
        block = "\n".join(summary_lines)
        if omitted > 0:
            block += f"\n（更早的 {omitted} 轮已按预算省略）"
        sections.append(f"【更早的轮次摘要】\n{block}")

    sections.append("【最近轮次】\n" + "\n".join(recent_lines))

    # 回捞出来的轮次只补充“槽位视角”，同样不带 SQL
    if recalled:
        exist_seqs = {turn.seq for turn in turns}
        extra = [turn for turn in recalled if turn.seq not in exist_seqs]
        if extra:
            extra_lines = "\n".join(format_turn(turn, compact=True) for turn in extra)
            sections.append(f"【按指代回捞的历史轮次】\n{extra_lines}")

    return "\n\n".join(sections)


def build_sql_baseline(turns: list[ChatTurn]) -> str:
    """取最近一次真正产出 SQL 的那一轮，作为本轮增量修改的基线

    只给一条：多轮改列是链式的，第 N 轮在第 N−1 轮的结果集上做 diff。
    给多条 SQL，模型就得先猜“哪条是被改的基线”，很容易把不同轮的过滤条件缝在一起。
    上一轮如果是澄清轮或执行失败（sql 为空），自然回溯到更早那条。
    """

    for turn in reversed(turns):
        if turn.sql:
            question = turn.rewritten_query or turn.user_query
            return f"第{turn.seq}轮问题：{question}\n{turn.sql.strip()}"
    return ""


def build_column_history(turns: list[ChatTurn], limit: int = RECENT_TURN_LIMIT) -> str:
    """最近几轮各自展示过的列清单

    列名很轻，只用于“回到第 N 轮那个口径”这类跨轮引用；
    基线 SQL 只覆盖最近一轮，更早轮次展示过什么列靠这份清单兜住。
    """

    lines: list[str] = []
    for turn in turns[-limit:]:
        slots = turn.slots or {}
        columns = [str(item) for item in slots.get("select_columns") or []]
        if not columns:
            # 空结果或没抽到列的历史轮次直接跳过，不要用空数组制造“上一轮什么都没查”的错觉
            continue
        question = turn.rewritten_query or turn.user_query
        lines.append(f"第{turn.seq}轮：{question}｜列：{'、'.join(columns)}")
    return "\n".join(lines)
