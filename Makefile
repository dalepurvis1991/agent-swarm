.PHONY: help install test lint format security clean docker-up docker-down

help:		## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:	## Install dependencies
	poetry install

test:		## Run all tests
	poetry run pytest tests/ -v

test-unit:	## Run unit tests only
	poetry run pytest tests/ -v -m "not integration"

test-integration:	## Run integration tests only
	poetry run pytest tests/ -v -m integration

test-coverage:	## Run tests with coverage report
	poetry run pytest tests/ --cov=backend --cov-report=html --cov-report=term-missing

lint:		## Run all linting checks
	poetry run black --check --diff .
	poetry run flake8 backend/ tests/ tools/
	poetry run mypy backend/ tools/ --ignore-missing-imports

format:		## Format code with black
	poetry run black .

security:	## Run security checks
	poetry run safety check
	poetry run bandit -r backend/

clean:		## Clean up cache and temporary files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/

docker-up:	## Start all services with docker-compose
	docker-compose up -d

docker-down:	## Stop all services
	docker-compose down -v

docker-logs:	## Show logs from all services
	docker-compose logs -f

db-migrate:	## Run database migrations
	poetry run python -c "import psycopg; from backend.app.db import DB_DSN; conn = psycopg.connect(DB_DSN); [conn.execute(open(f'migrations/{f}').read()) for f in ['001_initial.sql', '002_offers.sql']]; conn.commit(); print('Migrations completed')"

run-quote:	## Run quote tool example
	poetry run python tools/run_quote.py "eco-friendly tote bags" --k 3 --poll-duration 30

dev-setup:	## Set up development environment
	@echo "Setting up development environment..."
	cp .env.example .env
	@echo "📝 Created .env file from template"
	make install
	@echo "📦 Installed dependencies"
	make docker-up
	@echo "🐳 Started services"
	sleep 10
	make db-migrate
	@echo "🗄️ Applied database migrations"
	@echo ""
	@echo "✅ Development environment ready!"
	@echo "   - Database: postgresql://dev:dev@localhost:5432/email_processing"
	@echo "   - MailHog UI: http://localhost:8025"
	@echo "   - Run tests: make test"
	@echo "   - Run quote tool: make run-quote"

ci-local:	## Run full CI pipeline locally
	@echo "Running local CI pipeline..."
	make clean
	make lint
	make test-unit
	@echo "✅ Local CI checks passed!" 