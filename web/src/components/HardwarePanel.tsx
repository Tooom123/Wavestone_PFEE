import type { GpuRow, SystemInfo } from "@/lib/types";

const n = (v: number, digits = 0) => v.toLocaleString("fr-FR", { maximumFractionDigits: digits });

function cell(row: GpuRow, model: string) {
  const m = row.models[model];
  if (!m) return "—";
  return m.fits ? (
    <span className="fit">
      {m.tokens_per_second !== null && (row.is_reference ? `${n(m.tokens_per_second, 1)} (mesuré)` : `≈ ${n(m.tokens_per_second)}`)}
    </span>
  ) : (
    <span className="nofit">ne tient pas</span>
  );
}

/** Le GPU qui porte l'agent, en direct, et ce que d'autres cartes changeraient. */
export function HardwarePanel({ system }: { system: SystemInfo }) {
  const { gpu, live, catalog, models } = system;
  const usedPct = gpu && live ? Math.round((live.memory_used_mb / gpu.memory_total_mb) * 100) : 0;
  const names = models.map((m) => m.name);

  return (
    <section className="hardware" aria-label="Matériel">
      <h2>Le matériel</h2>
      {gpu ? (
        <div className="gpu-card">
          <div className="gpu-head">
            <strong>{gpu.name}</strong>
            <span className="muted">
              {n(gpu.memory_total_mb / 1024, 0)} Go · pilote {gpu.driver} · {n(gpu.power_limit_w)} W max
            </span>
          </div>
          {live && (
            <div className="gpu-live">
              <div className="meter" role="img" aria-label={`Mémoire GPU utilisée : ${usedPct} %`}>
                <div style={{ width: `${usedPct}%` }} />
              </div>
              <span>
                {n(live.memory_used_mb / 1024, 1)} / {n(gpu.memory_total_mb / 1024, 0)} Go · {n(live.power_w)} W ·{" "}
                {n(live.utilization_pct)} % d&apos;activité
              </span>
            </div>
          )}
          <p className="muted small">
            {models.map((m) => `${m.name} (${n(m.size_gb, 1)} Go)`).join(" · ")} — un seul modèle tient en mémoire à la fois.
          </p>
        </div>
      ) : (
        <p className="muted">Aucun GPU NVIDIA détecté sur le serveur.</p>
      )}

      <h3>Et avec un autre GPU ?</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>GPU</th>
              <th className="num">VRAM</th>
              <th className="num">Mémoire <small>Go/s</small></th>
              <th className="num">Puissance</th>
              {names.map((m) => (
                <th key={m} className="num">{m} <small>tok/s</small></th>
              ))}
              <th>Plus gros modèle <small>(Md de param.)</small></th>
              <th>Prix / location</th>
            </tr>
          </thead>
          <tbody>
            {catalog.map((row) => (
              <tr key={row.key} className={row.is_reference ? "ref" : ""}>
                <td>
                  {row.name}
                  {row.is_reference && <span className="badge">ce poste</span>}
                </td>
                <td className="num">{row.vram_gb} Go</td>
                <td className="num">{n(row.bandwidth_gbs)}</td>
                <td className="num">{row.power_w} W</td>
                {names.map((m) => (
                  <td key={m} className="num">{cell(row, m)}</td>
                ))}
                <td>≈ {row.max_params_b}</td>
                <td className="price">{row.cloud_eur_per_hour !== null ? `${n(row.cloud_eur_per_hour, 2)} €/h en location` : row.price_note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">
        Le débit de ce poste est <strong>mesuré</strong> ; celui des autres GPU est <strong>estimé</strong> en le
        proportionnant à la bande passante mémoire, qui limite le décodage. « Plus gros modèle » : règle empirique de
        0,6 Go par milliard de paramètres en Q4. Locations : grille Scaleway hors taxes. Prix d&apos;achat actuels non vérifiés : ils ont fortement varié en
        2026.
      </p>
    </section>
  );
}
