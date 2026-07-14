.DEFAULT_GOAL := help
.PHONY: help logs test docker-test stop build up setup run shell api healthcheck migrate ensure-indexes

help:
	@perl -nle'print $& if m{^[a-zA-Z_-]+:.*?## .*$$}' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-25s\033[0m %s\n", $$1, $$2}'

# ============================================================================
# Local Development (Phase 3 - FastAPI + MongoDB)
# ============================================================================

install: ## Install all Python dependencies (local dev)
	pip install uv 2>/dev/null || true
	uv pip install -r requirements/base.txt

setup: install ## Install deps + Playwright browsers + ensure MongoDB indexes
	playwright install --with-deps chromium
	python -m openoutreach.cli ensure-indexes

run: ## Run the daemon (task queue worker)
	python -m openoutreach.cli rundaemon

api: ## Start the FastAPI server (dev mode with auto-reload)
	python -m openoutreach.cli runserver --host 0.0.0.0 --port 8001 --reload

shell: ## Open an interactive Python shell with MongoDB context
	python -m openoutreach.cli shell

healthcheck: ## Check system health (MongoDB connection, API availability)
	python -m openoutreach.cli healthcheck

migrate: ## Migrate data from SQLite to MongoDB (run once during migration)
	python -m openoutreach.cli migrate

ensure-indexes: ## Create all MongoDB indexes (idempotent)
	python -m openoutreach.cli ensure-indexes

showconfig: ## Show current configuration (env vars, safe)
	python -m openoutreach.cli showconfig

test: ## Run the test suite
	pytest

# ============================================================================
# Docker Targets (Phase 3 - FastAPI + MongoDB)
# ============================================================================

logs: ## Follow the logs of the service
	docker compose -f docker-compose.v2.yml logs -f

docker-test: ## Run tests in Docker
	docker compose -f docker-compose.v2.yml run --rm openoutreach pytest -vv

stop: ## Stop all services defined in Docker Compose
	docker compose -f docker-compose.v2.yml stop

down: ## Stop and remove all containers
	docker compose -f docker-compose.v2.yml down

build: ## Build all services defined in Docker Compose
	docker compose -f docker-compose.v2.yml build

up: ## Run the service in Docker Compose (foreground)
	docker compose -f docker-compose.v2.yml up --build

up-detached: ## Run the service in Docker Compose (background)
	docker compose -f docker-compose.v2.yml up --build -d
	docker compose -f docker-compose.v2.yml logs -f

restart: ## Restart all services
	docker compose -f docker-compose.v2.yml restart

ps: ## Show running containers
	docker compose -f docker-compose.v2.yml ps

# ============================================================================
# MongoDB Management
# ============================================================================

mongo-shell: ## Open MongoDB shell
	docker compose -f docker-compose.v2.yml exec mongodb mongosh openoutreach

mongo-backup: ## Backup MongoDB to ./data/mongo-backup/
	mkdir -p ./data/mongo-backup
	docker compose -f docker-compose.v2.yml exec -T mongodb mongodump --out=/data/db/backup --db=openoutreach
	docker compose -f docker-compose.v2.yml exec -T mongodb tar czf /data/db/backup.tar.gz -C /data/db backup
	docker cp $$(docker compose -f docker-compose.v2.yml ps -q mongodb):/data/db/backup.tar.gz ./data/mongo-backup/backup-$$(date +%Y%m%d-%H%M%S).tar.gz

mongo-restore: ## Restore MongoDB from latest backup in ./data/mongo-backup/
	@LATEST=$$(ls -t ./data/mongo-backup/backup-*.tar.gz 2>/dev/null | head -1); \
	if [ -z "$$LATEST" ]; then \
		echo "No backup found in ./data/mongo-backup/"; \
		exit 1; \
	fi; \
	echo "Restoring from $$LATEST"; \
	docker cp $$LATEST $$(docker compose -f docker-compose.v2.yml ps -q mongodb):/tmp/backup.tar.gz; \
	docker compose -f docker-compose.v2.yml exec -T mongodb tar xzf /tmp/backup.tar.gz -C /tmp; \
	docker compose -f docker-compose.v2.yml exec -T mongodb mongorestore --drop --db=openoutreach /tmp/backup/openoutreach

# ============================================================================
# Cleanup
# ============================================================================

clean: ## Remove Python cache files
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete
	find . -type d -name '*.egg-info' -exec rm -rf {} +
	find . -type d -name '.pytest_cache' -exec rm -rf {} +

clean-docker: ## Remove all Docker containers, images, and volumes
	docker compose -f docker-compose.v2.yml down -v --rmi all

# ============================================================================
# Frontend
# ============================================================================

frontend-install: ## Install frontend dependencies
	cd frontend && npm install

frontend-dev: ## Run frontend in dev mode
	cd frontend && npm run dev

frontend-build: ## Build frontend for production
	cd frontend && npm run build

frontend-start: ## Start frontend production server
	cd frontend && npm start
