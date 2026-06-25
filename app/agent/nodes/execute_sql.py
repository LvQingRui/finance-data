from langgraph.runtime import Runtime
import asyncio

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def execute_sql(state:DataAgentState,runtime:Runtime[DataAgentContext]):

    writer = runtime.stream_writer
    writer({"stage": "执行sql语句"})
    try:
        # 获取执行的repository
        dw_mysql_repository=runtime.context["dw_mysql_repository"]
        # 获取sql
        sql = state["sql"]
        # 执行sql
        result = await dw_mysql_repository.execute_sql(sql)

        # 输出最终结果
        writer({"result": result})
        logger.info(f"执行sql成功，结果：{result}")

    except Exception as e:
        logger.error(f"执行sql异常：{str(e)}")
        raise

