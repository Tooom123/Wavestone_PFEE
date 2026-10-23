"use client";

import { useState } from "react";
import type { ApiConfig } from "@/lib/api";

export function SettingsPanel({
  config,
  onSave,
  onClose,
}: {
  config: ApiConfig;
  onSave: (config: ApiConfig) => void;
  onClose: () => void;
}) {
  const [baseUrl, setBaseUrl] = useState(config.baseUrl);
  const [token, setToken] = useState(config.token);

  return (
    <form
      className="settings"
      onSubmit={(e) => {
        e.preventDefault();
        onSave({ baseUrl: baseUrl.trim(), token: token.trim() });
      }}
    >
      <p className="muted">
        L&apos;agent tourne sur le poste de l&apos;équipe : ses données et ses modèles ne quittent jamais cette machine. Ce site
        n&apos;est que l&apos;interface.
      </p>
      <label>
        Adresse du serveur
        <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://….trycloudflare.com" />
      </label>
      <label>
        Jeton d&apos;accès
        <input value={token} onChange={(e) => setToken(e.target.value)} type="password" autoComplete="off" />
      </label>
      <div className="row">
        <button type="submit" className="primary">Enregistrer</button>
        <button type="button" onClick={onClose}>Annuler</button>
      </div>
    </form>
  );
}
