"""
SQL 校验节点

负责在真正执行查询前做两道校验：
1. 执行白名单（本地 AST 校验）：只允许单条 SELECT、禁用系统库和危险函数、强制行数上限
2. 语法可执行性：交给数据库 explain

安全校验不通过时不抛异常，而是把原因写进 state["error"]，
由 graph.py 的条件边决定进入 correct_sql 让模型改，还是直接中止。
注意 correct_sql 的产物不会回到这个节点，所以 run_sql 里还有最后一道闸门。
"""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.sql_guard import allowed_tables_from_infos, guard_sql
from app.agent.state import DataAgentState
from app.core.log import logger
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository


async def validate_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """校验 SQL，并返回 error 字段控制后续条件分支"""

    writer = runtime.stream_writer
    step = "校验SQL"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        # 读取 generate_sql 或 correct_sql 写入状态的候选 SQL
        sql = state["sql"]

        # 第一道：本地安全校验。只允许查本次召回到的表，挡住跨库和拖库写法
        guard = guard_sql(sql, allowed_tables_from_infos(state.get("table_infos")))
        if not guard.allowed:
            logger.warning(f"SQL 未通过安全校验：{guard.rule} - {guard.reason}")
            writer({"type": "progress", "step": step, "status": "success"})
            return {
                "error": f"[安全校验] {guard.reason}",
                "sql_guard": guard.as_dict(),
            }

        # 通过校验时 SQL 可能被补了 LIMIT，必须写回 state，否则执行的是旧语句
        if guard.sql != sql:
            logger.info(f"SQL 已被安全策略调整：{guard.rule} - {guard.reason}")

        # SQL 可用性必须交给真实数仓判断，这里从运行时上下文取 DW Repository
        dw_mysql_repository: DWMySQLRepository = runtime.context["dw_mysql_repository"]

        try:
            # validate 内部使用 explain <sql>，只关心数据库能否成功解析这条 SQL
            await dw_mysql_repository.validate(guard.sql)
            writer({"type": "progress", "step": step, "status": "success"})
            logger.info("SQL语法正确")
            return {
                "sql": guard.sql,
                "error": None,
                "sql_guard": guard.as_dict(),
            }
        except Exception as e:
            # 不抛出异常中断图执行，而是把错误写入状态，供条件分支进入 correct_sql
            logger.info(f"SQL语法错误：{str(e)}")
            writer({"type": "progress", "step": step, "status": "success"})
            return {"error": str(e), "sql_guard": guard.as_dict()}

    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
