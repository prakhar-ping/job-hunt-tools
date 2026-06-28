.PHONY: install test lint fmt monitor web

install:        ## create venv + install (editable, with dev deps)
	python3 -m venv .venv
	./.venv/bin/pip install -e ".[dev]"

test:           ## run the offline test suite
	./.venv/bin/pytest

lint:           ## ruff lint
	./.venv/bin/ruff check .

fmt:            ## ruff autofix
	./.venv/bin/ruff check --fix .

monitor:        ## run the job monitor (dry run)
	./.venv/bin/python -m monitor --dry-run

web:            ## start the localhost dashboard
	./.venv/bin/python -m web
