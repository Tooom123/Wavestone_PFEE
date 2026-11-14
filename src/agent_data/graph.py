"""Graphe de l'etage 1 : la boucle agentique.

    profilage -> planification -> [validation humaine] -> generation -> execution
                      ^                                                     |
                      +------------------ critique <------------------------+

La boucle est bornee par `max_iterations` : sans plafond, un critique jamais satisfait
ferait tourner le systeme indefiniment.

Le graphe est construit sur LangGraph quand il est installe ; une implementation
sequentielle equivalente prend le relais sinon, pour que l'etage 1 reste testable sans
dependance lourde.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from agent_data.config import Settings, get_settings
from agent_data.critic import review
from agent_data.critic.critic import redact_data_values
from agent_data.executor import generate_code
from agent_data.llm import LLMClient, Usage, get_client
from agent_data.planner import plan_analysis
from agent_data.profiling import profile_csv
from agent_data.sandbox import DockerSandbox, MountedDataset
from agent_data.schemas import AgentState, AnalysisPlan, ExecutionStatus


@dataclass
class RunTrace:
    """Journal d'un run : ce qui s'est passe a chaque iteration.

    `events` est le journal lisible (console, expander Streamlit). `listener` recoit en plus
    des evenements structures, que l'API relaie au front pour afficher le run en direct.
    """

    events: list[str] = field(default_factory=list)
    listener: Callable[[dict], None] | None = None
    guardrails: list[dict[str, str]] = field(default_factory=list)

    def add(self, message: str) -> None:
        self.events.append(message)

    def block(self, agent: str, name: str, detail: str = "") -> None:
        """Note un garde-fou declenche : qui l'a declenche, lequel, pourquoi.

        L'ordre des declenchements est conserve : c'est le flux qui mene a un blocage
        (code en erreur, puis critique, puis plafond) qui interesse le suivi.
        """
        entry = {"agent": agent, "name": name, "detail": detail[:300]}
        self.guardrails.append(entry)
        self.emit("guardrail", **entry)

    def guardrail_counts(self) -> dict[str, dict[str, int]]:
        """Nombre de declenchements par agent et par garde-fou."""
        counts: dict[str, dict[str, int]] = {}
        for g in self.guardrails:
            per_agent = counts.setdefault(g["agent"], {})
            per_agent[g["name"]] = per_agent.get(g["name"], 0) + 1
        return counts

    def emit(self, kind: str, **data: object) -> None:
        """Signale un evenement structure a l'ecoute eventuelle."""
        if self.listener is not None:
            self.listener({"kind": kind, **data})


PlanApproval = Callable[[AgentState], bool]
"""Fonction de validation humaine du plan. Retourne True pour poursuivre."""


def _always_approve(_: AgentState) -> bool:
    return True


