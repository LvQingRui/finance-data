import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from omegaconf import OmegaConf

load_dotenv(Path(__file__).parents[2] / ".env", override=False)


@dataclass
class File:
    enable: bool
    level: str
    path: str
    rotation: str
    retention: str


@dataclass
class Console:
    enable: bool
    level: str


@dataclass
class LoggingConfig:
    file: File
    console: Console


@dataclass
class DBConfig:
    host: str
    port: int
    user: str
    password: str
    database: str


@dataclass
class QdrantConfig:
    host: str
    port: int
    embedding_size: int


@dataclass
class EmbeddingConfig:
    host: str
    port: int
    model: str


@dataclass
class ESConfig:
    host: str
    port: int
    index_name: str


@dataclass
class LLMConfig:
    model_name: str
    api_key: str


@dataclass
class AppConfig:
    logging: LoggingConfig
    db_meta: DBConfig
    db_dw: DBConfig
    qdrant: QdrantConfig
    embedding: EmbeddingConfig
    es: ESConfig
    llm: LLMConfig


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


config_file = Path(__file__).parents[2] / "conf" / "app_config.yaml"
context = OmegaConf.load(config_file)
schema = OmegaConf.structured(AppConfig)
app_config: AppConfig = OmegaConf.to_object(OmegaConf.merge(schema, context))

# 环境变量优先，避免在仓库中保存真实地址和密码
app_config.db_meta.host = os.getenv("DB_HOST", app_config.db_meta.host)
app_config.db_meta.port = _env_int("DB_PORT", app_config.db_meta.port)
app_config.db_meta.user = os.getenv("DB_USER", app_config.db_meta.user)
app_config.db_meta.password = os.getenv("DB_PASSWORD", app_config.db_meta.password)

app_config.db_dw.host = os.getenv("DB_HOST", app_config.db_dw.host)
app_config.db_dw.port = _env_int("DB_PORT", app_config.db_dw.port)
app_config.db_dw.user = os.getenv("DB_USER", app_config.db_dw.user)
app_config.db_dw.password = os.getenv("DB_PASSWORD", app_config.db_dw.password)
app_config.db_dw.database = os.getenv("DB_NAME", app_config.db_dw.database)

app_config.qdrant.host = os.getenv("QDRANT_HOST", app_config.qdrant.host)
app_config.qdrant.port = _env_int("QDRANT_PORT", app_config.qdrant.port)

app_config.embedding.host = os.getenv("TEI_HOST", app_config.embedding.host)
app_config.embedding.port = _env_int("TEI_PORT", app_config.embedding.port)

app_config.es.host = os.getenv("ES_HOST", app_config.es.host)
app_config.es.port = _env_int("ES_PORT", app_config.es.port)

if api_key := os.getenv("DEEPSEEK_API_KEY"):
    app_config.llm.api_key = api_key
