import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  const [hasMore, setHasMore] = useState(false);
  const [pageNo, setPageNo] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [seeding, setSeeding] = useState(false);
  // Qdrant scroll offsets are opaque values from next_offset. The map
  // remembers the offset each page started at so Prev can walk back.
  const offsetByPage = useRef<Map<number, unknown>>(new Map([[1, null]]));

  const loadList = useCallback(
    async (ag: string, lim: number, page = 1, direction?: "next" | "prev") => {
      setLoading(true);
      try {
        const off = page > 1 ? offsetByPage.current.get(page) : null;
        const data = await api.listPlaces(ag, lim, off);
        if (page > 1) offsetByPage.current.set(page, off);
        if (data.next_offset != null) {
          offsetByPage.current.set(page + 1, data.next_offset);
        }
        setPlaces(data.places);
        setTotal(data.total);
        setHasMore(data.next_offset != null);
        if (direction === "next") setPageNo((n) => n + 1);
        else if (direction === "prev") setPageNo((n) => Math.max(1, n - 1));
        else setPageNo(page);
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
    offsetByPage.current = new Map([[1, null]]);
    loadList(agent, limit);
  }, [agent, limit, reloadToken, loadList]);

  const selected = useMemo(
    () => places.find((p) => p.id === selectedId) || null,
    [places, selectedId],
  );

  function handleChanged(message: string) {
    onNotice(message);
    loadList(agent, limit, pageNo);
  }

  function nextPage() {
    if (!hasMore || loading) return;
    loadList(agent, limit, pageNo + 1, "next");
  }

  function prevPage() {
    if (pageNo <= 1 || loading) return;
    loadList(agent, limit, pageNo - 1, "prev");
  }

  async function seedDemo() {
    setSeeding(true);
    try {
      const fresh = await api.listPlaces(agent, 200);
      const demo = buildDemoPlaces(agent, fresh.places);
      await api.bulkAddPlaces(demo);
      onNotice(demo.length + " demo places added to " + agent + " in one request.");
      offsetByPage.current = new Map([[1, null]]);
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
            Memory list ({visible.length} shown of {total} stored)
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
            <button onClick={prevPage} disabled={loading || pageNo <= 1}>
              Prev
            </button>
            <span aria-label="Page number" style={{ alignSelf: "center", fontSize: 13 }}>
              Page {pageNo}
              {total > limit ? ` of ${Math.ceil(total / limit)}` : ""}
            </span>
            <button onClick={nextPage} disabled={loading || !hasMore}>
              Next
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
              {total === 0
                ? "No places stored for " + agent + " yet."
                : places.length === 0
                  ? "No places on this page."
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
              key={selected ? selected.id : "none"}
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
