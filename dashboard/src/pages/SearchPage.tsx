import { useCallback, useEffect, useMemo, useState } from "react";
import { api, formatTime, type Place, type SearchHit } from "../api";
import DetailPanel from "../components/DetailPanel";
import PoseMap from "../components/PoseMap";
import { noisyCopy, randomVector, seededRandom } from "../demo";
import {
  clearHistory as clearStoredHistory,
  deleteRecord as deleteStoredRecord,
  describeQuery,
  loadHistory,
  saveRecord,
  type QuerySource,
  type SearchQuery,
  type SearchRecord,
} from "../searchHistory";

type SourceMode = QuerySource;

interface Props {
  agent: string;
  reloadToken: number;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
}

function parseDateTime(raw: string): number | undefined | null {
  const clean = raw.trim();
  if (clean === "") return undefined;
  const ms = new Date(clean).getTime();
  if (Number.isNaN(ms) || ms < 0) return null;
  return Math.floor(ms / 1000);
}

function buildQueryVector(
  places: Place[],
  q: SearchQuery,
): { vector: number[]; label: string } | null {
  if (q.source === "random") {
    return { vector: randomVector(), label: "fresh random vector" };
  }
  const base = places.find((p) => p.id === q.sourceId);
  if (!base) return null;
  if (q.source === "near") {
    return {
      vector: noisyCopy(base.vector, 0.05, seededRandom(Date.now() % 100000)),
      label: "near " + base.id,
    };
  }
  return { vector: base.vector, label: "place " + base.id };
}

interface TimeWindow {
  since?: number;
  until?: number;
  error?: string;
}

function parseWindow(q: SearchQuery): TimeWindow {
  const since = parseDateTime(q.sinceInput);
  const until = parseDateTime(q.untilInput);
  if (since === null || until === null) {
    return { error: "Since and Until must be valid dates, or left blank." };
  }
  if (since !== undefined && until !== undefined && since > until) {
    return { error: "Since must not be after Until." };
  }
  return { since, until };
}

interface ExecParams {
  vector: number[];
  sourceLabel: string;
  query: SearchQuery;
  since?: number;
  until?: number;
}

interface ExecDeps {
  agent: string;
  setBusy: (busy: boolean) => void;
  applyResults: (hits: SearchHit[], ms: number) => void;
  recordHistory: (record: SearchRecord) => void;
  notify: (message: string) => void;
  fail: (message: string) => void;
}

async function executeSearch(deps: ExecDeps, p: ExecParams): Promise<void> {
  deps.setBusy(true);
  const started = performance.now();
  try {
    const res = await api.search({
      agent_id: deps.agent,
      vector: p.vector,
      top_k: p.query.topK,
      min_confidence: p.query.minConf,
      zones: p.query.zones,
      sensors: p.query.sensors,
      since: p.since,
      until: p.until,
    });
    const ms = Math.round(performance.now() - started);
    deps.applyResults(res, ms);
    const filterLabel = describeQuery(deps.agent, p.query);
    deps.recordHistory({
      id: deps.agent + "-" + Date.now(),
      time: Math.floor(Date.now() / 1000),
      agent: deps.agent,
      sourceLabel: p.sourceLabel,
      filterLabel,
      resultCount: res.length,
      topScore: res.length > 0 ? res[0].score : null,
      query: p.query,
    });
    deps.notify(
      "Search done in " + ms + " ms, " + res.length + " matches (" +
        p.sourceLabel + " | " + filterLabel + ").",
    );
  } catch (e) {
    deps.fail(e instanceof Error ? e.message : "Search failed");
  } finally {
    deps.setBusy(false);
  }
}

