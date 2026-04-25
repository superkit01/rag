PYTHON ?= .venv/bin/python
PYTEST ?= .venv/bin/pytest
PNPM ?= pnpm

.PHONY: backend-dev worker-dev web-dev test-backend compose-up compose-down

backend-dev:
	cd backend && $(PYTHON) -m uvicorn app.main:app --reload --port 8000

worker-dev:
	cd backend && $(PYTHON) -m app.workflows.worker

web-dev:
	cd web && $(PNPM) run dev

test-backend:
	cd backend && PYTHONPATH=. $(PYTEST) -q

compose-up:
	docker compose up --build

compose-down:
	docker compose down -v
