"""初始化数据库"""

import logging
import os
from pathlib import Path

import pymysql
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 路径常量
CURRENT_DIR = Path(__file__).parent  # 当前文件所在目录
ROOT_DIR = CURRENT_DIR  # 根目录


class MySQLInit:
    """MySQL 数据库初始化"""

    def __init__(self, host: str, port: int, user: str, password: str):
        self.conn_conf = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
        }

    def init_db(self, db_sql_files: list[tuple[str, Path]]):
        """初始化数据库并导入数据"""
        if not db_sql_files:
            raise RuntimeError("未找到数据库初始化 SQL 文件")
        logger.info(f"开始初始化数据库 {[db_name for db_name, _ in db_sql_files]}")
        for db_name, sql_file_path in db_sql_files:
            if self.check_db_exists(db_name):
                self.delete_db(db_name)
            self.create_db(db_name)
            self.exec_sql_file(db_name, sql_file_path)
            logger.info(f"{db_name} 初始化完成")

    def check_db_exists(self, db_name: str) -> bool:
        """查询 MySQL 实例中是否已存在指定数据库"""
        conn = None
        try:
            conn = pymysql.connect(**self.conn_conf)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA "
                    "WHERE SCHEMA_NAME = %s",
                    (db_name,),
                )
                result = cur.fetchone()
                return result is not None
        except Exception as e:
            logger.exception(f"检查数据库 {db_name} 是否存在时失败: {e}")
            raise
        finally:
            if conn is not None:
                conn.close()

    def delete_db(self, db_name: str):
        """删除指定数据库"""
        conn = None
        try:
            conn = pymysql.connect(**self.conn_conf, autocommit=True)
            with conn.cursor() as cur:
                cur.execute(f"DROP DATABASE `{db_name}`")
        except Exception as e:
            logger.exception(f"数据库 {db_name} 删除失败: {e}")
            raise
        finally:
            if conn is not None:
                conn.close()

    def create_db(self, db_name: str):
        """创建指定数据库，并统一使用 utf8mb4 字符集"""
        conn = None
        try:
            conn = pymysql.connect(**self.conn_conf, autocommit=True)
            with conn.cursor() as cur:
                cur.execute(f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4")
        except Exception as e:
            logger.exception(f"数据库 {db_name} 创建失败: {e}")
            raise
        finally:
            if conn is not None:
                conn.close()

    def exec_sql_file(self, db_name: str, sql_file_path: Path):
        """在指定数据库中按分号拆分并顺序执行 SQL 文件内容"""
        conn = None
        try:
            with open(sql_file_path, "r", encoding="utf-8") as f:
                sql = f.read()
            conn = pymysql.connect(**self.conn_conf, database=db_name)
            conn.begin()
            with conn.cursor() as cur:
                statements = [stmt.strip() for stmt in sql.split(";") if stmt.strip()]
                for statement in statements:
                    cur.execute(statement)
                conn.commit()
        except Exception as e:
            if conn is not None:
                conn.rollback()
            logger.exception(f"{sql_file_path.stem} 执行sql失败: {e}")
            raise
        finally:
            if conn is not None:
                conn.close()


def prepare():
    """获取 (数据库名, SQL 脚本文件路径) 元组"""
    sql_dir = ROOT_DIR / "sql"
    return [(f.stem, f) for f in sql_dir.glob("*.sql")]


if __name__ == "__main__":
    load_dotenv(ROOT_DIR / ".env", override=False)

    db_init = MySQLInit(
        host=os.getenv("DB_HOST", ""),
        port=int(os.getenv("DB_PORT", "")),
        user=os.getenv("DB_USER", ""),
        password=os.getenv("DB_PASSWORD", ""),
    )
    db_init.init_db(prepare())
