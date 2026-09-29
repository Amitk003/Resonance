import { useCallback, useEffect, useMemo, useState } from "react";
import { api, formatTime, type Place } from "../api";
import DetailPanel from "../components/DetailPanel";
import PoseMap from "../components/PoseMap";
import SearchPanel from "../components/SearchPanel";
import AddPlaceForm from "../components/AddPlaceForm";
import { buildDemoPlaces } from "../demo";

const LIMIT_CHOICES = [10, 25, 50, 100, 200];

type SortKey = "time" | "confidence" | "id";

interface Props {
  agent: string;
  reloadToken: number;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
}

export default function MemoryPage({ agent, reloadToken, onError, onNotice }: Props) {
  const [places, setPlaces] = useState<Place[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [zone, setZone] = useState("all");
  const [sort, setSort] = useState<SortKey>("time");
  const [limit, setLimit] = useState(50);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [seeding, setSeeding] = useState(false);

  const loadList = useCallback(
    async (ag: string, lim: number) => {
      setLoading(true);
      try {
        const data = await api.listPlaces(ag, lim);
        setPlaces(data.places);
        setTotal(data.total);
        setSelectedId((prev) =>
          prev && data.places.some((p) => p.id === prev) ? prev : null,
        );
      } catch (e) {
        onError(e instanceof Error ? e.message : "Load failed");
      } finally {
        setLoading(false);
      }
    },
    [onError],
  );

  useEffect(() => {
    setQuery("");
    setZone("all");
    loadList(agent, limit);
  }, [agent, limit, reloadToken, loadList]);

  const selected = useMemo(
    () => places.find((p) => p.id === selectedId) || null,
    [places, selectedId],
  );

  function handleChanged(message: string) {
    onNotice(message);
    loadList(agent, limit);
  }

  async function seedDemo() {
    setSeeding(true);
    try {
      const fresh = await api.listPlaces(agent, 200);
      const demo = buildDemoPlaces(agent, fresh.places);
      for (const p of demo) {
        await api.addPlace(p);
      }
      onNotice(demo.length + " demo places added to " + agent + ".");
      loadList(agent, limit);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Seed failed");
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
    <>
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
                onError={onError}
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
              onError={onError}
            />
          </section>
          <section className="card">
            <h2>Similar search</h2>
            <SearchPanel
              places={visible}
              selectedId={selectedId}
              onSelect={setSelectedId}
              onError={onError}
            />
          </section>
        </aside>
      </div>
    </>
  );
}
