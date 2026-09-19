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

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from agent_data.config import Settings, get_settings
from agent_data.critic import review
from agent_data.critic.critic import redact_data_values
from agent_data.executor import generate_code
from agent_data.llm import LLMClient, get_client
from agent_data.planner import plan_analysis
from agent_data.profiling import profile_csv
from agent_data.sandbox import DockerSandbox, MountedDataset
from agent_data.schemas import AgentState, ExecutionStatus


@dataclass
class RunTrace:
    """Journal d'un run : ce qui s'est passe a chaque iteration."""

    events: list[str] = field(default_factory=list)

    def add(self, message: str) -> None:
        self.events.append(message)


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
        self.client = client or get_client(self.settings)
        self.sandbox = sandbox or DockerSandbox(self.settings)

    def run(
        self,
        question: str,
        csv_paths: list[Path | str],
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
        known_columns = {c.name for p in state.profiles for c in p.columns}

        state.plan = plan_analysis(question, state.profiles, client=self.client)
        trace.add(f"plan : {len(state.plan.steps)} etape(s) — {state.plan.restated_question}")

        if self.settings.human_validation and not approve(state):
            state.errors.append("Plan refuse par l'utilisateur.")
            trace.add("plan refuse : arret")
            return state

        previous_error: str | None = None
        while not state.budget_exhausted:
            state.iteration += 1
            trace.add(f"--- iteration {state.iteration}/{state.max_iterations}")

            assert state.plan is not None
            state.code = generate_code(
                state.plan,
                state.profiles,
                datasets,
                client=self.client,
                critique=state.critique,
                previous_code=state.code,
                previous_error=previous_error,
            )
            state.execution = self.sandbox.run(state.code, datasets=datasets)
            trace.add(
                f"execution : {state.execution.status.value} "
                f"({len(state.execution.artifacts)} artefact(s), "
                f"{state.execution.duration_seconds:.1f}s)"
            )

            # L'erreur repart vers l'executeur : elle doit etre expurgee des valeurs de
            # donnees, sans quoi la boucle de correction les reinjecterait dans le LLM.
            previous_error = (
                redact_data_values(state.execution.stderr[-2000:], known_columns=known_columns)
                if state.execution.status is not ExecutionStatus.SUCCESS
                else None
            )
            state.critique = review(
                state.plan, state.execution, client=self.client, known_columns=known_columns
            )

            if state.critique.is_satisfactory:
                state.artifacts = list(state.execution.artifacts)
                trace.add("critique : resultat accepte")
                return state

            trace.add(f"critique : {'; '.join(state.critique.issues)[:200]}")
            if state.critique.replan:
                state.plan = plan_analysis(question, state.profiles, client=self.client)
                trace.add("replanification")

        # Budget epuise : on rend le meilleur resultat disponible plutot que rien.
        state.errors.append(
            f"Plafond de {state.max_iterations} iterations atteint sans resultat satisfaisant."
        )
        if state.execution:
            state.artifacts = list(state.execution.artifacts)
        trace.add("budget epuise")
        return state


def build_graph(stage: Stage1):  # pragma: no cover - depend de langgraph
    """Construit le graphe LangGraph equivalent, si LangGraph est disponible.

    L'interet par rapport a :meth:`Stage1.run` est l'outillage : points d'arret,
    reprise, `interrupt` natif pour la validation humaine, et traces par noeud.
    """
    from langgraph.graph import END, StateGraph

    graph = StateGraph(dict)

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

    graph.add_node("plan", _plan)
    graph.add_node("execute", _execute)
    graph.add_node("review", _review)
    graph.set_entry_point("plan")
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", "review")
    graph.add_conditional_edges("review", _next)
    return graph.compile()
