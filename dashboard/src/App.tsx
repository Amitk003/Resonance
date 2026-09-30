import { useCallback, useEffect, useState } from "react";
import { api, getApiBase, setApiBase } from "./api";
import { AGENTS, PAGES, type PageKey } from "./common";
import MemoryPage from "./pages/MemoryPage";
import MergesPage from "./pages/MergesPage";
import SearchPage from "./pages/SearchPage";
import SyncPage from "./pages/SyncPage";

export default function App() {
  const [page, setPage] = useState<PageKey>("memory");
  const [baseInput, setBaseInput] = useState(getApiBase());
  const [backendOk, setBackendOk] = useState<boolean | null>(null);
  const [agent, setAgent] = useState(AGENTS[0]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reloadToken, setReloadToken] = useState(0);

  const checkHealth = useCallback(async () => {
    try {
      const h = await api.health();
      setBackendOk(h.status === "ok");
    } catch {
      setBackendOk(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  function retryAll() {
    setError("");
    checkHealth();
    setReloadToken((n) => n + 1);
  }

  function applyBaseUrl() {
    const clean = baseInput.trim().replace(/\/+$/, "") || "http://localhost:8000";
    setApiBase(clean);
    setBaseInput(clean);
    setNotice("Backend address saved. Reloading data.");
    retryAll();
  }

  function switchAgent(next: string) {
    if (next === agent) return;
    setAgent(next);
    setNotice("");
    setError("");
  }

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <h1>Resonance Memory</h1>
          <p>Local place memory for each edge robot</p>
        </div>
        <div className="header-right">
          <span className="status" title="Backend connection state">
            <span
              className={
                "dot " + (backendOk === null ? "" : backendOk ? "on" : "off")
              }
            />
            {backendOk === null
              ? "Checking"
              : backendOk
                ? "Backend online"
                : "Backend offline"}
          </span>
          <input
            type="text"
            value={baseInput}
            onChange={(e) => setBaseInput(e.target.value)}
            placeholder="http://localhost:8000"
            style={{ width: 190 }}
            aria-label="Backend address"
          />
          <button onClick={applyBaseUrl}>Connect</button>
          <button onClick={retryAll}>Retry</button>
          <div className="agent-switch" role="group" aria-label="Agent">
            {AGENTS.map((a) => (
              <button
                key={a}
                className={a === agent ? "active" : ""}
                onClick={() => switchAgent(a)}
              >
                {a}
              </button>
            ))}
          </div>
          <nav className="agent-switch" aria-label="Pages">
            {PAGES.map((p) => (
              <button
                key={p.key}
                className={page === p.key ? "active" : ""}
                onClick={() => setPage(p.key)}
              >
                {p.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      {error && (
        <div className="banner error">
          <span>{error}</span>
          <button className="small" onClick={retryAll}>
            Retry
          </button>
        </div>
      )}
      {notice && (
        <div className="banner notice">
          <span>{notice}</span>
          <button className="small" onClick={() => setNotice("")}>
            Dismiss
          </button>
        </div>
      )}

      {page === "memory" ? (
        <MemoryPage
          agent={agent}
          reloadToken={reloadToken}
          onError={setError}
          onNotice={setNotice}
        />
      ) : page === "search" ? (
        <SearchPage
          agent={agent}
          reloadToken={reloadToken}
          onError={setError}
          onNotice={setNotice}
        />
      ) : page === "merges" ? (
        <MergesPage
          reloadToken={reloadToken}
          onError={setError}
          onNotice={setNotice}
        />
      ) : (
        <SyncPage
          agent={agent}
          reloadToken={reloadToken}
          onError={setError}
          onNotice={setNotice}
        />
      )}
    </div>
  );
}
