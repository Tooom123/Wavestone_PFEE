import type { Health, Role } from "@/lib/types";
import { ROLE_LABELS, RoleBadge } from "./RoleBadge";

function Dot({ ok }: { ok: boolean }) {
  return <span className={`dot ${ok ? "ok" : "ko"}`} aria-label={ok ? "disponible" : "indisponible"} />;
}

export function StatusBar({
  health,
  connection,
  onSettings,
}: {
  health: Health | null;
  connection: string | null;
  onSettings: () => void;
}) {
  return (
    <div className="status">
      {health ? (
        <>
          <span className="chip" title="Serveur de modèles local (Ollama)">
            <Dot ok={health.llm} /> LLM local
          </span>
          <span className="chip" title="Les analyses générées s'exécutent dans un conteneur isolé, sans réseau">
            <Dot ok={health.docker && health.sandbox_image} /> Sandbox Docker
          </span>
          <details className="chip models">
            <summary>Modèles par tâche</summary>
            <ul>
              {(Object.keys(ROLE_LABELS) as Role[]).map((role) => (
                <li key={role}>
                  <RoleBadge role={role} />
                  <code>{health.models[role].name}</code>
                  <Dot ok={health.models[role].installed} />
                </li>
              ))}
            </ul>
          </details>
        </>
      ) : (
        <span className="chip warn" role="status">
          <Dot ok={false} /> {connection ?? "Connexion…"}
        </span>
      )}
      <button className="ghost" onClick={onSettings} aria-label="Réglages de connexion">
        Connexion
      </button>
    </div>
  );
}
