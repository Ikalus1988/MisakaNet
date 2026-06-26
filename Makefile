.PHONY: help install-core install-dev install-web install-semantic test test-python test-web lint format-check audit audit-python audit-js secret-scan validate validate-lessons validate-protocol update-lessons ci-local deploy deploy-web deploy-api deploy-email

help:
	@echo "MisakaNet local developer targets"
	@echo ""
	@echo "Setup:"
	@echo "  make install-core       Install the repo package with core dependencies only"
	@echo "  make install-dev        Install dev/test/audit tooling plus hub/feishu/harvest extras"
	@echo "  make install-web        Install web test dependencies"
	@echo "  make install-semantic   Install semantic-search extras (large ML dependency set)"
	@echo ""
	@echo "Checks:"
	@echo "  make test               Run Python and web tests"
	@echo "  make lint               Run ruff lint"
	@echo "  make audit              Run secret, Python dependency, and web dependency audits"
	@echo "  make validate           Validate lessons and protocol config"
	@echo "  make ci-local           Run the same local gate used before opening a PR"

install-core:
	python3 -m pip install -e .

install-dev:
	python3 -m pip install -e ".[hub,feishu,harvest]"
	python3 -m pip install pytest pytest-cov ruff jsonschema pip-audit

install-web:
	cd web && npm ci

install-semantic:
	python3 -m pip install -e ".[semantic]"

test: test-python test-web

test-python:
	python3 -m pytest tests/

test-web:
	cd web && if test -n "$$(find tests -type f \( -name '*.test.js' -o -name '*.spec.js' \) 2>/dev/null | head -n 1)"; then npm test; else echo "No web tests found; skipping"; fi

lint:
	python3 -m ruff check .

format-check:
	python3 -m ruff format --check .

secret-scan:
	python3 scripts/check_worker_secrets.py

audit-python:
	python3 -m pip_audit --requirement requirements.txt

audit-js:
	cd web && npm audit --audit-level=high

audit: secret-scan audit-python audit-js

validate-lessons:
	python3 scripts/validate_lessons.py

validate-protocol:
	python3 scripts/verify_protocol_config.py

validate: validate-lessons validate-protocol

update-lessons:
	python3 scripts/update_lessons_json.py

ci-local: lint test validate audit

deploy-email:
	cd workers/email-register && npx wrangler deploy

deploy-api:
	cd workers && npx wrangler deploy --config wrangler.api.jsonc

deploy-web:
	cd web && npx wrangler deploy

deploy: deploy-web deploy-api deploy-email
