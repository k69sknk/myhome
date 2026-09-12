"""Recuperer un fichier sur le reseau local, et nulle part ailleurs (adr/0015).

Un agent conversationnel tourne rarement sur la machine de Home Assistant. Pour
qu'il puisse joindre une facture a une fiche, il faut que les octets voyagent —
et aucun des chemins evidents ne convient : un appel de service les ecrirait
dans la base de Home Assistant (son enregistreur conserve les donnees de chaque
appel), et un dossier partage suppose un systeme de fichiers commun.

Reste celui-ci : l'agent expose le fichier a une URL, MaBarak va le chercher.

Le garde-fou tient en une regle : **l'adresse visee doit etre privee**. C'est ce
qui empeche cette route de devenir un moyen de faire sortir des donnees de la
maison, ou d'aller chercher n'importe quoi sur Internet au nom de l'add-on. Le
local-first du produit est une propriete du code, pas une intention.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from pathlib import Path
from urllib.parse import unquote, urlparse
from uuid import uuid4

import httpx

from ..config import Settings
from .documents import ALLOWED_EXTENSIONS, MAX_SIZE, StoredFile

_LOGGER = logging.getLogger(__name__)

# Assez pour un scan de facture ou une notice ; au-dela, c'est un lien qu'il
# faut enregistrer, pas une copie.
TIMEOUT_SECONDES = 30


class TelechargementRefuseError(Exception):
    """La source est refusee, ou le contenu ne convient pas.

    Le message est destine a etre relu tel quel : c'est lui qui dit a l'agent
    quoi corriger.
    """


def _adresses(hote: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(hote, None)
    except socket.gaierror as exc:
        raise TelechargementRefuseError(
            f"Le nom « {hote} » est introuvable sur le reseau."
        ) from exc
    return [ipaddress.ip_address(info[4][0]) for info in infos]


def verifier_source(url: str) -> None:
    """Refuse tout ce qui n'est pas une adresse privee, avant d'ouvrir quoi que ce soit.

    La verification porte sur **toutes** les adresses resolues, et non sur la
    premiere : un nom qui pointe a la fois vers une adresse privee et une
    publique ne doit pas passer.
    """
    morceaux = urlparse(url)
    if morceaux.scheme not in ("http", "https"):
        raise TelechargementRefuseError(
            "Seules les adresses http:// et https:// peuvent etre telechargees."
        )
    if not morceaux.hostname:
        raise TelechargementRefuseError(f"« {url} » n'est pas une adresse valide.")

    adresses = _adresses(morceaux.hostname)
    publiques = [adresse for adresse in adresses if not adresse.is_private]
    if publiques:
        raise TelechargementRefuseError(
            f"MaBarak ne telecharge que depuis le reseau local, et « {morceaux.hostname} » "
            f"repond sur {publiques[0]}, une adresse publique. Pour un document qui vit "
            "ailleurs, enregistrez plutot son lien : il sera garde tel quel, sans copie."
        )


def _extension(url: str, entetes: httpx.Headers) -> str:
    """L'extension du fichier, deduite du nom transmis ou de l'URL.

    Le type MIME n'est volontairement pas utilise pour choisir : un serveur
    approximatif annonce `application/octet-stream` pour tout, et on se
    retrouverait a ranger un PDF sans extension.
    """
    disposition = entetes.get("content-disposition", "")
    if "filename=" in disposition:
        nom = disposition.split("filename=", 1)[1].strip().strip('"; ')
        extension = Path(unquote(nom)).suffix.lower()
        if extension in ALLOWED_EXTENSIONS:
            return extension

    extension = Path(unquote(urlparse(url).path)).suffix.lower()
    if extension in ALLOWED_EXTENSIONS:
        return extension

    acceptees = ", ".join(sorted(ALLOWED_EXTENSIONS))
    raise TelechargementRefuseError(
        f"Impossible de deviner le type du fichier a partir de « {url} ». "
        f"L'adresse doit se terminer par une extension acceptee ({acceptees})."
    )


def telecharger(url: str, settings: Settings, *, scope: str) -> StoredFile:
    """Telecharge le fichier et l'ecrit dans /data, comme un import manuel.

    Les redirections ne sont pas suivies : une redirection peut sortir du
    reseau local apres coup, et la verifier a chaque saut compliquerait le code
    pour un cas que personne n'a demande. Un refus explicite vaut mieux.
    """
    verifier_source(url)

    try:
        with (
            httpx.Client(follow_redirects=False, timeout=TIMEOUT_SECONDES) as client,
            client.stream("GET", url) as reponse,
        ):
            if reponse.is_redirect:
                raise TelechargementRefuseError(
                    "L'adresse redirige ailleurs. Donnez l'adresse finale du fichier."
                )
            reponse.raise_for_status()

            extension = _extension(url, reponse.headers)
            contenu = bytearray()
            for bloc in reponse.iter_bytes():
                contenu.extend(bloc)
                # Verifie a chaque bloc, et non sur `Content-Length` : un
                # serveur peut mentir sur la taille annoncee, ou n'en
                # annoncer aucune.
                if len(contenu) > MAX_SIZE:
                    raise TelechargementRefuseError(
                        f"Le fichier depasse {MAX_SIZE // (1024 * 1024)} Mo. "
                        "Enregistrez plutot son lien."
                    )
    except httpx.HTTPStatusError as exc:
        raise TelechargementRefuseError(
            f"Le serveur a repondu {exc.response.status_code} pour « {url} »."
        ) from exc
    except httpx.HTTPError as exc:
        raise TelechargementRefuseError(f"« {url} » est injoignable : {exc}") from exc

    if not contenu:
        raise TelechargementRefuseError(f"« {url} » a rendu un fichier vide.")

    repertoire = settings.documents_dir / scope
    repertoire.mkdir(parents=True, exist_ok=True)
    nom_stocke = f"{uuid4().hex}{extension}"
    (repertoire / nom_stocke).write_bytes(bytes(contenu))

    _LOGGER.info("Document telecharge depuis %s (%d octets)", url, len(contenu))
    return StoredFile(
        file_path=f"{scope}/{nom_stocke}",
        file_size=len(contenu),
        mime_type=None,
        original_name=Path(unquote(urlparse(url).path)).name or f"document{extension}",
    )
