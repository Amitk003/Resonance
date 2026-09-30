import { useCallback, useEffect, useState } from "react";
import {
  api,
  decideFuse,
  type MergeRecord,
  type SyncItem,
  type SyncPushResponse,
} from "../api";
import { downloadJson } from "../common";
import ThresholdControl from "../components/ThresholdControl";

interface Props {
  agent: string;
  reloadToken: number;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
}

export default function SyncPage({ agent, reloadToken, onError, onNotice }: Props) {
  const [queue, setQueue] = useState<SyncItem[]>([]);
  const [history, setHistory] = useState<MergeRecord[]>([]);
  const [threshold, setThreshold] = useState(0.8);
  const [loading, setLoading] = useState(false);
  const [pushing, setPushing] = useState(false);
  const [lastPush, setLastPush] = useState<SyncPushResponse | null>(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [rows, merges, live] = await Promise.all([
        api.syncQueue(agent, 20),
        api.listMerges(50),
        api.getThreshold(),
      ]);
      setQueue(rows);
      setHistory(merges);
      setThreshold(live.threshold);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Load failed");
    } finally {
      setLoading(false);
    }
  }, [agent, onError]);

  useEffect(() => {
    loadAll();
  }, [reloadToken, loadAll]);

  async function pushNow() {
    setPushing(true);
    try {
      const report = await api.pushSync(agent, 20);
      setLastPush(report);
      onNotice(
        "Push done: " + report.uploaded + " uploaded, " +
        report.unchanged + " unchanged, " + (report.kept || 0) + " kept, " +
        report.conflicts.length + " conflicts.",
      );
      await loadAll();
    } catch (e) {
      onError(e instanceof Error ? e.message : "Push failed");
    } finally {
      setPushing(false);
    }
  }

  return (
    <div className="layout">
      <section className="card">
        <h2>Fuse threshold for {agent}</h2>
        <ThresholdControl
          value={threshold}
          onSaved={setThreshold}
          onError={onError}
          onNotice={onNotice}
        />
        <p style={{ fontSize: 12, color: "var(--muted)" }}>
          Live value {threshold.toFixed(2)}. Merges at or above it fuse,
          below it only log. Move it and watch the verdicts change.
        </p>
      </section>

      <section className="card">
        <h2>Upload queue ({queue.length})</h2>
        {queue.length === 0 && !loading ? (
          <div className="empty">Queue is empty for {agent}.</div>
        ) : (
          <table className="grid">
            <thead>
              <tr>
                <th>Place</th>
                <th>Score</th>
                <th>Why first</th>
              </tr>
            </thead>
            <tbody>
              {queue.map((row) => (
                <tr key={row.place.id}>
                  <td>{row.place.id}</td>
                  <td className="score">{row.score.toFixed(3)}</td>
                  <td>{row.reasons.length > 0 ? row.reasons.join(", ") : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <button className="primary" onClick={pushNow} disabled={pushing || loading}>
            {pushing ? "Pushing" : "Push to cloud"}
          </button>
          <button onClick={loadAll} disabled={loading}>
            {loading ? "Loading" : "Refresh"}
          </button>
          <button onClick={() => downloadJson("queue-" + agent + ".json", queue)}>
            Export queue
          </button>
        </div>
        {!loading && (
          <p style={{ fontSize: 12, color: "var(--muted)" }}>
            Push needs the cloud at localhost:6333. Without it you get a
            clear 503, nothing breaks.
          </p>
        )}
      </section>

      <aside className="side" style={{ display: "grid", gap: 12 }}>
        <section className="card">
          <h2>Last push</h2>
          {!lastPush ? (
            <p style={{ color: "var(--muted)" }}>No push yet this session.</p>
          ) : (
            <div>
              <dl className="kv">
                <dt>Uploaded</dt>
                <dd>{lastPush.uploaded}</dd>
                <dt>Unchanged</dt>
                <dd>{lastPush.unchanged}</dd>
                <dt>Kept</dt>
                <dd>{lastPush.kept || 0}</dd>
                <dt>Conflicts</dt>
                <dd>{lastPush.conflicts.length}</dd>
              </dl>
              {lastPush.conflicts.length > 0 && (
                <table className="grid" style={{ marginTop: 8 }}>
                  <thead>
                    <tr>
                      <th>Place</th>
                      <th>Winner</th>
                      <th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lastPush.conflicts.map((c, i) => (
                      <tr key={c.id + "-" + i}>
                        <td>{c.id}</td>
                        <td>{c.winner_id}</td>
                        <td>{c.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <div style={{ marginTop: 8 }}>
                <button
                  className="small"
                  onClick={() => downloadJson("push-" + agent + ".json", lastPush)}
                >
                  Export report
                </button>
              </div>
            </div>
          )}
        </section>
        <section className="card">
          <h2>Merge verdicts</h2>
          {history.length === 0 ? (
            <p style={{ color: "var(--muted)" }}>No meetings logged yet.</p>
          ) : (
            <table className="grid">
              <thead>
                <tr>
                  <th>Pair</th>
                  <th>Score</th>
                  <th>Verdict</th>
                </tr>
              </thead>
              <tbody>
                {history.map((r) => (
                  <tr key={r.id}>
                    <td>
                      {r.agent_a} + {r.agent_b}
                    </td>
                    <td className="score">{r.score.toFixed(3)}</td>
                    <td>
                      <span
                        className={
                          "badge " + (decideFuse(r.score, threshold) ? "fuse" : "log")
                        }
                      >
                        {decideFuse(r.score, threshold) ? "fuse" : "log"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div style={{ marginTop: 8 }}>
            <button
              className="small"
              onClick={() => downloadJson("merges.json", history)}
            >
              Export history
            </button>
          </div>
        </section>
      </aside>
    </div>
  );
}
