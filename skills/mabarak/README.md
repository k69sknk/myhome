# Skill MaBarak, pour un agent externe

[`SKILL.md`](SKILL.md) apprend à un agent conversationnel — Claude, ou tout assistant qui lit ce
format — à se servir des six actions que MaBarak expose dans Home Assistant.

Elle ne sert qu'à **l'agent**, pas à l'application : rien ici n'est embarqué dans l'add-on ni
dans l'intégration. Elle vit néanmoins dans ce dépôt pour une raison précise — elle nomme les
actions et leurs paramètres, et doit donc suivre le code qui les définit
(`custom_components/mabarak/actions.py`). `scripts/check-integration.py` échoue en CI si une
action cesse d'y figurer.

## L'installer

Déposez le dossier `mabarak/` dans le répertoire de skills de votre agent :

- **Claude Code** — `~/.claude/skills/` (personnel) ou `.claude/skills/` (dans un projet) ;
- **Hermes** — `~/.hermes/skills/`.

Le format est le même de part et d'autre : un `SKILL.md` avec un frontmatter YAML portant `name`
et `description`, suivant le standard [agentskills.io](https://agentskills.io).

## Ce qu'elle apporte

Les descriptions des outils, que Home Assistant transmet déjà, suffisent à un agent pour les
appeler. La skill couvre ce qu'elles ne peuvent pas dire :

- **commencer par l'aperçu**, qui donne le vocabulaire de la maison — sans quoi l'agent invente
  des noms de pièces ;
- **ne pas trancher une ambiguïté à la place de l'utilisateur** quand l'outil rend une liste de
  candidats ;
- la distinction entre **valider** un entretien planifié, qui replanifie l'échéance, et
  **consigner** une réparation, qui ne replanifie rien ;
- **quels champs sont obligatoires** — Home Assistant ne transmet pas cette information dans le
  schéma des outils MCP ([ADR-0013](../../docs/adr/0013-pilotage-par-agent-externe.md)) ;
- convertir les dates relatives, plutôt que de laisser « hier » devenir aujourd'hui.
