# Makefile — developer entry points. Every path referenced below must exist in this repository.
#
# Where these three things actually deploy (deployment table in `docs/agents/repo-operations.md`):
#   * main worker `misakanet-register-proxy` (serves `/mcp` and `/api`)
#       → push to main → `.github/workflows/deploy-worker.yml`
#         (`npx wrangler deploy --config wrangler.toml`, run from `workers/`)
#   * site `misakanet-web` (assets = `docs/`)
#       → Cloudflare **Workers Builds** (Git integration) fires on every push to main. There is no
#         `web/` directory; the site config is the **root** `wrangler.jsonc`, kept for local preview
#         and emergency use only (`npm run deploy`).
#   * `email-register` worker
#       → `make deploy-email` (= `npm run deploy:email`), the only path this file still owns: no CI
#         workflow deploys it.
#
# ⚠️  `make deploy-*` is a LOCAL → PRODUCTION path (audit Theme 3): `wrangler deploy` runs straight
#     from a developer's checkout with no PR, no review and no CI gate in between. Merged changes
#     never need it — the two routes above already deploy them. No approval mechanism belongs here;
#     the aggregate `deploy` target merely warns before it starts. The same dead paths were fixed on
#     the npm side in #2150 (`deploy:web` deleted, `deploy:api` repointed at `wrangler.toml`); this
#     Makefile was the copy that was missed — see `docs/reviews/2026-08-30-dual-axis-review.md` (A10).

.PHONY: deploy deploy-api deploy-email warn-local-to-production doctor check-versions

doctor:
	python3 scripts/doctor.py

deploy-email:
	cd workers/email-register && npx wrangler deploy

deploy-api:
	cd workers && npx wrangler deploy --config wrangler.toml

# Runs before `deploy`'s real work because prerequisites are executed in order.
warn-local-to-production:
	@echo "WARNING: 'make deploy' pushes straight to production from this checkout — no PR, no review, no CI gate (audit Theme 3)."
	@echo "         Merged changes do not need it: main worker -> .github/workflows/deploy-worker.yml, site -> Cloudflare Workers Builds."

deploy: warn-local-to-production deploy-api deploy-email

check-versions:
	python3 scripts/align_versions.py --check
