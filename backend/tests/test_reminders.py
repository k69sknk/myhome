"""Rappels a l'approche de l'echeance (ADR-0009)."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import text

from mabarak_api.clock import utc_today
from mabarak_api.db import create_db_engine, session_factory_for
from mabarak_api.ha_client import HaUnavailableError
from mabarak_api.migrate import upgrade_to_head
from mabarak_api.models import Asset, Home, MaintenanceTask, Member
from mabarak_api.services import reminders as reminders_module
from mabarak_api.services.home import ensure_home
from mabarak_api.services.reminders import (
    RELANCE_DAYS,
    ReminderConfigurationError,
    is_pass_due,
    plan_reminders,
    run_reminders,
)
from mabarak_api.services.scheduler import run_pass_if_due


@dataclass
class SentNotification:
    service: str
    title: str
    message: str


@pytest.fixture
def session(settings):
    """Une base migree, avec une maison, un equipement et rien d'autre."""
    upgrade_to_head(settings)
    factory = session_factory_for(create_db_engine(settings))
    with factory() as opened:
        ensure_home(opened)
        opened.commit()
        yield opened


@pytest.fixture
def envois(monkeypatch) -> list[SentNotification]:
    """Intercepte les appels a Home Assistant, qui n'existe pas dans les tests."""
    sent: list[SentNotification] = []

    def fake_send(service: str, title: str, message: str) -> None:
        sent.append(SentNotification(service, title, message))

    monkeypatch.setattr(reminders_module, "send_notification", fake_send)
    return sent


def _home(session) -> Home:
    home = ensure_home(session)
    home.task_notifications_enabled = 1
    home.default_notify_service = "mobile_app_maison"
    session.flush()
    return home


