// Contrat avec l'API (src/agent_data/api) : memes noms que les modeles Pydantic.

export type Role = "planner" | "coder" | "critic" | "synthesis";

export interface Health {
  llm: boolean;
  docker: boolean;
  sandbox_image: boolean;
  models: Record<Role, { name: string; installed: boolean }>;
  auth_required: boolean;
  busy: boolean;
}

export interface DatasetInfo {
  name: string;
  rows: number;
  columns: { name: string; kind: string; unique: number }[];
  questions: string[];
}

export interface PlanStep {
  id: string;
  goal: string;
  method: string;
  columns: string[];
  rationale: string;
}

export interface Plan {
  question: string;
  restated_question: string;
  assumptions: string[];
  steps: PlanStep[];
  datasets: string[];
}

export type Payload =
  | { kind: "table"; columns: string[]; rows: (string | number | boolean | null)[][] }
  | { kind: "figure"; spec: { data: unknown[]; layout?: Record<string, unknown> } }
  | { kind: "finding"; statement: string; evidence: string; confidence: number };

export interface Artifact {
  id: string;
  step_id: string;
  title: string;
  payload: Payload;
}

export interface Report {
  question: string;
  restated_question: string;
  assumptions: string[];
  synthesis: string;
  artifacts: Artifact[];
  generated_at: string;
}

export type RunEvent = { i: number; t: number } & (
  | { kind: "start"; question: string; datasets: string[] }
  | { kind: "profile"; datasets: { name: string; rows: number; columns: number }[] }
  | { kind: "stage"; name: "planner" | "critic" | "synthesis"; model: string }
  | { kind: "plan"; plan: Plan; replanned?: boolean }
  | { kind: "awaiting_approval" }
  | { kind: "iteration"; n: number; max: number; model: string }
  | { kind: "code"; code: string }
  | { kind: "execution"; status: "success" | "error" | "timeout"; artifacts: number; seconds: number; error: string | null }
  | { kind: "critique"; satisfactory: boolean; issues: string[]; replan: boolean }
  | { kind: "done"; report: Report; code: string | null; iterations: number; errors: string[] }
  | { kind: "error"; message: string; fatal?: string }
);
