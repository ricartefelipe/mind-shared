.PHONY: test test-wallet test-malha test-web install-malha install-web seed serve-api serve-web

PYTHON ?= python3
VENV := malha/.venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

install-malha:
	$(PYTHON) -m venv $(VENV) 2>/dev/null || $(PYTHON) -m venv --without-pip $(VENV)
	if [ ! -x "$(PIP)" ]; then curl -sS https://bootstrap.pypa.io/get-pip.py | $(VENV)/bin/python; fi
	$(PIP) install -e "./malha[dev]"

install-web:
	cd web && npm install

test-wallet:
	npm test

test-malha: $(PY)
	cd malha && ../$(PY) -m pytest

test-web: web/node_modules
	cd web && npm run typecheck

test: test-wallet test-malha test-web

web/node_modules:
	cd web && npm install

$(PY):
	$(MAKE) install-malha

seed: $(PY)
	cd malha && ../$(PY) -m mind_shared.cli seed

serve-api: $(PY)
	cd malha && ../$(PY) -m mind_shared.cli serve

serve-web:
	cd web && npm run dev
