"""Contrat consomme par l'integration Home Assistant.

`/api/ha/summary` est l'unique point de couplage entre l'add-on et l'integration
(docs/ARCHITECTURE.md section 5.3). Il est declare des maintenant, avec une
reponse vide mais conforme, pour deux raisons :

* la chaine add-on vers integration est testable de bout en bout des le squelette ;
* le contrat, qui doit rester stable entre deux versions installees separement
  (ADR-0005), est fige avant que quoi que ce soit ne le consomme.

Les valeurs seront calculees par `homekeeper_api.services` a partir de la vue SQL
`v_task_status`, une fois le modele de donnees valide.
"""

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..config import API_SCHEMA_VERSION

router = APIRouter(prefix="/ha", tags=["home assistant"])

TaskStatus = Literal["ok", "due_soon", "overdue", "unscheduled"]


class SummaryCounts(BaseModel):
    overdue: int = 0
    due_soon: int = 0
    ok: int = 0
    unscheduled: int = 0


class NextTask(BaseModel):
    id: int
    name: str
    asset_name: str | None = None
    due_date: str
    days_until: int


class AssetStatus(BaseModel):
    id: int
    name: str
    status: TaskStatus


class ExpiringWarranty(BaseModel):
    asset_id: int
    asset_name: str
    end_date: str


class HaSummary(BaseModel):
    """Etat agrege de la maison, projete en entites Home Assistant."""

    api_schema_version: int = Field(
        default=API_SCHEMA_VERSION,
        description=(
            "Version du contrat. L'integration la lit pour detecter un add-on "
            "trop ancien et le signaler explicitement."
        ),
    )
    generated_at: datetime
    counts: SummaryCounts
    next_task: NextTask | None = None
    assets: list[AssetStatus] = Field(default_factory=list)
    warranties_expiring: list[ExpiringWarranty] = Field(default_factory=list)


@router.get("/summary", response_model=HaSummary, summary="Synthese pour Home Assistant")
def summary() -> HaSummary:
    return HaSummary(generated_at=datetime.now(UTC), counts=SummaryCounts())
