from dataclasses import dataclass
from pathlib import Path

from omegaconf import OmegaConf

from app.conf.app_config import app_config


@dataclass
class Console:
    enable: bool
    level: str

@dataclass
class TextConfig:
    name: str
    age: int
    height: float
    console: Console


# 定义配置文件路径
file_url = Path(__file__).parents[2]/'conf'/'text_config.yaml'
# 加载配置文件内容
content = OmegaConf.load(file_url)
# 设置配置封装结构
schema=OmegaConf.structured(TextConfig)
# 合并数据和结构，再转换成对象
text_config:TextConfig=OmegaConf.to_object(OmegaConf.merge(schema,content))

print(text_config.height)
print(text_config.name)
print(text_config.age)
print(text_config.console.enable)

print(app_config.db_dw.database)