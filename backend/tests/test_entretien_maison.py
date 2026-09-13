"""Un entretien qui ne vise aucun equipement se valide comme les autres.

« Tester les detecteurs de fumee », « purger les radiateurs », le ramonage quand
aucun appareil ne le porte : `maintenance_task` acceptait ces entretiens depuis
l'origine, le planning les affichait, et `intervention.asset_id NOT NULL` les
empechait d'etre marques comme faits. La migration 0015 leve la contrainte ; ces
tests verifient qu'elle le fait sans rien casser de ce qui existait.
"""

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from fastapi.testclient import TestClient

from mabarak_api.config import Settings
from mabarak_api.migrate import alembic_config


def _entretien_de_la_maison(client: TestClient, name: str = "Detecteurs de fumee") -> int:
    response = client.post(
        "/api/catalog/maintenances",
        json={
            "selections": [
                {
                    "asset_id": None,
                    "task": {"name": name, "recurrence_type": "years", "recurrence_interval": 1},
                }
            ]
        },
    )
    assert response.status_code == 201
    return int(next(t for t in client.get("/api/tasks").json() if t["name"] == name)["id"])


def test_marquer_fait_replanifie_comme_pour_un_equipement(client: TestClient) -> None:
    task_id = _entretien_de_la_maison(client)

    done = client.post(f"/api/tasks/{task_id}/complete", json={"performed_on": "2026-03-15"})
    assert done.status_code == 200
    body = done.json()
    assert body["last_completed_on"] == "2026-03-15"
    assert body["next_due_on"] == "2027-03-15"
    assert body["asset_id"] is None


def test_l_intervention_rejoint_l_historique_sous_le_nom_de_la_maison(
    client: TestClient,
) -> None:
    """Une jointure interne sur `asset` la faisait disparaitre de l'historique."""
    task_id = _entretien_de_la_maison(client)
    client.post(f"/api/tasks/{task_id}/complete", json={"performed_on": "2026-03-15"})

    historique = client.get("/api/interventions").json()
    assert len(historique) == 1
    assert historique[0]["asset_id"] is None
    assert historique[0]["asset_name"] == client.get("/api/homes/current").json()["name"]
    assert historique[0]["task_name"] == "Detecteurs de fumee"


def test_l_historique_de_l_entretien_lui_meme(client: TestClient) -> None:
    task_id = _entretien_de_la_maison(client)
    client.post(f"/api/tasks/{task_id}/complete", json={"performed_on": "2026-03-15"})

    interventions = client.get(f"/api/tasks/{task_id}/interventions").json()
    assert [row["performed_on"] for row in interventions] == ["2026-03-15"]


def test_le_cout_saisi_se_rattache_a_la_maison(client: TestClient) -> None:
    task_id = _entretien_de_la_maison(client)

    client.post(
        f"/api/tasks/{task_id}/complete",
        json={"performed_on": "2026-03-15", "amount_cents": 3500},
    )

    historique = client.get("/api/interventions").json()
    assert historique[0]["cost"]["amount_cents"] == 3500


def test_une_facture_peut_y_etre_jointe(client: TestClient, settings: Settings) -> None:
    """Sans equipement, le fichier va dans le repertoire commun plutot que sous
    un identifiant de fiche qui n'existe pas."""
    task_id = _entretien_de_la_maison(client)
    done = client.post(f"/api/tasks/{task_id}/complete", json={"performed_on": "2026-03-15"})
    intervention_id = client.get(f"/api/tasks/{task_id}/interventions").json()[0]["id"]
    assert done.status_code == 200

    created = client.post(
        f"/api/interventions/{intervention_id}/documents",
        data={"storage_mode": "local_file", "doc_type": "invoice", "name": "Facture ramonage"},
        files={"file": ("f.pdf", b"%PDF-1.4 x", "application/pdf")},
    )
    assert created.status_code == 201
    assert len(list((settings.documents_dir / "divers").glob("*.pdf"))) == 1


def test_supprimer_l_intervention_de_la_maison(client: TestClient) -> None:
    task_id = _entretien_de_la_maison(client)
    client.post(f"/api/tasks/{task_id}/complete", json={"performed_on": "2026-03-15"})
    intervention_id = client.get("/api/interventions").json()[0]["id"]

    assert client.delete(f"/api/interventions/{intervention_id}").status_code == 200
    assert client.get("/api/interventions").json() == []


