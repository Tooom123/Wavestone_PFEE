"use client";

import { useEffect, useState } from "react";
import type { DatasetInfo } from "@/lib/types";

const KIND_LABELS: Record<string, string> = {
  numeric: "numérique",
  categorical: "catégorie",
  datetime: "date",
  boolean: "booléen",
  text: "texte",
};

export function Form({
  datasets,
  busy,
  ready,
  onSubmit,
}: {
  datasets: DatasetInfo[];
  busy: boolean;
  ready: boolean;
  onSubmit: (body: { question: string; datasets: string[]; validate_plan: boolean }) => void;
}) {
  const [selected, setSelected] = useState<string>("");
  const [question, setQuestion] = useState("");
  const [validate, setValidate] = useState(true);

  useEffect(() => {
    if (!selected && datasets.length) setSelected(datasets[0].name);
  }, [datasets, selected]);

  const dataset = datasets.find((d) => d.name === selected);

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({ question: question.trim(), datasets: [selected], validate_plan: validate });
      }}
    >
      <h2>1 · Données</h2>
      {datasets.length === 0 && <p className="muted">Aucun jeu de données disponible. Le serveur est-il connecté ?</p>}
      <div className="cards" role="radiogroup" aria-label="Jeu de données">
        {datasets.map((d) => (
          <label key={d.name} className={`card ${d.name === selected ? "active" : ""}`}>
            <input type="radio" name="dataset" checked={d.name === selected} onChange={() => setSelected(d.name)} />
            <strong>{d.name}</strong>
            <span className="muted">
              {d.rows.toLocaleString("fr-FR")} lignes · {d.columns.length} colonnes
            </span>
          </label>
        ))}
      </div>

      {dataset && (
        <details className="profile">
          <summary>Ce que le modèle voit de ces données</summary>
          <p className="muted">
            Uniquement le profil : noms, types, cardinalités et statistiques agrégées. Aucune ligne n&apos;est transmise.
          </p>
          <ul>
            {dataset.columns.map((c) => (
              <li key={c.name}>
                <code>{c.name}</code>
                <span className="muted">
                  {KIND_LABELS[c.kind] ?? c.kind} · {c.unique} val.
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}

      <h2>2 · Question métier</h2>
      <textarea
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        rows={4}
        placeholder="Ex. : quels clients risquent de partir, et pourquoi ?"
        aria-label="Question métier"
      />
      {dataset && dataset.questions.some((q) => q !== question) && (
        <div className="suggestions">
          {dataset.questions.filter((q) => q !== question).map((q) => (
            <button type="button" key={q} className="suggestion" onClick={() => setQuestion(q)}>
              {q}
            </button>
          ))}
        </div>
      )}

      <label className="check">
        <input type="checkbox" checked={validate} onChange={(e) => setValidate(e.target.checked)} />
        <span>
          Valider le plan avant exécution
          <small className="muted"> — l&apos;humain garde la main sur la démarche</small>
        </span>
      </label>

      <button className="primary wide" type="submit" disabled={busy || !ready || !question.trim() || !selected}>
        {busy ? "Analyse en cours…" : "Lancer l'analyse"}
      </button>
      {!ready && <p className="muted small">Le LLM local et le sandbox doivent être disponibles pour lancer une analyse.</p>}
    </form>
  );
}
