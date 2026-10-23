import type { Role } from "@/lib/types";

export const ROLE_LABELS: Record<Role, string> = {
  planner: "Plan",
  coder: "Code",
  critic: "Critique",
  synthesis: "Réponse",
};

/** Pastille d'un agent : sa couleur est la meme partout, de la barre d'etat au rapport. */
export function RoleBadge({ role, model }: { role: Role; model?: string }) {
  return (
    <span className="role" data-role={role} title={model ? `Agent ${ROLE_LABELS[role]} : ${model}` : undefined}>
      <i aria-hidden />
      {ROLE_LABELS[role]}
      {model && <code>{model}</code>}
    </span>
  );
}
