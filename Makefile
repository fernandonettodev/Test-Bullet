.PHONY: help install dev test lint format clean docker-build docker-run

# Default target
help:
	@echo "Available commands:"
	@echo "  install     - Install dependencies"
	@echo "  dev         - Run development server"
	@echo "  test        - Run tests"
	@echo "  test-cov    - Run tests with coverage"
	@echo "  lint        - Run linting"
	@echo "  format      - Format code"
	@echo "  clean       - Clean cache files"
	@echo "  docker-build- Build Docker image"
	@echo "  docker-run  - Run with Docker Compose"

# Install dependencies
install:
	pip install -r requirements.txt

# Run development server
dev:
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run tests
test:
	pytest tests/ -v

# Run tests with coverage
test-cov:
	pytest tests/ -v --cov=. --cov-report=html --cov-report=term

# Run concurrent tests specifically
test-concurrent:
	pytest tests/test_transactions.py::TestConcurrency -v -s

# Lint code
lint:
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
	mypy . --ignore-missing-imports

# Format code
format:
	black .
	isort .

# Clean cache files
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/

# Docker commands
docker-build:
	docker build -t transaction-api .

docker-run:
	docker-compose up -d

docker-stop:
	docker-compose down

docker-logs:
	docker-compose logs -f api

# Load testing (requires 'hey' tool: go install github.com/rakyll/hey@latest)
load-test:
	hey -n 1000 -c 10 -m POST \
		-H "Content-Type: application/json" \
		-d '{"idempotencyKey":"load-test-$(shell date +%s)-$${RANDOM}","accountId":"acc_001","amount":1.00,"type":"credit","description":"Load test"}' \
		http://localhost:8000/transactions

# Database migration placeholder (for future database integration)
migrate:
	@echo "Migrations not implemented yet (in-memory storage)"

# Security scan (requires safety: pip install safety)
security:
	safety check
	bandit -r . -x tests/

# Generate API documentation
docs:
	@echo "API documentation available at:"
	@echo "  Swagger UI: http://localhost:8000/docs"
	@echo "  ReDoc: http://localhost:8000/redoc"

# Performance profiling
profile:
	python -m cProfile -o profile.stats -m uvicorn main:app --host 0.0.0.0 --port 8000