"""
澄清节点

多轮场景下有些指代靠历史也补不出来（例如历史里的轮次已经被预算裁掉），
这时继续往下走只会拿残缺信息硬生成 SQL，返回“看起来对但算错”的数据。

所以本节点只做一件事：把待确认的问题抛给用户，然后直接结束本次流程，
等用户补充后作为新一轮问答继续。
"""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState


async def clarify(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """向前端抛出一条追问，并终止本次图执行"""

    writer = runtime.stream_writer
    step = "确认口径"
    writer({"type": "progress", "step": step, "status": "running"})

    missing_slots = state.get("missing_slots") or []
    questions = [item["question"] for item in missing_slots if item.get("question")]
    question = "；".join(questions) or "能再补充一下要查的范围吗？"

    writer(
        {
            "type": "clarify",
            "question": question,
            "slots": [item.get("slot") for item in missing_slots],
        }
    )
    writer({"type": "progress", "step": step, "status": "success"})

    # 澄清节点不产出新状态，返回空字典即可，图会直接走到 END
    return {}
