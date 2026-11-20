PYTHON ?= python3

.PHONY: run test

run:
	PYTHONPATH=src $(PYTHON) -m depviz $(ARGS)

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v
