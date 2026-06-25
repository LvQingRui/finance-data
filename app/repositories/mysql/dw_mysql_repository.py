from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils import serialize_rows, serialize_value


class DwMysqlRepository:
    def __init__(self,session:AsyncSession):
        self.session = session

    async def get_column_types(self, table_name:str):
        """
        获取表的字段和类型列表
        :param table_name:
        :return:
        """
        # 定义sql
        sql = f"SHOW COLUMNS from {table_name}"
        # 执行sql
        result =  await self.session.execute(text(sql))
        # 获取结果 [(Row),(Row),(Row)]
        return {row.Field: row.Type for row in result.fetchall()}

    async def get_column_values(self, table_name, column_name,limit:int = 10 ):
        """
        查询当前字段的取值实例
        :param table_name:
        :param column_name:
        :return:
        """
        # 定义sql
        sql = f"select distinct {column_name} from {table_name} limit {limit}"
        # 执行sql
        result = await self.session.execute(text(sql))
        return [serialize_value(value) for value in result.scalars().fetchall()]

    async def get_db_info(self):
        """
        查询数据信息
        :return:
        """
        # 1.查询数据的版本
        result =await self.session.execute(text(" SELECT VERSION() "))
        # 获取单行单列的数据
        version=result.scalar()
        # 2.获取方言
        dialect=self.session.get_bind().dialect.name

        return {"version":version,"dialect":dialect}

    async def validate_sql(self, sql:str):
        """
        校验sql语句
        :param sql:
        :return:
        """

        await self.session.execute(text(sql))

    async def execute_sql(self, sql:str):

        """
        执行sql
        :param sql:
        :return:
        """
        # 执行sql
        result = await self.session.execute(text(sql))
        return serialize_rows([dict(row) for row in result.mappings().fetchall()])
