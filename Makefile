PYTHON ?= python3

.PHONY: dev lint test

dev:
	$(PYTHON) -m uvicorn server.main:app --reload --host 0.0.0.0 --port 8000

lint:
	$(PYTHON) -m compileall server crawler config db

test:
	$(PYTHON) -m unittest discover -s tests -p "test_*.py"
