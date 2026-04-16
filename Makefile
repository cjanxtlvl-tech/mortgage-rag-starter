PYTHON := .venv/bin/python
PIP := .venv/bin/pip
UVICORN := .venv/bin/uvicorn

.PHONY: help venv install check-env ingest run run-prod test freeze clean

help:
	@echo "Available commands:"
	@echo "  make help        - Show this help message"
	@echo "  make venv        - Create virtual environment"
	@echo "  make install     - Install dependencies"
	@echo "  make check-env   - Check environment variables"
	@echo "  make ingest      - Process data and build index"
	@echo "  make run         - Run the app in development mode"
	@echo "  make run-prod    - Run the app in production mode"
	@echo "  make test        - Run tests"
	@echo "  make freeze      - Freeze current dependencies"
	@echo "  make clean       - Clean up temporary files"

venv:
	@if [ ! -d ".venv" ]; then \
		echo "[setup] Creating virtual environment"; \
		python3 -m venv .venv; \
		$(PIP) install --upgrade pip; \
	fi

install: venv
	@echo "[setup] Installing dependencies"
	$(PIP) install -r requirements.txt

check-env:
	@$(PYTHON) -c "from app.config import get_settings; \
		settings = get_settings(); \
		print(f'OPENAI_API_KEY loaded: {bool(settings.openai_api_key.get_secret_value())}'); \
		print(f'rasa_webhook_url: {settings.rasa_webhook_url}'); \
		print(f'project_root: {settings.project_root}')"

ingest:
	@echo "[run] Processing data"
	$(PYTHON) scripts/process_data.py

run:
	@echo "[run] Starting app in development mode"
	$(UVICORN) app.main:app --host 127.0.0.1 --port 8000 --reload

run-prod:
	@echo "[run] Starting app in production mode"
	$(UVICORN) app.main:app --host 0.0.0.0 --port 8000

test:
	@if [ -d "tests" ]; then \
		echo "[test] Running tests"; \
		$(PYTHON) -m unittest discover -s tests; \
	else \
		echo "[test] No tests directory found"; \
	fi

freeze:
	@echo "[freeze] Freezing dependencies"
	$(PIP) freeze > requirements.txt

clean:
	@echo "[clean] Removing temporary files"
	find . -type d -name "__pycache__" -exec rm -r {} +;
	find . -type f -name "*.pyc" -delete