def test_un_agent_peut_aussi_le_valider(client: TestClient) -> None:
    task_id = _entretien_de_la_maison(client)
    assert task_id

    response = client.post(
        "/api/agent/entretiens/valider",
        json={"entretien": "Detecteurs de fumee", "date": "2026-03-15"},
    )
    assert response.status_code == 200
    message = response.json()["message"]
    # « sur la PAC » n'aurait aucun sens ici : l'agent relit cette phrase telle quelle.
    assert "pour la maison" in message
    assert "sur «" not in message


def test_le_check_refuse_les_deux_rattachements_a_la_fois(client: TestClient) -> None:
    """Le garde-fou est dans la base, pas seulement dans le code qui ecrit."""
    from mabarak_api.models import Intervention

    asset_id = int(client.post("/api/assets", json={"name": "PAC"}).json()["id"])
    home_id = int(client.get("/api/homes/current").json()["id"])

    from sqlalchemy.exc import IntegrityError

    session = client.app.state.session_factory()  # type: ignore[attr-defined]
    try:
        session.add(
            Intervention(
                asset_id=asset_id,
                home_id=home_id,
                performed_on="2026-01-01",
                intervention_type="maintenance",
                created_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()
    finally:
        session.rollback()
        session.close()


def test_migration_0015_preserve_documents_couts_et_contraintes(tmp_path: Path) -> None:
    """Le remaniement recree deux tables. Sous `foreign_keys = ON`, le DROP TABLE
    aurait efface en cascade les documents de l'intervention — c'est la perte de
    donnees dont la 0004 garde la trace. Ce test en est le garde-fou."""
    settings = Settings(data_dir=tmp_path / "data")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    config = alembic_config(settings)

    command.upgrade(config, "0014_provenance_ecriture")
    connexion = sqlite3.connect(settings.database_path)
    connexion.execute("PRAGMA foreign_keys=ON")
    connexion.executescript(
        """
        INSERT INTO home (id, name) VALUES (1,'Maison');
        INSERT INTO asset (id, home_id, kind, name) VALUES (1,1,'equipment','PAC');
        INSERT INTO intervention (id, asset_id, performed_on, notes)
          VALUES (1,1,'2026-01-01','Filtres');
        INSERT INTO document (intervention_id, name, storage_mode, reference_note)
          VALUES (1,'Facture','reference_note','classeur');
        INSERT INTO cost (id, asset_id, intervention_id, cost_type, amount_cents, incurred_on)
          VALUES (1,1,1,'maintenance',18000,'2026-01-01');
        """
    )
    connexion.commit()
    connexion.close()

    command.upgrade(config, "head")

    connexion = sqlite3.connect(settings.database_path)
    lire = lambda sql: connexion.execute(sql).fetchone()[0]  # noqa: E731

    assert lire("SELECT COUNT(*) FROM document") == 1, "la facture a disparu avec la table"
    assert lire("SELECT COUNT(*) FROM cost WHERE intervention_id = 1") == 1
    assert lire("SELECT notes FROM intervention WHERE id = 1") == "Filtres"

    # Les CHECK ne sont pas rendus par la reflexion SQLite : une reconstruction
    # par `batch_alter_table` les aurait perdus en silence.
    ddl_intervention = lire("SELECT sql FROM sqlite_master WHERE name = 'intervention'")
    assert "performed_by_member_id IS NULL OR" in ddl_intervention
    assert "(asset_id IS NOT NULL) + (home_id IS NOT NULL) = 1" in ddl_intervention
    assert "cost_type IN" in lire("SELECT sql FROM sqlite_master WHERE name = 'cost'")

    assert lire("SELECT COUNT(*) FROM sqlite_master WHERE name = 'v_asset_timeline'") == 1
    assert connexion.execute("PRAGMA foreign_key_check").fetchall() == []
    connexion.close()


def test_migration_0015_est_rejouable(tmp_path: Path) -> None:
    """`upgrade` doit pouvoir retomber sur ses pieds si la base est deja a jour."""
    settings = Settings(data_dir=tmp_path / "data")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    config = alembic_config(settings)
    command.upgrade(config, "head")
    command.upgrade(config, "head")
