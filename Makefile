PYTHON ?= python

.PHONY: setup dev dev-fast test lint build migrate db-up db-down
setup dev dev-fast test lint build migrate db-up db-down:
	$(PYTHON) scripts/dev.py $@