export default function SearchPage({ agent, reloadToken, onError, onNotice }: Props) {
  const [places, setPlaces] = useState<Place[]>([]);
  const [sourceMode, setSourceMode] = useState<SourceMode>("place");
  const [sourceId, setSourceId] = useState("");
  const [topK, setTopK] = useState(5);
  const [minConf, setMinConf] = useState(0);
  const [zoneSel, setZoneSel] = useState<string[]>([]);
  const [sensorSel, setSensorSel] = useState<string[]>([]);
  const [sinceInput, setSinceInput] = useState("");
  const [untilInput, setUntilInput] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [searched, setSearched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [queryMs, setQueryMs] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const loadPlaces = useCallback(async () => {
    try {
      const data = await api.listPlaces(agent, 200);
      setPlaces(data.places);
      setSourceId((prev) =>
        prev && data.places.some((p) => p.id === prev)
          ? prev
          : data.places.length > 0
            ? data.places[0].id
            : "",
      );
    } catch (e) {
      onError(e instanceof Error ? e.message : "Load failed");
    }
  }, [agent, onError]);

  useEffect(() => {
    setHits([]);
    setSearched(false);
    setSelectedId(null);
    setZoneSel([]);
    setSensorSel([]);
    setSinceInput("");
    setUntilInput("");
    loadPlaces();
  }, [agent, reloadToken, loadPlaces]);

  const allZones = useMemo(
    () => Array.from(new Set(places.map((p) => p.payload.zone || "(none)"))).sort(),
    [places],
  );
  const allSensors = useMemo(
    () => Array.from(new Set(places.map((p) => p.payload.sensor || "(none)"))).sort(),
    [places],
  );

  function toggle(list: string[], value: string, set: (v: string[]) => void) {
    set(list.includes(value) ? list.filter((x) => x !== value) : [...list, value]);
  }

  const [history, setHistory] = useState<SearchRecord[]>(() => loadHistory());

  function deps(): ExecDeps {
    return {
      agent,
      setBusy,
      applyResults: (hits, ms) => {
        setHits(hits);
        setSearched(true);
        setSelectedId(null);
        setQueryMs(ms);
      },
      recordHistory: (record) => setHistory(saveRecord(record)),
      notify: onNotice,
      fail: onError,
    };
  }

  function currentQuery(): SearchQuery {
    return {
      source: sourceMode,
      sourceId,
      topK,
      minConf,
      zones: zoneSel,
      sensors: sensorSel,
      sinceInput,
      untilInput,
    };
  }

  async function runSearch() {
    const q = currentQuery();
    const built = buildQueryVector(places, q);
    if (!built) {
      onError("Pick a source place first, or use a random vector.");
      return;
    }
    const window = parseWindow(q);
    if (window.error) {
      onError(window.error);
      return;
    }
    await executeSearch(deps(), {
      vector: built.vector,
      sourceLabel: built.label,
      query: q,
      since: window.since,
      until: window.until,
    });
  }

  async function reRun(record: SearchRecord) {
    const q = record.query;
    setSourceMode(q.source);
    setSourceId(q.sourceId);
    setTopK(q.topK);
    setMinConf(q.minConf);
    setZoneSel(q.zones);
    setSensorSel(q.sensors);
    setSinceInput(q.sinceInput);
    setUntilInput(q.untilInput);
    const built = buildQueryVector(places, q);
    if (!built) {
      onError("Source place " + q.sourceId + " is not loaded. Pick another source.");
      return;
    }
    const window = parseWindow(q);
    if (window.error) {
      onError(window.error);
      return;
    }
    await executeSearch(deps(), {
      vector: built.vector,
      sourceLabel: built.label,
      query: q,
      since: window.since,
      until: window.until,
    });
  }

  function clearAll() {
    setHits([]);
    setSearched(false);
    setSelectedId(null);
  }

  const selected = hits.find((h) => h.id === selectedId)?.place || null;

  async function handleChanged(message: string) {
    onNotice(message);
    await loadPlaces();
    if (searched) runSearch();
  }

  const needsSource = sourceMode !== "random";
  const canRun = !busy && (!needsSource || sourceId !== "");

  return (
    <div className="layout">
      <section className="card">
        <h2>Build a query on {agent}</h2>
        <div className="toolbar" role="group" aria-label="Query source">
          <button
            className={sourceMode === "place" ? "active" : ""}
            onClick={() => setSourceMode("place")}
          >
            Stored place
          </button>
          <button
            className={sourceMode === "near" ? "active" : ""}
            onClick={() => setSourceMode("near")}
          >
            Near a place
          </button>
          <button
            className={sourceMode === "random" ? "active" : ""}
            onClick={() => setSourceMode("random")}
          >
            Random vector
          </button>
        </div>

        {needsSource && (
          <label style={{ fontSize: 12, color: "var(--muted)" }}>
            Source place
            <select
              value={sourceId}
              onChange={(e) => setSourceId(e.target.value)}
              style={{ width: "100%", marginTop: 4 }}
              aria-label="Source place"
            >
              {places.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.id} ({p.payload.zone || "no zone"}, {p.confidence.toFixed(2)})
                </option>
              ))}
            </select>
          </label>
        )}

        <div className="slider-row">
          <label>Top results: {topK}</label>
          <input
            type="range"
            min={1}
            max={20}
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            aria-label="Top results"
          />
        </div>
        <div className="slider-row">
          <label>Min confidence: {minConf.toFixed(2)}</label>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={minConf}
            onChange={(e) => setMinConf(Number(e.target.value))}
            aria-label="Minimum confidence"
          />
        </div>

        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <button className="primary" onClick={runSearch} disabled={!canRun}>
            {busy ? "Searching" : "Run search"}
          </button>
          {searched && <button onClick={clearAll}>Clear</button>}
          {(zoneSel.length > 0 ||
            sensorSel.length > 0 ||
            sinceInput !== "" ||
            untilInput !== "") && (
            <button
              onClick={() => {
                setZoneSel([]);
                setSensorSel([]);
                setSinceInput("");
                setUntilInput("");
              }}
            >
              Reset filters
            </button>
          )}
        </div>

        <h3 style={{ fontSize: 13, margin: "14px 0 6px" }}>Zones</h3>
        {allZones.length === 0 ? (
          <p style={{ color: "var(--muted)" }}>No places loaded yet.</p>
        ) : (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {allZones.map((z) => (
              <label key={z} style={{ fontSize: 13 }}>
                <input
                  type="checkbox"
                  checked={zoneSel.includes(z)}
                  onChange={() => toggle(zoneSel, z, setZoneSel)}
                />{" "}
                {z}
              </label>
            ))}
          </div>
        )}

        <h3 style={{ fontSize: 13, margin: "14px 0 6px" }}>Sensors</h3>
        {allSensors.length === 0 ? (
          <p style={{ color: "var(--muted)" }}>No places loaded yet.</p>
        ) : (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {allSensors.map((s) => (
              <label key={s} style={{ fontSize: 13 }}>
                <input
                  type="checkbox"
                  checked={sensorSel.includes(s)}
                  onChange={() => toggle(sensorSel, s, setSensorSel)}
                />{" "}
                {s}
              </label>
            ))}
          </div>
        )}

        <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
          <label style={{ fontSize: 12, color: "var(--muted)", flex: 1 }}>
            Since
            <input
              type="datetime-local"
              value={sinceInput}
              onChange={(e) => setSinceInput(e.target.value)}
              style={{ width: "100%", marginTop: 4 }}
              aria-label="Since date"
            />
          </label>
          <label style={{ fontSize: 12, color: "var(--muted)", flex: 1 }}>
            Until
            <input
              type="datetime-local"
              value={untilInput}
              onChange={(e) => setUntilInput(e.target.value)}
              style={{ width: "100%", marginTop: 4 }}
              aria-label="Until date"
            />
          </label>
        </div>

        {searched && (
          <div style={{ marginTop: 12 }}>
            <h2>
              Results ({hits.length}) in {queryMs} ms
            </h2>
            {hits.length === 0 ? (
              <div className="empty">No matches. Loosen the filters and retry.</div>
            ) : (
              <table className="grid">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Match</th>
                    <th>Score</th>
                    <th>Zone</th>
                    <th>Sensor</th>
                    <th>Conf</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {hits.map((h, i) => (
                    <tr
                      key={h.id}
                      className={h.id === selectedId ? "selected" : ""}
                      onClick={() => setSelectedId(h.id === selectedId ? null : h.id)}
                      style={{ cursor: "pointer" }}
                    >
                      <td>{i + 1}</td>
                      <td>{h.id}</td>
                      <td>
                        <span className="conf-bar">
                          <span
                            className="conf-fill"
                            style={{ width: Math.round(h.score * 100) + "%" }}
                          />
                        </span>
                        <span className="score">{h.score.toFixed(3)}</span>
                      </td>
                      <td>
                        <span className="badge">{h.place.payload.zone || "-"}</span>
                      </td>
                      <td>{h.place.payload.sensor || "-"}</td>
                      <td>{h.place.confidence.toFixed(2)}</td>
                      <td>{formatTime(h.place.timestamp)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </section>

      <aside className="side" style={{ display: "grid", gap: 12 }}>
        <section className="card">
          <h2>Result map</h2>
          {hits.length === 0 ? (
            <p style={{ color: "var(--muted)" }}>
              Run a search to plot its matches.
            </p>
          ) : (
            <PoseMap
              places={hits.map((h) => h.place)}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          )}
        </section>
        <section className="card">
          <h2>Match details</h2>
          <DetailPanel
            key={selected ? selected.id : "none"}
            place={selected}
            onChanged={handleChanged}
            onError={onError}
          />
        </section>
        <section className="card">
          <h2>Past searches</h2>
          {history.length === 0 ? (
            <p style={{ color: "var(--muted)" }}>
              No searches yet. Each run is saved here for re-runs.
            </p>
          ) : (
            <>
              <div style={{ display: "grid", gap: 8 }}>
                {history.map((r) => (
                  <div
                    key={r.id}
                    style={{
                      border: "1px solid var(--line)",
                      borderRadius: 8,
                      padding: "8px 10px",
                      fontSize: 12,
                    }}
                  >
                    <div>
                      <strong>{r.sourceLabel}</strong>
                    </div>
                    <div style={{ color: "var(--muted)" }}>{r.filterLabel}</div>
                    <div style={{ color: "var(--muted)" }}>
                      {r.resultCount} matches
                      {r.topScore !== null && (
                        <>, top score <span className="score">{r.topScore.toFixed(3)}</span></>
                      )}{" "}
                      on {new Date(r.time * 1000).toLocaleString()}
                    </div>
                    <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
                      <button className="small" onClick={() => reRun(r)}>
                        Re-run
                      </button>
                      <button
                        className="small"
                        onClick={() => setHistory(deleteStoredRecord(r.id))}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 8 }}>
                <button
                  className="small"
                  onClick={() => setHistory(clearStoredHistory())}
                >
                  Clear history
                </button>
              </div>
            </>
          )}
        </section>
      </aside>
    </div>
  );
}
