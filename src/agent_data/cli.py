"""Ligne de commande de l'agent.

uv run agent-data check                       # etat du systeme
uv run agent-data profile data/**/*.csv       # profil d'un dataset
uv run agent-data ask "..." -d data/x.csv     # analyse complete
uv run agent-data serve                       # API du front web
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent_data.config import DATA_DIR, get_settings


def _cmd_check(_: argparse.Namespace) -> int:
    """Verifie que les prerequis d'un run sont reunis."""
    from agent_data.llm import OllamaClient
    from agent_data.sandbox import DockerSandbox, docker_available

    settings = get_settings()
    print(f"Fournisseur LLM  : {settings.llm_provider} ({settings.llm_model})")

    ollama = OllamaClient(settings)
    llm_ok = settings.llm_provider != "ollama" or ollama.is_available()
    print(f"  serveur        : {'joignable' if llm_ok else 'INJOIGNABLE'}")
    if llm_ok and settings.llm_provider == "ollama":
        models = ollama.installed_models()
        present = settings.llm_model in models
        etat = "present" if present else f"ABSENT — ollama pull {settings.llm_model}"
        print(f"  modele         : {etat}")
        llm_ok = present

    docker_ok = docker_available()
    print(f"Sandbox Docker   : {'disponible' if docker_ok else 'INDISPONIBLE'}")
    image_ok = docker_ok and DockerSandbox(settings).image_exists()
    if docker_ok:
        print(f"  image          : {'construite' if image_ok else 'ABSENTE — ./scripts/setup.sh'}")

    csvs = sorted(DATA_DIR.rglob("*.csv")) if DATA_DIR.exists() else []
    print(f"Jeux de donnees  : {len(csvs)} CSV dans data/")
    for path in csvs:
        print(f"  - {path.relative_to(DATA_DIR)}")

    ready = llm_ok and image_ok and bool(csvs)
    print()
    print("Systeme pret." if ready else "Systeme incomplet : lancer ./scripts/setup.sh")
    return 0 if ready else 1


def _cmd_profile(args: argparse.Namespace) -> int:
    """Affiche le profil d'un CSV — exactement ce que verra le LLM."""
    from agent_data.profiling import profile_csv

    for raw in args.csv:
        profile = profile_csv(raw)
        print(f"\n{profile.name} — {profile.row_count} lignes, {len(profile.columns)} colonnes")
        for col in profile.columns:
            line = (
                f"  {col.name:28} {col.kind.value:12} "
                f"nulls={col.null_ratio:6.1%} uniq={col.unique_count}"
            )
            if col.top_values:
                line += f"  {col.top_values[:4]}"
            print(line)
        if args.json:
            print(profile.model_dump_json(indent=2))
    return 0


def _cmd_ask(args: argparse.Namespace) -> int:
    """Lance une analyse complete."""
    from agent_data.graph import RunTrace
    from agent_data.pipeline import analyze
    from agent_data.sandbox import SandboxUnavailableError

    paths = [Path(p) for p in args.dataset]
    missing = [p for p in paths if not p.exists()]
    if missing:
        print(f"CSV introuvable(s) : {', '.join(str(m) for m in missing)}", file=sys.stderr)
        return 1

    trace = RunTrace()
    try:
        report, state = analyze(args.question, paths, trace=trace)
    except SandboxUnavailableError as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 1
    except (RuntimeError, ValueError) as exc:
        print(f"\nL'analyse a echoue : {exc}", file=sys.stderr)
        for event in trace.events:
            print(f"  {event}", file=sys.stderr)
        return 1

    if args.verbose:
        print("Journal :")
        for event in trace.events:
            print(f"  {event}")
        print()

    print(report.to_markdown())
    if args.output:
        report.to_json(args.output)
        print(f"\nRapport ecrit dans {args.output}")
    if state.errors:
        print(f"\nAvertissements : {' · '.join(state.errors)}", file=sys.stderr)
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    """Demarre l'API de demonstration consommee par le front web."""
    import secrets

    import uvicorn

    settings = get_settings()
    if args.public and not settings.api_token:
        # Une API qui genere et execute du code ne s'expose jamais sans jeton.
        token = secrets.token_urlsafe(24)
        import os

        os.environ["API_TOKEN"] = token
        get_settings.cache_clear()
        print(f"Jeton d'acces genere (a saisir dans le front) : {token}\n")
    uvicorn.run(
        "agent_data.api:create_app", factory=True, host=args.host, port=args.port, log_level="info"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-data", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Verifie l'etat du systeme")
    check.set_defaults(func=_cmd_check)

    profile = sub.add_parser("profile", help="Affiche le profil d'un CSV")
    profile.add_argument("csv", nargs="+", help="Chemins des CSV a profiler")
    profile.add_argument("--json", action="store_true", help="Affiche aussi le profil JSON brut")
    profile.set_defaults(func=_cmd_profile)

    ask = sub.add_parser("ask", help="Pose une question metier")
    ask.add_argument("question", help="La question, en langage naturel")
    ask.add_argument("-d", "--dataset", action="append", required=True, help="CSV a analyser")
    ask.add_argument("-o", "--output", help="Ecrit le rapport JSON dans ce fichier")
    ask.add_argument("-v", "--verbose", action="store_true", help="Affiche le journal du run")
    ask.set_defaults(func=_cmd_ask)

    serve = sub.add_parser("serve", help="Demarre l'API du front web")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument(
        "--public",
        action="store_true",
        help="Prevu pour etre expose (tunnel) : genere un jeton si aucun n'est configure",
    )
    serve.set_defaults(func=_cmd_serve)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    raise SystemExit(args.func(args))
