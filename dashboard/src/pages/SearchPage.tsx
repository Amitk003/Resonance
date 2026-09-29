import { useCallback, useEffect, useMemo, useState } from "react";
import { api, formatTime, type Place, type SearchHit } from "../api";
import DetailPanel from "../components/DetailPanel";
import { noisyCopy, randomVector, seededRandom } from "../demo";

type SourceMode = "place" | "random" | "near";

interface Props {
  agent: string;
  reloadToken: number;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
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

  function parseDateTime(raw: string): number | undefined | null {
    const clean = raw.trim();
    if (clean === "") return undefined;
    const ms = new Date(clean).getTime();
    if (Number.isNaN(ms) || ms < 0) return null;
    return Math.floor(ms / 1000);
  }

  function buildVector(): { vector: number[]; label: string } | null {
    if (sourceMode === "random") {
      return { vector: randomVector(), label: "fresh random vector" };
    }
    const base = places.find((p) => p.id === sourceId);
    if (!base) return null;
    if (sourceMode === "near") {
      return {
        vector: noisyCopy(base.vector, 0.05, seededRandom(Date.now() % 100000)),
        label: "near " + base.id,
      };
    }
    return { vector: base.vector, label: "place " + base.id };
  }

  async function runSearch() {
    const built = buildVector();
    if (!built) {
      onError("Pick a source place first, or use a random vector.");
      return;
    }
    const since = parseDateTime(sinceInput);
    const until = parseDateTime(untilInput);
    if (since === null || until === null) {
      onError("Since and Until must be valid dates, or left blank.");
      return;
    }
    if (since !== undefined && until !== undefined && since > until) {
      onError("Since must not be after Until.");
      return;
    }
    setBusy(true);
    const started = performance.now();
    try {
      const res = await api.search({
        agent_id: agent,
        vector: built.vector,
        top_k: topK,
        min_confidence: minConf,
        zones: zoneSel,
        sensors: sensorSel,
        since,
        until,
      });
      setHits(res);
      setSearched(true);
      setSelectedId(null);
      const ms = Math.round(performance.now() - started);
      setQueryMs(ms);
      const parts = [built.label, "top " + topK];
      if (zoneSel.length > 0) parts.push("zones " + zoneSel.join(", "));
      if (sensorSel.length > 0) parts.push("sensors " + sensorSel.join(", "));
      if (minConf > 0) parts.push("confidence over " + minConf.toFixed(2));
      onNotice("Search done in " + ms + " ms, " + res.length + " matches (" + parts.join(" | ") + ").");
    } catch (e) {
      onError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setBusy(false);
    }
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
          <h2>Match details</h2>
          <DetailPanel
            place={selected}
            onChanged={handleChanged}
            onError={onError}
          />
        </section>
      </aside>
    </div>
  );
}
