"""Resolution du chemin de base de l'ingress Home Assistant.

Home Assistant expose l'add-on derriere une URL de la forme
`/api/hassio_ingress/<token>/`, dont le token change a chaque instance et a chaque
redemarrage. L'application ne peut donc pas connaitre son chemin de base a la
compilation : Home Assistant le transmet a chaque requete dans l'en-tete
`X-Ingress-Path`.

Le backend injecte cette valeur dans la coquille HTML, ou le frontend la lit au
demarrage. Voir docs/ARCHITECTURE.md section 4.
"""

import re

INGRESS_HEADER = "X-Ingress-Path"

# Marqueur present dans frontend/index.html, remplace a la volee a chaque requete.
BASE_PLACEHOLDER = "__HOMEKEEPER_BASE__"

# La valeur injectee finit dans un attribut HTML. L'en-tete est normalement
# emise par Home Assistant, mais si quelqu'un ouvre le port direct de l'add-on
# elle devient controlable par le client : on n'accepte donc qu'un chemin d'URL
# strict, et on retombe sur la racine pour tout le reste.
_SAFE_PATH = re.compile(r"^/[A-Za-z0-9._~/-]*$")


def resolve_base_path(header_value: str | None) -> str:
    """Normalise l'en-tete d'ingress en un chemin de base sur et terminé par `/`.

    Retourne `/` quand l'en-tete est absente (developpement local) ou refusee.
    """
    if not header_value:
        return "/"

    candidate = header_value.strip()
    if not candidate:
        return "/"

    if not candidate.startswith("/"):
        candidate = f"/{candidate}"
    if not candidate.endswith("/"):
        candidate = f"{candidate}/"

    if not _SAFE_PATH.match(candidate) or ".." in candidate:
        return "/"

    return candidate


def render_index(html: str, base_path: str) -> str:
    """Injecte le chemin de base dans la coquille HTML."""
    return html.replace(BASE_PLACEHOLDER, base_path)
