PYTHON ?= python
PYTEST_REPORT ?= build/pytest.xml

.PHONY: help install test check

help:
	@echo "Available targets:"
	@echo "  install  Install the package in editable mode with pytest"
	@echo "  test     Run the pytest suite"
	@echo "  check    Run tests and the duration-independent workflow structure check"
	@echo ""
	@echo "User workflow: copy examples/case and use 'monan-jedi-workflow campaign ...'."

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e . pytest

test:
	mkdir -p $(dir $(PYTEST_REPORT))
	$(PYTHON) -m pytest -q --tb=short --junitxml=$(PYTEST_REPORT)

check: test
	$(PYTHON) scripts/report_native_cycle_structure.py
