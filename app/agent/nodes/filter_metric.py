import asyncio

import yaml
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState, MetricInfoState
from app.core.log import logger
from app.prompt.prompt_loader import loader_prompt


async def filter_metric(state:DataAgentState,runtime:Runtime[DataAgentContext]):

    writer = runtime.stream_writer
    writer({"stage": "过滤指标信息"})

    try:
        # 获取用户问题
        query = state["query"]
        # 获取合并的表信息
        metric_infos:list[MetricInfoState] = state["metric_infos"]

        # 1.llm根据合并信息，筛选跟问题相关的内容
        # 加载提示词文本呢
        tml= await loader_prompt("filter_metric_info")
        # 1.1 定义提示词模版
        prompt = PromptTemplate(template=tml,input_variables=["query","metric_infos"])
        # 1.2 定义结果转换器
        output_parser= JsonOutputParser()
        # 1.3.定义chain链
        chain = prompt |llm |output_parser
        # 1.4 执行chain链
        result=await chain.ainvoke({"query":query,"metric_infos":yaml.dump(metric_infos, allow_unicode=True, sort_keys=False)})
        """
        返回的结果：
        [
          "指标一",
          "指标二"
        ]

        """
        logger.info(f"指标信息过滤后的结果{result}")


        # 2.根据结果过滤召回的信息
        for metric_info in metric_infos[:]:
            # 判断是否在需求的结果中
            if metric_info['name'] not in result:
                metric_infos.remove(metric_info)


        logger.info(f"过滤后的指标信息{[metric_info['name'] for metric_info in metric_infos]}")

        return {"metric_infos":metric_infos}
    except Exception as e:
        logger.error(f"过滤指标信息异常：{str(e)}")
        raise
