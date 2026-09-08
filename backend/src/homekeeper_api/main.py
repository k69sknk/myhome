"""Application FastAPI de HomeKeeper.

Squelette : seule la route `/api/health` existe. Les routes metier seront ajoutees
apres validation du modele de donnees (docs/DATA_MODEL.md).
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import APP_NAME, Settings, get_settings
from .ingress import INGRESS_HEADER, render_index, resolve_base_path
from .routers import ha, health

_LOGGER = logging.getLogger(__name__)

# Page servie quand aucun build frontend n'est present, ce qui est le cas normal
# en developpement : Vite sert alors l'interface sur son propre port.
_NO_FRONTEND_PAGE = f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>{APP_NAME}</title></head>
<body style="font-family: system-ui; margin: 3rem auto; max-width: 42rem;">
<h1>{APP_NAME} — API</h1>
<p>L'API fonctionne, mais aucun build du frontend n'a ete trouve.</p>
<p>En developpement, lancez l'interface avec <code>npm run dev</code> dans
<code>frontend/</code>. Pour l'add-on, le build est produit par
<code>scripts/stage-addon.sh</code>.</p>
<p><a href="./api/docs">Documentation de l'API</a></p>
</body></html>
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    settings.documents_dir.mkdir(parents=True, exist_ok=True)
    _LOGGER.info("%s %s demarre (donnees: %s)", APP_NAME, __version__, settings.data_dir)
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """Fabrique de l'application. Les tests l'appellent avec leurs propres reglages."""
    settings = settings or get_settings()

    app = FastAPI(
        title=f"{APP_NAME} API",
        version=__version__,
        lifespan=lifespan,
        # Chemins relatifs : l'application est servie derriere un prefixe
        # d'ingress inconnu a la compilation.
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.state.settings = settings

    app.include_router(health.router, prefix="/api")
    app.include_router(ha.router, prefix="/api")

    _mount_frontend(app, settings)
    return app


def _mount_frontend(app: FastAPI, settings: Settings) -> None:
    """Sert la coquille SPA, en y injectant le chemin de base de l'ingress.

    En production, nginx sert les assets hashes directement et ne relaie ici que
    la coquille et l'API. Le montage de `/assets` reste utile pour previsualiser
    un build sans nginx.
    """
    index_file = settings.frontend_dir / "index.html"
    assets_dir = settings.frontend_dir / "assets"

    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(request: Request, full_path: str) -> HTMLResponse:
        if not index_file.is_file():
            return HTMLResponse(_NO_FRONTEND_PAGE, status_code=200)

        base_path = resolve_base_path(request.headers.get(INGRESS_HEADER))
        html = render_index(index_file.read_text(encoding="utf-8"), base_path)

        # La coquille porte le chemin d'ingress, qui change a chaque instance :
        # la mettre en cache servirait un jour un chemin de base perime.
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})


app = create_app()
