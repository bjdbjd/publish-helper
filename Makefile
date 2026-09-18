# Makefile for Publish Helper development

.PHONY: help install install-dev test lint format clean run-gui run-api docker-build docker-run

# Default target
help:
	@echo "Available targets:"
	@echo "  install      - Install production dependencies"
	@echo "  install-dev  - Install development dependencies"
	@echo "  test         - Run tests with coverage"
	@echo "  lint         - Run linting (flake8, mypy)"
	@echo "  format       - Format code (black, isort)"
	@echo "  clean        - Clean up generated files"
	@echo "  run-gui      - Run GUI application"
	@echo "  run-api      - Run API server"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run   - Run Docker container"

# Installation
install:
	pip install -r requirements.txt

install-dev: install
	pip install -r requirements-dev.txt
	pre-commit install

# Testing
test:
	pytest tests/ -v

test-coverage:
	pytest tests/ --cov=src --cov-report=html --cov-report=term

# Code quality
lint:
	flake8 src/ tests/
	mypy src/

format:
	black src/ tests/
	isort src/ tests/

format-check:
	black --check src/ tests/
	isort --check-only src/ tests/

# Cleanup
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf dist/
	rm -rf build/

# Running applications
run-gui:
	python src/main_gui.py

run-api:
	python src/main_api.py

# Docker
docker-build:
	docker build -t publish-helper .

docker-run:
	docker-compose up -d

docker-stop:
	docker-compose down

# Package building
build:
	python -m build

# Security check
security:
	bandit -r src/
	safety check

# All checks
check-all: format-check lint test security
