"""
SQL 执行节点

负责执行最终 SQL，并记录查询结果。
它是当前 SQL 闭环的结束节点，执行完成后流程进入 END。

这里还有一道安全闸门：correct_sql 修正后的 SQL 不会回到 validate_sql，
所以执行前必须再校验一次，否则"模型改一改就能绕过校验"。
"""

import time

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.sql_guard import allowed_tables_from_infos, guard_sql
from app.agent.state import DataAgentState
from app.core.log import logger


async def run_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """执行 SQL 并产出最终问数结果"""

    writer = runtime.stream_writer
    step = "执行SQL"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        # 这里拿到的可能是 generate_sql 直接通过校验的 SQL，也可能是 correct_sql 覆盖后的 SQL
        sql = state["sql"]

        # 最后一道闸门：correct_sql 的产物没经过 validate_sql，必须再校验
        guard = guard_sql(sql, allowed_tables_from_infos(state.get("table_infos")))
        if not guard.allowed:
            logger.warning(f"SQL 在执行前被拦截：{guard.rule} - {guard.reason}")
            writer({"type": "progress", "step": step, "status": "error"})
            writer(
                {
                    "type": "error",
                    "message": f"SQL 被安全策略拦截：{guard.reason}",
                }
            )
            return {"error": guard.reason, "sql_guard": guard.as_dict()}

        dw_mysql_repository = runtime.context["dw_mysql_repository"]

        # 真实数据库访问统一封装在仓储层，节点只负责从状态取 SQL 并触发执行
        started = time.perf_counter()
        result = await dw_mysql_repository.run(guard.sql)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info(f"SQL执行结果：{result}")
        writer({"type": "progress", "step": step, "status": "success"})
        # 把 SQL 一起回传给前端：多轮场景下用户需要确认“刚才那句话到底查了什么”
        # 注意回传的是实际执行的 guard.sql，可能比模型生成的多了 LIMIT
        writer({"type": "result", "data": result, "sql": guard.sql})

        return {
            "sql": guard.sql,
            "sql_guard": guard.as_dict(),
            "sql_elapsed_ms": elapsed_ms,
        }

    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
