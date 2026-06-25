import asyncio
from typing import Optional

from elasticsearch import AsyncElasticsearch

from app.conf.app_config import app_config, ESConfig


class EsClientManager:
    def __init__(self,config:ESConfig):
        self.client:Optional[AsyncElasticsearch]=None
        self.config = config


    def _get_url(self):
        return f"http://{self.config.host}:{self.config.port}"

    def init(self):
        self.client=AsyncElasticsearch(
            hosts=[self._get_url()],

        )

    async def close(self):
        await self.client.close()

es_client_manager= EsClientManager(app_config.es)


if __name__ == '__main__':

    # 初始化es客户端对象
    es_client_manager.init()
    # 获取客户端
    client=es_client_manager.client

    async def test():
        # 判断指定所以是否存在
        if not await client.indices.exists(index="mybook"):

            # 不存在，创建索引---静态创建（分词器）
            await client.indices.create(
                index="mybook",
                mappings={
                    "dynamic": False,
                    "properties": {
                        "name": {
                            "type": "text",
                            "analyzer": "ik_max_word",
                            "search_analyzer": "ik_smart"
                        },
                        "author": {
                            "type": "text"
                        },
                        "release_date": {
                            "type": "date",
                            "format": "yyyy-MM-dd"
                        },
                        "page_count": {
                            "type": "integer"
                        }
                    }
                },
            )

        # 添加文档到索引库（批量添加）
        # await client.bulk(
        #     operations=[
        #         {
        #             "index": {
        #                 "_index": "mybook"
        #             }
        #         },
        #         {
        #             "name": "Revelation Space",
        #             "author": "Alastair Reynolds",
        #             "release_date": "2000-03-15",
        #             "page_count": 585
        #         },
        #         {
        #             "index": {
        #                 "_index": "mybook"
        #             }
        #         },
        #         {
        #             "name": "1984",
        #             "author": "George Orwell",
        #             "release_date": "1985-06-01",
        #             "page_count": 328
        #         },
        #         {
        #             "index": {
        #                 "_index": "mybook"
        #             }
        #         },
        #         {
        #             "name": "Fahrenheit 451",
        #             "author": "Ray Bradbury",
        #             "release_date": "1953-10-15",
        #             "page_count": 227
        #         },
        #         {
        #             "index": {
        #                 "_index": "mybook"
        #             }
        #         },
        #         {
        #             "name": "Brave New World",
        #             "author": "Aldous Huxley",
        #             "release_date": "1932-06-01",
        #             "page_count": 268
        #         },
        #         {
        #             "index": {
        #                 "_index": "mybook"
        #             }
        #         },
        #         {
        #             "name": "The Handmaids Tale",
        #             "author": "Margaret Atwood",
        #             "release_date": "1985-06-01",
        #             "page_count": 311
        #         }
        #     ],
        # )



        # 根据关键字检索数据，返回结果

        resp = await client.search(
            index="mybook",
            query={
                "match": {
                    "name": "Brave"
                }
            },
        )
        print(resp)
        print(type(resp))
        print(resp['hits']['hits'])
        print("---------------")
        for res in resp['hits']['hits']:
            print(res["_source"])

        # 解析返回的结果


        await es_client_manager.close()


    asyncio.run(test())




