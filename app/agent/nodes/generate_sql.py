import yaml
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
import asyncio

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState, TableInfoState, MetricInfoState
from app.core.log import logger
from app.prompt.prompt_loader import loader_prompt


async def generate_sql(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"stage": "生成sql语句"})

    try:
        query:str = state["query"]
        table_infos:list[TableInfoState] = state["table_infos"]
        metric_infos:list[MetricInfoState] = state["metric_infos"]
        date_info = state["date_info"]
        db_info = state["db_info"]

        # 定义模版
        # 加载提示词文本
        tml = await loader_prompt("generate_sql")
        # 1.1 定义提示词模版
        prompt = PromptTemplate(template=tml, input_variables=["query","table_infos","metric_infos","date_info","db_info"])
        # 定义转化器
        output_parser=StrOutputParser()
        # 定义chain链
        chain = prompt | llm | output_parser
        # 执行chain链
        sql = await chain.ainvoke({
            "query": query,
            "table_infos": yaml.dump(table_infos,allow_unicode=True,sort_keys=False),
            "metric_infos": yaml.dump(metric_infos,allow_unicode=True,sort_keys=False),
            "date_info": yaml.dump(date_info,allow_unicode=True,sort_keys=False),
            "db_info": yaml.dump(db_info,allow_unicode=True,sort_keys=False),
        })

        # sql="""
        # SELECT SUM(fo.order_amount) AS 销售总额
        #     FROM fact_order fo
        #              JOI dim_region dr N fo.region_id = dr.region_id
        #     WHE dr.region_name = '华北';
        #
        # """

        logger.info(f"生成的sql语句\n：{sql}")
        return {"sql":sql}
    except Exception as e:
        logger.error(f"生成sql异常：{str(e)}")
        raise