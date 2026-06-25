from dataclasses import asdict
from langgraph.runtime import Runtime
import  asyncio
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, TableInfoState, ColumnInfoState, MetricInfoState
from app.core.log import logger
from app.models.es.value_info_es import ValueInfoEs
from app.models.mysql.column_info_mysql import ColumnInfoMySQL
from app.models.mysql.table_info_mysql import TableInfoMySQL
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant




async def merge_retrieved_info(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"stage": "合并召回信息"})

    try:
        # 获取召回的字段列表
        retrieved_columns:list[ColumnInfoQdrant]=state["retrieved_columns"]
        # 获取召回的字段取值
        retrieved_values:list[ValueInfoEs]=state["retrieved_values"]
        # 获取召回的指标信息
        retrieved_metrics:list[MetricInfoQdrant]=state["retrieved_metrics"]

        # 获取持久层操作对象
        meta_mysql_repository =runtime.context["meta_mysql_repository"]


        # 定义收集表信息的列表
        table_infos:list[TableInfoState]=[]
        # 定义收集指标信息列表
        metric_infos:list[MetricInfoState]=[]

        # 去重：转换召回的字段列表结构为字典结构
        retrieved_columns_map:dict[str,ColumnInfoQdrant]={retrieved_column["id"]: retrieved_column for retrieved_column in retrieved_columns}
        # 1.判断召回的指标中关联的字段是否已经存在
        for retrieved_metric in retrieved_metrics:
            # 获取当前指标关联的字段列表
            relevant_columns=retrieved_metric["relevant_columns"]
            # 遍历列表
            for relevant_column in relevant_columns:
                # relevant_column 指标关联的字段id
                if relevant_column not in retrieved_columns_map:
                    # 根据字段id 查询字段信息
                    column_info_mysql:ColumnInfoMySQL=await meta_mysql_repository.get_column_info_by_id(relevant_column)
                    # 转换类型
                    column_info_qdrant:ColumnInfoQdrant=_conver_column_info_form_mysql_to_qdrant(column_info_mysql)
                    # 加入字段列表
                    retrieved_columns_map[relevant_column]=column_info_qdrant

        # 2.判断召回的字段取值对应的字段信息是否已经存在
        for retrieved_value in retrieved_values:
            # 获取当前值对象对应字段id
            column_id = retrieved_value["column_id"]
            # 获取召回的字段取值
            column_value=retrieved_value["value"]
            # 判断
            if column_id not in retrieved_columns_map:
                # 根据id查询字段信息
                column_info_mysql: ColumnInfoMySQL = await meta_mysql_repository.get_column_info_by_id(column_id)
                # 转换类型
                column_info_qdrant: ColumnInfoQdrant = _conver_column_info_form_mysql_to_qdrant(column_info_mysql)
                # 加入字段列表
                retrieved_columns_map[column_id] = column_info_qdrant

            #判断当前召回的值，是否存在对应字段的examples
            if column_value not in retrieved_columns_map[column_id]["examples"]:
                # 存储当前召回的值
                retrieved_columns_map[column_id]["examples"].append(column_value)

        # 3.根据所有的字段，以表分组整合
        #表1----字段1，字段2，字段3
        #表2----字段1，字段2，字段3
        # key--table_id    value--字段列表
        table_to_column_map:dict[str,list[ColumnInfoQdrant]]={}

        # 遍历召回的字段列表,构建表和字段的关联
        for column in retrieved_columns_map.values():

            # 获取当前字段对应的表信息
            table_id = column["table_id"]
            # 判断
            if table_id not in table_to_column_map:

                table_to_column_map[table_id]=[]

            # 添加字段到表的关联中
            table_to_column_map[table_id].append(column)



        # 处理表对应的主外键关系
        for table_id in table_to_column_map.keys():
            # 根据表id查询当前表的主键和外键
            key_columns:list[ColumnInfoMySQL]=await meta_mysql_repository.get_key_columns_by_table_id(table_id)

            # 获取当前表对应的所有字段的id
            column_ids=[column["id"] for column in table_to_column_map[table_id]]

            # 遍历查询的主外键列表
            for key_column in key_columns:
                # 获取ID
                column_id=key_column.id
                # 判断是否已经存在
                if column_id not in column_ids:
                    table_to_column_map[table_id].append(_conver_column_info_form_mysql_to_qdrant(key_column))


        # 构建表和字段的完整结构信息[(key:value),(key:value)]
        for table_id,columns in table_to_column_map.items():
            # table 表ID
            # columns: 对应的字段列表

            # 转换字段列表对应的实体结构
            columns_state=[
                ColumnInfoState(
                    name=column['name'],
                    type=column['type'],
                    role=column['role'],
                    examples=column['examples'],
                    description=column["description"],
                    alias=column["alias"]

                )for column in columns]

            #根据表ID查询信息
            table_info_mysql:TableInfoMySQL= await meta_mysql_repository.get_table_by_id(table_id)
            # 转换结构
            table_info= TableInfoState(
                name=table_info_mysql.name,
                role=table_info_mysql.role,
                description=table_info_mysql.description,
                columns=columns_state
            )

            # 收集表信息对象
            table_infos.append(table_info)



            pass



        logger.info(f"合并表信息完成，表信息{[table_info['name'] for table_info in table_infos]}")


        # 处理指标信息，构建指标数据结构

        for retrieved_metric in retrieved_metrics:

            # 构建实体
            metric_info_state=MetricInfoState(**retrieved_metric)
            # 收集指标数据
            metric_infos.append(metric_info_state)

        logger.info(f"合并指标信息完成，表信息{[metric_info['name'] for metric_info in metric_infos]}")

        return {"table_infos":table_infos,"metric_infos":metric_infos}
    except Exception as e:
        logger.error(f"合并召回信息异常{str(e)}")
        raise















def _conver_column_info_form_mysql_to_qdrant(column_info_mysql:ColumnInfoMySQL)->ColumnInfoQdrant:
    return ColumnInfoQdrant(
        id=column_info_mysql.id,
        name=column_info_mysql.name,
        type=column_info_mysql.type,
        role=column_info_mysql.role,
        examples=column_info_mysql.examples,
        description=column_info_mysql.description,
        alias=column_info_mysql.alias,
        table_id=column_info_mysql.table_id
    )