def _asset(session, home: Home, name: str = "Chaudiere") -> Asset:
    asset = Asset(
        home_id=home.id,
        kind="equipment",
        name=name,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    session.add(asset)
    session.flush()
    return asset


def _task(session, asset: Asset, *, name: str, due: date, **kwargs) -> MaintenanceTask:
    task = MaintenanceTask(
        asset_id=asset.id,
        name=name,
        recurrence_type="months",
        recurrence_interval=3,
        next_due_on=due.isoformat(),
        # Seuil large : le statut derive de la vue SQL, qui compare a la date du
        # jour REELLE. Une echeance proche doit donc etre 'due_soon' aujourd'hui.
        lead_time_days=30,
        is_active=1,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        **kwargs,
    )
    session.add(task)
    session.flush()
    return task


# --- Selection de ce qui doit etre rappele -----------------------------------


def test_un_entretien_en_retard_est_rappele(session, envois) -> None:
    home = _home(session)
    asset = _asset(session, home)
    _task(session, asset, name="Ramoner", due=utc_today() - timedelta(days=3))

    result = run_reminders(session, today=utc_today())

    assert result.sent == 1
    assert result.tasks == 1
    assert envois[0].service == "mobile_app_maison"
    assert "Ramoner" in envois[0].message
    assert "en retard depuis 3 jours" in envois[0].message


def test_un_entretien_a_jour_ne_declenche_rien(session, envois) -> None:
    home = _home(session)
    asset = _asset(session, home)
    _task(session, asset, name="Detartrer", due=utc_today() + timedelta(days=200))

    result = run_reminders(session, today=utc_today())

    assert result.sent == 0
    assert envois == []


def test_un_entretien_desactive_ne_declenche_rien(session, envois) -> None:
    home = _home(session)
    asset = _asset(session, home)
    task = _task(session, asset, name="Ramoner", due=utc_today() - timedelta(days=3))
    task.is_active = 0
    session.flush()

    assert run_reminders(session, today=utc_today()).sent == 0


# --- Ne pas harceler ---------------------------------------------------------


def test_un_entretien_deja_rappele_se_tait(session, envois) -> None:
    home = _home(session)
    asset = _asset(session, home)
    _task(session, asset, name="Ramoner", due=utc_today() - timedelta(days=3))

    run_reminders(session, today=utc_today())
    envois.clear()
    run_reminders(session, today=utc_today() + timedelta(days=1))

    assert envois == []


def test_un_entretien_en_retard_relance_apres_une_semaine(session, envois) -> None:
    home = _home(session)
    asset = _asset(session, home)
    _task(session, asset, name="Ramoner", due=utc_today() - timedelta(days=3))

    run_reminders(session, today=utc_today())
    envois.clear()
    run_reminders(session, today=utc_today() + timedelta(days=RELANCE_DAYS))

    assert len(envois) == 1


def test_une_nouvelle_echeance_reprend_la_parole(session, envois) -> None:
    """La trace est remise a NULL des que `next_due_on` change (complete_task,
    patch_task) : un entretien tout juste replanifie ne doit pas rester muet."""
    home = _home(session)
    asset = _asset(session, home)
    task = _task(session, asset, name="Ramoner", due=utc_today() - timedelta(days=3))

    run_reminders(session, today=utc_today())
    assert task.last_reminded_on is not None
    envois.clear()

    task.last_reminded_on = None
    task.next_due_on = (utc_today() + timedelta(days=2)).isoformat()
    session.flush()
    run_reminders(session, today=utc_today())

    assert len(envois) == 1


# --- Un message par personne -------------------------------------------------


def test_plusieurs_entretiens_tiennent_dans_un_seul_message(session, envois) -> None:
    home = _home(session)
    asset = _asset(session, home)
    for index in range(4):
        _task(session, asset, name=f"Entretien {index}", due=utc_today() - timedelta(days=index))

    result = run_reminders(session, today=utc_today())

    assert result.sent == 1
    assert result.tasks == 4
    assert len(envois) == 1
    assert envois[0].message.count("\n") == 3


def test_au_dela_de_huit_lignes_le_reste_est_compte(session, envois) -> None:
    home = _home(session)
    asset = _asset(session, home)
    for index in range(11):
        _task(session, asset, name=f"Entretien {index}", due=utc_today() - timedelta(days=index))

    run_reminders(session, today=utc_today())

    assert "… et 3 autres." in envois[0].message


def test_le_plus_en_retard_arrive_en_tete(session, envois) -> None:
    home = _home(session)
    asset = _asset(session, home)
    _task(session, asset, name="Recent", due=utc_today() - timedelta(days=1))
    _task(session, asset, name="Ancien", due=utc_today() - timedelta(days=40))

    run_reminders(session, today=utc_today())

    lignes = envois[0].message.splitlines()
    assert "Ancien" in lignes[0]
    assert "Recent" in lignes[1]


# --- Qui recoit quoi ---------------------------------------------------------


def test_la_personne_assignee_recoit_son_propre_message(session, envois) -> None:
    home = _home(session)
    asset = _asset(session, home)
    member = Member(
        home_id=home.id,
        name="Alice",
        ha_notify_service="mobile_app_alice",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    session.add(member)
    session.flush()
    _task(session, asset, name="A Alice", due=utc_today(), assignee_id=member.id)
    _task(session, asset, name="A personne", due=utc_today())

    run_reminders(session, today=utc_today())

    par_service = {envoi.service: envoi.message for envoi in envois}
    assert "A Alice" in par_service["mobile_app_alice"]
    assert "A personne" in par_service["mobile_app_maison"]
    assert "A Alice" not in par_service["mobile_app_maison"]


def test_sans_destinataire_le_rappel_est_compte_et_non_perdu(session, envois) -> None:
    home = _home(session)
    home.default_notify_service = None
    session.flush()
    asset = _asset(session, home)
    _task(session, asset, name="Ramoner", due=utc_today() - timedelta(days=3))

    result = run_reminders(session, today=utc_today())

    assert result.sent == 0
    assert result.without_recipient == 1
    assert envois == []


def test_le_plan_dit_ce_qui_partirait_sans_rien_envoyer(session, envois) -> None:
    """Le calcul est separe de l'envoi : il doit tenir debout sans Home Assistant,
    et sans laisser de trace sur les entretiens."""
    home = _home(session)
    asset = _asset(session, home)
    task = _task(session, asset, name="Ramoner", due=utc_today() - timedelta(days=3))

    plan = plan_reminders(session, today=utc_today())

    assert [reminder.service for reminder in plan.reminders] == ["mobile_app_maison"]
    assert plan.reminders[0].task_ids == (task.id,)
    assert envois == []
    assert task.last_reminded_on is None


def test_une_personne_sans_service_retombe_sur_celui_de_la_maison(session, envois) -> None:
    home = _home(session)
    asset = _asset(session, home)
    member = Member(
        home_id=home.id,
        name="Bob",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    session.add(member)
    session.flush()
    _task(session, asset, name="A Bob", due=utc_today(), assignee_id=member.id)

    run_reminders(session, today=utc_today())

    assert envois[0].service == "mobile_app_maison"


# --- Home Assistant injoignable ----------------------------------------------


def test_un_envoi_rate_ne_marque_pas_l_entretien(session, monkeypatch) -> None:
    home = _home(session)
    asset = _asset(session, home)
    task = _task(session, asset, name="Ramoner", due=utc_today() - timedelta(days=3))

    def refuse(service: str, title: str, message: str) -> None:
        raise HaUnavailableError("SUPERVISOR_TOKEN absent")

    monkeypatch.setattr(reminders_module, "send_notification", refuse)
    result = run_reminders(session, today=utc_today())

    assert result.sent == 0
    assert result.errors
    assert task.last_reminded_on is None


def test_notifications_coupees_refuse_le_passage(session) -> None:
    home = ensure_home(session)
    home.task_notifications_enabled = 0
    session.flush()

    with pytest.raises(ReminderConfigurationError):
        run_reminders(session, today=utc_today())


# --- Heure du passage et rattrapage ------------------------------------------


def test_avant_l_heure_choisie_aucun_passage(session) -> None:
    home = _home(session)
    home.reminder_hour = 8
    home.last_reminder_run_on = None

    assert is_pass_due(home, datetime(2026, 9, 11, 7, 59)) is False
    assert is_pass_due(home, datetime(2026, 9, 11, 8, 0)) is True


def test_un_seul_passage_par_jour(session) -> None:
    home = _home(session)
    home.reminder_hour = 8
    home.last_reminder_run_on = "2026-09-11"

    assert is_pass_due(home, datetime(2026, 9, 11, 20, 0)) is False
    assert is_pass_due(home, datetime(2026, 9, 12, 8, 0)) is True


def test_un_add_on_eteint_le_matin_rattrape_l_apres_midi(session) -> None:
    """C'est tout l'interet de la formulation « pas encore passe aujourd'hui, et
    l'heure est atteinte » : le passage manque a 8h a lieu au demarrage de 14h."""
    home = _home(session)
    home.reminder_hour = 8
    home.last_reminder_run_on = "2026-09-09"

    assert is_pass_due(home, datetime(2026, 9, 11, 14, 30)) is True


def test_le_planificateur_note_la_date_meme_sans_notification(settings, monkeypatch) -> None:
    """Sans cette trace, un add-on aux notifications coupees rouvrirait la base a
    chaque battement pour rien."""
    upgrade_to_head(settings)
    factory = session_factory_for(create_db_engine(settings))
    with factory() as opened:
        ensure_home(opened)
        opened.commit()

    monkeypatch.setattr(
        "mabarak_api.services.scheduler.local_now", lambda: datetime(2026, 9, 11, 9, 0)
    )

    assert run_pass_if_due(factory) is True
    assert run_pass_if_due(factory) is False

    with factory() as opened:
        assert ensure_home(opened).last_reminder_run_on == "2026-09-11"


# --- Contrat HTTP ------------------------------------------------------------


def test_la_route_refuse_si_les_notifications_sont_coupees(client) -> None:
    assert client.post("/api/ha/reminders/run").status_code == 409


def test_la_route_rend_le_compte_rendu_du_passage(client, monkeypatch) -> None:
    monkeypatch.setattr(reminders_module, "send_notification", lambda *args: None)
    client.patch(
        "/api/homes/current",
        json={"task_notifications_enabled": True, "default_notify_service": "mobile_app_maison"},
    )

    response = client.post("/api/ha/reminders/run")

    assert response.status_code == 200
    assert response.json() == {"sent": 0, "tasks": 0, "without_recipient": 0, "errors": []}


def test_l_heure_de_rappel_est_bornee(client) -> None:
    assert client.patch("/api/homes/current", json={"reminder_hour": 24}).status_code == 422
    assert client.patch("/api/homes/current", json={"reminder_hour": 6}).status_code == 200
    assert client.get("/api/homes/current").json()["reminder_hour"] == 6


def test_la_maison_expose_ses_reglages_de_rappel_par_defaut(client) -> None:
    body = client.get("/api/homes/current").json()

    assert body["reminder_hour"] == 8
    assert body["default_notify_service"] is None


def test_valider_un_entretien_efface_la_trace_de_rappel(client) -> None:
    """`complete_task` recalcule `next_due_on` : la trace doit tomber avec elle."""
    asset_id = client.post("/api/assets", json={"name": "Chaudiere"}).json()["id"]
    task_id = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={"name": "Ramoner", "recurrence_type": "months", "recurrence_interval": 3},
    ).json()["id"]

    engine = create_db_engine(client.app.state.settings)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE maintenance_task SET last_reminded_on = '2026-09-01' WHERE id = :id"),
            {"id": task_id},
        )

    client.post(f"/api/tasks/{task_id}/complete", json={})

    with engine.connect() as connection:
        trace = connection.execute(
            text("SELECT last_reminded_on FROM maintenance_task WHERE id = :id"), {"id": task_id}
        ).scalar_one()
    assert trace is None
