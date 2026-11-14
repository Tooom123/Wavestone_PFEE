"""Modeles de donnees partages par les deux etages de l'agent.

Trois contrats structurent le systeme :

- :class:`DatasetProfile` est le **seul** objet issu des donnees qui entre dans le contexte
  du LLM. Il ne contient que des metadonnees et des statistiques agregees, jamais de lignes
  brutes (cf. parti pris 1 : le LLM ne voit jamais les donnees).
- :class:`AnalysisPlan` porte la traduction question metier -> question statistique bien
  posee. C'est la piece qui porte la valeur du systeme.
- :class:`Artifact` est le contrat entre l'etage 1 (generation et execution du code) et
  l'etage 2 (restitution). Streamlit et le rapport Word/PDF sont deux renderers du meme JSON.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Base(BaseModel):
    """Base commune : interdit les champs inconnus pour garder les contrats stricts."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- profil


class ColumnKind(StrEnum):
    """Nature d'une colonne, telle que l'agent doit la raisonner."""

    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    TEXT = "text"


class NumericStats(Base):
    """Statistiques descriptives d'une colonne numerique."""

    min: float | None = None
    max: float | None = None
    mean: float | None = None
    std: float | None = None
    p25: float | None = None
    median: float | None = None
    p75: float | None = None


class ColumnProfile(Base):
    """Profil d'une colonne. Aucune valeur brute hormis un echantillon de modalites."""

    name: str
    kind: ColumnKind
    dtype: str = Field(description="dtype pandas d'origine, ex. 'int64'")
    null_count: int = Field(ge=0)
    null_ratio: Annotated[float, Field(ge=0.0, le=1.0)]
    unique_count: int = Field(ge=0)
    stats: NumericStats | None = Field(
        default=None, description="Renseigne pour les colonnes numeriques uniquement"
    )
    top_values: list[str] = Field(
        default_factory=list,
        description=(
            "Modalites les plus frequentes d'une colonne categorielle. Tronque : sert a "
            "orienter le plan, pas a transmettre les donnees."
        ),
    )
    date_range: tuple[str, str] | None = Field(
        default=None,
        description=(
            "Premiere et derniere date d'une colonne de dates (ISO). Permet au planificateur "
            "de voir qu'une question sur une periode non couverte est hors perimetre."
        ),
    )


class DatasetProfile(Base):
    """Profil complet d'un CSV. Seul objet transmis au LLM."""

    name: str = Field(description="Identifiant court du dataset")
    source_path: str = Field(description="Chemin local du CSV ; jamais son contenu")
    row_count: int = Field(ge=0)
    columns: list[ColumnProfile]
    size_mb: float = Field(default=0.0, ge=0.0, description="Taille du fichier source, en Mo")
    profiling: str = Field(
        default="pandas, fichier complet",
        description="Comment le profil a ete calcule (moteur, echantillon eventuel)",
    )
    profiled_at: datetime = Field(default_factory=datetime.now)

    def column(self, name: str) -> ColumnProfile | None:
        """Retourne le profil de la colonne `name`, ou None si absente."""
        return next((c for c in self.columns if c.name == name), None)


# ----------------------------------------------------------------------------- plan


class AnalysisStep(Base):
    """Une etape du plan d'analyse, formulee en intention, pas en code."""

    id: str = Field(description="Identifiant court, reference par les artefacts produits")
    goal: str = Field(description="Ce que l'etape doit etablir, en une phrase")
    method: str = Field(description="Approche statistique ou ML envisagee")
    columns: list[str] = Field(
        default_factory=list, description="Colonnes mobilisees, telles que nommees dans le profil"
    )
    rationale: str = Field(
        default="", description="Pourquoi cette etape repond a la question metier"
    )


class AnalysisPlan(Base):
    """Traduction de la question metier en demarche d'analyse structuree."""

    question: str = Field(description="Question metier d'origine, verbatim")
    restated_question: str = Field(
        description="Reformulation en question statistique bien posee, avec ses hypotheses"
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Definitions retenues quand la question est ambigue (ex. ce qu'est une "
        "'bonne' vente)",
    )
    steps: list[AnalysisStep] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list, description="Noms des datasets mobilises")
    answerable: bool = Field(
        default=True,
        description="Faux quand les donnees ne permettent pas de repondre a la question",
    )
    unanswerable_reason: str = Field(
        default="", description="Ce qui manque dans les donnees, quand answerable est faux"
    )

    @model_validator(mode="after")
    def _steps_if_answerable(self) -> AnalysisPlan:
        if self.answerable and not self.steps:
            raise ValueError("Un plan realisable doit comporter au moins une etape.")
        return self


# ------------------------------------------------------------------------ artefacts


class Table(Base):
    """Resultat tabulaire agrege, pret a l'affichage."""

    kind: Literal["table"] = "table"
    columns: list[str]
    rows: list[list[Any]]


class Figure(Base):
    """Figure Plotly serialisee : reutilisable par le web comme par le PDF."""

    kind: Literal["figure"] = "figure"
    spec: dict[str, Any] = Field(description="Figure Plotly au format JSON (data + layout)")


class Finding(Base):
    """Constat en langage naturel, adosse a un resultat chiffre."""

    kind: Literal["finding"] = "finding"
    statement: str = Field(description="Le constat, en une phrase")
    evidence: str = Field(default="", description="Le chiffre ou le test qui l'appuie")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = 0.5


ArtifactPayload = Annotated[Table | Figure | Finding, Field(discriminator="kind")]


class Artifact(Base):
    """Unite de resultat produite par l'etage 1 et consommee par l'etage 2."""

    id: str
    step_id: str = Field(description="Etape du plan dont cet artefact decoule")
    title: str
    payload: ArtifactPayload


# ------------------------------------------------------------------------ execution


class ExecutionStatus(StrEnum):
    """Issue d'une execution de code dans le sandbox."""

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


class ExecutionResult(Base):
    """Ce que le sandbox renvoie apres avoir execute le code genere."""

    status: ExecutionStatus
    stdout: str = ""
    stderr: str = ""
    artifacts: list[Artifact] = Field(default_factory=list)
    duration_seconds: float = Field(default=0.0, ge=0.0)

    @property
    def ok(self) -> bool:
        """Vrai si l'execution s'est terminee sans erreur."""
        return self.status is ExecutionStatus.SUCCESS


class Critique(Base):
    """Verdict du critique sur un resultat d'execution."""

    is_satisfactory: bool
    issues: list[str] = Field(default_factory=list)
    suggestion: str = Field(
        default="", description="Correction a apporter si le resultat n'est pas satisfaisant"
    )
    replan: bool = Field(
        default=False, description="Vrai si la correction impose de repasser par le planificateur"
    )


# ----------------------------------------------------------------------------- etat


class AgentState(Base):
    """Etat partage circulant dans le graphe LangGraph de l'etage 1."""

    question: str
    profiles: list[DatasetProfile] = Field(default_factory=list)
    plan: AnalysisPlan | None = None
    code: str | None = Field(default=None, description="Dernier code Python genere")
    execution: ExecutionResult | None = None
    critique: Critique | None = None
    artifacts: list[Artifact] = Field(default_factory=list)
    iteration: int = Field(default=0, ge=0)
    max_iterations: int = Field(default=5, ge=1)
    errors: list[str] = Field(default_factory=list)

    @property
    def budget_exhausted(self) -> bool:
        """Vrai quand le plafond d'iterations est atteint : la boucle doit s'arreter."""
        return self.iteration >= self.max_iterations
