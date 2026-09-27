.PHONY: install dev test lint clean build

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

lint:
	ruff check truthzero/
	ruff format --check truthzero/

format:
	ruff format truthzero/

clean:
	rm -rf build/ dist/ *.egg-info __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build:
	python -m build

run:
	python -m truthzero
