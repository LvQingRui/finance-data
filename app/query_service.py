import json

from langchain_core.embeddings import Embeddings

from app.agent.context import DataAgentContext
from app.agent.graph import graph
from app.agent.state import DataAgentState
from app.repositories.es.values_es_repository import ValueEsRepository
from app.repositories.mysql.dw_mysql_repository import DwMysqlRepository
from app.repositories.mysql.meta_mysql_repository import MetaMysqlRepository
from app.repositories.qdrant.column_qdrant_respository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository


class QueryService:


    def __init__(self,
                embeddings: Embeddings,
                column_qdrant_repository:ColumnQdrantRepository,
                metric_qdrant_repository:MetricQdrantRepository,
                value_es_repository:ValueEsRepository,
                meta_mysql_repository:MetaMysqlRepository,
                dw_mysql_repository: DwMysqlRepository
                ):
        self.embeddings = embeddings
        self.column_qdrant_repository = column_qdrant_repository
        self.metric_qdrant_repository = metric_qdrant_repository
        self.value_es_repository = value_es_repository
        self.meta_mysql_repository = meta_mysql_repository
        self.dw_mysql_repository = dw_mysql_repository



    # 智能体查询服务
    async def query(self,query:str):
        # 创建状态信息
        state: DataAgentState = {"query": query}

        # 创建上下文信息
        context: DataAgentContext = {
            "embeddings": self.embeddings,
            "column_qdrant_repository": self.column_qdrant_repository,
            "metric_qdrant_repository": self.metric_qdrant_repository,
            "value_es_repository": self.value_es_repository,
            "meta_mysql_repository": self.meta_mysql_repository,
            "dw_mysql_repository": self.dw_mysql_repository,
        }
        try:
            # 执行graph
            async  for chunk in graph.astream(input=state, context=context, stream_mode="custom"):
                yield f"data:{json.dumps(chunk,ensure_ascii=False,default=str)}  \n\n"

        except Exception as e:
            yield f"data:{json.dumps({'error':str(e)}, ensure_ascii=False, default=str)}  \n\n"
