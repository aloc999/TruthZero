.PHONY: install dev test lint clean build

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

lint:
	ruff check zer0code/
	ruff format --check zer0code/

format:
	ruff format zer0code/

clean:
	rm -rf build/ dist/ *.egg-info __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build:
	python -m build

run:
	python -m zer0code
