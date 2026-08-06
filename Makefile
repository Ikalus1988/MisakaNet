.PHONY: deploy deploy-web deploy-api deploy-email

deploy-email:
	cd workers/email-register && npx wrangler deploy

deploy-api:
	cd workers && npx wrangler deploy --config wrangler.api.jsonc

deploy-web:
	cd web && npx wrangler deploy

deploy: deploy-web deploy-api deploy-email
