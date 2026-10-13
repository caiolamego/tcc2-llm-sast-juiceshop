PYTHON ?= python3
SEMGREP ?= semgrep

.PHONY: test-unit test-rules
test-unit:
	$(PYTHON) -m unittest discover -s tests/unit -p 'test_*.py'

test-rules:
	$(SEMGREP) scan --test rules
