.PHONY: run setup install env test lint clean

PYTHON := $(shell command -v python3 2>/dev/null || command -v python 2>/dev/null)
VENV   := .venv
VENV_PYTHON := $(VENV)/bin/python

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
	$(VENV_PYTHON) -m pytest test_navigation.py -v

lint: $(VENV_PYTHON)
	$(VENV_PYTHON) -m py_compile ha-tui.py && echo "Syntax OK"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	find . -name "*.pyc" -delete
	rm -rf $(VENV)
