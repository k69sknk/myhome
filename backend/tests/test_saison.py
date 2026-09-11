"""Fenetre de saison sur les entretiens a intervalle (ADR-0010)."""

from datetime import date

from mabarak_api.catalog import load_catalog
from mabarak_api.services.recurrence import (
    Recurrence,
    compute_next_due,
    in_season,
    initial_next_due,
)

TONTE = Recurrence(
    recurrence_type="days",
    interval=7,
    anchor="from_completion",
    season_start_month=3,
    season_end_month=10,
)

# Fenetre a cheval sur le nouvel an : l'entretien d'hiver.
HIVER = Recurrence(
    recurrence_type="months",
    interval=1,
    anchor="from_completion",
    season_start_month=11,
    season_end_month=2,
)


# --- Appartenance a la fenetre -----------------------------------------------


def test_la_fenetre_inclut_ses_bornes() -> None:
    assert in_season(3, TONTE) is True
    assert in_season(10, TONTE) is True
    assert in_season(2, TONTE) is False
    assert in_season(11, TONTE) is False


def test_une_fenetre_peut_enjamber_le_nouvel_an() -> None:
    assert in_season(12, HIVER) is True
    assert in_season(1, HIVER) is True
    assert in_season(2, HIVER) is True
    assert in_season(6, HIVER) is False


def test_sans_saison_tous_les_mois_conviennent() -> None:
    toute_annee = Recurrence(recurrence_type="days", interval=7)
    assert all(in_season(month, toute_annee) for month in range(1, 13))


# --- Le cas qui a motive l'ADR : la tonte ------------------------------------


def test_une_tonte_en_pleine_saison_revient_la_semaine_suivante() -> None:
    next_due = compute_next_due(
        completed_on=date(2026, 6, 10),
        previous_due=date(2026, 6, 8),
        today=date(2026, 6, 10),
        recurrence=TONTE,
    )

    assert next_due == date(2026, 6, 17)


def test_la_derniere_tonte_de_l_automne_repousse_au_printemps() -> None:
    """Sans la saison, ce calcul donnerait le 4 novembre, puis une tache en retard
    affichee tout l'hiver — la raison d'etre de l'ADR."""
    next_due = compute_next_due(
        completed_on=date(2026, 10, 28),
        previous_due=date(2026, 10, 21),
        today=date(2026, 10, 28),
        recurrence=TONTE,
    )

    assert next_due == date(2027, 3, 1)


def test_l_hiver_ne_rattrape_pas_les_tontes_sautees() -> None:
    """Repousser, pas decaler de proche en proche : la reprise de mars est une
    seule echeance, pas vingt."""
    reprise = compute_next_due(
        completed_on=date(2027, 3, 5),
        previous_due=date(2027, 3, 1),
        today=date(2027, 3, 5),
        recurrence=TONTE,
    )

    assert reprise == date(2027, 3, 12)


def test_une_saison_d_hiver_repousse_a_novembre() -> None:
    next_due = compute_next_due(
        completed_on=date(2026, 2, 20),
        previous_due=None,
        today=date(2026, 2, 20),
        recurrence=HIVER,
    )

    assert next_due == date(2026, 11, 1)


# --- La saison n'abime pas l'ancrage (ADR-0004) ------------------------------


def test_l_ancrage_sur_date_theorique_reste_theorique_en_saison() -> None:
    saisonnier = Recurrence(
        recurrence_type="months",
        interval=1,
        anchor="from_due_date",
        season_start_month=5,
        season_end_month=9,
    )

    next_due = compute_next_due(
        completed_on=date(2026, 6, 20),
        previous_due=date(2026, 6, 1),
        today=date(2026, 6, 20),
        recurrence=saisonnier,
    )

    assert next_due == date(2026, 7, 1)


def test_l_ancrage_sur_date_theorique_repousse_aussi_hors_saison() -> None:
    saisonnier = Recurrence(
        recurrence_type="months",
        interval=1,
        anchor="from_due_date",
        season_start_month=5,
        season_end_month=9,
    )

    next_due = compute_next_due(
        completed_on=date(2026, 9, 20),
        previous_due=date(2026, 9, 1),
        today=date(2026, 9, 20),
        recurrence=saisonnier,
    )

    assert next_due == date(2027, 5, 1)


def test_une_date_fixe_ignore_la_saison() -> None:
    """`annual_fixed` porte deja son mois : la repousser reviendrait a lui retirer
    la date que l'utilisateur a choisie. Base et catalogue refusent d'ailleurs la
    combinaison ; le calcul ne doit pas non plus en dependre."""
    next_due = compute_next_due(
        completed_on=date(2026, 1, 15),
        previous_due=None,
        today=date(2026, 1, 15),
        recurrence=Recurrence(
            recurrence_type="annual_fixed",
            anchor="from_due_date",
            fixed_month=1,
            fixed_day=15,
            season_start_month=6,
            season_end_month=8,
        ),
    )

    assert next_due == date(2027, 1, 15)


