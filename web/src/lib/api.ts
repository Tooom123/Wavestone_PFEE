import type { DatasetInfo, Health, RunEvent } from "./types";

export interface ApiConfig {
  baseUrl: string;
  token: string;
}

const STORAGE_KEY = "agent-data:api";
const DEFAULT_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Lit la configuration de l'API. Un lien de demonstration peut la porter dans son fragment
 * (`#api=https://...&token=...`) : le fragment n'est jamais envoye a un serveur, et l'URL
 * d'un tunnel change a chaque demarrage.
 */
export function loadConfig(): ApiConfig {
  let stored: Partial<ApiConfig> = {};
  try {
    stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
  } catch {
    /* stockage indisponible : valeurs par defaut */
  }
  const hash = new URLSearchParams(window.location.hash.slice(1));
  const config = {
    baseUrl: hash.get("api") ?? stored.baseUrl ?? DEFAULT_URL,
    token: hash.get("token") ?? stored.token ?? "",
  };
  if (hash.has("api") || hash.has("token")) {
    saveConfig(config);
    history.replaceState(null, "", window.location.pathname);
  }
  return config;
}

export function saveConfig(config: ApiConfig): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
  } catch {
    /* sans persistance, la configuration vaut pour la session */
  }
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
  }
}

function headers(config: ApiConfig, json = false): HeadersInit {
  return {
    ...(json ? { "Content-Type": "application/json" } : {}),
    ...(config.token ? { Authorization: `Bearer ${config.token}` } : {}),
  };
}

async function request<T>(config: ApiConfig, path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(config.baseUrl.replace(/\/$/, "") + path, init);
  } catch {
    throw new ApiError("Serveur injoignable. Vérifiez qu'il est démarré et que l'adresse est correcte.");
  }
  if (!response.ok) {
    const detail = await response.json().then((b) => b.detail as string).catch(() => response.statusText);
    throw new ApiError(detail, response.status);
  }
  return response.json() as Promise<T>;
}

export const getHealth = (c: ApiConfig) => request<Health>(c, "/api/health", { headers: headers(c) });
export const getDatasets = (c: ApiConfig) => request<DatasetInfo[]>(c, "/api/datasets", { headers: headers(c) });

export const startRun = (c: ApiConfig, body: { question: string; datasets: string[]; validate_plan: boolean }) =>
  request<{ run_id: string }>(c, "/api/runs", { method: "POST", headers: headers(c, true), body: JSON.stringify(body) });

export const decidePlan = (c: ApiConfig, runId: string, approved: boolean) =>
  request<{ ok: boolean }>(c, `/api/runs/${runId}/approval`, {
    method: "POST",
    headers: headers(c, true),
    body: JSON.stringify({ approved }),
  });

/**
 * Suit les evenements d'un run (SSE). `fetch` plutot que `EventSource`, qui ne sait pas
 * envoyer l'en-tete d'autorisation. En cas de coupure, reprend la ou le flux s'est arrete.
 */
export async function streamEvents(
  config: ApiConfig,
  runId: string,
  onEvent: (event: RunEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  let cursor = 0;
  let failures = 0;
  while (!signal.aborted) {
    try {
      const response = await fetch(`${config.baseUrl.replace(/\/$/, "")}/api/runs/${runId}/events?after=${cursor}`, {
        headers: headers(config),
        signal,
      });
      if (!response.ok || !response.body) throw new ApiError(response.statusText, response.status);
      const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
      let buffer = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += value;
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";
        for (const frame of frames) {
          const line = frame.split("\n").find((l) => l.startsWith("data: "));
          if (!line) continue;
          const event = JSON.parse(line.slice(6)) as RunEvent;
          cursor = event.i + 1;
          failures = 0;
          onEvent(event);
          if (event.kind === "done" || event.kind === "error") return;
        }
      }
      return; // flux termine proprement par le serveur
    } catch (error) {
      if (signal.aborted) return;
      if (++failures > 5) throw error;
      await new Promise((r) => setTimeout(r, 1000 * failures));
    }
  }
}
