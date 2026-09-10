"""Application FastAPI de MaBarak."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import __version__
from .config import APP_NAME, Settings, get_settings
from .db import create_db_engine, session_factory_for
from .ingress import INGRESS_HEADER, render_index, resolve_base_path
from .migrate import upgrade_to_head
from .routers import assets, catalog, ha, health, house, members
from .services.home import ensure_home

_LOGGER = logging.getLogger(__name__)

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
    engine = create_db_engine(settings)
    app.state.engine = engine
    app.state.session_factory = session_factory_for(engine)
    upgrade_to_head(settings)
    factory = app.state.session_factory
    session: Session = factory()
    try:
        ensure_home(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    _LOGGER.info("%s %s demarre (donnees: %s)", APP_NAME, __version__, settings.data_dir)
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(
        title=f"{APP_NAME} API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.state.settings = settings

    app.include_router(health.router, prefix="/api")
    app.include_router(ha.router, prefix="/api")
    app.include_router(house.router, prefix="/api")
    app.include_router(members.router, prefix="/api")
    app.include_router(assets.router, prefix="/api")
    app.include_router(catalog.router, prefix="/api")

    _mount_frontend(app, settings)
    return app


def _mount_frontend(app: FastAPI, settings: Settings) -> None:
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
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})


app = create_app()
