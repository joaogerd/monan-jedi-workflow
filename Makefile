PYTHON ?= python
CONFIG_DIR ?= configs/experiments/3dfgat_mpastatic_x1.10242_2018041500

.PHONY: help install test validate render-yaml render-pbs

help:
	@echo "Available targets:"
	@echo "  install      Install the package in editable mode with pytest"
	@echo "  test         Run the pytest suite"
	@echo "  validate     Validate the baseline experiment configuration"
	@echo "  render-yaml  Render the MPAS-JEDI YAML file"
	@echo "  render-pbs   Render the PBS script"
	@echo ""
	@echo "Override CONFIG_DIR to use another experiment directory."
	@echo "Example: make validate CONFIG_DIR=configs/experiments/my_experiment"

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e . pytest

test:
	$(PYTHON) -m pytest -q --tb=short

validate:
	$(PYTHON) -m monan_jedi_workflow.cli validate-config $(CONFIG_DIR)

render-yaml:
	$(PYTHON) -m monan_jedi_workflow.cli render-yaml $(CONFIG_DIR)

render-pbs:
	$(PYTHON) -m monan_jedi_workflow.cli render-pbs $(CONFIG_DIR)
