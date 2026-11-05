.PHONY: sandbox-image up down test eval-init eval-run eval-compare eval-list

# Build the ephemeral sandbox image used by packages/sandbox/manager.py
sandbox-image:
	docker build -t agent-sandbox:latest infra/sandbox-image

up:
	docker compose up -d --build

down:
	docker compose down

# Run the sandbox unit tests (mocked - no docker needed)
test:
	.venv/bin/python -m pytest

# Evaluation commands
eval-init:
	.venv/bin/python scripts/eval.py init

eval-run:
	.venv/bin/python scripts/eval.py run --markdown

eval-compare:
	@echo "Usage: make eval-compare RUN1=<run1_id> RUN2=<run2_id>"
	.venv/bin/python scripts/eval.py compare --run1 $(RUN1) --run2 $(RUN2) --markdown

eval-list:
	.venv/bin/python scripts/eval.py list
