#!/usr/bin/env bash
# Applique les réglages GitHub du workflow (voir docs/ci-cd.md). À lancer une fois, par le
# propriétaire du dépôt, après `gh auth login && gh auth refresh -s workflow`.
#
#   ./scripts/github-setup.sh --dry-run      # affiche sans rien appliquer
#   ./scripts/github-setup.sh                # applique
#   REPO=org/depot ./scripts/github-setup.sh # autre dépôt que celui du remote origin
#
# Idempotent : on peut le relancer sans risque.

set -euo pipefail
cd "$(dirname "$0")/.."

DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1

REPO="${REPO:-$(git remote get-url origin | sed -E 's#^(git@github.com:|https://github.com/)##; s#\.git$##')}"
CHECK="CI OK"   # nom du job agrégateur de ci.yml

run() {
  if [ "$DRY" = "1" ]; then printf '[dry-run] %s\n' "$*"; else "$@" >/dev/null; fi
}
api() { run gh api "$@"; }

echo "Dépôt : $REPO $([ "$DRY" = 1 ] && echo '(simulation)')"

if [ "$DRY" = "0" ]; then
  gh api "repos/$REPO" --jq '.permissions.admin' | grep -q true \
    || { echo "Droits d'administration requis sur $REPO (voir docs/ci-cd.md)." >&2; exit 1; }
fi

echo "==> Réglages du dépôt"
api -X PATCH "repos/$REPO" \
  -F allow_squash_merge=true -F allow_merge_commit=true -F allow_rebase_merge=false \
  -F allow_auto_merge=true -F delete_branch_on_merge=true \
  -f squash_merge_commit_title=PR_TITLE -f squash_merge_commit_message=BLANK 

echo "==> Les Actions peuvent ouvrir des PR (auto-pr.yml)"
api -X PUT "repos/$REPO/actions/permissions/workflow" \
  -f default_workflow_permissions=read -F can_approve_pull_request_reviews=true

echo "==> Alertes de sécurité et correctifs automatiques"
api -X PUT "repos/$REPO/vulnerability-alerts"
api -X PUT "repos/$REPO/automated-security-fixes"

protect() {  # protect <branche> <relectures> <historique linéaire>
  local branch="$1" reviews="$2" linear="$3"
  echo "==> Protection de $branch (relectures : $reviews, historique linéaire : $linear)"
  local body
  body=$(cat <<JSON
{
  "required_status_checks": { "strict": true, "contexts": ["$CHECK"] },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": $reviews,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false
  },
  "restrictions": null,
  "required_linear_history": $linear,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON
)
  if [ "$DRY" = "1" ]; then
    printf '[dry-run] gh api -X PUT repos/%s/branches/%s/protection --input - <<< %s\n' \
      "$REPO" "$branch" "$(echo "$body" | tr -d '\n' | tr -s ' ')"
  else
    echo "$body" | gh api -X PUT "repos/$REPO/branches/$branch/protection" --input - >/dev/null
  fi
}

# main : aucune relecture pendant la simulation en solo (à remonter à 1 pour Wavestone) ;
# develop : la CI suffit. Les administrateurs ne sont pas
# bloqués (enforce_admins=false) pour ne pas verrouiller une petite équipe.
protect main 0 false  # simulation en solo : repasser à 1 pour la livraison à Wavestone
protect develop 0 true

echo "==> Étiquettes"
label() { gh api -X POST "repos/$REPO/labels" -f name="$1" -f color="$2" -f description="$3" >/dev/null 2>&1 || true; }
if [ "$DRY" = "1" ]; then echo "[dry-run] création des étiquettes : dependencies, python, web, ci, docker"; else
  label dependencies 0366d6 "Mise à jour de dépendances"
  label python 3572A5 "Code Python"
  label web 7cc4a8 "Front Next.js"
  label ci 8a63d2 "Pipeline CI/CD"
  label docker 0db7ed "Image du sandbox"
fi

cat <<'NEXT'

Reste à faire à la main (Settings > Secrets and variables > Actions) pour les mails :
  variable MAIL_NOTIFICATIONS=true ; secrets MAIL_SERVER, MAIL_PORT, MAIL_USERNAME,
  MAIL_PASSWORD, MAIL_TO (voir docs/ci-cd.md).
NEXT