class Stage1:
    """Boucle agentique de l'etage 1."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client: LLMClient | None = None,
        sandbox: DockerSandbox | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        # Un client par role : chaque tache peut etre servie par un modele different. Un
        # client injecte (tests) sert tous les roles.
        self.clients: dict[str, LLMClient] = {
            role: client or get_client(self.settings, role)
            for role in ("planner", "coder", "critic", "synthesis")
        }
        self.client = self.clients["coder"]
        self.sandbox = sandbox or DockerSandbox(self.settings)

    def _plan(self, question: str, state: AgentState, trace: RunTrace) -> AnalysisPlan:
        return _plan_with_guardrails(self, question, state, trace)

    def usage_by_role(self) -> dict[str, dict[str, float | int]]:
        """Tokens et temps consommes par chaque agent depuis la creation de la boucle."""
        out: dict[str, dict[str, float | int]] = {}
        for role, client in self.clients.items():
            usage = getattr(client, "usage", None)
            out[role] = usage.as_dict() if usage is not None else Usage().as_dict()
        return out

    def run(
        self,
        question: str,
        csv_paths: Sequence[Path | str],
        *,
        approve_plan: PlanApproval | None = None,
        trace: RunTrace | None = None,
    ) -> AgentState:
        """Execute la boucle complete et retourne l'etat final."""
        trace = trace or RunTrace()
        approve = approve_plan or _always_approve

        datasets = [MountedDataset(Path(p).stem, Path(p)) for p in csv_paths]
        state = AgentState(
            question=question,
            profiles=[profile_csv(d.host_path, name=d.name) for d in datasets],
            max_iterations=self.settings.max_iterations,
        )
        trace.add(f"profilage : {len(state.profiles)} dataset(s)")
        trace.emit(
            "profile",
            datasets=[
                {"name": p.name, "rows": p.row_count, "columns": len(p.columns)}
                for p in state.profiles
            ],
        )
        known_columns = {c.name for p in state.profiles for c in p.columns}

        trace.emit("stage", name="planner", model=self.settings.model_for("planner"))
        state.plan = self._plan(question, state, trace)
        trace.add(f"plan : {len(state.plan.steps)} etape(s) — {state.plan.restated_question}")
        trace.emit("plan", plan=state.plan.model_dump(mode="json"))

        if not state.plan.answerable:
            # Garde-fou de faisabilite : rien n'est calcule sur une question que les donnees
            # ne couvrent pas, plutot que de fabriquer un indicateur de substitution.
            trace.block("planner", "hors_perimetre", state.plan.unanswerable_reason)
            state.errors.append(f"Question hors perimetre : {state.plan.unanswerable_reason}")
            trace.add("question hors perimetre : arret avant tout calcul")
            return state

        if self.settings.human_validation:
            trace.emit("awaiting_approval")
            if not approve(state):
                state.errors.append("Plan refuse par l'utilisateur.")
                trace.block("humain", "plan_refuse")
                trace.add("plan refuse : arret")
                return state

        previous_error: str | None = None
        best_artifacts: list = []
        while not state.budget_exhausted:
            state.iteration += 1
            trace.add(f"--- iteration {state.iteration}/{state.max_iterations}")
            trace.emit(
                "iteration",
                n=state.iteration,
                max=state.max_iterations,
                model=self.settings.model_for("coder"),
            )

            if state.plan is None:  # pragma: no cover - garanti par le planificateur
                raise RuntimeError("Aucun plan disponible pour generer le code.")
            state.code = generate_code(
                state.plan,
                state.profiles,
                datasets,
                client=self.clients["coder"],
                critique=state.critique,
                previous_code=state.code,
                previous_error=previous_error,
            )
            trace.emit("code", code=state.code)
            state.execution = self.sandbox.run(state.code, datasets=datasets)
            trace.add(
                f"execution : {state.execution.status.value} "
                f"({len(state.execution.artifacts)} artefact(s), "
                f"{state.execution.duration_seconds:.1f}s)"
            )

            if state.execution.status is ExecutionStatus.TIMEOUT:
                trace.block("sandbox", "delai_depasse")
            elif state.execution.status is not ExecutionStatus.SUCCESS:
                trace.block("coder", "code_en_erreur", state.execution.stderr[-200:])

            # L'erreur repart vers l'executeur : elle doit etre expurgee des valeurs de
            # donnees, sans quoi la boucle de correction les reinjecterait dans le LLM.
            previous_error = (
                redact_data_values(state.execution.stderr[-2000:], known_columns=known_columns)
                if state.execution.status is not ExecutionStatus.SUCCESS
                else None
            )
            trace.emit(
                "execution",
                status=state.execution.status.value,
                artifacts=len(state.execution.artifacts),
                seconds=round(state.execution.duration_seconds, 1),
                error=previous_error,
            )
            if len(state.execution.artifacts) > len(best_artifacts):
                best_artifacts = list(state.execution.artifacts)

            trace.emit("stage", name="critic", model=self.settings.model_for("critic"))
            state.critique = review(
                state.plan,
                state.execution,
                client=self.clients["critic"],
                known_columns=known_columns,
            )
            trace.emit(
                "critique",
                satisfactory=state.critique.is_satisfactory,
                issues=state.critique.issues,
                replan=state.critique.replan,
            )

            if state.critique.is_satisfactory:
                state.artifacts = list(state.execution.artifacts)
                trace.add("critique : resultat accepte")
                return state

            trace.add(f"critique : {'; '.join(state.critique.issues)[:200]}")
            trace.block("critic", "resultat_rejete", "; ".join(state.critique.issues))
            if state.critique.replan:
                trace.block("critic", "replanification")
                state.plan = self._plan(question, state, trace)
                trace.add("replanification")
                trace.emit("plan", plan=state.plan.model_dump(mode="json"), replanned=True)

        # Budget epuise : on rend le meilleur resultat obtenu, pas celui de la derniere
        # iteration — une tentative tardive peut avoir echoue alors qu'une precedente
        # avait produit des resultats exploitables.
        state.errors.append(
            f"Plafond de {state.max_iterations} iterations atteint sans resultat satisfaisant."
        )
        trace.block("boucle", "plafond_iterations", f"{state.max_iterations} iterations")
        state.artifacts = list(best_artifacts)
        trace.add(f"budget epuise ({len(state.artifacts)} artefact(s) conserve(s))")
        return state


def _plan_with_guardrails(
    stage: Stage1, question: str, state: AgentState, trace: RunTrace
) -> AnalysisPlan:
    dropped: list[str] = []
    plan = plan_analysis(question, state.profiles, client=stage.clients["planner"], dropped=dropped)
    if dropped:
        trace.block("planner", "colonnes_inventees", ", ".join(sorted(set(dropped))))
    return plan


def build_graph(stage: Stage1):  # pragma: no cover - depend de langgraph
    """Construit le graphe LangGraph equivalent, si LangGraph est disponible.

    L'interet par rapport a :meth:`Stage1.run` est l'outillage : points d'arret,
    reprise, `interrupt` natif pour la validation humaine, et traces par noeud.
    """
    from langgraph.graph import END, StateGraph

    graph = StateGraph(dict)  # type: ignore[type-var]  # etat libre : non utilise en production

    def _plan(state: dict) -> dict:
        profiles = state["profiles"]
        state["plan"] = plan_analysis(state["question"], profiles, client=stage.client)
        return state

    def _execute(state: dict) -> dict:
        state["code"] = generate_code(
            state["plan"], state["profiles"], state["datasets"], client=stage.client
        )
        state["execution"] = stage.sandbox.run(state["code"], datasets=state["datasets"])
        return state

    def _review(state: dict) -> dict:
        state["critique"] = review(state["plan"], state["execution"], client=stage.client)
        state["iteration"] = state.get("iteration", 0) + 1
        return state

    def _next(state: dict) -> str:
        if state["critique"].is_satisfactory:
            return END
        if state["iteration"] >= stage.settings.max_iterations:
            return END
        return "plan" if state["critique"].replan else "execute"

    graph.add_node("plan", _plan)  # type: ignore[type-var]
    graph.add_node("execute", _execute)  # type: ignore[type-var]
    graph.add_node("review", _review)  # type: ignore[type-var]
    graph.set_entry_point("plan")
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", "review")
    graph.add_conditional_edges("review", _next)
    return graph.compile()
