.PHONY: setup test lint

PYTHON ?= python

setup:
	$(PYTHON) -m pip install -r requirements.txt -e .

test:
	$(PYTHON) -m pytest -q

lint:
	ruff check .
	ruff format --check .
