# ── Makefile — tone-transfer ─────────────────────────────────────────────────
# All commands use the project-local virtualenv at .venv/
# Run `make install` once after cloning, then use the other targets as needed.

VENV       := .venv
PYTHON     := $(VENV)/bin/python
PIP        := $(VENV)/bin/pip
PYTEST     := $(VENV)/bin/pytest
RUFF       := $(VENV)/bin/ruff
PYTHONPATH := src
SAM        := sam

# Source dirs / test dirs
SRC_DIR    := src
TEST_DIR   := tests

.DEFAULT_GOAL := help

# ── help ──────────────────────────────────────────────────────────────────────
.PHONY: help
help:
	@echo ""
	@echo "  tone-transfer — available make targets"
	@echo ""
	@echo "  install          Install all Python dependencies into .venv"
	@echo "  test             Run the full pytest suite"
	@echo "  lint             Lint & format-check with ruff"
	@echo "  build            Run sam build (packages Lambda + layer)"
	@echo "  deploy-guided    First-time interactive SAM deploy (creates samconfig.toml)"
	@echo "  deploy           Subsequent SAM deploys (uses samconfig.toml)"
	@echo "  local            Start LocalStack + sam local start-api for local testing"
	@echo "  localstack-up    Spin up LocalStack only (docker-compose)"
	@echo "  localstack-down  Tear down LocalStack containers"
	@echo "  demo             Run scripts/demo.py end-to-end demo (set API, SRC, REF)"
	@echo "  clean            Remove build artifacts and caches"
	@echo ""

# ── install ───────────────────────────────────────────────────────────────────
.PHONY: install
install: $(VENV)/bin/activate

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "✅  Dependencies installed into $(VENV)"

# ── test ──────────────────────────────────────────────────────────────────────
.PHONY: test
test: install
	PYTHONPATH=$(PYTHONPATH) $(PYTEST) $(TEST_DIR) -v

# ── lint ──────────────────────────────────────────────────────────────────────
.PHONY: lint
lint: install
	$(RUFF) check $(SRC_DIR) $(TEST_DIR)
	$(RUFF) format --check $(SRC_DIR) $(TEST_DIR)
	@echo "✅  Lint passed"

# ── build ─────────────────────────────────────────────────────────────────────
.PHONY: build
build:
	$(SAM) build
	@echo "✅  SAM build complete"

# ── deploy (first time — interactive) ─────────────────────────────────────────
.PHONY: deploy-guided
deploy-guided: build
	$(SAM) deploy --guided

# ── deploy (subsequent — reads samconfig.toml) ────────────────────────────────
.PHONY: deploy
deploy: build
	$(SAM) deploy

# ── local — LocalStack + sam local start-api ──────────────────────────────────
# Requires: Docker, AWS SAM CLI, LocalStack
# The Lambda functions will talk to LocalStack at http://localhost:4566.
.PHONY: local
local: localstack-up build
	@echo "Starting sam local start-api against LocalStack …"
	AWS_DEFAULT_REGION=us-east-1 \
	AWS_ACCESS_KEY_ID=test \
	AWS_SECRET_ACCESS_KEY=test \
	BUCKET_NAME=tone-transfer-local \
	$(SAM) local start-api \
	  --env-vars env.local.json \
	  --docker-network host \
	  --port 3000

# ── localstack helpers ────────────────────────────────────────────────────────
.PHONY: localstack-up
localstack-up:
	docker compose up -d localstack
	@echo "⏳  Waiting for LocalStack to be ready …"
	@until curl -s http://localhost:4566/_localstack/health | grep -q '"s3": "available"'; do sleep 1; done
	@echo "✅  LocalStack is ready"
	@echo "Creating local S3 bucket …"
	AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
	aws --endpoint-url=http://localhost:4566 \
	  s3 mb s3://tone-transfer-local --region us-east-1 2>/dev/null || true

.PHONY: localstack-down
localstack-down:
	docker compose down

# ── demo ──────────────────────────────────────────────────────────────────────
# Usage:
#   make demo API=https://<id>.execute-api.<region>.amazonaws.com/prod \
#             SRC=path/to/source.jpg REF=path/to/reference.jpg
.PHONY: demo
demo: install
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/demo.py \
	  --api-base "$(API)" \
	  --source   "$(SRC)" \
	  --reference "$(REF)"

# ── clean ─────────────────────────────────────────────────────────────────────
.PHONY: clean
clean:
	rm -rf .aws-sam/ .pytest_cache/ __pycache__ src/**/__pycache__ \
	       $(VENV) .ruff_cache *.egg-info
	@echo "🧹  Clean complete"
