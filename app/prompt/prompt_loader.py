import asyncio
from pathlib import Path


async def loader_prompt(name:str):

    # 定义提示词文件的路径
    prompt_path=Path(__file__).parents[2]/'prompts'/f'{name}.prompt'
    # 读取提示词文本内容

    return prompt_path.read_text(encoding='utf-8')


if __name__ == '__main__':

    async def test():
        print(await loader_prompt("generate_sql"))


    asyncio.run(test())