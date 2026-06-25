import asyncio
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession, async_sessionmaker

from app.conf.app_config import app_config, DBConfig


class MysqlClientManager:
    def __init__(self, db_config: DBConfig):
        self.engine: Optional[AsyncEngine] = None
        self.config = db_config
        self.session_factory = None

    def _get_url(self):
        return f"mysql+asyncmy://{self.config.user}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}?charset=utf8mb4"

    def init(self):
        self.engine = create_async_engine(
            url=self._get_url(),
            pool_size=5,
            pool_pre_ping=True
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            autoflush=True, autobegin=True,
            expire_on_commit=False
        )

    async def close(self):
        await self.engine.dispose()


dw_mysql_client_manager = MysqlClientManager(app_config.db_dw)

meta_mysql_client_manager = MysqlClientManager(app_config.db_meta)

if __name__ == '__main__':
    # 创建engine
    dw_mysql_client_manager.init()


    async def test():
        # 获取session，执行操作
        # async with AsyncSession(bind=dw_mysql_client_manager.engine, autoflush=True, autobegin=True,
        #                         expire_on_commit=False) as session:
        async with dw_mysql_client_manager.session_factory() as session:
            # 定义sql
            sql = "select *from fact_order limit 10"
            # 执行sql
            result = await session.execute(text(sql))
            # 获取结果
            # [(),(),()] ()-Row对象  对象.属性名
            # rows  = result.fetchall()
            # [{},{},{}] ['[order_id']
            rows = result.mappings().fetchall()
            print(type(rows))
            # Row()
            # print(type(rows[0]))
            print(rows[0]['order_id'])
        # 释放资源
        await dw_mysql_client_manager.close()


    asyncio.run(test())
