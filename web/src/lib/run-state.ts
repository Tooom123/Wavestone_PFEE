import type { Plan, Report, Role, RunEvent } from "./types";

export interface Iteration {
  n: number;
  max: number;
  model: string;
  code?: string;
  execution?: { status: "success" | "error" | "timeout"; artifacts: number; seconds: number; error: string | null };
  critique?: { satisfactory: boolean; issues: string[]; replan: boolean };
}

export interface RunState {
  phase: "idle" | "running" | "awaiting" | "done" | "error";
  startedAt?: number;
  finishedAt?: number;
  profile?: { name: string; rows: number; columns: number }[];
  plan?: Plan;
  planModel?: string;
  replans: number;
  iterations: Iteration[];
  /** Etape en cours : ce que le modele est en train de faire. */
  current?: { label: string; model: string; role?: Role };
  criticModel?: string;
  synthesisModel?: string;
  report?: Report;
  warnings: string[];
  error?: string;
}

export const initialRun: RunState = { phase: "idle", replans: 0, iterations: [], warnings: [] };

export type Action = { type: "event"; event: RunEvent } | { type: "reset" } | { type: "begin" } | { type: "fail"; message: string };

const ROLE_OF = { planner: "planner", critic: "critic", synthesis: "synthesis" } as const;

const LABELS = {
  planner: "Planification de l'analyse",
  critic: "Relecture du résultat",
  synthesis: "Rédaction de la réponse",
} as const;

export function runReducer(state: RunState, action: Action): RunState {
  if (action.type === "reset") return initialRun;
  if (action.type === "begin") return { ...initialRun, phase: "running", startedAt: Date.now() };
  if (action.type === "fail") return { ...state, phase: "error", error: action.message, finishedAt: Date.now() };

  const e = action.event;
  const last = state.iterations.at(-1);
  const patchLast = (patch: Partial<Iteration>) => [...state.iterations.slice(0, -1), { ...last!, ...patch }];

  switch (e.kind) {
    case "start":
      return { ...state, current: { label: "Profilage des données", model: "pandas" } };
    case "profile":
      return { ...state, profile: e.datasets };
    case "stage":
      return {
        ...state,
        current: { label: LABELS[e.name], model: e.model, role: ROLE_OF[e.name] },
        ...(e.name === "planner" ? { planModel: e.model } : {}),
        ...(e.name === "critic" ? { criticModel: e.model } : {}),
        ...(e.name === "synthesis" ? { synthesisModel: e.model } : {}),
      };
    case "plan":
      return { ...state, plan: e.plan, replans: state.replans + (e.replanned ? 1 : 0) };
    case "awaiting_approval":
      return { ...state, phase: "awaiting", current: undefined };
    case "iteration":
      return {
        ...state,
        phase: "running",
        current: { label: `Génération du code (essai ${e.n}/${e.max})`, model: e.model, role: "coder" },
        iterations: [...state.iterations, { n: e.n, max: e.max, model: e.model }],
      };
    case "code":
      return {
        ...state,
        current: { label: "Exécution dans le sandbox Docker", model: "isolé · sans réseau" },
        iterations: patchLast({ code: e.code }),
      };
    case "execution":
      return { ...state, iterations: patchLast({ execution: e }) };
    case "critique":
      return { ...state, iterations: patchLast({ critique: e }) };
    case "done":
      return { ...state, phase: "done", report: e.report, warnings: e.errors, current: undefined, finishedAt: Date.now() };
    case "error":
      return { ...state, phase: "error", error: e.message, current: undefined, finishedAt: Date.now() };
  }
}
