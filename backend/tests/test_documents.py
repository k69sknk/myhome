"""Les trois modes de stockage d'un document, et les passages de l'un a l'autre.

L'adr/0002 a choisi une seule table justement pour que changer de mode soit un
`UPDATE` : un document garde son `id`, donc ses rattachements, qu'il soit un
fichier depose dans l'application, un lien vers un NAS ou une note « facture
dans l'e-mail du 12 mai ». Ces tests verifient les deux engagements qui en
decoulent et qui ne se voient pas dans le schema : l'identite survit au
changement de mode, et quitter le fichier local efface le fichier.
"""

from io import BytesIO

from fastapi.testclient import TestClient

from mabarak_api.config import Settings

FAUX_PDF = b"%PDF-1.4 fausse facture"


def _asset(client: TestClient, name: str = "Chaudiere") -> int:
    created: int = client.post("/api/assets", json={"name": name}).json()["id"]
    return created


def _fichiers(settings: Settings) -> list[str]:
    if not settings.documents_dir.exists():
        return []
    return [path.name for path in settings.documents_dir.rglob("*") if path.is_file()]


def test_les_trois_modes_sont_acceptes_a_la_creation(client: TestClient) -> None:
    asset_id = _asset(client)

    fichier = client.post(
        f"/api/assets/{asset_id}/documents",
        files={"file": ("notice.pdf", BytesIO(FAUX_PDF), "application/pdf")},
        data={"storage_mode": "local_file", "doc_type": "manual"},
    )
    lien = client.post(
        f"/api/assets/{asset_id}/documents",
        data={
            "storage_mode": "external_link",
            "doc_type": "invoice",
            "name": "Facture d'achat",
            "url": "https://nextcloud.exemple/factures/chaudiere.pdf",
        },
    )
    reference = client.post(
        f"/api/assets/{asset_id}/documents",
        data={
            "storage_mode": "reference_note",
            "doc_type": "warranty",
            "name": "Garantie constructeur",
            "reference_note": "classeur chauffage au garage",
        },
    )

    assert [fichier.status_code, lien.status_code, reference.status_code] == [201, 201, 201]
    assert fichier.json()["storage_mode"] == "local_file"
    assert fichier.json()["name"] == "notice.pdf"
    assert lien.json()["url"] == "https://nextcloud.exemple/factures/chaudiere.pdf"
    assert lien.json()["file_size"] is None
    assert reference.json()["reference_note"] == "classeur chauffage au garage"
    assert reference.json()["doc_type"] == "warranty"

    listed = client.get(f"/api/assets/{asset_id}/documents").json()
    assert {row["storage_mode"] for row in listed} == {
        "local_file",
        "external_link",
        "reference_note",
    }


def test_les_modes_sans_fichier_ne_touchent_pas_au_disque(
    client: TestClient, settings: Settings
) -> None:
    """La promesse de confidentialite : ces deux modes n'ecrivent rien, donc
    n'entrent pas dans les sauvegardes Home Assistant."""
    asset_id = _asset(client)
    lien = client.post(
        f"/api/assets/{asset_id}/documents",
        data={
            "storage_mode": "external_link",
            "name": "Facture",
            "url": "smb://nas/maison/factures/2026.pdf",
        },
    ).json()
    client.post(
        f"/api/assets/{asset_id}/documents",
        data={
            "storage_mode": "reference_note",
            "name": "Certificat",
            "reference_note": "e-mail du 12/05/2024",
        },
    )

    assert _fichiers(settings) == []
    # Rien a telecharger : le contenu n'est pas dans l'application.
    assert client.get(f"/api/documents/{lien['id']}/file").status_code == 409


def test_un_document_sans_fichier_a_besoin_dun_nom_et_dun_contenu(client: TestClient) -> None:
    asset_id = _asset(client)

    sans_nom = client.post(
        f"/api/assets/{asset_id}/documents",
        data={"storage_mode": "external_link", "url": "https://exemple/facture.pdf"},
    )
    sans_url = client.post(
        f"/api/assets/{asset_id}/documents",
        data={"storage_mode": "external_link", "name": "Facture"},
    )
    sans_protocole = client.post(
        f"/api/assets/{asset_id}/documents",
        data={"storage_mode": "external_link", "name": "Facture", "url": "nas/factures.pdf"},
    )
    sans_texte = client.post(
        f"/api/assets/{asset_id}/documents",
        data={"storage_mode": "reference_note", "name": "Garantie", "reference_note": "   "},
    )
    sans_fichier = client.post(
        f"/api/assets/{asset_id}/documents",
        data={"storage_mode": "local_file", "name": "Notice"},
    )

    assert sans_nom.status_code == 422
    assert sans_url.status_code == 422
    assert sans_protocole.status_code == 422
    assert sans_texte.status_code == 422
    assert sans_fichier.status_code == 422
    assert client.get(f"/api/assets/{asset_id}/documents").json() == []


