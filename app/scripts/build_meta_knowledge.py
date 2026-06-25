import asyncio
from pathlib import Path

import argparse

from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import meta_mysql_client_manager, dw_mysql_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.repositories.es.values_es_repository import ValueEsRepository
from app.repositories.mysql.dw_mysql_repository import DwMysqlRepository
from app.repositories.mysql.meta_mysql_repository import MetaMysqlRepository
from app.repositories.qdrant.column_qdrant_respository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from app.meta_knowledge_service import MetaKnowledgeService


async def build(config_path: Path):

    # 初始化客户端
    meta_mysql_client_manager.init()
    dw_mysql_client_manager.init()
    qdrant_client_manager.init()
    embedding_client_manager.init()
    es_client_manager.init()
    # 获取session
    async with meta_mysql_client_manager.session_factory() as meta_session,dw_mysql_client_manager.session_factory() as dw_session:
        # 创建repository
        meta_mysql_repository = MetaMysqlRepository(meta_session)
        dw_mysql_repository = DwMysqlRepository(dw_session)
        column_qdrant_repository=ColumnQdrantRepository(qdrant_client_manager.client)
        column_es_repository=ValueEsRepository(es_client_manager.client)
        metric_qdrant_repository=MetricQdrantRepository(qdrant_client_manager.client)
        # 创建业务层对象
        meta_knowledge_service=MetaKnowledgeService(
            meta_mysql_repository=meta_mysql_repository,
            dw_mysql_repository=dw_mysql_repository,
            column_qdrant_repository=column_qdrant_repository,
            embeddings=embedding_client_manager.embeddings,
            column_es_repository=column_es_repository,
            metric_qdrant_repository= metric_qdrant_repository
        )
        # 调用构建函数
        await meta_knowledge_service.build(config_path)

    # 释放资源
    await meta_mysql_client_manager.close()
    await qdrant_client_manager.close()
    await es_client_manager.close()


if __name__ == '__main__':
    # 构建argparse的解析器对象
    parser = argparse.ArgumentParser()
    # 设置参数传递配置项
    parser.add_argument('-c', '--conf')  # 接受一个值的选项
    # 解析获取参数
    args = parser.parse_args()
    # 转换path对象
    config_path= Path(args.conf)
    asyncio.run(build(config_path))
