from qdrant_client import AsyncQdrantClient, models

from app.conf.app_config import app_config
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant


class ColumnQdrantRepository:

    collection_name = "finance-agent-column"

    def __init__(self,client:AsyncQdrantClient):
        self.client=client

    async def ensure_collection(self):
        """
        确保存储字段向量的集合存在
        :return:
        """
        # 判断是否存在
        if not await self.client.collection_exists(collection_name=self.collection_name):
            # 如果不存在，创建向量集合
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(size=app_config.qdrant.embedding_size, distance=models.Distance.COSINE),
            )

    async def upsert_column(self, ids:list[str], embeddings:list[list[float]], payloads:list[ColumnInfoQdrant],batch_size:int=10):
        """
        为字段构建向量索引

        :param ids:
        :param embeddings:
        :param payloads:
        :return:
        ids:list[str], embeddings:list[list[float]], payloads:list[ColumnInfoQdrant]
        👇
         points=[
                models.PointStruct(
                    id="5c56c793-69f3-4fbf-87e6-c4bf54c28c26",
                    payload={
                        "color": "red",
                    },
                    vector=[0.9, 0.1, 0.1, 0.5],
                ),
            ],
        """
        # 合并数据[(id,embedding,payload),(id,embedding,payload),(id,embedding,payload)]
        zipped = list(zip(ids,embeddings,payloads))
        # 批次处理
        for i in range(0,len(zipped),batch_size):
            # 获取批次数据
            batch_zipped = zipped[i:i+batch_size]
            # 转换类型
            points=[
                models.PointStruct(
                    id=id,
                    payload=payload,
                    vector=embedding,
                )
                for id,embedding,payload in batch_zipped]
            # 保存数据
            await self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )

    async def search(self, embedding:list[float],score_threshold:float=0.6)->list:
       """
       召回字段查询
       :param embedding:
       :return:
       """
       points = await self.client.query_points(
           collection_name=self.collection_name,
           query=embedding,
           score_threshold=score_threshold
       )

       return [point.payload for point in points.points]


