"""
关键词抽取节点

负责从用户自然语言问题中识别检索线索
后续字段召回 字段取值召回和指标召回都会基于这些关键词展开
"""

import jieba.analyse
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, get_effective_query
from app.core.log import logger


async def extract_keywords(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """抽取用户问题中的关键词，并通过流式输出反馈当前进度"""

    step = "抽取关键词"
    writer = runtime.stream_writer
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        # 多轮追问时要用改写后的完整问题，原话可能只有“那华东呢”
        query = get_effective_query(state)

        # 只保留更可能承载业务含义的词性，减少“的、帮我、一下”这类无检索价值的噪声
        allow_pos = (
            "n",  # 名词: 商品、订单、销售额
            "nr",  # 人名: 张三、李四
            "ns",  # 地名: 华北、北京、上海
            "nt",  # 机构团体名: 门店、品牌、渠道
            "nz",  # 其他专有名词: SKU、GMV、AOV
            "v",  # 动词: 统计、对比、查询
            "vn",  # 名动词: 销售、成交、退款
            "a",  # 形容词: 新增、有效、活跃
            "an",  # 名形词: 可用、有效、异常
            "eng",  # 英文: GMV、SKU、ROI
            "i",  # 成语或习用语，避免遗漏整体表达
            "l",  # 常用固定短语，例如“销售总额”
        )

        """
        好处：
        1.给ES喂数据:Elasticsearch底层(倒排索引)在处
        理中文时，必须要有一个分词器，把一句话切成
        词，才能建索引。虽然ES有自带的IK分词器，但有
        时候为了保持Python端和ES端的逻辑一致，或
        者为了降低复杂度，开发者会直接使用Python,

        2.降低Token成本与延迟:在调用最贵的大模型之前，
        jieba来做轻量级的分词和关键词召回。
        用jieba这种纯CPU计算的本地工具，迅速把一
        些毫无意义的语气词(比如"帮我”、"那个")过滤掉，
        能节省一点点成本。

        现主流做法：
        1.直接让 LLM 抽（最主流）：
        用 with_structured_output()（就是我们之前聊过的 Pydantic），强制大模型吐出格式化的 JSON。准确率最高，什么多义词、同义词全都不在话下。

        2.Function Calling（工具调用）：
        把“提取信息”做成一个工具，让大模型自己去决定什么时候调用、填什么参数。

        3.本地小型模型（成本敏感）：
        如果觉得调用 GPT-4 太贵，可以在本地跑一个很小的模型（比如 Qwen-1.5B 或 Llama-3-8B），专门用它来干“实体抽取”这种脏活累活。速度快，还不花钱。
        """

        # extract_tags 会基于 TF-IDF 抽取关键词，并按 allowPOS 做词性过滤
        keywords = jieba.analyse.extract_tags(query, allowPOS=allow_pos)

        # 保留原始问题作为兜底检索入口，避免关键词切分不准时丢掉完整语义
        # set 用来去重；顺序不参与后续判断，所以这里不依赖关键词顺序
        keywords = list(set(keywords + [query]))

        writer({"type": "progress", "step": step, "status": "success"})
        logger.info(f"抽取关键词成功: {keywords}")
        return {"keywords": keywords}
    except Exception as e:
        logger.error(f"抽取关键词失败: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
