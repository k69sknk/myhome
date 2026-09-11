"""Prestataires : table a part, exclusivite du responsable, et demenagement des
entreprises saisies quand elles etaient encore des membres (adr/0011)."""

from fastapi.testclient import TestClient
from sqlalchemy import text

from mabarak_api.db import create_db_engine
from mabarak_api.main import create_app
from mabarak_api.migrate import upgrade_to_head


def _asset(client: TestClient) -> int:
    return int(client.post("/api/assets", json={"name": "Chaudiere"}).json()["id"])


def _task(client: TestClient, asset_id: int, **overrides: object) -> dict:
    body = {"name": "Revision annuelle", "recurrence_type": "months", "recurrence_interval": 12}
    return dict(client.post(f"/api/assets/{asset_id}/tasks", json={**body, **overrides}).json())


def test_prestataire_crud(client: TestClient) -> None:
    created = client.post(
        "/api/providers",
        json={
            "name": "Dupont Chauffage",
            "specialty": "chauffagiste",
            "phone": "04 72 00 00 00",
            "customer_ref": "CL-2019-4471",
        },
    )
    assert created.status_code == 201, created.text
    provider = created.json()
    assert provider["customer_ref"] == "CL-2019-4471"

    patched = client.patch(
        f"/api/providers/{provider['id']}", json={"email": "contact@dupont.fr"}
    ).json()
    assert patched["email"] == "contact@dupont.fr"
    assert patched["phone"] == "04 72 00 00 00"  # le patch n'efface pas le reste

    assert client.delete(f"/api/providers/{provider['id']}").status_code == 200
    assert client.get("/api/providers").json() == []


def test_un_membre_ne_peut_plus_etre_une_entreprise(client: TestClient) -> None:
    """Le type a disparu : c'est ce qui empeche de recreer l'ancien melange."""
    response = client.post("/api/members", json={"name": "Dupont", "member_type": "company"})
    assert response.status_code == 422


def test_entretien_confie_a_un_prestataire(client: TestClient) -> None:
    provider = client.post("/api/providers", json={"name": "Dupont Chauffage"}).json()
    task = _task(client, _asset(client), assignee_provider_id=provider["id"])

    assert task["assignee_provider_id"] == provider["id"]
    assert task["assignee_id"] is None
    # Le nom s'affiche sans que l'appelant ait a savoir de quelle table il vient.
    assert task["assignee_name"] == "Dupont Chauffage"


def test_un_entretien_n_a_qu_un_responsable(client: TestClient) -> None:
    member = client.post("/api/members", json={"name": "Alice"}).json()
    provider = client.post("/api/providers", json={"name": "Dupont Chauffage"}).json()
    asset_id = _asset(client)

    refuse = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={
            "name": "Revision",
            "assignee_id": member["id"],
            "assignee_provider_id": provider["id"],
        },
    )
    assert refuse.status_code == 422


def test_confier_a_un_membre_retire_le_prestataire(client: TestClient) -> None:
    """Sans cela, un entretien finirait avec deux responsables : le CHECK de
    schema.sql l'interdit, et une base migree ne l'a pas."""
    member = client.post("/api/members", json={"name": "Alice"}).json()
    provider = client.post("/api/providers", json={"name": "Dupont Chauffage"}).json()
    task = _task(client, _asset(client), assignee_provider_id=provider["id"])

    patched = client.patch(f"/api/tasks/{task['id']}", json={"assignee_id": member["id"]}).json()
    assert patched["assignee_id"] == member["id"]
    assert patched["assignee_provider_id"] is None

    back = client.patch(
        f"/api/tasks/{task['id']}", json={"assignee_provider_id": provider["id"]}
    ).json()
    assert back["assignee_id"] is None
    assert back["assignee_provider_id"] == provider["id"]


def test_supprimer_un_prestataire_desassigne_ses_entretiens(client: TestClient) -> None:
    provider = client.post("/api/providers", json={"name": "Dupont Chauffage"}).json()
    task = _task(client, _asset(client), assignee_provider_id=provider["id"])

    client.delete(f"/api/providers/{provider['id']}")

    refreshed = client.get("/api/tasks").json()[0]
    assert refreshed["id"] == task["id"]
    assert refreshed["assignee_provider_id"] is None
    assert refreshed["assignee_name"] is None


