"""
拒绝节点

问数只能读：用户要求删除、更新、建表、导出文件时，继续往下走会出两种坏结果——
要么模型把“删除”降级成“把这些数据查出来”，返回“执行成功”的假象；
要么真的写出 DML，被 SQL 白名单拦下，用户看到一条看不懂的安全错误。

所以这一类请求在改写阶段就被识别出来，直接在这里给一句人话说明并结束。
"""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState

# 模型偶尔会漏写说明，兜一句通用的，保证前端永远有内容可展示
DEFAULT_REASON = "我只能查询数据，不能修改、删除或导出数据。"


async def reject(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """告知用户该请求超出只读范围，并终止本次图执行"""

    writer = runtime.stream_writer
    step = "判断请求类型"
    writer({"type": "progress", "step": step, "status": "running"})

    reason = (state.get("reject_reason") or "").strip() or DEFAULT_REASON
    writer({"type": "reject", "reason": reason})
    writer({"type": "progress", "step": step, "status": "success"})

    # 与 clarify 一样不产出新状态，图直接走到 END
    return {}
