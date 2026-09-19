"""Point d'entree en ligne de commande."""


def main() -> None:
    print(f"agent-data {__import__('agent_data').__version__}")