def test_un_prestataire_inconnu_est_refuse(client: TestClient) -> None:
    response = client.post(
        f"/api/assets/{_asset(client)}/tasks",
        json={"name": "Revision", "assignee_provider_id": 404},
    )
    assert response.status_code == 404


def test_liste_des_metiers(client: TestClient) -> None:
    trades = client.get("/api/trades").json()
    slugs = {trade["slug"] for trade in trades}
    assert {"chauffagiste", "plombier", "autre"} <= slugs
    assert all(trade["label"] for trade in trades)


def test_les_metiers_integres_sont_ordonnes_et_autre_ferme_la_liste(
    client: TestClient,
) -> None:
    trades = client.get("/api/trades").json()
    assert trades[-1]["slug"] == "autre"
    assert all(trade["is_builtin"] for trade in trades)


def test_un_metier_absent_de_la_liste_sajoute(client: TestClient) -> None:
    """« Autre » seul faisait perdre l'information : on ne savait plus qui on
    appelle. Un vitrier n'est pas dans la liste integree, il doit pouvoir y
    entrer."""
    created = client.post("/api/trades", json={"name": "Vitrier"})

    assert created.status_code == 201
    assert created.json() == {"slug": "vitrier", "label": "Vitrier", "is_builtin": False}

    trades = client.get("/api/trades").json()
    slugs = [trade["slug"] for trade in trades]
    assert "vitrier" in slugs
    # Un metier a part entiere : apres les integres, mais avant « Autre ».
    assert slugs.index("vitrier") < slugs.index("autre")
    assert slugs.index("chauffagiste") < slugs.index("vitrier")

    # Et il se pose sur une fiche comme n'importe quel autre.
    provider = client.post(
        "/api/providers", json={"name": "Vitrerie du Rhone", "specialty": "vitrier"}
    ).json()
    assert provider["specialty"] == "vitrier"
    assert client.get("/api/providers").json()[0]["specialty"] == "vitrier"


def test_le_meme_metier_saisi_deux_fois_ne_fait_pas_de_sosie(client: TestClient) -> None:
    """Deux saisies qui ne different que par la casse ou les accents designent le
    meme metier (meme regle que le didacticiel en 0.24) : sans cela, regrouper
    par metier ne regrouperait rien."""
    premier = client.post("/api/trades", json={"name": "Vitrier"}).json()
    avant = len(client.get("/api/trades").json())

    for saisie in ("vitrier", "VITRIER", "  Vitrier  "):
        again = client.post("/api/trades", json={"name": saisie})
        assert again.status_code == 201
        assert again.json()["slug"] == premier["slug"]

    assert len(client.get("/api/trades").json()) == avant
    assert client.get("/api/trades").json()[-1]["slug"] == "autre"


def test_un_metier_integre_saisi_a_la_main_reste_integre(client: TestClient) -> None:
    retrouve = client.post("/api/trades", json={"name": "Plombier"})

    assert retrouve.json()["slug"] == "plombier"
    assert retrouve.json()["is_builtin"] is True
    assert len([t for t in client.get("/api/trades").json() if t["slug"] == "plombier"]) == 1


def test_un_metier_sans_nom_est_refuse(client: TestClient) -> None:
    assert client.post("/api/trades", json={"name": "   "}).status_code == 422
    assert client.post("/api/trades", json={"name": ""}).status_code == 422


def test_une_base_migree_recoit_les_metiers_integres(settings) -> None:
    """Migration 0013 : la table est creee vide sur une base existante, et le
    seed du demarrage la remplit — sinon l'ecran des prestataires serait vide."""
    upgrade_to_head(settings)
    engine = create_db_engine(settings)
    with engine.connect() as connection:
        avant = connection.execute(text("SELECT COUNT(*) FROM trade")).scalar_one()

    with TestClient(create_app(settings)) as client:
        trades = client.get("/api/trades").json()

    assert avant == 0
    assert {"chauffagiste", "plombier", "autre"} <= {trade["slug"] for trade in trades}


