from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
import asyncio
from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant
from app.prompt.prompt_loader import loader_prompt


async def recall_metric(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"stage": "召回指标信息"})

    try:
        # 获取向量转换对象
        embeddings = runtime.context["embeddings"]
        # 获取持久层查询对象
        metric_qdrant_repository = runtime.context["metric_qdrant_repository"]
        # 获取问题
        query = state["query"]
        # 获取关键字列表
        keywords = state["keywords"]

        # 1.扩展关键字--llm
        tml = await loader_prompt("extend_keywords_for_metric_recall")
        # 1.1 定义提示词模版
        prompt = PromptTemplate(template=tml, input_variables=["query"])
        # 1.2 构建结果转换器
        output_parser = JsonOutputParser()
        # 1.3 定义chain执行链
        chain = prompt | llm | output_parser
        # 1.4 执行chain链
        result = await  chain.ainvoke({"query": query})
        # 1.5 合并关键字
        keywords = set(keywords + result)
        logger.info(f"指标扩展后关键字列表：{keywords}")

        # 2.字段召回--qdrant
        # 定义字典结构去除召回的重复字段信息
        retrieved_metric_map: dict[str, MetricInfoQdrant] = {}
        # 遍历关键字
        for keyword in keywords:
            # 转换成向量
            embedding = await embeddings.aembed_query(keyword)
            # 查询qdrant
            payloads: list = await metric_qdrant_repository.search(embedding)
            # 遍历召回结果
            for payload in payloads:
                # 获取召回指标信息的id
                metric_id = payload["id"]
                # 判断当前字段是否已经被召回
                if metric_id not in retrieved_metric_map:
                    retrieved_metric_map[metric_id] = payload

        # 获取召回指标列表
        retrieved_metrics = list(retrieved_metric_map.values())

        logger.info(f"召回指标信息成功，{list(retrieved_metric_map.keys())}")

        return {"retrieved_metrics": retrieved_metrics}
    except Exception as e:
        logger.error(f"召回指标信息异常，{str(e)}")
        raise