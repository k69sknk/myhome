"""Creation de la maison unique exposee en V1."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..clock import utc_now_iso
from ..models import Home


def ensure_home(session: Session) -> Home:
    home = session.scalars(select(Home).limit(1)).first()
    if home is not None:
        return home
    now = utc_now_iso()
    home = Home(
        name="Ma maison", currency="EUR", due_soon_threshold_days=30, created_at=now, updated_at=now
    )
    session.add(home)
    session.flush()
    return home
