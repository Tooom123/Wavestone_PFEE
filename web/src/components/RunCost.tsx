import { API_PRICES_USD_PER_MTOK, ELECTRICITY_EUR_PER_KWH } from "@/lib/pricing";
import type { Role, RunMetrics } from "@/lib/types";
import { RoleBadge } from "./RoleBadge";

const ROLES: Role[] = ["planner", "coder", "critic", "synthesis"];
const n = (v: number, digits = 0) => v.toLocaleString("fr-FR", { maximumFractionDigits: digits });

/** Ce que le run a consomme, et ce que le meme run aurait coute via une API. */
export function RunCost({ metrics }: { metrics: RunMetrics }) {
  const tokensIn = ROLES.reduce((sum, r) => sum + metrics.usage[r].prompt_tokens, 0);
  const tokensOut = ROLES.reduce((sum, r) => sum + metrics.usage[r].completion_tokens, 0);
  const seconds = metrics.wall_seconds - metrics.approval_wait_seconds;
  const kwh = metrics.gpu.energy_wh / 1000;
  const electricity = kwh * ELECTRICITY_EUR_PER_KWH;

  return (
    <section className="cost" aria-label="Coût du run">
      <h3>Ce que ce run a consommé</h3>
      <div className="kpis">
        <div><strong>{n(seconds)} s</strong><span>de calcul</span></div>
        <div><strong>{n(metrics.gpu.energy_wh, 2)} Wh</strong><span>GPU · moy. {n(metrics.gpu.avg_power_w)} W</span></div>
        <div><strong>{electricity * 100 < 0.01 ? "< 0,01" : n(electricity * 100, 2)} c€</strong><span>d&apos;électricité</span></div>
        <div><strong>{n(tokensIn + tokensOut)}</strong><span>tokens ({n(tokensIn)} lus, {n(tokensOut)} écrits)</span></div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Agent</th>
              <th className="num">Appels</th>
              <th className="num">Tokens lus</th>
              <th className="num">Tokens écrits</th>
              <th className="num">Temps</th>
            </tr>
          </thead>
          <tbody>
            {ROLES.map((role) => {
              const u = metrics.usage[role];
              return (
                <tr key={role}>
                  <td><RoleBadge role={role} model={metrics.models[role]} /></td>
                  <td className="num">{u.calls}</td>
                  <td className="num">{n(u.prompt_tokens)}</td>
                  <td className="num">{n(u.completion_tokens)}</td>
                  <td className="num">{n(u.seconds)} s</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <h4>Le même run via une API (estimation)</h4>
      <div className="table-wrap">
        <table>
          <tbody>
            {API_PRICES_USD_PER_MTOK.map((p) => {
              const usd = (tokensIn * p.input + tokensOut * p.output) / 1e6;
              return (
                <tr key={p.model}>
                  <td>{p.model}</td>
                  <td className="num">{n(usd * 100, 3)} c$</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="muted small">
        Estimation à partir des tokens comptés par les modèles locaux, dont le découpage diffère de celui de Claude :
        un ordre de grandeur, pas une facture. Hors coût du matériel et de la maintenance (voir le benchmark FinOps).
      </p>
    </section>
  );
}
