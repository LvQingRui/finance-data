from elasticsearch import AsyncElasticsearch

from app.models.es.value_info_es import ValueInfoEs


class ValueEsRepository:

    es_index_name = "finance_agent_values"

    es_index_mappings = {
        "dynamic": False,
        "properties": {
            "id": {"type": "keyword"},
            "value": {"type": "text", "analyzer": "ik_max_word", "search_analyzer": "ik_max_word"},
            "type": {"type": "keyword"},
            "column_id": {"type": "keyword"},
            "column_name": {"type": "keyword"},
            "table_id": {"type": "keyword"},
            "table_name": {"type": "keyword"},
        }
    }

    def __init__(self,client:AsyncElasticsearch):
        self.client=client

    async def ensure_index(self):
        """
        [
                {
                    "index": {
                        "_index": "books"
                    }
                },
                {
                    "name": "Revelation Space",
                    "author": "Alastair Reynolds",
                    "release_date": "2000-03-15",
                    "page_count": 585
                },
                {
                    "index": {
                        "_index": "books"
                    }
                },
                {
                    "name": "1984",
                    "author": "George Orwell",
                    "release_date": "1985-06-01",
                    "page_count": 328
                }
            ]
        确保存储字段取值的索引存在
        :return:
        """
        if not await self.client.indices.exists(index=self.es_index_name):
            await self.client.indices.create(
                index=self.es_index_name,
                mappings=self.es_index_mappings
            )

    async def save_column_values(self, value_infos:list[ValueInfoEs],batch_size=20):
        """
        保存字段取值到es
        :param value_infos:
        :return:
        """

        # 遍历，批次处理
        for i in range(0,len(value_infos),batch_size):
            # 获取批次
            batch_value_infos = value_infos[i:i+batch_size]
            # 定义存储结构列表
            operations=[]
            # 构建存储结果
            for batch_value_info in batch_value_infos:
                # 存储索引声明
                operations.append({
                    "index": {
                        "_index": self.es_index_name
                    }
                })
                # 存储取值数据
                operations.append(batch_value_info)


            # 保存取值列表
            await self.client.bulk(
                operations=operations,
            )

    async def search(self, keyword:str):
        """
        召回字段取值查询
        :param keyword:
        :return:
        """
        # 全文检索匹配
        resp =await  self.client.search(
            index=self.es_index_name,
            query={
                "match": {
                    "value": keyword
                }
            }
        )
        # 获取结果列表
        hits:list=resp['hits']['hits']
        # 处理结果
        if not hits:
            return []
        return [hit['_source'] for hit in hits]




