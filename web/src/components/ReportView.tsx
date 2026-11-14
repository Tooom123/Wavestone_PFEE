import type { Artifact, Report, RunMetrics } from "@/lib/types";
import { DataTable } from "./DataTable";
import { Plot } from "./Plot";
import { RoleBadge } from "./RoleBadge";
import { Guardrails } from "./Guardrails";
import { RunCost } from "./RunCost";

function ArtifactView({ artifact }: { artifact: Artifact }) {
  const p = artifact.payload;
  if (p.kind === "finding") {
    return (
      <div className="finding">
        <p>{p.statement}</p>
        {p.evidence && <small className="muted">{p.evidence}</small>}
      </div>
    );
  }
  return (
    <figure className="artifact">
      <figcaption>{artifact.title}</figcaption>
      {p.kind === "table" ? <DataTable columns={p.columns} rows={p.rows} /> : <Plot spec={p.spec} />}
    </figure>
  );
}

export function ReportView({ report, model, metrics }: { report: Report; model?: string; metrics?: RunMetrics }) {
  const findings = report.artifacts.filter((a) => a.payload.kind === "finding");
  const visuals = report.artifacts.filter((a) => a.payload.kind !== "finding");

  const download = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
    const link = Object.assign(document.createElement("a"), { href: url, download: "rapport.json" });
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <article className="report" data-role="synthesis">
      <header>
        <span className="eyebrow">Réponse</span>
        {model && <RoleBadge role="synthesis" model={model} />}
      </header>
      <div className="answer">
        {report.synthesis.split(/\n{2,}/).map((para, i) => (
          <p key={i}>{para}</p>
        ))}
      </div>

      {findings.length > 0 && (
        <>
          <h3>Constats</h3>
          <div className="findings">
            {findings.map((a) => (
              <ArtifactView key={a.id} artifact={a} />
            ))}
          </div>
        </>
      )}
      {visuals.length > 0 && (
        <>
          <h3>Résultats détaillés</h3>
          <div className="artifacts">
            {visuals.map((a) => (
              <ArtifactView key={a.id} artifact={a} />
            ))}
          </div>
        </>
      )}
      {metrics?.guardrails && <Guardrails items={metrics.guardrails} />}
      {metrics && <RunCost metrics={metrics} />}
      <footer>
        <button onClick={download}>Télécharger le rapport (JSON)</button>
      </footer>
    </article>
  );
}
