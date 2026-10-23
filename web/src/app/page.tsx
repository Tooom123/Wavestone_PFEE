"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { Form } from "@/components/Form";
import { RunView } from "@/components/RunView";
import { SettingsPanel } from "@/components/SettingsPanel";
import { StatusBar } from "@/components/StatusBar";
import { ApiConfig, ApiError, decidePlan, getDatasets, getHealth, loadConfig, saveConfig, startRun, streamEvents } from "@/lib/api";
import { initialRun, runReducer } from "@/lib/run-state";
import type { DatasetInfo, Health } from "@/lib/types";

export default function Home() {
  const [config, setConfig] = useState<ApiConfig | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [connection, setConnection] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [run, dispatch] = useReducer(runReducer, initialRun);
  const runId = useRef<string | null>(null);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => setConfig(loadConfig()), []);

  const refresh = useCallback(async (c: ApiConfig) => {
    try {
      const h = await getHealth(c);
      setHealth(h);
      setDatasets(await getDatasets(c));
      setConnection(null);
    } catch (error) {
      setHealth(null);
      setDatasets([]);
      setConnection(error instanceof ApiError ? error.message : "Connexion impossible.");
      if (error instanceof ApiError && error.status === 401) setShowSettings(true);
    }
  }, []);

  useEffect(() => {
    if (!config) return;
    refresh(config);
    const timer = setInterval(() => getHealth(config).then(setHealth).catch(() => setHealth(null)), 15000);
    return () => clearInterval(timer);
  }, [config, refresh]);

  const launch = async (body: { question: string; datasets: string[]; validate_plan: boolean }) => {
    if (!config) return;
    abort.current?.abort();
    dispatch({ type: "begin" });
    try {
      const { run_id } = await startRun(config, body);
      runId.current = run_id;
      const controller = new AbortController();
      abort.current = controller;
      await streamEvents(config, run_id, (event) => dispatch({ type: "event", event }), controller.signal);
    } catch (error) {
      dispatch({ type: "fail", message: error instanceof Error ? error.message : String(error) });
    }
  };

  const decide = async (approved: boolean) => {
    if (!config || !runId.current) return;
    try {
      await decidePlan(config, runId.current, approved);
    } catch (error) {
      dispatch({ type: "fail", message: error instanceof Error ? error.message : String(error) });
    }
  };

  const busy = run.phase === "running" || run.phase === "awaiting";

  return (
    <>
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden />
          <div>
            <h1>Agent Data</h1>
            <p>Analyse de données agentique · EPITA × Wavestone</p>
          </div>
        </div>
        <StatusBar health={health} connection={connection} onSettings={() => setShowSettings((v) => !v)} />
      </header>

      {showSettings && config && (
        <SettingsPanel
          config={config}
          onSave={(next) => {
            saveConfig(next);
            setConfig(next);
            setShowSettings(false);
          }}
          onClose={() => setShowSettings(false)}
        />
      )}

      <main className="layout">
        <aside className="panel">
          <Form
            datasets={datasets}
            busy={busy}
            ready={!!health?.llm && !!health?.docker && !!health?.sandbox_image}
            onSubmit={launch}
          />
        </aside>
        <section className="stage" aria-live="polite">
          <RunView run={run} onDecide={decide} onReset={() => dispatch({ type: "reset" })} />
        </section>
      </main>
    </>
  );
}
