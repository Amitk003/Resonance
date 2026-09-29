import { useCallback, useEffect, useMemo, useState } from "react";
import { api, formatTime, getApiBase, setApiBase, type Place } from "./api";
import DetailPanel from "./components/DetailPanel";
import PoseMap from "./components/PoseMap";
import SearchPanel from "./components/SearchPanel";
import AddPlaceForm from "./components/AddPlaceForm";
import { buildDemoPlaces } from "./demo";

// Fixed pair for the demo. A third robot needs a backend agent-list
// endpoint first (no such contract yet), then this becomes dynamic.
const AGENTS = ["robot-a", "robot-b"];
const LIMIT_CHOICES = [10, 25, 50, 100, 200];

type SortKey = "time" | "confidence" | "id";

export default function App() {
  const [baseInput, setBaseInput] = useState(getApiBase());
  const [backendOk, setBackendOk] = useState<boolean | null>(null);
  const [agent, setAgent] = useState(AGENTS[0]);
  const [places, setPlaces] = useState<Place[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");
  const [zone, setZone] = useState("all");
  const [sort, setSort] = useState<SortKey>("time");
  const [limit, setLimit] = useState(50);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [seeding, setSeeding] = useState(false);

  const checkHealth = useCallback(async () => {
    try {
      const h = await api.health();
      setBackendOk(h.status === "ok");
      return true;
    } catch {
      setBackendOk(false);
      return false;
    }
  }, []);

  const loadList = useCallback(async (ag: string, lim: number) => {
    setLoading(true);
    setError("");
    try {
      const data = await api.listPlaces(ag, lim);
      setPlaces(data.places);
      setTotal(data.total);
      setBackendOk(true);
      setSelectedId((prev) =>
        prev && data.places.some((p) => p.id === prev) ? prev : null,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Load failed");
      setBackendOk(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    loadList(agent, limit);
  }, [agent, limit, checkHealth, loadList]);

  function applyBaseUrl() {
    const clean = baseInput.trim().replace(/\/+$/, "") || "http://localhost:8000";
    setApiBase(clean);
    setBaseInput(clean);
    setNotice("Backend address saved. Reloading data.");
    checkHealth();
    loadList(agent, limit);
  }

  function switchAgent(next: string) {
    if (next === agent) return;
    setAgent(next);
    setQuery("");
    setZone("all");
    setNotice("");
    setError("");
  }

  const selected = useMemo(
    () => places.find((p) => p.id === selectedId) || null,
    [places, selectedId],
  );

  function handleChanged(message: string) {
    setNotice(message);
    setError("");
    loadList(agent, limit);
  }

  function handlePanelError(message: string) {
    setError(message);
  }

  async function seedDemo() {
    setSeeding(true);
    setError("");
    try {
      const fresh = await api.listPlaces(agent, 200);
      const demo = buildDemoPlaces(agent, fresh.places);
      for (const p of demo) {
        await api.addPlace(p);
      }
      setNotice(demo.length + " demo places added to " + agent + ".");
      loadList(agent, limit);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Seed failed");
    } finally {
      setSeeding(false);
    }
  }

  const zones = useMemo(() => {
    const set = new Set(places.map((p) => p.payload.zone || "(none)"));
    return ["all", ...Array.from(set).sort()];
  }, [places]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const rows = places.filter((p) => {
      if (zone !== "all" && (p.payload.zone || "(none)") !== zone) return false;
      if (!q) return true;
      const hay = [p.id, p.payload.zone, p.payload.sensor, p.payload.note]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
    const sorted = [...rows];
    if (sort === "confidence") sorted.sort((a, b) => b.confidence - a.confidence);
    else if (sort === "id") sorted.sort((a, b) => a.id.localeCompare(b.id));
    else sorted.sort((a, b) => b.timestamp - a.timestamp);
    return sorted;
  }, [places, query, zone, sort]);

  const stats = useMemo(() => {
    const count = places.length;
    const avg =
      count === 0 ? 0 : places.reduce((s, p) => s + p.confidence, 0) / count;
    const zoneCount = new Set(places.map((p) => p.payload.zone)).size;
    const sensorCount = new Set(places.map((p) => p.payload.sensor)).size;
    return { count, avg, zoneCount, sensorCount };
  }, [places]);

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
          <button
            onClick={() => {
              checkHealth();
              loadList(agent, limit);
            }}
          >
            Retry
          </button>
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
        </div>
      </header>

      {error && (
        <div className="banner error">
          <span>{error}</span>
          <button
            className="small"
            onClick={() => {
              checkHealth();
              loadList(agent, limit);
            }}
          >
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

      <section className="stats">
        <div className="stat">
          <div className="label">Places in view</div>
          <div className="value">{stats.count}</div>
        </div>
        <div className="stat">
          <div className="label">Total stored</div>
          <div className="value">{total}</div>
        </div>
        <div className="stat">
          <div className="label">Avg confidence</div>
          <div className="value">{stats.avg.toFixed(2)}</div>
        </div>
        <div className="stat">
          <div className="label">Zones</div>
          <div className="value">{stats.zoneCount}</div>
        </div>
        <div className="stat">
          <div className="label">Sensors</div>
          <div className="value">{stats.sensorCount}</div>
        </div>
      </section>

      <div className="layout">
        <section className="card">
          <h2>
            Memory list ({visible.length} of {total})
          </h2>
          {showAdd && (
            <div className="card" style={{ marginBottom: 10 }}>
              <h2>Add a place</h2>
              <AddPlaceForm
                agent={agent}
                places={places}
                seedPlace={selected}
                onAdded={handleChanged}
                onError={handlePanelError}
                onClose={() => setShowAdd(false)}
              />
            </div>
          )}
          <div className="toolbar">
            <input
              className="grow"
              type="text"
              placeholder="Filter by id, zone, sensor, or note"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Filter places"
            />
            <select
              value={zone}
              onChange={(e) => setZone(e.target.value)}
              aria-label="Zone filter"
            >
              {zones.map((z) => (
                <option key={z} value={z}>
                  {z === "all" ? "All zones" : z}
                </option>
              ))}
            </select>
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as SortKey)}
              aria-label="Sort order"
            >
              <option value="time">Newest first</option>
              <option value="confidence">Top confidence</option>
              <option value="id">By id</option>
            </select>
            <select
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              aria-label="Page size"
            >
              {LIMIT_CHOICES.map((n) => (
                <option key={n} value={n}>
                  Show {n}
                </option>
              ))}
            </select>
            <button onClick={() => loadList(agent, limit)} disabled={loading}>
              {loading ? "Loading" : "Refresh"}
            </button>
            <button onClick={() => setShowAdd((v) => !v)}>
              {showAdd ? "Close form" : "Add place"}
            </button>
            <button onClick={seedDemo} disabled={seeding || loading}>
              {seeding ? "Seeding" : "Seed demo"}
            </button>
            {(query !== "" || zone !== "all") && (
              <button
                onClick={() => {
                  setQuery("");
                  setZone("all");
                }}
              >
                Clear filters
              </button>
            )}
          </div>

          {visible.length === 0 && !loading ? (
            <div className="empty">
              {places.length === 0
                ? "No places stored for " + agent + " yet."
                : "No places match the current filters."}
            </div>
          ) : (
            <table className="grid">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Pose x, y</th>
                  <th>Confidence</th>
                  <th>Zone</th>
                  <th>Sensor</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((p) => (
                  <tr
                    key={p.id}
                    className={p.id === selectedId ? "selected" : ""}
                    onClick={() =>
                      setSelectedId(p.id === selectedId ? null : p.id)
                    }
                    style={{ cursor: "pointer" }}
                  >
                    <td>{p.id}</td>
                    <td>
                      {p.pose.x.toFixed(2)}, {p.pose.y.toFixed(2)}
                    </td>
                    <td>
                      <span className="conf-bar">
                        <span
                          className="conf-fill"
                          style={{ width: Math.round(p.confidence * 100) + "%" }}
                        />
                      </span>
                      {p.confidence.toFixed(2)}
                    </td>
                    <td>
                      <span className="badge">{p.payload.zone || "-"}</span>
                    </td>
                    <td>{p.payload.sensor || "-"}</td>
                    <td>{formatTime(p.timestamp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <aside className="side" style={{ display: "grid", gap: 12 }}>
          <section className="card">
            <h2>Pose map</h2>
            <PoseMap
              places={visible}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          </section>
          <section className="card">
            <h2>Details</h2>
            <DetailPanel
              place={selected}
              onChanged={handleChanged}
              onError={handlePanelError}
            />
          </section>
          <section className="card">
            <h2>Similar search</h2>
            <SearchPanel
              places={visible}
              selectedId={selectedId}
              onSelect={setSelectedId}
              onError={handlePanelError}
            />
          </section>
        </aside>
      </div>
    </div>
  );
}
