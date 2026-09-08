#!/usr/bin/env bash
# =============================================================================
# Prepare les artefacts necessaires au build de l'image de l'add-on.
#
# Le builder Home Assistant utilise le repertoire de l'add-on comme contexte de
# build : le Dockerfile ne peut donc pas atteindre ../../backend ni
# ../../frontend. Ce script copie ce qu'il faut dans :
#     addon/homekeeper/pkg/   <- source du paquet Python
#     addon/homekeeper/www/   <- build Vite du frontend
#
# Ces deux repertoires SONT versionnes : le Supervisor construit l'image a
# partir du seul dossier de l'add-on, sans executer ce script. Sans eux,
# l'installation depuis GitHub echoue sur un COPY introuvable.
#
# Usage : ./scripts/stage-addon.sh
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ADDON_DIR="${REPO_ROOT}/addon/homekeeper"
PKG_DIR="${ADDON_DIR}/pkg"
WWW_DIR="${ADDON_DIR}/www"

echo "==> Nettoyage des artefacts stages"
rm -rf "${PKG_DIR}" "${WWW_DIR}"
mkdir -p "${PKG_DIR}" "${WWW_DIR}"

# --- Frontend -----------------------------------------------------------------
echo "==> Build du frontend"
cd "${REPO_ROOT}/frontend"
if [[ -f package-lock.json ]]; then
    npm ci
else
    npm install
fi
npm run build
cp -R dist/. "${WWW_DIR}/"

# --- Backend ------------------------------------------------------------------
# Seules les sources du paquet sont copiees : le Dockerfile fait `pip install`
# du repertoire. Les artefacts locaux (venv, caches, base de donnees) ne doivent
# pas entrer dans l'image.
echo "==> Copie des sources du backend"
cd "${REPO_ROOT}/backend"
cp pyproject.toml README.md "${PKG_DIR}/"
cp -R src "${PKG_DIR}/src"

# Boucle plutot que `-exec ... +` ou `xargs` : les deux dependent de la limite
# d'arguments du systeme, indisponible dans certains environnements confines.
find "${PKG_DIR}" \
    \( -name '__pycache__' -o -name '*.pyc' -o -name '*.egg-info' \) \
    -prune -print0 | while IFS= read -r -d '' path; do
    rm -rf "${path}"
done

echo
echo "==> Artefacts prets :"
echo "    ${WWW_DIR#"${REPO_ROOT}/"}  (build du frontend)"
echo "    ${PKG_DIR#"${REPO_ROOT}/"}  (sources du paquet Python)"
