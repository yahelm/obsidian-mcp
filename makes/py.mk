.EXPORT_ALL_VARIABLES:

.PHONY: py/help
py/help:
	@echo "Python targets:"
	@echo "  py/install             - Install Python and project dependencies"
	@echo "  py/check               - Check Python dependencies"
	@echo "  py/lint                - Run ruff, pylint & mypy"
	@echo "  py/lint/ruff           - Run ruff linter"
	@echo "  py/fmt/ruff            - Run ruff format"
	@echo "  py/fix/ruff            - Run ruff lint checker (fix issues)"
	@echo "  py/lint/mypy           - Run mypy type checker"

.PHONY: py/install
py/install:
	uv lock --check
	uv sync --frozen

.PHONY: py/check
py/check:
	uv run python -c "from obsidian_mcp import server; print('OK')"

.PHONY: py/lint
py/lint: py/lint/ruff py/lint/mypy

.PHONY: py/lint/ruff
py/lint/ruff:
	uv run ruff format . --check
	uv run ruff check .

.PHONY: py/fmt/ruff
py/fmt/ruff:
	uv run ruff format .

.PHONY: py/fix/ruff
py/fix/ruff:
	uv run ruff format .
	uv run ruff check . --fix

.PHONY: py/lint/mypy
py/lint/mypy:
	uv run mypy .
