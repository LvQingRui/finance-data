from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
import asyncio

from app.core.log import logger
from app.models.es.value_info_es import ValueInfoEs
from app.prompt.prompt_loader import loader_prompt


async def recall_value(state:DataAgentState,runtime:Runtime[DataAgentContext]):

    writer = runtime.stream_writer
    writer({"stage": "召回字段取值"})
    try:
        # 获取问题
        query = state["query"]
        # 获取关键字列表
        keywords = state["keywords"]
        # 获取持久层查询对象
        value_es_repository= runtime.context["value_es_repository"]

        # 1.扩展关键字--llm
        tml = await loader_prompt("extend_keywords_for_value_recall")
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
        logger.info(f"取值扩展后关键字列表：{keywords}")

        # 2.召回字段取值

        # 定义去除召回的重复字段值
        retrieved_value_map:dict[str,ValueInfoEs]={}
        # 遍历列表查询
        for keyword in keywords:
            # 查询全文匹配结果
            values:list=await value_es_repository.search(keyword)
            # 遍历处理结果
            if values:
                for value in values:
                    # 获取取值的id
                    value_id =value["id"]
                    # 判断
                    if value_id not in retrieved_value_map:
                        retrieved_value_map[value_id] = value


        #  获取召回的取值列表
        retrieved_values=list(retrieved_value_map.values())
        logger.info(f"召回字段取值成功：{list(retrieved_value_map.keys())}")

        return {"retrieved_values":retrieved_values}
    except Exception as e:
        logger.error(f"召回字段取值异常：{str(e)}")
        raise


