.PHONY: install dev backend frontend db-reset db-seed test lint build

VENV    := .venv
PYTHON  := $(VENV)/bin/python3
PIP     := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn
BACKEND_DIR := backend
FRONTEND_DIR := frontend

$(VENV)/bin/activate:
	python3 -m venv $(VENV)

install: $(VENV)/bin/activate
	$(PIP) install -r $(BACKEND_DIR)/requirements.txt
	cd $(FRONTEND_DIR) && npm install

dev: $(VENV)/bin/activate
	cd $(FRONTEND_DIR) && npx concurrently \
		--names "backend,frontend" \
		--prefix-colors "cyan,magenta" \
		"cd .. && PYTHONPATH=. $(UVICORN) backend.main:app --reload --host 0.0.0.0 --port 8001" \
		"npm run dev" & \
	sleep 3 && open http://localhost:5173 2>/dev/null || true; \
	wait

backend: $(VENV)/bin/activate
	PYTHONPATH=. $(UVICORN) backend.main:app --reload --host 0.0.0.0 --port 8001

frontend:
	cd $(FRONTEND_DIR) && npm run dev

db-reset: $(VENV)/bin/activate
	PYTHONPATH=. $(PYTHON) -c "from backend.database import reset_db; reset_db()"
	@echo "Database reset complete."

db-seed: $(VENV)/bin/activate
	PYTHONPATH=. $(PYTHON) -c "from backend.database import seed_db; seed_db()"
	@echo "Database seeded."

test: $(VENV)/bin/activate
	PYTHONPATH=. $(VENV)/bin/pytest $(BACKEND_DIR)/tests/ -v

lint: $(VENV)/bin/activate
	$(VENV)/bin/ruff check $(BACKEND_DIR)/
	cd $(FRONTEND_DIR) && npx eslint src/

build:
	cd $(FRONTEND_DIR) && npm run build
