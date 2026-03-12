.PHONY: help install test test-integration test-e2e lint typecheck format validate backup viewer restore docker-build docker-backup docker-viewer docker-restore docker-validate docker-test-e2e clean

VENV := .venv
PYTHON := $(VENV)/bin/python
POETRY := poetry
IMAGE_NAME := atlassian-backup
IMAGE_TAG := latest

help: ## Show this help message
	@echo "Atlassian Backup System"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Backup & Restore (local, requires: make install):"
	@echo "  backup             Run Confluence backup (pass URL=<confluence-url>)"
	@echo "  restore            Restore from backup (pass DIR=<backup-dir> SPACE=<space-key>)"
	@echo "  viewer             Start backup viewer (pass DIR=<backup-dir>)"
	@echo ""
	@echo "Development:"
	@echo "  install            Install dependencies with Poetry into .venv"
	@echo "  test               Run unit tests with pytest"
	@echo "  test-integration   Run integration tests against real Confluence"
	@echo "  test-e2e           Run end-to-end backup/restore cycle against real Confluence"
	@echo "  lint               Run ruff linter"
	@echo "  typecheck          Run mypy type checker"
	@echo "  format             Run ruff formatter"
	@echo "  validate           Run format + lint + typecheck + tests"
	@echo ""
	@echo "Docker (no local Python required, runs in container):"
	@echo "  docker-build       Build Docker image"
	@echo "  docker-backup      Run backup in Docker (pass URL=<url> [ENV_FILE=.env] [ARGS=\"...\"])"
	@echo "  docker-restore     Run restore in Docker (pass DIR=<backup-dir> SPACE=<space-key> [ENV_FILE=.env])"
	@echo "  docker-viewer      Start backup viewer in Docker (pass DIR=<backup-dir>)"
	@echo "  docker-validate    Run lint + typecheck + tests in Docker"
	@echo "  docker-test-e2e    Run end-to-end backup/restore cycle in Docker"
	@echo ""
	@echo "Other:"
	@echo "  clean              Remove build artifacts and caches"

install: ## Install dependencies into local .venv
	$(POETRY) config virtualenvs.in-project true
	$(POETRY) install

test: ## Run unit tests
	$(POETRY) run pytest tests/ -m "not integration" -v --tb=short

test-integration: ## Run integration tests
	$(POETRY) run pytest tests/ -m "integration" -v --tb=short || test $$? -eq 5

test-e2e: ## Run end-to-end backup/restore integration test (requires running Confluence)
	bash tests/integration/test_backup_restore.sh

lint: ## Run ruff linter
	$(POETRY) run ruff check src/ tests/

typecheck: ## Run mypy type checker
	$(POETRY) run mypy src/

format: ## Run ruff formatter
	$(POETRY) run ruff format src/ tests/
	$(POETRY) run ruff check --fix src/ tests/

validate: format lint typecheck test ## Run all checks

backup: ## Run Confluence backup (usage: make backup URL=<confluence-url> [ARGS="--format zip -v"])
	@if [ -z "$(URL)" ]; then echo "Error: URL is required. Usage: make backup URL=<confluence-url>"; exit 1; fi
	$(POETRY) run confluence-backup $(URL) $(ARGS)

restore: ## Restore from backup (usage: make restore DIR=<backup-dir> SPACE=<space-key> [ARGS="--dry-run -v"])
	@if [ -z "$(DIR)" ]; then echo "Error: DIR is required. Usage: make restore DIR=<backup-dir> SPACE=<space-key>"; exit 1; fi
	@if [ -z "$(SPACE)" ]; then echo "Error: SPACE is required. Usage: make restore DIR=<backup-dir> SPACE=<space-key>"; exit 1; fi
	$(POETRY) run confluence-restore $(DIR) --space-key $(SPACE) $(ARGS)

viewer: ## Start backup viewer (usage: make viewer DIR=<backup-dir>)
	@if [ -z "$(DIR)" ]; then echo "Error: DIR is required. Usage: make viewer DIR=<backup-dir>"; exit 1; fi
	$(POETRY) run confluence-backup-viewer $(DIR)

docker-build: ## Build Docker image
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .

docker-backup: ## Run backup in Docker (usage: make docker-backup URL=<url> [ENV_FILE=.env] [ARGS="--name my-backup --verbose"])
	@if [ -z "$(URL)" ]; then echo "Error: URL is required. Usage: make docker-backup URL=<url> [ARGS=\"...\"]"; exit 1; fi
	@mkdir -p output logs
	docker run --rm \
		--user $$(id -u):$$(id -g) \
		--env-file $(or $(ENV_FILE),.env) \
		-v "$$(pwd)/output:/app/output" \
		-v "$$(pwd)/logs:/app/logs" \
		$(IMAGE_NAME):$(IMAGE_TAG) \
		$(URL) --output-dir /app/output $(ARGS)
docker-restore: ## Run restore in Docker (usage: make docker-restore DIR=<backup-dir> SPACE=<space-key> [ENV_FILE=.env] [ARGS="--dry-run -v"])
	@if [ -z "$(DIR)" ]; then echo "Error: DIR is required. Usage: make docker-restore DIR=<backup-dir> SPACE=<space-key>"; exit 1; fi
	@if [ -z "$(SPACE)" ]; then echo "Error: SPACE is required. Usage: make docker-restore DIR=<backup-dir> SPACE=<space-key>"; exit 1; fi
	@BACKUP_ABS=$$(cd "$(DIR)" && pwd) && \
	docker run --rm \
		--user $$(id -u):$$(id -g) \
		--env-file $(or $(ENV_FILE),.env) \
		-v "$$(dirname $$BACKUP_ABS):/data" \
		-v "$$(pwd)/logs:/app/logs" \
		--entrypoint confluence-restore \
		$(IMAGE_NAME):$(IMAGE_TAG) \
		/data/$$(basename $$BACKUP_ABS) --space-key $(SPACE) $(ARGS)

docker-viewer: ## Start backup viewer in Docker (usage: make docker-viewer DIR=<backup-dir> [PORT=5000])
	@if [ -z "$(DIR)" ]; then echo "Error: DIR is required. Usage: make docker-viewer DIR=<backup-dir>"; exit 1; fi
	@echo "Serving backup: $(DIR)"
	@echo "Open http://127.0.0.1:$(or $(PORT),5000)/ in your browser"
	docker run --rm \
		-p $(or $(PORT),5000):5000 \
		-v "$$(cd "$(DIR)" && pwd):/data:ro" \
		--entrypoint confluence-backup-viewer \
		$(IMAGE_NAME):$(IMAGE_TAG) \
		/data --host 0.0.0.0

docker-validate: docker-build ## Run validation in Docker
	docker run --rm $(IMAGE_NAME):$(IMAGE_TAG) --version || true
	docker run --rm --entrypoint "" $(IMAGE_NAME):$(IMAGE_TAG) \
		sh -c "ruff check src/ && mypy src/ && pytest tests/ -m 'not integration' -v --tb=short"

docker-test-e2e: ## Run end-to-end backup/restore cycle in Docker (requires running Confluence)
	bash tests/integration/test_backup_restore_docker.sh

clean: ## Remove build artifacts
	rm -rf .venv __pycache__ .mypy_cache .pytest_cache .ruff_cache htmlcov .coverage dist build
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