def test_quitter_le_fichier_local_efface_le_fichier(client: TestClient, settings: Settings) -> None:
    """La consequence negative annoncee par l'adr/0002, traitee.

    Sortir ses factures de l'application n'a de sens que si le PDF part
    vraiment : sinon il reste dans les sauvegardes de l'utilisateur.
    """
    asset_id = _asset(client)
    document = client.post(
        f"/api/assets/{asset_id}/documents",
        files={"file": ("facture.pdf", BytesIO(FAUX_PDF), "application/pdf")},
        data={"doc_type": "invoice"},
    ).json()
    assert len(_fichiers(settings)) == 1

    patched = client.patch(
        f"/api/documents/{document['id']}",
        json={
            "storage_mode": "reference_note",
            "reference_note": "facture dans l'e-mail du 12/05/2024",
        },
    )

    assert patched.status_code == 200
    # L'identite du document survit au changement de mode : c'est tout l'interet
    # d'une seule table.
    assert patched.json()["id"] == document["id"]
    assert patched.json()["name"] == "facture.pdf"
    assert patched.json()["storage_mode"] == "reference_note"
    assert patched.json()["file_size"] is None
    assert _fichiers(settings) == []
    assert client.get(f"/api/documents/{document['id']}/file").status_code == 409


def test_retrouver_le_pdf_dun_document_simplement_note(
    client: TestClient, settings: Settings
) -> None:
    """Le chemin inverse : la note devient fichier, sans perdre le document."""
    asset_id = _asset(client)
    document = client.post(
        f"/api/assets/{asset_id}/documents",
        data={
            "storage_mode": "reference_note",
            "doc_type": "invoice",
            "name": "Facture de la chaudiere",
            "reference_note": "a chercher dans les mails",
        },
    ).json()

    attached = client.post(
        f"/api/documents/{document['id']}/file",
        files={"file": ("facture.pdf", BytesIO(FAUX_PDF), "application/pdf")},
    )

    assert attached.status_code == 200
    assert attached.json()["id"] == document["id"]
    assert attached.json()["storage_mode"] == "local_file"
    assert attached.json()["reference_note"] is None
    assert attached.json()["name"] == "Facture de la chaudiere"
    assert len(_fichiers(settings)) == 1
    downloaded = client.get(f"/api/documents/{document['id']}/file")
    assert downloaded.status_code == 200
    assert downloaded.content == FAUX_PDF


def test_changer_de_fichier_ne_laisse_pas_lancien(client: TestClient, settings: Settings) -> None:
    asset_id = _asset(client)
    document = client.post(
        f"/api/assets/{asset_id}/documents",
        files={"file": ("notice.pdf", BytesIO(FAUX_PDF), "application/pdf")},
    ).json()

    client.post(
        f"/api/documents/{document['id']}/file",
        files={"file": ("notice-v2.pdf", BytesIO(b"%PDF-1.4 v2"), "application/pdf")},
    )

    assert len(_fichiers(settings)) == 1
    assert client.get(f"/api/documents/{document['id']}/file").content == b"%PDF-1.4 v2"


def test_corriger_le_contenu_du_mode_en_cours(client: TestClient) -> None:
    asset_id = _asset(client)
    lien = client.post(
        f"/api/assets/{asset_id}/documents",
        data={
            "storage_mode": "external_link",
            "name": "Facture",
            "url": "https://nextcloud.exemple/ancien.pdf",
        },
    ).json()

    corrige = client.patch(
        f"/api/documents/{lien['id']}",
        json={"url": "https://nextcloud.exemple/factures/2026.pdf"},
    )
    assert corrige.status_code == 200
    assert corrige.json()["url"] == "https://nextcloud.exemple/factures/2026.pdf"
    assert corrige.json()["storage_mode"] == "external_link"

    # Ecrire une note sur un lien ferait mentir `storage_mode` : il faut annoncer
    # le changement de mode.
    incoherent = client.patch(
        f"/api/documents/{lien['id']}", json={"reference_note": "dans mes mails"}
    )
    assert incoherent.status_code == 422
    # Et refuser les deux contenus a la fois.
    deux_contenus = client.patch(
        f"/api/documents/{lien['id']}",
        json={
            "storage_mode": "reference_note",
            "reference_note": "dans mes mails",
            "url": "https://exemple/f.pdf",
        },
    )
    assert deux_contenus.status_code == 422


def test_renommer_et_requalifier_un_document(client: TestClient) -> None:
    asset_id = _asset(client)
    document = client.post(
        f"/api/assets/{asset_id}/documents",
        files={"file": ("scan0012.pdf", BytesIO(FAUX_PDF), "application/pdf")},
        data={"doc_type": "other"},
    ).json()

    patched = client.patch(
        f"/api/documents/{document['id']}",
        json={
            "name": "Certificat de conformite gaz",
            "doc_type": "certificate",
            "notes": "remis par le chauffagiste",
        },
    )

    assert patched.status_code == 200
    assert patched.json()["name"] == "Certificat de conformite gaz"
    assert patched.json()["doc_type"] == "certificate"
    assert patched.json()["notes"] == "remis par le chauffagiste"
    assert client.patch(f"/api/documents/{document['id']}", json={"name": "   "}).status_code == 422


