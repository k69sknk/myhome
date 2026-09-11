"""Les metiers des prestataires : la liste integree, et ce qu'elle ignore.

`catalog/trades.yaml` fait foi pour les metiers integres — c'est un contrat, on
n'y renomme jamais un slug (adr/0008). Mais la liste est volontairement courte,
et courte veut dire incomplete : un vitrier, un cuisiniste, un antenniste n'y
sont pas. Jusqu'ici ils devenaient « Autre », ce qui revient a oublier qui on
appelle.

La table `trade` recoit donc les deux : le seed de la liste versionnee, rejoue a
chaque demarrage pour qu'un metier ajoute au fichier rejoigne les installations
existantes, et les metiers saisis par l'utilisateur. Le seed n'ecrase jamais un
nom : un metier integre renomme par l'utilisateur le reste.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..catalog import load_trades
from ..clock import utc_now_iso
from ..models import Trade
from .catalog import slugify

# « Autre » ferme la liste : c'est le choix de ne pas repondre, pas un metier.
FALLBACK_SLUG = "autre"
FALLBACK_SORT = 1000

# Les metiers saisis par l'utilisateur se rangent apres les integres, avant
# « Autre » : ce sont des metiers a part entiere, pas un appendice.
CUSTOM_SORT = 500


def ensure_trades(session: Session) -> None:
    """Sema les metiers integres manquants. Idempotent, appele au demarrage."""
    known = set(session.scalars(select(Trade.slug)))
    now = utc_now_iso()
    for position, trade in enumerate(load_trades(), start=1):
        if trade.slug in known:
            continue
        session.add(
            Trade(
                slug=trade.slug,
                name=trade.label,
                is_builtin=1,
                sort_order=FALLBACK_SORT if trade.slug == FALLBACK_SLUG else position * 10,
                created_at=now,
                updated_at=now,
            )
        )


def list_trades(session: Session) -> list[Trade]:
    return list(session.scalars(select(Trade).order_by(Trade.sort_order, Trade.name)))


def trade_for_name(session: Session, name: str) -> Trade:
    """Le metier portant ce nom, cree s'il n'existe pas encore.

    Deux saisies qui ne different que par la casse ou les accents designent le
    meme metier : « Vitrier » et « vitrier » donnent le meme slug, et la seconde
    retrouve la premiere au lieu de lui faire un sosie (meme regle que pour les
    objets du didacticiel en 0.24).
    """
    slug = slugify(name)
    existing = session.scalar(select(Trade).where(Trade.slug == slug))
    if existing is not None:
        return existing
    now = utc_now_iso()
    row = Trade(
        slug=slug,
        name=name.strip(),
        is_builtin=0,
        sort_order=CUSTOM_SORT,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    return row
