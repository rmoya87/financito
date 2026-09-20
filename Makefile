.PHONY: api-test web-install web-build validate dev run
api-test:
	cd apps/api && FINANCITO_ALLOW_PLAINTEXT_SQLITE=1 PYTHONPATH=. pytest
web-install:
	cd apps/web && npm install
web-build:
	cd apps/web && npm run typecheck && npm run build
validate: api-test web-build
dev:
	./scripts/dev.sh
run:
	./scripts/run-local.sh
