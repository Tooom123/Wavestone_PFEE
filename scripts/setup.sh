#!/usr/bin/env bash
# Installation complete du projet pour un nouveau poste.
#
#   git clone <repo> && cd Wavestone_PFEE && ./scripts/setup.sh
#
# Le script est idempotent : on peut le relancer sans risque.

set -euo pipefail

cd "$(dirname "$0")/.."

BOLD=$'\033[1m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; OFF=$'\033[0m'
ok()   { echo "${GREEN}[ok]${OFF} $*"; }
warn() { echo "${YELLOW}[!]${OFF}  $*"; }
err()  { echo "${RED}[x]${OFF}  $*"; }
step() { echo; echo "${BOLD}==> $*${OFF}"; }

SKIP_MODEL=0
SKIP_DATA=0
SKIP_DOCKER=0
for arg in "$@"; do
  case "$arg" in
    --skip-model)  SKIP_MODEL=1 ;;
    --skip-data)   SKIP_DATA=1 ;;
    --skip-docker) SKIP_DOCKER=1 ;;
    -h|--help)
      cat <<'USAGE'
Usage : ./scripts/setup.sh [options]

  --skip-model    N'installe pas le modele LLM local (~9 Go)
  --skip-data     Ne telecharge pas les jeux de donnees
  --skip-docker   Ne construit pas l'image du sandbox
  -h, --help      Affiche cette aide
USAGE
      exit 0 ;;
    *) err "Option inconnue : $arg (voir --help)"; exit 1 ;;
  esac
done

WARNINGS=0

# --- 1. uv ------------------------------------------------------------------
step "Gestionnaire de paquets (uv)"
if command -v uv >/dev/null 2>&1; then
  ok "uv present ($(uv --version))"
else
  warn "uv absent : installation…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  command -v uv >/dev/null 2>&1 || { err "uv introuvable apres installation. Ouvrir un nouveau terminal puis relancer."; exit 1; }
  ok "uv installe ($(uv --version))"
fi

# --- 2. Dependances Python --------------------------------------------------
step "Dependances Python"
uv sync --all-groups
ok "environnement pret (.venv)"

# --- 3. Fichier .env --------------------------------------------------------
step "Configuration (.env)"
if [ -f .env ]; then
  ok ".env deja present (inchange)"
else
  cp .env.example .env
  ok ".env cree depuis .env.example"
fi

# --- 4. Modele LLM local ----------------------------------------------------
step "Modele de langage local"
MODEL="$(grep -E '^LLM_MODEL=' .env | cut -d= -f2- | tr -d '"' || true)"
MODEL="${MODEL:-qwen2.5-coder:14b}"
if [ "$SKIP_MODEL" = "1" ]; then
  warn "ignore (--skip-model) — modele attendu : $MODEL"
elif ! command -v ollama >/dev/null 2>&1; then
  warn "Ollama absent : installation…"
  if curl -fsSL https://ollama.com/install.sh | sh; then
    ok "Ollama installe"
  else
    err "Installation d'Ollama impossible. Voir https://ollama.com/download"
    WARNINGS=$((WARNINGS+1))
  fi
fi

if [ "$SKIP_MODEL" != "1" ] && command -v ollama >/dev/null 2>&1; then
  # Le serveur doit tourner pour que `ollama pull` aboutisse.
  if ! curl -sf -m 5 http://localhost:11434/api/version >/dev/null 2>&1; then
    warn "serveur Ollama arrete : demarrage en arriere-plan…"
    (ollama serve >/tmp/ollama-setup.log 2>&1 &) || true
    for _ in $(seq 1 15); do
      curl -sf -m 2 http://localhost:11434/api/version >/dev/null 2>&1 && break
      sleep 1
    done
  fi
  if ollama list 2>/dev/null | grep -q "^${MODEL%%:*}"; then
    ok "modele $MODEL deja present"
  else
    warn "telechargement de $MODEL (~9 Go, cela peut etre long)…"
    if ollama pull "$MODEL"; then
      ok "modele $MODEL pret"
    else
      err "echec du telechargement de $MODEL"
      WARNINGS=$((WARNINGS+1))
    fi
  fi
fi

# --- 5. Sandbox Docker ------------------------------------------------------
step "Sandbox Docker"
if [ "$SKIP_DOCKER" = "1" ]; then
  warn "ignore (--skip-docker)"
elif ! command -v docker >/dev/null 2>&1; then
  warn "Docker absent. Le code genere ne pourra pas etre execute (aucun repli sur l'hote, par conception)."
  echo "     Installation : https://docs.docker.com/get-docker/"
  echo "     Sous WSL : activer l'integration WSL dans Docker Desktop (Settings > Resources > WSL integration)."
  WARNINGS=$((WARNINGS+1))
elif ! docker info >/dev/null 2>&1; then
  warn "Docker installe mais le daemon ne repond pas. Demarrer Docker Desktop puis relancer ce script."
  WARNINGS=$((WARNINGS+1))
else
  IMAGE="$(grep -E '^SANDBOX_IMAGE=' .env | cut -d= -f2- | tr -d '"' || true)"
  IMAGE="${IMAGE:-agent-data-sandbox:latest}"
  if docker image inspect "$IMAGE" >/dev/null 2>&1; then
    ok "image $IMAGE deja construite"
  else
    warn "construction de l'image $IMAGE…"
    docker build -t "$IMAGE" -f docker/sandbox.Dockerfile docker/
    ok "image $IMAGE construite"
  fi
fi

# --- 6. Jeux de donnees -----------------------------------------------------
step "Jeux de donnees"
if [ "$SKIP_DATA" = "1" ]; then
  warn "ignore (--skip-data)"
else
  uv run python scripts/download_data.py
fi

# --- 7. Verification --------------------------------------------------------
step "Verification"
uv run ruff check . >/dev/null && ok "ruff : aucun probleme"
uv run pytest -q 2>&1 | tail -1

# --- Resume -----------------------------------------------------------------
echo
if [ "$WARNINGS" -eq 0 ]; then
  echo "${GREEN}${BOLD}Installation terminee.${OFF}"
else
  echo "${YELLOW}${BOLD}Installation terminee avec $WARNINGS avertissement(s) — voir ci-dessus.${OFF}"
fi
cat <<'NEXT'

Pour demarrer :
  uv run streamlit run src/agent_data/ui/app.py   # interface
  uv run agent-data --help                        # ligne de commande
  uv run pytest                                   # tests
NEXT
