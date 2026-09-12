#!/usr/bin/env python3
"""Verifie que les trois descriptions des services ne divergent pas.

Un service de MaBarak est decrit a trois endroits, pour trois lecteurs :

* `actions.py` — le schema reellement valide a l'appel, et les descriptions que
  recoit un agent branche en MCP ;
* `services.yaml` — la forme des champs, pour l'interface de Home Assistant ;
* `strings.json` et `translations/` — les libelles affiches a l'utilisateur ;
* `skills/mabarak/SKILL.md` — les noms qu'apprend un agent externe.

Rien dans Home Assistant ne verifie que les trois parlent des memes champs :
hassfest compare `services.yaml` aux traductions, mais ignore `actions.py`. Un
champ ajoute au schema et oublie ailleurs serait donc invisible dans
l'interface, et un champ retire de `actions.py` continuerait d'y figurer sans
aucun effet. Ce script comble ce trou, et la CI le joue a chaque commit.

Il ne demande pas Home Assistant : `actions.py` est lu comme du texte, pour que
la verification tourne partout.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parent.parent
INTEGRATION = RACINE / "custom_components" / "mabarak"
TRADUCTIONS = ("strings.json", "translations/en.json", "translations/fr.json")
SKILL = RACINE / "skills" / "mabarak" / "SKILL.md"


def actions_declarees() -> dict[str, set[str]]:
    """Les actions de `actions.py`, lues dans l'arbre syntaxique.

    On cherche les appels `Action(...)` et, dans leur `schema`, les
    `vol.Required("x")` / `vol.Optional("x")`.
    """
    arbre = ast.parse((INTEGRATION / "actions.py").read_text(encoding="utf-8"))
    actions: dict[str, set[str]] = {}

    for noeud in ast.walk(arbre):
        if not (
            isinstance(noeud, ast.Call)
            and isinstance(noeud.func, ast.Name)
            and noeud.func.id == "Action"
        ):
            continue

        arguments = {mot.arg: mot.value for mot in noeud.keywords}
        nom_noeud = arguments.get("nom")
        if not isinstance(nom_noeud, ast.Constant):
            raise SystemExit("ECHEC: une Action a un `nom` qui n'est pas une chaine litterale.")

        champs: set[str] = set()
        schema = arguments.get("schema")
        if isinstance(schema, ast.Dict):
            for clef in schema.keys:
                if (
                    isinstance(clef, ast.Call)
                    and clef.args
                    and isinstance(clef.args[0], ast.Constant)
                ):
                    champs.add(str(clef.args[0].value))
        actions[str(nom_noeud.value)] = champs

    return actions


def services_yaml() -> dict[str, set[str]]:
    donnees = yaml.safe_load((INTEGRATION / "services.yaml").read_text(encoding="utf-8"))
    return {nom: set((corps or {}).get("fields") or {}) for nom, corps in (donnees or {}).items()}


def traduction(chemin: str) -> dict[str, set[str]]:
    donnees = json.loads((INTEGRATION / chemin).read_text(encoding="utf-8"))
    services = donnees.get("services") or {}
    return {nom: set((corps.get("fields") or {})) for nom, corps in services.items()}


def comparer(attendu: dict[str, set[str]], observe: dict[str, set[str]], source: str) -> list[str]:
    erreurs: list[str] = []
    for manquant in sorted(set(attendu) - set(observe)):
        erreurs.append(f"{source} : le service « {manquant} » manque.")
    for surnumeraire in sorted(set(observe) - set(attendu)):
        erreurs.append(f"{source} : le service « {surnumeraire} » n'existe pas dans actions.py.")
    for nom in sorted(set(attendu) & set(observe)):
        for champ in sorted(attendu[nom] - observe[nom]):
            erreurs.append(f"{source} : le champ « {nom}.{champ} » manque.")
        for champ in sorted(observe[nom] - attendu[nom]):
            erreurs.append(f"{source} : le champ « {nom}.{champ} » n'existe pas dans actions.py.")
    return erreurs


def textes_complets() -> list[str]:
    """Chaque service et chaque champ doit avoir un libelle ET une description.

    C'est ce qu'exige hassfest ; le verifier ici evite d'attendre la CI de
    Home Assistant pour decouvrir un oubli.
    """
    erreurs: list[str] = []
    for chemin in TRADUCTIONS:
        donnees = json.loads((INTEGRATION / chemin).read_text(encoding="utf-8"))
        for nom, corps in (donnees.get("services") or {}).items():
            for clef in ("name", "description"):
                if not corps.get(clef):
                    erreurs.append(f"{chemin} : « {nom} » n'a pas de {clef}.")
            for champ, texte in (corps.get("fields") or {}).items():
                for clef in ("name", "description"):
                    if not texte.get(clef):
                        erreurs.append(f"{chemin} : « {nom}.{champ} » n'a pas de {clef}.")
    return erreurs


def type_intention(nom: str) -> str:
    """Le nom de l'outil expose en MCP, construit comme dans `intents.py`."""
    return "MaBarak" + "".join(morceau.capitalize() for morceau in nom.split("_"))


def skill_a_jour(attendu: dict[str, set[str]]) -> list[str]:
    """La skill de l'agent doit nommer chaque action, sous ses deux formes.

    Elle n'est pas embarquee dans le produit, mais elle enseigne a un agent des
    noms d'outils et de champs : une action ajoutee sans elle resterait
    inconnue de l'agent, et une action supprimee le ferait appeler dans le vide.
    La verification reste volontairement grossiere — la presence du nom, rien de
    plus — parce qu'une skill est de la prose, et qu'imposer sa forme la rendrait
    illisible.
    """
    if not SKILL.is_file():
        return [f"{SKILL.relative_to(RACINE)} : fichier absent."]

    texte = SKILL.read_text(encoding="utf-8")
    erreurs: list[str] = []
    for nom in sorted(attendu):
        for forme in (type_intention(nom), f"mabarak.{nom}"):
            if forme not in texte:
                erreurs.append(f"skills/mabarak/SKILL.md : « {forme} » n'y figure pas.")
    return erreurs


def main() -> int:
    attendu = actions_declarees()
    if not attendu:
        print("ECHEC: aucune Action trouvee dans actions.py.")
        return 1

    erreurs = comparer(attendu, services_yaml(), "services.yaml")
    for chemin in TRADUCTIONS:
        erreurs += comparer(attendu, traduction(chemin), chemin)
    erreurs += textes_complets()
    erreurs += skill_a_jour(attendu)

    if erreurs:
        print("Les descriptions des services ont diverge :\n")
        for erreur in erreurs:
            print(f"  - {erreur}")
        return 1

    champs = sum(len(valeur) for valeur in attendu.values())
    print(
        f"OK: {len(attendu)} services et {champs} champs, decrits partout de la meme facon, "
        "et tous nommes dans la skill de l'agent."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
