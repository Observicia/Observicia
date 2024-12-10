.PHONY: clean install test lint security build publish help

PYTHON := python3.11
PACKAGE_NAME := observicia
TEST_PATH := sdk/tests
COVERAGE_THRESHOLD := 35

help:
	@echo "Available commands:"
	@echo "clean      - Remove build artifacts and cache files"
	@echo "install    - Install package dependencies"
	@echo "test       - Run tests with coverage"
	@echo "lint       - Run code linting"
	@echo "security   - Run security checks"
	@echo "build      - Build package distribution"
	@echo "publish    - Publish package to PyPI"

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

test:
	$(PYTHON) -m pytest $(TEST_PATH) \
		--cov=$(PACKAGE_NAME) \
		--cov-report=html \
		--cov-report=term-missing \
		--cov-fail-under=$(COVERAGE_THRESHOLD)

lint:
	$(PYTHON) -m black .
	$(PYTHON) -m isort .
	$(PYTHON) -m flake8 .
	$(PYTHON) -m mypy .

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