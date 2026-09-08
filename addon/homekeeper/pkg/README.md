# Backend HomeKeeper

API FastAPI de l'add-on : maison, lieux, fiches d'équipement, entretiens et contrat
`/api/ha/summary` consommé par l'intégration Home Assistant.

Le modèle de données de référence reste [../docs/DATA_MODEL.md](../docs/DATA_MODEL.md)
et [../docs/schema.sql](../docs/schema.sql).

## Prérequis

Python 3.13. Le Python du système est en 3.9, et Alpine ne fournit que 3.12 : l'image de
l'add-on utilise donc Debian trixie, qui fournit 3.13.

```bash
brew install python@3.13    # macOS
```

## Installation

```bash
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Lancement

```bash
HOMEKEEPER_DATA_DIR=./.data uvicorn homekeeper_api.main:app --reload --port 8000
```

`HOMEKEEPER_DATA_DIR` est indispensable en local : la valeur par défaut est `/data`, qui
n'existe que dans le conteneur de l'add-on.

L'API est alors sur <http://127.0.0.1:8000/api/health> et sa documentation sur
<http://127.0.0.1:8000/api/docs>.

## Tests et qualité

```bash
pytest
ruff check .
ruff format --check .
mypy
```

## Structure

- `config.py` : réglages lus depuis les variables `HOMEKEEPER_*`, plus `APP_NAME` et
  `API_SCHEMA_VERSION`
- `db.py` : moteur SQLAlchemy et PRAGMA SQLite. `foreign_keys = ON` y est appliqué à chaque
  connexion : sans lui, SQLite ignore silencieusement toutes les règles `ON DELETE` du schéma
- `ingress.py` : normalisation de l'en-tête `X-Ingress-Path` et injection dans la coquille HTML
- `main.py` : fabrique de l'application et service de la coquille SPA
- `routers/` : surface HTTP, sans règle métier
- `services/` : règles métier, notamment le calcul des échéances
- `models/`, `schemas/` : tables et contrats Pydantic
- `migrate.py` : commande `homekeeper-migrate`, appelée au démarrage de l'add-on

## Migrations

Les migrations vivent **dans** le paquet, sous `src/homekeeper_api/alembic/`, et non à côté :
dans le conteneur, seul le paquet installé existe.

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

`render_as_batch` est activé dans `env.py`. C'est obligatoire avec SQLite, dont les `ALTER
TABLE` sont trop limités : Alembic recrée la table et recopie les données.

La révision `0001_schema` exécute le schéma SQL packagé. Sur une install 0.1.0, elle
crée les tables métier dans `/data` sans effacer le volume.
