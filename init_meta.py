"""仅初始化 meta 元数据库，不影响 finance 业务库。"""

import logging
import os
from pathlib import Path

import pymysql
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent
META_SQL = ROOT_DIR / "sql" / "meta.sql"


def init_meta_only() -> None:
    load_dotenv(ROOT_DIR / ".env", override=False)

    conn_conf = {
        "host": os.getenv("DB_HOST", ""),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", ""),
        "password": os.getenv("DB_PASSWORD", ""),
    }

    conn = pymysql.connect(**conn_conf, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("DROP DATABASE IF EXISTS `meta`")
            cur.execute("CREATE DATABASE `meta` CHARACTER SET utf8mb4")
        logger.info("meta 数据库已重建")
    finally:
        conn.close()

    with open(META_SQL, "r", encoding="utf-8") as f:
        sql = f.read()

    conn = pymysql.connect(**conn_conf, database="meta")
    try:
        conn.begin()
        with conn.cursor() as cur:
            for statement in [s.strip() for s in sql.split(";") if s.strip()]:
                cur.execute(statement)
        conn.commit()
        logger.info("meta 表结构初始化完成")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    init_meta_only()
