#!/usr/bin/env bash
set -euo pipefail

CMD=${1:-all}

case "$CMD" in
  email)
    cd workers/email-register && npx wrangler deploy
    ;;
  api)
    cd workers && npx wrangler deploy --config wrangler.api.jsonc
    ;;
  web)
    cd web && npx wrangler deploy
    ;;
  all)
    echo "🚀 Deploying all Workers..."
    cd workers/email-register && npx wrangler deploy
    cd ../../workers && npx wrangler deploy --config wrangler.api.jsonc
    cd ../web && npx wrangler deploy
    echo "✅ All deployed"
    ;;
  *)
    echo "Usage: $0 [web|api|email|all]"
    exit 1
    ;;
esac
