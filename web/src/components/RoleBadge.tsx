import type { Role } from "@/lib/types";

/** Les cinq etapes d'un run : le profilage (pandas) puis les quatre agents (LLM). */
export type StepRole = Role | "profile";

export const ROLE_LABELS: Record<StepRole, string> = {
  profile: "Profil",
  planner: "Plan",
  coder: "Code",
  critic: "Critique",
  synthesis: "Réponse",
};

/** Pastille d'une etape : sa couleur est la meme partout, de la barre d'etat au rapport. */
export function RoleBadge({ role, model }: { role: StepRole; model?: string }) {
  return (
    <span className="role" data-role={role} title={model ? `${ROLE_LABELS[role]} : ${model}` : undefined}>
      <i aria-hidden />
      {ROLE_LABELS[role]}
      {model && <code>{model}</code>}
    </span>
  );
}
