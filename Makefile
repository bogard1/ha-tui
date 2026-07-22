.PHONY: run setup install env test lint clean docker-build docker-run

PYTHON := $(shell command -v python3 2>/dev/null || command -v python 2>/dev/null)
VENV   := .venv
VENV_PYTHON := $(VENV)/bin/python
IMAGE  := ha-tui

run: $(VENV_PYTHON)
	$(VENV_PYTHON) ha-tui.py

setup: install env

$(VENV_PYTHON):
	$(PYTHON) -m venv $(VENV)

install: $(VENV_PYTHON)
	$(VENV_PYTHON) -m pip install -r requirements.txt

env:
	@if [ ! -f .env ]; then cp .env.example .env && echo ".env created — edit it and set HA_TOKEN"; else echo ".env already exists"; fi

test: $(VENV_PYTHON)
	$(VENV_PYTHON) -m pytest tests/ -v --cov=. --cov-report=term-missing --cov-config=.coveragerc

lint: $(VENV_PYTHON)
	$(VENV_PYTHON) -m py_compile ha-tui.py ha_client.py widgets.py && echo "Syntax OK"

docker-build:
	docker build -t $(IMAGE) .

docker-run:
	docker run -it --rm \
		-v $(PWD)/dashboard.yml:/app/dashboard.yml \
		-v $(PWD)/.env:/app/.env \
		$(IMAGE)

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	find . -name "*.pyc" -delete
	rm -rf $(VENV)
