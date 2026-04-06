# Twitter Scraping Pipeline - Makefile

.PHONY: help install install-dev install-twikit test lint format clean run-search run-trends status

# Default target
help:
	@echo "Twitter Scraping Pipeline - Available Commands"
	@echo ""
	@echo "  make install         Install core dependencies"
	@echo "  make install-dev     Install development dependencies"
	@echo "  make install-twikit Install twikit for extended features"
	@echo "  make test           Run tests"
	@echo "  make lint           Run linter (ruff)"
	@echo "  make format         Format code"
	@echo "  make clean          Clean cache files"
	@echo "  make run-search    Run example search"
	@echo "  make run-trends    Run example trends"
	@echo "  make status        Show pipeline status"

# Installation
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install pytest pytest-asyncio ruff mypy

install-twikit:
	pip install -e ../twikit

# Testing
test:
	pytest -v

# Linting
lint:
	ruff check .

# Code formatting
format:
	ruff format .

# Cleanup
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ .pytest_cache/ .ruff_cache/ 2>/dev/null || true
	rm -f pipeline.db 2>/dev/null || true

# Example runs
run-search:
	python cli.py search "python programming" --limit 10

run-trends:
	python cli.py trends --categories trending --limit 5

status:
	python cli.py status

# Full setup (one command)
setup: install install-twikit
	@echo "Setup complete! Run 'make status' to verify."