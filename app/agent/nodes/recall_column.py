from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
import asyncio
from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.prompt.prompt_loader import loader_prompt


async def recall_column(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"stage": "召回字段信息"})

    try:
        # 获取向量转换对象
        embeddings=runtime.context["embeddings"]
        # 获取持久层查询对象
        column_qdrant_repository= runtime.context["column_qdrant_repository"]
        # 获取问题
        query = state["query"]
        # 获取关键字列表
        keywords = state["keywords"]

        # 1.扩展关键字--llm
        tml =await loader_prompt("extend_keywords_for_column_recall")
        # 1.1 定义提示词模版
        prompt = PromptTemplate(template=tml,input_variables=["query"])
        # 1.2 构建结果转换器
        output_parser=JsonOutputParser()
        # 1.3 定义chain执行链
        chain = prompt | llm | output_parser
        # 1.4 执行chain链
        result =await  chain.ainvoke({"query":query})
        # 1.5 合并关键字
        keywords=set(keywords+result)
        logger.info(f"字段扩展后关键字列表：{keywords}")



        # 2.字段召回--qdrant
        # 定义字典结构去除召回的重复字段信息
        retrieved_column_map:dict[str,ColumnInfoQdrant]={}
        # 遍历关键字
        for keyword in keywords:
            # 转换成向量
            embedding=await embeddings.aembed_query(keyword)
            # 查询qdrant
            payloads:list=await column_qdrant_repository.search(embedding)
            # 遍历召回结果
            for payload in payloads:
                # 获取召回字段信息的id
                column_id =payload["id"]
                # 判断当前字段是否已经被召回
                if column_id not in retrieved_column_map:
                    retrieved_column_map[column_id]=payload

        # 获取召回字段列表
        retrieved_columns=list(retrieved_column_map.values())

        logger.info(f"召回字段信息成功，{list(retrieved_column_map.keys())}")

        return {"retrieved_columns":retrieved_columns}
    except Exception as e:
        logger.error(f"召回字段信息异常，{str(e)}")
        raise