# --- Premiere echeance, avant toute validation -------------------------------


def test_une_tonte_creee_en_hiver_demarre_au_printemps() -> None:
    next_due = initial_next_due(last_completed_on=None, today=date(2027, 1, 10), recurrence=TONTE)

    assert next_due == date(2027, 3, 1)


def test_une_tonte_creee_en_saison_demarre_dans_la_semaine() -> None:
    next_due = initial_next_due(last_completed_on=None, today=date(2026, 5, 10), recurrence=TONTE)

    assert next_due == date(2026, 5, 17)


def test_une_tonte_creee_avec_un_dernier_entretien_hors_saison() -> None:
    next_due = initial_next_due(
        last_completed_on=date(2026, 10, 30), today=date(2026, 11, 2), recurrence=TONTE
    )

    assert next_due == date(2027, 3, 1)


# --- Catalogue ---------------------------------------------------------------


def test_la_tonte_est_au_catalogue() -> None:
    """L'entretien de pelouse le plus evident manquait, faute de pouvoir
    l'exprimer."""
    pelouse = next(item for item in load_catalog().items if item.key == "pelouse")
    tonte = next(m for m in pelouse.maintenances if m.key == "pelouse_tonte")

    assert tonte.recurrence.type == "days"
    assert tonte.recurrence.interval == 7
    assert (tonte.recurrence.season_start_month, tonte.recurrence.season_end_month) == (3, 10)


def test_le_bassin_se_nettoie_a_la_belle_saison() -> None:
    piscine = next(item for item in load_catalog().items if item.key == "piscine")
    saisons = {
        m.key: (m.recurrence.season_start_month, m.recurrence.season_end_month)
        for m in piscine.maintenances
    }

    assert saisons["piscine_nettoyage"] == (5, 9)
    assert saisons["piscine_filtre"] == (5, 9)
    # L'hivernage et la remise en service sont des rendez-vous a date fixe : une
    # saison n'a rien a y ajouter.
    assert saisons["piscine_hivernage"] == (None, None)


# --- Contrat HTTP ------------------------------------------------------------


def test_un_entretien_saisonnier_se_cree_et_se_relit(client) -> None:
    asset_id = client.post("/api/assets", json={"name": "Jardin"}).json()["id"]

    created = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={
            "name": "Tondre",
            "recurrence_type": "days",
            "recurrence_interval": 7,
            "season_start_month": 3,
            "season_end_month": 10,
            "last_completed_on": "2026-10-28",
        },
    )

    assert created.status_code == 201
    body = created.json()
    assert body["season_start_month"] == 3
    assert body["season_end_month"] == 10
    assert body["next_due_on"] == "2027-03-01"


def test_ajouter_une_saison_replanifie_l_entretien(client) -> None:
    asset_id = client.post("/api/assets", json={"name": "Jardin"}).json()["id"]
    task_id = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={
            "name": "Tondre",
            "recurrence_type": "days",
            "recurrence_interval": 7,
            "last_completed_on": "2026-10-28",
        },
    ).json()["id"]

    patched = client.patch(
        f"/api/tasks/{task_id}", json={"season_start_month": 3, "season_end_month": 10}
    )

    assert patched.status_code == 200
    assert patched.json()["next_due_on"] == "2027-03-01"


def test_une_seule_borne_de_saison_est_refusee(client) -> None:
    asset_id = client.post("/api/assets", json={"name": "Jardin"}).json()["id"]

    response = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={
            "name": "Tondre",
            "recurrence_type": "days",
            "recurrence_interval": 7,
            "season_start_month": 3,
        },
    )

    assert response.status_code == 422


def test_une_saison_sur_une_date_fixe_est_refusee(client) -> None:
    asset_id = client.post("/api/assets", json={"name": "Jardin"}).json()["id"]

    response = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={
            "name": "Scarifier",
            "recurrence_type": "annual_fixed",
            "fixed_month": 4,
            "fixed_day": 1,
            "season_start_month": 3,
            "season_end_month": 10,
        },
    )

    assert response.status_code == 422


def test_un_mois_de_saison_hors_bornes_est_refuse(client) -> None:
    asset_id = client.post("/api/assets", json={"name": "Jardin"}).json()["id"]

    response = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={
            "name": "Tondre",
            "recurrence_type": "days",
            "recurrence_interval": 7,
            "season_start_month": 0,
            "season_end_month": 10,
        },
    )

    assert response.status_code == 422