def test_tous_les_types_du_schema_sont_acceptes(client: TestClient) -> None:
    """`warranty`, `certificate`, `service_contract` et `user_guide` existaient
    dans le schema mais etaient refuses par l'API. Le huitieme type, `photo`,
    demande un fichier : il a son propre test."""
    asset_id = _asset(client)
    for doc_type in (
        "invoice",
        "manual",
        "user_guide",
        "certificate",
        "warranty",
        "service_contract",
        "other",
    ):
        created = client.post(
            f"/api/assets/{asset_id}/documents",
            data={
                "storage_mode": "reference_note",
                "doc_type": doc_type,
                "name": f"Document {doc_type}",
                "reference_note": "classeur au garage",
            },
        )
        assert created.status_code == 201, doc_type
        assert created.json()["doc_type"] == doc_type


def test_la_photo_de_la_fiche_reste_un_fichier_local(client: TestClient) -> None:
    asset_id = _asset(client)
    lien = client.post(
        f"/api/assets/{asset_id}/documents",
        data={
            "storage_mode": "external_link",
            "doc_type": "photo",
            "name": "Photo",
            "url": "https://exemple/photo.jpg",
        },
    )
    assert lien.status_code == 422

    photo = client.post(
        f"/api/assets/{asset_id}/documents",
        files={"file": ("photo.jpg", BytesIO(b"\xff\xd8\xff fake jpeg"), "image/jpeg")},
        data={"doc_type": "photo"},
    ).json()
    # Elle est servie par /documents/{id}/file : elle ne peut pas devenir un lien.
    refuse = client.patch(
        f"/api/documents/{photo['id']}",
        json={"storage_mode": "external_link", "url": "https://exemple/photo.jpg"},
    )
    assert refuse.status_code == 422
    assert client.get(f"/api/assets/{asset_id}").json()["photo_document_id"] == photo["id"]


def test_une_photo_refusee_ne_fait_pas_perdre_la_precedente(client: TestClient) -> None:
    asset_id = _asset(client)
    photo = client.post(
        f"/api/assets/{asset_id}/documents",
        files={"file": ("photo.jpg", BytesIO(b"\xff\xd8\xff fake jpeg"), "image/jpeg")},
        data={"doc_type": "photo"},
    ).json()

    refuse = client.post(
        f"/api/assets/{asset_id}/documents",
        files={"file": ("photo.bmp", BytesIO(b"BM fake bitmap"), "image/bmp")},
        data={"doc_type": "photo"},
    )

    assert refuse.status_code == 415
    assert client.get(f"/api/assets/{asset_id}").json()["photo_document_id"] == photo["id"]
    assert client.get(f"/api/documents/{photo['id']}/file").status_code == 200


def test_supprimer_la_facture_dun_entretien(client: TestClient, settings: Settings) -> None:
    """Une facture rattachee a une intervention n'a pas d'`asset_id` : la
    suppression la declarait introuvable, et le fichier restait sur le disque."""
    asset_id = _asset(client)
    task = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={"name": "Revision annuelle", "recurrence_type": "months", "recurrence_interval": 12},
    ).json()
    completed = client.post(
        f"/api/tasks/{task['id']}/complete", json={"performed_on": "2026-03-01"}
    ).json()
    document = client.post(
        f"/api/interventions/{completed['last_intervention_id']}/documents",
        files={"file": ("facture.pdf", BytesIO(FAUX_PDF), "application/pdf")},
    ).json()
    assert len(_fichiers(settings)) == 1

    deleted = client.delete(f"/api/documents/{document['id']}")

    assert deleted.status_code == 200
    assert _fichiers(settings) == []
    assert client.get(f"/api/tasks/{task['id']}/interventions").json()[0]["documents"] == []


def test_une_facture_dentretien_peut_etre_un_lien(client: TestClient) -> None:
    asset_id = _asset(client)
    task = client.post(
        f"/api/assets/{asset_id}/tasks",
        json={"name": "Ramonage", "recurrence_type": "years", "recurrence_interval": 1},
    ).json()
    completed = client.post(
        f"/api/tasks/{task['id']}/complete", json={"performed_on": "2026-03-01"}
    ).json()

    created = client.post(
        f"/api/interventions/{completed['last_intervention_id']}/documents",
        data={
            "storage_mode": "external_link",
            "name": "Facture du ramoneur",
            "url": "https://drive.exemple/facture-ramonage.pdf",
        },
    )

    assert created.status_code == 201
    entry = client.get(f"/api/tasks/{task['id']}/interventions").json()[0]
    assert entry["documents"][0]["url"] == "https://drive.exemple/facture-ramonage.pdf"


def test_document_introuvable(client: TestClient) -> None:
    assert client.patch("/api/documents/4242", json={"name": "Facture"}).status_code == 404
    assert client.delete("/api/documents/4242").status_code == 404
    assert client.get("/api/documents/4242/file").status_code == 404
