.PHONY: install test lint typecheck check

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --cov --cov-report=term-missing

lint:
	ruff check .

typecheck:
	mypy core pipeline utils summarizer.py

check: lint typecheck test
