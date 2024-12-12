.PHONY: clean install test lint security build publish help run-samples format dependencies

PYTHON := python3.11
PACKAGE_NAME := observicia
TEST_PATH := sdk/tests
COVERAGE_THRESHOLD := 45
OPENAI_API_KEY ?= ""

help:
	@echo "Available commands:"
	@echo "clean      - Remove build artifacts and cache files"
	@echo "install    - Install package dependencies"
	@echo "test       - Run tests with coverage"
	@echo "lint       - Run code linting"
	@echo "security   - Run security checks"
	@echo "build      - Build package distribution"
	@echo "publish    - Publish package to PyPI"
	@echo "format     - Format code using black and isort"
	@echo "run-samples- Run sample applications (chat and RAG)"
	@echo "run-chat   - Run sample chat application in test mode"
	@echo "run-chat-interactive - Run sample chat application in interactive mode"
	@echo "run-rag    - Run sample RAG application"

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

install:
	$(PYTHON) -m pip install -e .
	$(PYTHON) -m pip install -r requirements-dev.txt

dependencies: sdk/requirements.txt requirements-dev.txt
	@$(PYTHON) -m pip install -r sdk/requirements.txt
	@$(PYTHON) -m pip install -r requirements-dev.txt

test: dependencies
	$(PYTHON) -m pytest $(TEST_PATH) \
		--cov=$(PACKAGE_NAME) \
		--cov-report=html \
		--cov-report=term-missing \
		--cov-fail-under=$(COVERAGE_THRESHOLD)

lint:
	yapf --diff --recursive --style="pep8" sdk 

security:
	$(PYTHON) -m bandit -r $(PACKAGE_NAME)
	$(PYTHON) -m safety check
	$(PYTHON) -m pip-audit

build:
	$(PYTHON) setup.py sdist bdist_wheel

publish:
	$(PYTHON) -m twine check dist/*
	$(PYTHON) -m twine upload dist/*

format: lint
	$(PYTHON) -m black .
	$(PYTHON) -m isort .

check-openai-key:
	@if [ -z "$(OPENAI_API_KEY)" ]; then \
		echo "Error: OPENAI_API_KEY environment variable is not set"; \
		exit 1; \
	fi

run-chat: check-openai-key install
	@echo "Running sample chat application in test mode..."
	cd examples/simple-chat && OPENAI_API_KEY=$(OPENAI_API_KEY) $(PYTHON) app.py --test

run-chat-interactive: check-openai-key install
	@echo "Running sample chat application in interactive mode..."
	cd examples/simple-chat && OPENAI_API_KEY=$(OPENAI_API_KEY) $(PYTHON) app.py

run-rag: check-openai-key install
	@echo "Running sample RAG application..."
	cd examples/rag-app && OPENAI_API_KEY=$(OPENAI_API_KEY) $(PYTHON) app.py

run-samples: run-chat run-rag