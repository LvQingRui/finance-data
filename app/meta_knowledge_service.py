import uuid

from pathlib import Path
from langchain_core.embeddings import Embeddings
from omegaconf import OmegaConf

from app.conf.meta_config import MetaConfig
from app.core.log import logger
from app.models.es.value_info_es import ValueInfoEs
from app.models.mysql.column_info_mysql import ColumnInfoMySQL
from app.models.mysql.column_metric_mysql import ColumnMetricMySQL
from app.models.mysql.metric_info_mysql import MetricInfoMySQL
from app.models.mysql.table_info_mysql import TableInfoMySQL
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant
from app.repositories.es.values_es_repository import ValueEsRepository
from app.repositories.mysql.dw_mysql_repository import DwMysqlRepository
from app.repositories.mysql.meta_mysql_repository import MetaMysqlRepository
from app.repositories.qdrant.column_qdrant_respository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository


class MetaKnowledgeService:
    def __init__(self,
                 meta_mysql_repository: MetaMysqlRepository,
                 dw_mysql_repository: DwMysqlRepository,
                 column_qdrant_repository: ColumnQdrantRepository,
                 embeddings: Embeddings,
                 column_es_repository: ValueEsRepository,
                 metric_qdrant_repository: MetricQdrantRepository,
                 ):
        self.meta_mysql_repository = meta_mysql_repository
        self.dw_mysql_repository = dw_mysql_repository
        self.column_qdrant_repository = column_qdrant_repository
        self.embeddings = embeddings
        self.column_es_repository = column_es_repository
        self.metric_qdrant_repository = metric_qdrant_repository

    async def build(self, config_path: Path):
        # 1.加载配置文件，获取配置信息
        # 1.1 获取指定路径配置文件内容
        context = OmegaConf.load(config_path)
        # 1.2 定义配置封装结构
        schema = OmegaConf.structured(MetaConfig)
        # 1.3 合并结构，转换对象
        meta_config: MetaConfig = OmegaConf.to_object(OmegaConf.merge(schema, context))
        logger.info("配置文件加载完成")

        # 2.表信息处理
        if meta_config.tables:
            # 2.1 保存表信息到meta数据库
            column_infos: list[ColumnInfoMySQL] = await self._save_table_info_to_meta_db(meta_config)
            logger.info("保存表信息到meta数据库")
            # 2.2 为字段信息构建向量索引
            await self._save_column_info_to_qdrant(column_infos)
            logger.info("为字段构建向量索引")
            # 2.3 为字段取值构建全文索引
            await self._save_column_value_to_es(meta_config, column_infos)
            logger.info("为字段取值建立全文索引")

        # 3.指标处理
        if meta_config.metrics:
            # 3.1 保存指标信息到meta数据库
            metric_infos:list[MetricInfoMySQL]=await self.save_metric_info_to_meta_db(meta_config)
            logger.info("保存指标信息到meta数据库")
            # 3.2 为指标信息构建向量索引
            await self._save_metric_info_to_qdrant(metric_infos)
            logger.info("为指标信息构建向量索引")

    async def _save_table_info_to_meta_db(self, meta_config: MetaConfig) -> list[ColumnInfoMySQL]:
        # 定义表信息收集列表
        table_infos: list[TableInfoMySQL] = []
        # 定义字段信息收集列表
        column_infos: list[ColumnInfoMySQL] = []

        # 封装保存数据列表
        for table in meta_config.tables:

            # 封装表信息对象
            table_info_mysql = TableInfoMySQL(
                id=table.name,
                name=table.name,
                role=table.role,
                description=table.description,
            )
            # 收集表信息
            table_infos.append(table_info_mysql)

            # 根据表查询字段的类型字典结果
            column_info_types: dict[str, str] = await self.dw_mysql_repository.get_column_types(table.name)
            # 处理字段信息
            for column in table.columns:
                # 查询当前字段的取值实例
                column_info_values: list[str] = await self.dw_mysql_repository.get_column_values(table.name,
                                                                                                 column.name)

                # 封装字段信息
                column_info_mysql = ColumnInfoMySQL(
                    id=f"{table.name}.{column.name}",
                    name=column.name,
                    type=column_info_types[column.name],
                    role=column.role,
                    examples=column_info_values,
                    description=column.description,
                    alias=column.alias,
                    table_id=table.name,

                )
                # 收集字段信息
                column_infos.append(column_info_mysql)

        async with self.meta_mysql_repository.session.begin():
            await self.meta_mysql_repository.save_table_infos(table_infos)
            await self.meta_mysql_repository.save_column_infos(column_infos)
        return column_infos

    def _convert_column_info_from_mysql_to_qdrant(self, column_info: ColumnInfoMySQL):
        return ColumnInfoQdrant(
            id=column_info.id,
            name=column_info.name,
            type=column_info.type,
            role=column_info.role,
            examples=column_info.examples,
            alias=column_info.alias,
            description=column_info.description,
            table_id=column_info.table_id
        )

    async def _save_column_info_to_qdrant(self, column_infos: list[ColumnInfoMySQL]):
        # 确保存储字段向量的集合存在
        await self.column_qdrant_repository.ensure_collection()
        # 封装构建结果
        points: list[dict] = []
        # 构建向量结果，存储数据
        for column_info in column_infos:
            # name
            points.append({
                "id": uuid.uuid4(),
                "embedding_text": column_info.name,
                "payload": self._convert_column_info_from_mysql_to_qdrant(column_info)

            })
            # description
            points.append({
                "id": uuid.uuid4(),
                "embedding_text": column_info.description,
                "payload": self._convert_column_info_from_mysql_to_qdrant(column_info)

            })
            # alias
            for alia in column_info.alias:
                points.append({
                    "id": uuid.uuid4(),
                    "embedding_text": alia,
                    "payload": self._convert_column_info_from_mysql_to_qdrant(column_info)

                })

        # 获取所有的向量文本
        embedding_texts = [point['embedding_text'] for point in points]

        # 定义向量接收列表 list[list[float],list[float]]
        embeddings = []
        # 定义批次
        batch_size = 10
        # 循环获取批次数据
        for i in range(0, len(embedding_texts), batch_size):
            # 取批次数据
            batch_embedding_texts = embedding_texts[i:i + batch_size]
            # 转换向量 list[list[float],list[float]]
            embedding = await self.embeddings.aembed_documents(batch_embedding_texts)
            # 收集数据
            embeddings.extend(embedding)

        # 获取所有的id
        ids = [point['id'] for point in points]
        # 获取所有负载
        payloads = [point['payload'] for point in points]

        # 保存向量到qdrant
        await self.column_qdrant_repository.upsert_column(ids, embeddings, payloads)

    async def _save_column_value_to_es(self, meta_config: MetaConfig, column_infos: list[ColumnInfoMySQL]):
        # 确保存储字段取值的索引存在
        await self.column_es_repository.ensure_index()

        # 构建数据
        # 定义字典结构存储
        column2sync: dict = {}
        # 获取配置中所有字段是否索引的描述
        for table in meta_config.tables:
            # 获取字段信息
            for column in table.columns:
                column2sync[f"{table.name}.{column.name}"] = column.sync

        # 定义取值封装列表
        value_infos: list[ValueInfoEs] = []
        # 遍历并判断当前字段是否索引
        for column_info in column_infos:
            sync = column2sync[column_info.id]
            # 判断是否索引
            if sync:
                # 获取当前字段的所有值
                column_values: list[str] = await self.dw_mysql_repository.get_column_values(column_info.table_id,
                                                                                            column_info.name, 10000)

                # 封装具体结构
                sub_value_infos: list[ValueInfoEs] = [
                    ValueInfoEs(
                        id=f"{column_info.id}.{column_value}",
                        value=column_value,
                        type=column_info.type,
                        column_id=column_info.id,
                        column_name=column_info.name,
                        table_id=column_info.table_id,
                        table_name=column_info.table_id

                    )
                    for column_value in column_values]
                value_infos.extend(sub_value_infos)

        # 保存实现
        await self.column_es_repository.save_column_values(value_infos)

    async def save_metric_info_to_meta_db(self, meta_config:MetaConfig):
        metric_infos: list[MetricInfoMySQL] = []
        column_metrics: list[ColumnMetricMySQL] = []

        for metric in meta_config.metrics:
            # 构建指标保存结构
            metric_info = MetricInfoMySQL(
                id=metric.name,
                name=metric.name,
                description=metric.description,
                relevant_columns=metric.relevant_columns,
                alias=metric.alias
            )
            metric_infos.append(metric_info)
            # 构建字段指标关联结构
            for relevant_column in metric.relevant_columns:
                column_metric = ColumnMetricMySQL(
                    column_id=relevant_column,
                    metric_id=metric.name

                )
                column_metrics.append(column_metric)
        # 保存指标
        async with self.meta_mysql_repository.session.begin():
            await self.meta_mysql_repository.save_metrics(metric_infos)
            await self.meta_mysql_repository.save_column_metrics(column_metrics)
        return metric_infos

    def _convert_metric_info_from_mysql_to_qdrant(self, metric_info:MetricInfoMySQL):
        return MetricInfoQdrant(
            id=metric_info.id,
            name=metric_info.name,
            description=metric_info.description,
            relevant_columns=metric_info.relevant_columns,
            alias=metric_info.alias

        )


    async def _save_metric_info_to_qdrant(self, metric_infos:list[MetricInfoMySQL]):
        # 确保存储指标向量的集合存在
        await self.metric_qdrant_repository.ensure_collection()
        # 封装构建结果
        points: list[dict] = []
        # 构建向量结果，存储数据
        for metric_info in metric_infos:
            # name
            points.append({
                "id": uuid.uuid4(),
                "embedding_text": metric_info.name,
                "payload": self._convert_metric_info_from_mysql_to_qdrant(metric_info)

            })
            # description
            points.append({
                "id": uuid.uuid4(),
                "embedding_text": metric_info.description,
                "payload": self._convert_metric_info_from_mysql_to_qdrant(metric_info)

            })
            # alias
            for alia in metric_info.alias:
                points.append({
                    "id": uuid.uuid4(),
                    "embedding_text": alia,
                    "payload": self._convert_metric_info_from_mysql_to_qdrant(metric_info)

                })

        # 获取所有的向量文本
        embedding_texts = [point['embedding_text'] for point in points]

        # 定义向量接收列表 list[list[float],list[float]]
        embeddings = []
        # 定义批次
        batch_size = 10
        # 循环获取批次数据
        for i in range(0, len(embedding_texts), batch_size):
            # 取批次数据
            batch_embedding_texts = embedding_texts[i:i + batch_size]
            # 转换向量 list[list[float],list[float]]
            embedding = await self.embeddings.aembed_documents(batch_embedding_texts)
            # 收集数据
            embeddings.extend(embedding)

        # 获取所有的id
        ids = [point['id'] for point in points]
        # 获取所有负载
        payloads = [point['payload'] for point in points]

        # 保存向量
        await self.metric_qdrant_repository.upsert_metric(ids, embeddings, payloads)
