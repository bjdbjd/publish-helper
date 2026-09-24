# Makefile for Publish Helper development

.PHONY: help install install-dev test lint format clean run-gui run-api docker-build docker-run docker-stop

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

run-cli:
	python src/main_cli.py

# Docker（统一镜像：Vue 前端 + Flask API + nginx 同容器）
# context 必须是**两个仓库的公共父目录**（..），因为前端 publish-helper-vue
# 是独立仓库、需在 node 阶段 COPY 其源码。故本目标先 cd .. 再构建。
docker-build:
	cd .. && docker build -f publish-helper/deploy/Dockerfile -t publish-helper:local .

docker-run:
	docker compose -f deploy/docker-compose.yml up -d

docker-stop:
	docker compose -f deploy/docker-compose.yml down

# Package building
build:
	python -m build

# Security check
security:
	bandit -r src/
	safety check

# All checks
check-all: format-check lint test security
