import asyncio
import random
import uuid
from typing import Optional

from qdrant_client import AsyncQdrantClient, models

from app.conf.app_config import app_config, QdrantConfig


class QdrantClientManager:
    def __init__(self,config:QdrantConfig):
        self.client:Optional[AsyncQdrantClient]=None
        self.config=config

    def _get_url(self):
        return f"http://{self.config.host}:{self.config.port}"

    def init(self):
        self.client = AsyncQdrantClient(url=self._get_url())

    async def close(self):
        await self.client.close()


qdrant_client_manager= QdrantClientManager(app_config.qdrant)

if __name__ == '__main__':
    # 初始化客户端
    qdrant_client_manager.init()
    # 获取客户端
    client=qdrant_client_manager.client
    async def test():

        # 判断指定的集合是否存在
        if not await  client.collection_exists(collection_name="my_collection"):
            # 不存在创建集合
            await client.create_collection(
                collection_name="my_collection",
                vectors_config=models.VectorParams(size=app_config.qdrant.embedding_size, distance=models.Distance.COSINE),
            )

        # 存储数据

        await client.upsert(
            collection_name="my_collection",
            points=[

                   models.PointStruct(
                       id=uuid.uuid4(),
                       payload={
                           "color": f"red{i}",
                       },
                       vector=[ random.random() for _ in range(1024)],
                   )



                   for i in range(100)],
        )




        # 查询数据
        points = await client.query_points(
            collection_name="my_collection",
            query=[ random.random() for _ in range(1024)],
            limit=2,
            score_threshold=0.7
        )
        print(points.points)
        print(type(points.points))

        for point in points.points:


            print(point.payload)

        # 释放资源
        await qdrant_client_manager.close()


    asyncio.run(test())
















