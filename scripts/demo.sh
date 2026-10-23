#!/usr/bin/env bash
# Lance la demonstration : API locale + tunnel public + lien a ouvrir.
#
#   ./scripts/demo.sh https://agent-data.vercel.app     # front deploye sur Vercel
#   ./scripts/demo.sh --local                           # front local, sans tunnel
#
# L'agent (LLM, sandbox, donnees) reste sur CE poste. Vercel n'heberge que l'interface ; le
# tunnel n'expose que l'API, protegee par un jeton genere a chaque lancement.

set -euo pipefail
cd "$(dirname "$0")/.."

FRONT="${1:-}"
[ -n "$FRONT" ] || { echo "Usage : $0 <url du front Vercel> | --local" >&2; exit 1; }

PORT=8000
LOG="$(mktemp -d)"
PIDS=()
cleanup() { for p in "${PIDS[@]:-}"; do kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM

uv run agent-data check >/dev/null 2>&1 || { echo "Systeme incomplet : lancer 'uv run agent-data check'." >&2; exit 1; }

TOKEN="${API_TOKEN:-$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')}"
export API_TOKEN="$TOKEN"
if [ "$FRONT" = "--local" ]; then
  export API_CORS_ORIGINS="http://localhost:3000"
else
  export API_CORS_ORIGINS="${FRONT%/}"
fi

uv run agent-data serve --port "$PORT" >"$LOG/api.log" 2>&1 &
PIDS+=($!)
for _ in $(seq 1 30); do curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null && break; sleep 1; done
curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null || { echo "L'API ne demarre pas :"; cat "$LOG/api.log"; exit 1; }

if [ "$FRONT" = "--local" ]; then
  echo "API : http://localhost:$PORT   jeton : $TOKEN"
  echo "Front local : cd web && npm run dev, puis ouvrir http://localhost:3000/#api=http://localhost:$PORT&token=$TOKEN"
else
  command -v cloudflared >/dev/null || { echo "cloudflared absent (voir README, section Demonstration)." >&2; exit 1; }
  cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$PORT" >"$LOG/tunnel.log" 2>&1 &
  PIDS+=($!)
  URL=""
  for _ in $(seq 1 30); do
    URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG/tunnel.log" | head -1 || true)"
    [ -n "$URL" ] && break; sleep 1
  done
  [ -n "$URL" ] || { echo "Le tunnel ne demarre pas :"; cat "$LOG/tunnel.log"; exit 1; }
  echo
  echo "Lien de demonstration (contient le jeton : ne pas le diffuser) :"
  echo "  ${FRONT%/}/#api=$URL&token=$TOKEN"
fi

echo
echo "Ctrl+C pour arreter l'API et fermer le tunnel."
wait
