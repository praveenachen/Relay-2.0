PYTHON ?= python

.PHONY: setup dev test lint build migrate db-up db-down
setup dev test lint build migrate db-up db-down:
	$(PYTHON) scripts/dev.py $@
