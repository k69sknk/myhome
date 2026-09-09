# =============================================================================
# Image de l'add-on MaBarak
# =============================================================================
#
# IMPORTANT — artefacts pre-construits.
#
# Le builder Home Assistant utilise le repertoire de l'add-on comme contexte de
# build. Ce Dockerfile ne peut donc PAS atteindre ../../backend ni ../../frontend.
# Les artefacts doivent etre stages dans ce dossier au prealable :
#
#     ./scripts/stage-addon.sh
#
# qui produit :
#     addon/mabarak/pkg/   <- source du paquet Python
#     addon/mabarak/www/   <- build Vite du frontend
#
# Ces repertoires sont versionnes : le Supervisor Home Assistant ne lance pas
# le script de stage, il construit uniquement depuis ce dossier.
# =============================================================================

ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:trixie
FROM ${BUILD_FROM}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    MABARAK_DATA_DIR=/data

# Debian trixie fournit Python 3.13. nginx sert les assets statiques et filtre
# les adresses IP ; il ne fait pas de reecriture de contenu, l'injection du
# chemin d'ingress est faite par le backend.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        python3 \
        python3-venv \
        nginx \
        tzdata \
        ca-certificates; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/* /etc/nginx/sites-enabled/default

RUN python3 -m venv "${VIRTUAL_ENV}" \
    && "${VIRTUAL_ENV}/bin/pip" install --upgrade pip setuptools wheel

# Backend : installe comme un vrai paquet, pas monte en source.
COPY pkg /tmp/mabarak-src
RUN "${VIRTUAL_ENV}/bin/pip" install /tmp/mabarak-src \
    && rm -rf /tmp/mabarak-src

# Frontend : build statique servi par nginx.
COPY www /usr/share/mabarak/www

# Services s6-overlay et configuration nginx.
COPY rootfs /
RUN chmod +x \
        /etc/s6-overlay/s6-rc.d/init-mabarak/run \
        /etc/s6-overlay/s6-rc.d/mabarak-api/run \
        /etc/s6-overlay/s6-rc.d/mabarak-api/finish \
        /etc/s6-overlay/s6-rc.d/nginx/run \
        /etc/s6-overlay/s6-rc.d/nginx/finish

# Etiquettes renseignees par le builder Home Assistant.
ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_DESCRIPTION
ARG BUILD_NAME
ARG BUILD_REF
ARG BUILD_REPOSITORY
ARG BUILD_VERSION

LABEL \
    io.hass.name="${BUILD_NAME}" \
    io.hass.description="${BUILD_DESCRIPTION}" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version="${BUILD_VERSION}" \
    org.opencontainers.image.created="${BUILD_DATE}" \
    org.opencontainers.image.revision="${BUILD_REF}" \
    org.opencontainers.image.source="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.version="${BUILD_VERSION}"
