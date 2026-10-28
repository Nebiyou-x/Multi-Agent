.PHONY: sandbox-image up down test

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
