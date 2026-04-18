.PHONY: install dev backend frontend db-reset db-seed test lint build

PYTHON := python3
PIP := pip3
UVICORN := uvicorn
BACKEND_DIR := backend
FRONTEND_DIR := frontend

install:
	$(PIP) install -r $(BACKEND_DIR)/requirements.txt
	cd $(FRONTEND_DIR) && npm install

dev:
	cd $(FRONTEND_DIR) && npx concurrently \
		--names "backend,frontend" \
		--prefix-colors "cyan,magenta" \
		"cd .. && PYTHONPATH=. $(UVICORN) backend.main:app --reload --host 0.0.0.0 --port 8000" \
		"npm run dev"

backend:
	PYTHONPATH=. $(UVICORN) backend.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd $(FRONTEND_DIR) && npm run dev

db-reset:
	PYTHONPATH=. $(PYTHON) -c "from backend.database import reset_db; reset_db()"
	@echo "Database reset complete."

db-seed:
	PYTHONPATH=. $(PYTHON) -c "from backend.database import seed_db; seed_db()"
	@echo "Database seeded."

test:
	PYTHONPATH=. pytest $(BACKEND_DIR)/tests/ -v

lint:
	ruff check $(BACKEND_DIR)/
	cd $(FRONTEND_DIR) && npx eslint src/

build:
	cd $(FRONTEND_DIR) && npm run build
