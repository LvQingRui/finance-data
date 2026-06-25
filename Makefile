.PHONY: help init_db gen smoke run clean

help:
	@echo "make init_db      	- 初始化数据库"
	@echo "make gen          	- 生成全量数据并执行验收"
	@echo "make smoke        	- 生成小规模数据并执行验收"
	@echo "make run          	- 启动服务"
	@echo "make clean        	- 清理临时文件"

init_db:
	uv run init_db.py

gen:
	uv run init_db.py
	uv run -m generate.main --profile full

smoke:
	uv run init_db.py
	uv run -m generate.main --profile smoke

run:
	uv run -m app.main

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "logs" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".venv" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
