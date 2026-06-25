import asyncio

import yaml
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState, TableInfoState
from app.core.log import logger
from app.prompt.prompt_loader import loader_prompt


async def filter_table(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"stage": "过滤表信息"})

    try:
        # 获取用户问题
        query = state["query"]
        # 获取合并的表信息
        table_infos:list[TableInfoState] = state["table_infos"]

        # 1.llm根据合并信息，筛选跟问题相关的内容
        # 加载提示词文本呢
        tml= await loader_prompt("filter_table_info")
        # 1.1 定义提示词模版
        prompt = PromptTemplate(template=tml,input_variables=["query","table_infos"])
        # 1.2 定义结果转换器
        output_parser= JsonOutputParser()
        # 1.3.定义chain链
        chain = prompt |llm |output_parser
        # 1.4 执行chain链
        result=await chain.ainvoke({"query":query,"table_infos":yaml.dump(table_infos, allow_unicode=True, sort_keys=False)})
        """
        返回的结果：
        {
        "表名1":["字段1", "字段2", "..."],
        "表名2":["字段1", "字段2", "..."]
        }
        """
        logger.info(f"表信息过滤后的结果{result}")


        # 2.根据结果过滤召回的信息

        for table_info in table_infos[:]:
            # 获取辨明
            table_name=table_info["name"]
            # 判断当前表是否存在过滤的结果中
            if table_name not in result:
                table_infos.remove(table_info)
            else:
                # 获取当前表合并后对应的字段列表
                for column in table_info["columns"][:]:
                    # 获取字段名称
                    column_name =column["name"]
                    # 判断
                    if column_name not in result[table_name]:
                        table_info["columns"].remove(column)

        logger.info(f"过滤后的表信息{[table_info['name'] for table_info in table_infos]}")

        return {"table_infos":table_infos}
    except Exception as e:
        logger.error(f"过滤表信息异常：{str(e)}")
        raise