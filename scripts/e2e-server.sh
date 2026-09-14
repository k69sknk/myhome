#!/usr/bin/env bash
# Lance la pile complete pour les tests de bout en bout : le backend sert le
# build du frontend, comme le fait l'add-on.
#
# Playwright appelle ce script (voir frontend/playwright.config.ts) et attend
# que /api/health reponde. Le meme chemin est emprunte en local et en CI, pour
# qu'un test qui passe d'un cote passe de l'autre.
set -euo pipefail

RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${MABARAK_E2E_PORT:-8188}"
DONNEES="$RACINE/frontend/.e2e-data"

# Le venv du depot quand il existe (mode developpeur), sinon le python courant :
# en CI, le backend est installe dans l'environnement du job.
PYTHON="$RACINE/backend/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"

echo "==> Build du frontend"
cd "$RACINE/frontend"
npm run build

# Base vide a chaque campagne : un test qui compte des lignes ne doit pas
# dependre de ce qu'a laisse la campagne precedente.
echo "==> Base de donnees neuve dans $DONNEES"
rm -rf "$DONNEES"
mkdir -p "$DONNEES"

echo "==> Backend sur le port $PORT, servant frontend/dist"
cd "$RACINE/backend"
exec env \
  MABARAK_DATA_DIR="$DONNEES" \
  MABARAK_FRONTEND_DIR="$RACINE/frontend/dist" \
  "$PYTHON" -m uvicorn mabarak_api.main:app --host 127.0.0.1 --port "$PORT"
