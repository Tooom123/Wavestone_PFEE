"use client";

import { useEffect, useState } from "react";
import type { Iteration, RunState } from "@/lib/run-state";
import { ReportView } from "./ReportView";

function useElapsed(run: RunState) {
  const [now, setNow] = useState(() => Date.now());
  const active = run.phase === "running" || run.phase === "awaiting";
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(timer);
  }, [active]);
  if (!run.startedAt) return "";
  return `${Math.round(((run.finishedAt ?? now) - run.startedAt) / 1000)} s`;
}

function Idle() {
  return (
    <div className="idle">
      <h2>Une question, une analyse conduite de bout en bout</h2>
      <p className="lead">
        L&apos;agent ne déroule pas une procédure figée : il traduit votre question en démarche statistique, écrit le code,
        l&apos;exécute, relit le résultat et se corrige.
      </p>
      <ol className="steps">
        <li><strong>Profil</strong><span>Le modèle ne voit que le schéma et des statistiques agrégées, jamais les lignes.</span></li>
        <li><strong>Plan</strong><span>La question métier devient une question statistique explicite, avec ses hypothèses.</span></li>
        <li><strong>Code</strong><span>Du pandas / scikit-learn réellement exécuté, dans un conteneur sans réseau.</span></li>
        <li><strong>Critique</strong><span>Le résultat est relu ; en cas d&apos;échec, le code est corrigé.</span></li>
        <li><strong>Réponse</strong><span>Les résultats chiffrés sont traduits en langage de décideur.</span></li>
      </ol>
    </div>
  );
}

/** Pourquoi l'essai est rejete, et ce que l'agent en fait : c'est la boucle de correction. */
function reason(it: Iteration): string {
  const issue = it.critique?.issues[0]?.split("\n").find((l) => l.trim() && !l.startsWith("Le code a echoue"));
  const next = it.critique?.replan ? "replanification" : "correction du code";
  return `${issue ?? "résultat insuffisant"} → ${next}`;
}

function IterationView({ it, isLast, running }: { it: Iteration; isLast: boolean; running: boolean }) {
  const status = it.execution?.status;
  return (
    <details className="iteration" open={isLast}>
      <summary>
        <span className={`pill ${status === "success" ? "ok" : status ? "ko" : "wait"}`}>
          {status === "success" ? "exécuté" : status === "timeout" ? "timeout" : status ? "échec" : "en cours"}
        </span>
        Essai {it.n}
        <span className="badge">{it.model}</span>
        {it.execution && <span className="muted"> · {it.execution.seconds} s · {it.execution.artifacts} artefact(s)</span>}
        {it.critique && !it.critique.satisfactory && (
          <span className="why">{reason(it)}</span>
        )}
      </summary>
      {it.code && (
        <details className="code">
          <summary>Code généré</summary>
          <pre>{it.code}</pre>
        </details>
      )}
      {it.execution?.error && <pre className="error-trace">{it.execution.error}</pre>}
      {it.critique?.satisfactory && <p className="critique ok">Critique : résultat accepté.</p>}
      {!it.critique && running && isLast && <p className="muted">…</p>}
    </details>
  );
}

export function RunView({
  run,
  onDecide,
  onReset,
}: {
  run: RunState;
  onDecide: (approved: boolean) => void;
  onReset: () => void;
}) {
  const elapsed = useElapsed(run);
  if (run.phase === "idle") return <Idle />;
  const running = run.phase === "running";

  return (
    <div className="run">
      <div className="run-head">
        <div>
          <span className="eyebrow">Analyse</span>
          <span className="muted"> · {elapsed}</span>
        </div>
        {(run.phase === "done" || run.phase === "error") && <button onClick={onReset}>Nouvelle analyse</button>}
      </div>

      {run.current && (
        <div className="working" role="status">
          <span className="spinner" aria-hidden />
          <span>{run.current.label}</span>
          <span className="badge">{run.current.model}</span>
        </div>
      )}

      {run.profile && (
        <section className="block">
          <h3>Profilage</h3>
          <p className="muted">
            {run.profile.map((d) => `${d.name} : ${d.rows.toLocaleString("fr-FR")} lignes, ${d.columns} colonnes`).join(" · ")}
          </p>
        </section>
      )}

      {run.plan && (
        <section className="block">
          <h3>
            Plan d&apos;analyse
            {run.planModel && <span className="badge">{run.planModel}</span>}
            {run.replans > 0 && <span className="badge warn">replanifié ×{run.replans}</span>}
          </h3>
          <p className="restated">{run.plan.restated_question}</p>
          {run.plan.assumptions.length > 0 && (
            <ul className="assumptions">
              {run.plan.assumptions.map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ul>
          )}
          <ol className="plan-steps">
            {run.plan.steps.map((s) => (
              <li key={s.id}>
                <strong>{s.goal}</strong>
                <span className="muted"> — {s.method}</span>
              </li>
            ))}
          </ol>
          {run.phase === "awaiting" && (
            <div className="approval" role="group" aria-label="Validation du plan">
              <p>Ce plan correspond-il à votre question ? L&apos;exécution démarre après votre accord.</p>
              <div className="row">
                <button className="primary" onClick={() => onDecide(true)}>Valider et exécuter</button>
                <button onClick={() => onDecide(false)}>Refuser</button>
              </div>
            </div>
          )}
        </section>
      )}

      {run.iterations.length > 0 && (
        <section className="block">
          <h3>Génération et exécution</h3>
          {run.iterations.map((it, i) => (
            <IterationView key={it.n} it={it} isLast={i === run.iterations.length - 1} running={running} />
          ))}
        </section>
      )}

      {run.phase === "error" && (
        <div className="alert" role="alert">
          <strong>L&apos;analyse n&apos;a pas abouti.</strong>
          <p>{run.error}</p>
        </div>
      )}

      {run.warnings.length > 0 && (
        <div className="alert soft" role="status">
          {run.warnings.map((w) => (
            <p key={w}>{w}</p>
          ))}
        </div>
      )}

      {run.report && <ReportView report={run.report} model={run.synthesisModel} />}
    </div>
  );
}