def test_les_entreprises_dejà_saisies_demenagent_avec_leurs_liens(settings) -> None:
    """Migration 0012 : une entreprise saisie en 0.22 est un `member`, deja
    referencee par un entretien et une intervention. Elle doit devenir un
    `provider` SANS que ces deux liens se perdent en route."""
    upgrade_to_head(settings)
    engine = create_db_engine(settings)

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO home (id, name, created_at, updated_at) "
                "VALUES (1, 'Ma maison', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO asset (id, home_id, kind, name, status, created_at, updated_at) "
                "VALUES (1, 1, 'equipment', 'Chaudiere', 'active', "
                "'2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
            )
        )
        # Une entreprise telle que 0.22 la creait, et un ami qui doit rester membre.
        # Le CHECK de schema.sql interdit desormais 'company' : cette ligne ne peut
        # venir que d'une version anterieure, on la recree donc en desactivant la
        # contrainte le temps de l'insertion.
        connection.execute(text("PRAGMA ignore_check_constraints = ON"))
        connection.execute(
            text(
                "INSERT INTO member (id, home_id, name, member_type, contact, "
                "created_at, updated_at) VALUES "
                "(1, 1, 'Dupont Chauffage', 'company', '04 72 00 00 00', "
                "'2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'), "
                "(2, 1, 'Bob', 'friend', 'bob@exemple.fr', "
                "'2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
            )
        )
        connection.execute(text("PRAGMA ignore_check_constraints = OFF"))
        connection.execute(
            text(
                "INSERT INTO maintenance_task (id, asset_id, assignee_id, name, "
                "recurrence_type, recurrence_interval, is_active, created_at, updated_at) "
                "VALUES (1, 1, 1, 'Revision annuelle', 'months', 12, 1, "
                "'2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO intervention (id, asset_id, task_id, performed_on, "
                "performed_by, performed_by_member_id, created_at, updated_at) "
                "VALUES (1, 1, 1, '2026-03-01', 'Dupont Chauffage', 1, "
                "'2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
            )
        )
        # On rejoue la migration sur ces donnees.
        connection.execute(text("DELETE FROM alembic_version"))
        connection.execute(text("INSERT INTO alembic_version VALUES ('0011_intervention_membre')"))

    upgrade_to_head(settings)

    with engine.connect() as connection:
        providers = connection.execute(text("SELECT id, name, phone, email FROM provider")).all()
        members = connection.execute(text("SELECT name, member_type FROM member")).all()
        task = connection.execute(
            text("SELECT assignee_id, assignee_provider_id FROM maintenance_task WHERE id = 1")
        ).one()
        intervention = connection.execute(
            text(
                "SELECT performed_by, performed_by_member_id, performed_by_provider_id "
                "FROM intervention WHERE id = 1"
            )
        ).one()

    assert [(row.name, row.phone, row.email) for row in providers] == [
        ("Dupont Chauffage", "04 72 00 00 00", None)
    ]
    # L'ami reste un membre, lui.
    assert [(row.name, row.member_type) for row in members] == [("Bob", "friend")]

    provider_id = providers[0].id
    assert (task.assignee_id, task.assignee_provider_id) == (None, provider_id)
    assert intervention.performed_by == "Dupont Chauffage"
    assert (intervention.performed_by_member_id, intervention.performed_by_provider_id) == (
        None,
        provider_id,
    )


def test_un_contact_avec_arobase_part_dans_l_email(settings) -> None:
    """Seule heuristique de la migration : `contact` etait un champ libre."""
    upgrade_to_head(settings)
    engine = create_db_engine(settings)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO home (id, name, created_at, updated_at) "
                "VALUES (1, 'Ma maison', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
            )
        )
        connection.execute(text("PRAGMA ignore_check_constraints = ON"))
        connection.execute(
            text(
                "INSERT INTO member (id, home_id, name, member_type, contact, "
                "created_at, updated_at) VALUES (1, 1, 'Clim 69', 'company', "
                "'contact@clim69.fr', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
            )
        )
        connection.execute(text("PRAGMA ignore_check_constraints = OFF"))
        connection.execute(text("DELETE FROM alembic_version"))
        connection.execute(text("INSERT INTO alembic_version VALUES ('0011_intervention_membre')"))

    upgrade_to_head(settings)

    with engine.connect() as connection:
        row = connection.execute(text("SELECT phone, email FROM provider")).one()
    assert (row.phone, row.email) == (None, "contact@clim69.fr")
