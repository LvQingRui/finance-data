from sqlalchemy import Select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mysql.column_info_mysql import ColumnInfoMySQL
from app.models.mysql.column_metric_mysql import ColumnMetricMySQL
from app.models.mysql.metric_info_mysql import MetricInfoMySQL
from app.models.mysql.table_info_mysql import TableInfoMySQL


class MetaMysqlRepository:
    def __init__(self,session:AsyncSession):
        self.session = session

    async def save_table_infos(self, table_infos:list[TableInfoMySQL]):
        """
        保存表信息到meta数据库
        :param table_infos:
        :return:
        """
        self.session.add_all(table_infos)

    async def save_column_infos(self, column_infos:list[ColumnInfoMySQL]):
        """
        保存字段信息到meta数据库
        :param column_infos:
        :return:
        """
        self.session.add_all(column_infos)

    async def save_metrics(self, metric_infos:list[MetricInfoMySQL]):
        """
        保存指标信息到meta数据库
        :param metric_infos:
        :return:
        """
        self.session.add_all(metric_infos)

    async def save_column_metrics(self, column_metrics:list[ColumnMetricMySQL]):
        """
        保存字段指标关联信息到meta数据
        :param column_metrics:
        :return:
        """
        self.session.add_all(column_metrics)

    async def get_column_info_by_id(self, column_id:str):
        """
        根据字段id查询字段信息对象
        :param relevant_column:
        :return:
        """
        return await self.session.get(ColumnInfoMySQL,column_id)

    async def get_key_columns_by_table_id(self, table_id:str):
        """
        查询指定表的主外键字段
        select*
        from column_info
        where role in ('primary_key', 'foreign_key')
          and table_id = 'fact_order'
        :param table_id:
        :return:
        """
        # 定义sql
        sql ="""
            select*
            from column_info
            where role in ('primary_key', 'foreign_key')
              and table_id = :table_id
        """
        # 设置封装结构
        query=Select(ColumnInfoMySQL).from_statement(text(sql))
        # 执行sql
        result = await self.session.execute(query,{"table_id":table_id})
        # 结果ScalarResult-->[(ColumnInfoMysql对象),(ColumnInfoMysql对象),(ColumnInfoMysql对象)]
        return result.scalars().fetchall()

    async def get_table_by_id(self, table_id:str):
        """
        根据表ID查询表信息对象
        :param table_id:
        :return:
        """
        return await self.session.get(TableInfoMySQL,table_id)
