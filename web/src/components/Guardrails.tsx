import type { Guardrail } from "@/lib/types";

const AGENTS: Record<string, string> = {
  planner: "Planificateur",
  coder: "Générateur de code",
  sandbox: "Sandbox",
  critic: "Critique",
  boucle: "Boucle",
  humain: "Validation humaine",
};

const NAMES: Record<string, string> = {
  hors_perimetre: "Question hors périmètre : arrêt avant tout calcul",
  colonnes_inventees: "Colonnes inventées retirées du plan",
  code_en_erreur: "Code en erreur, renvoyé pour correction",
  delai_depasse: "Délai d'exécution dépassé",
  resultat_rejete: "Résultat rejeté par la critique",
  replanification: "Nouveau plan demandé",
  plafond_iterations: "Plafond d'itérations atteint",
  plan_refuse: "Plan refusé",
};

/** Les garde-fous déclenchés pendant le run, dans l'ordre : le chemin qui mène au résultat. */
export function Guardrails({ items }: { items: Guardrail[] }) {
  return (
    <section className="guardrails">
      <h3>Garde-fous déclenchés</h3>
      {items.length === 0 ? (
        <p className="muted">Aucun : le premier résultat a été accepté.</p>
      ) : (
        <ol>
          {items.map((g, i) => (
            <li key={i} title={g.detail || undefined}>
              <strong>{AGENTS[g.agent] ?? g.agent}</strong> — {NAMES[g.name] ?? g.name}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
