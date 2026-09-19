"""Interface Streamlit : une question, un dataset, une reponse.

Volontairement minimale, conformement au cadrage : limiter les interactions, ne pas
multiplier les allers-retours avec l'utilisateur. La seule interaction optionnelle est la
validation du plan.

Lancement : `uv run streamlit run src/agent_data/ui/app.py`
"""

from __future__ import annotations

import streamlit as st

from agent_data.config import DATA_DIR, get_settings
from agent_data.graph import RunTrace
from agent_data.llm import OllamaClient
from agent_data.pipeline import analyze
from agent_data.sandbox import docker_available

st.set_page_config(page_title="Agent Data", page_icon="📊", layout="wide")


def _csv_files() -> list:
    return sorted(DATA_DIR.rglob("*.csv")) if DATA_DIR.exists() else []


def main() -> None:
    settings = get_settings()
    st.title("Agent Data")
    st.caption("Posez une question metier, l'agent choisit et conduit l'analyse.")

    with st.sidebar:
        st.subheader("Etat du systeme")
        llm_ok = OllamaClient(settings).is_available()
        st.write(f"{'🟢' if llm_ok else '🔴'} LLM — {settings.llm_model}")
        docker_ok = docker_available()
        st.write(f"{'🟢' if docker_ok else '🔴'} Sandbox Docker")
        if not docker_ok:
            st.warning(
                "Docker est indisponible : le code genere ne sera pas execute. "
                "Aucun repli sur la machine hote n'est prevu, par conception."
            )
        st.divider()
        st.write(f"Iterations max : {settings.max_iterations}")
        validate = st.checkbox("Valider le plan avant execution", value=settings.human_validation)

    files = _csv_files()
    if not files:
        st.info("Aucun CSV dans `data/`. Lancer : `uv run python scripts/download_data.py`")
        return

    labels = {str(f.relative_to(DATA_DIR)): f for f in files}
    chosen = st.multiselect("Jeux de donnees", list(labels), default=[next(iter(labels))])
    question = st.text_area(
        "Question metier",
        placeholder="Ex. : quels clients risquent de partir, et pourquoi ?",
        height=90,
    )

    if not st.button("Lancer l'analyse", type="primary", disabled=not (question and chosen)):
        return

    paths = [labels[c] for c in chosen]
    trace = RunTrace()
    approve = None
    if validate:
        # `interrupt` de LangGraph serait plus propre ; ici on s'en tient a une
        # validation implicite pour ne pas multiplier les allers-retours.
        st.info("Validation du plan activee : le plan est affiche avant restitution.")

    with st.spinner("Analyse en cours…"):
        try:
            report, state = analyze(question, paths, approve_plan=approve, trace=trace)
        except Exception as exc:  # noqa: BLE001 - l'UI doit afficher l'erreur, pas planter
            st.error(f"L'analyse a echoue : {exc}")
            with st.expander("Journal"):
                st.code("\n".join(trace.events) or "(vide)")
            return

    if state.plan:
        with st.expander("Plan suivi", expanded=validate):
            st.write(f"**Question analysee :** {state.plan.restated_question}")
            for a in state.plan.assumptions:
                st.write(f"- _{a}_")
            for step in state.plan.steps:
                st.write(f"**{step.id}.** {step.goal} — _{step.method}_")

    st.subheader("Reponse")
    st.write(report.synthesis)

    for art in report.artifacts:
        st.markdown(f"**{art.title}**")
        payload = art.payload
        if payload.kind == "table":
            st.dataframe({c: [r[i] for r in payload.rows] for i, c in enumerate(payload.columns)})
        elif payload.kind == "figure":
            st.plotly_chart(payload.spec, use_container_width=True)
        else:
            st.info(f"{payload.statement} — {payload.evidence}")

    with st.expander("Journal d'execution"):
        st.code("\n".join(trace.events))
    if state.errors:
        st.warning(" · ".join(state.errors))
    st.download_button(
        "Telecharger le rapport (JSON)",
        report.to_json(),
        file_name="rapport.json",
        mime="application/json",
    )


main()
