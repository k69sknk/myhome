#!/usr/bin/env python3
"""Verifie que tous les artefacts annoncent la meme version.

L'add-on et l'integration se mettent a jour separement chez l'utilisateur, mais
partagent un numero unique : c'est la contrainte posee par
[ADR-0005](../docs/adr/0005-monodepot-addon-et-hacs.md). Cinq fichiers le
portent, et rien ne les comparait entre eux — de sorte que
`backend/src/mabarak_api/__init__.py` est reste bloque a 0.11.0 pendant dix-huit
versions, le backend annoncant ce numero dans son journal, sa documentation
OpenAPI et sa reponse de sante.

Ce script existe pour que cela ne recommence pas. Il ne demande aucune
dependance : les cinq fichiers sont lus par expression reguliere, pour qu'il
tourne avant toute installation.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# fichier -> motif capturant la version dans son groupe 1
FICHIERS: dict[str, str] = {
    "addon/mabarak/config.yaml": r'^version:\s*"([^"]+)"',
    "backend/pyproject.toml": r'^version\s*=\s*"([^"]+)"',
    "backend/src/mabarak_api/__init__.py": r'^__version__\s*=\s*"([^"]+)"',
    "custom_components/mabarak/manifest.json": r'"version"\s*:\s*"([^"]+)"',
    "frontend/package.json": r'"version"\s*:\s*"([^"]+)"',
}


def lire(chemin: str, motif: str) -> str | None:
    texte = (RACINE / chemin).read_text(encoding="utf-8")
    trouve = re.search(motif, texte, re.MULTILINE)
    return trouve.group(1) if trouve else None


def main() -> int:
    versions: dict[str, str] = {}
    erreurs: list[str] = []

    for chemin, motif in FICHIERS.items():
        version = lire(chemin, motif)
        if version is None:
            erreurs.append(f"{chemin} : aucune version trouvee.")
        else:
            versions[chemin] = version

    distinctes = set(versions.values())
    if len(distinctes) > 1:
        erreurs.append("Les artefacts n'annoncent pas la meme version :")
        # La majoritaire d'abord : c'est presque toujours la bonne, et celle
        # qui reste seule en bas est celle qu'on a oublie de mettre a jour.
        for chemin, version in sorted(versions.items(), key=lambda item: item[1], reverse=True):
            erreurs.append(f"    {version:12} {chemin}")

    if erreurs:
        for erreur in erreurs:
            print(erreur if erreur.startswith("    ") else f"  - {erreur}")
        print("\nADR-0005 impose un numero unique : mettez les cinq a jour ensemble.")
        return 1

    print(f"OK: les {len(versions)} artefacts annoncent tous la version {distinctes.pop()}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
