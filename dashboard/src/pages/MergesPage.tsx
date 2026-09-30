import { useCallback, useEffect, useState } from "react";
import { api, formatTime, type MergeRecord } from "../api";
import { AGENTS } from "../common";

interface Props {
  reloadToken: number;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
}

export default function MergesPage({ reloadToken, onError, onNotice }: Props) {
  const [records, setRecords] = useState<MergeRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [agentA, setAgentA] = useState(AGENTS[0]);
  const [agentB, setAgentB] = useState(AGENTS[1] || AGENTS[0]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    try {
      setRecords(await api.listMerges(50));
    } catch (e) {
      onError(e instanceof Error ? e.message : "Load failed");
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => {
    loadHistory();
  }, [reloadToken, loadHistory]);

  async function runMeeting() {
    if (agentA === agentB) {
      onError("Pick two different agents for a meeting.");
      return;
    }
    setRunning(true);
    try {
      const record = await api.runAlign({ agent_a: agentA, agent_b: agentB });
      onNotice(
        "Meeting done: score " + record.score.toFixed(3) + ", " +
        record.inliers + " of " + record.pairs_total + " pairs agree.",
      );
      setSelectedId(record.id);
      await loadHistory();
    } catch (e) {
      onError(e instanceof Error ? e.message : "Meeting failed");
    } finally {
      setRunning(false);
    }
  }

  const selected = records.find((r) => r.id === selectedId) || null;

  return (
    <div className="layout">
      <section className="card">
        <h2>Run a meeting</h2>
        <div style={{ display: "flex", gap: 8, alignItems: "end" }}>
          <label style={{ fontSize: 12, color: "var(--muted)", flex: 1 }}>
            Agent A (own map)
            <select
              value={agentA}
              onChange={(e) => setAgentA(e.target.value)}
              style={{ width: "100%", marginTop: 4 }}
              aria-label="Agent A"
            >
              {AGENTS.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </label>
          <label style={{ fontSize: 12, color: "var(--muted)", flex: 1 }}>
            Agent B (swap set)
            <select
              value={agentB}
              onChange={(e) => setAgentB(e.target.value)}
              style={{ width: "100%", marginTop: 4 }}
              aria-label="Agent B"
            >
              {AGENTS.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </label>
          <button
            className="primary"
            onClick={runMeeting}
            disabled={running || loading}
          >
            {running ? "Aligning" : "Run meeting"}
          </button>
          <button onClick={loadHistory} disabled={loading}>
            {loading ? "Loading" : "Refresh"}
          </button>
        </div>
        <p style={{ fontSize: 12, color: "var(--muted)" }}>
          Matches B's swap set against A's memory, fits the transform, and
          logs the scored record below. No fuse gate yet.
        </p>
      </section>

      <section className="card">
        <h2>Past meetings ({records.length})</h2>
        {records.length === 0 && !loading ? (
          <div className="empty">
            No meetings logged yet. Seed both robots, then run one above.
          </div>
        ) : (
          <table className="grid">
            <thead>
              <tr>
                <th>Time</th>
                <th>Pair</th>
                <th>Pairs</th>
                <th>Inliers</th>
                <th>Score</th>
                <th>Shift dx, dy</th>
              </tr>
            </thead>
            <tbody>
              {records.map((r) => (
                <tr
                  key={r.id}
                  className={r.id === selectedId ? "selected" : ""}
                  onClick={() => setSelectedId(r.id === selectedId ? null : r.id)}
                  style={{ cursor: "pointer" }}
                >
                  <td>{formatTime(r.timestamp)}</td>
                  <td>
                    {r.agent_a} + {r.agent_b}
                  </td>
                  <td>{r.pairs_total}</td>
                  <td>{r.inliers}</td>
                  <td>
                    <span className="conf-bar">
                      <span
                        className="conf-fill"
                        style={{ width: Math.round(r.score * 100) + "%" }}
                      />
                    </span>
                    <span className="score">{r.score.toFixed(3)}</span>
                  </td>
                  <td>
                    {r.transform.dx.toFixed(2)}, {r.transform.dy.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <aside className="side" style={{ display: "grid", gap: 12 }}>
        <section className="card">
          <h2>Merge details</h2>
          {!selected ? (
            <p style={{ color: "var(--muted)" }}>
              Select a row to see the full record.
            </p>
          ) : (
            <div>
              <dl className="kv">
                <dt>ID</dt>
                <dd>{selected.id}</dd>
                <dt>Mean vector score</dt>
                <dd>{selected.mean_score.toFixed(3)}</dd>
                <dt>Shape fit</dt>
                <dd>
                  {selected.inliers} of {selected.pairs_total}
                </dd>
                <dt>Heading change</dt>
                <dd>{selected.transform.dtheta.toFixed(3)} rad</dd>
              </dl>
              <h3 style={{ fontSize: 13, margin: "14px 0 6px" }}>Raw record</h3>
              <pre className="json">{JSON.stringify(selected, null, 2)}</pre>
            </div>
          )}
        </section>
      </aside>
    </div>
  );
}
