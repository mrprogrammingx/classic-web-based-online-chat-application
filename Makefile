# Makefile for common developer tasks

VENV=.venv
PYTHON=${VENV}/bin/python
PIP=${VENV}/bin/pip
PYTEST=${VENV}/bin/pytest

.PHONY: help dev-install test test-live lint

help:
	@echo "make dev-install   # install development dependencies"
	@echo "make test          # run test suite (uses .venv)"
	@echo "make test-live     # run networked tests against running server"
	@echo "make lint          # run linters (black/isort/flake8)"

dev-install:
	${PIP} install -r requirements-dev.txt

test:
	${PYTEST} -q

test-live:
	${PYTEST} -q -k "not hermetic"

lint:
	${VENV}/bin/black .
	${VENV}/bin/isort .
	${VENV}/bin/flake8 .
