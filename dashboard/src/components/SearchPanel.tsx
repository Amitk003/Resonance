import { useEffect, useState } from "react";
import { api, type Place, type SearchHit } from "../api";

interface Props {
  places: Place[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onError: (message: string) => void;
}

export default function SearchPanel({ places, selectedId, onSelect, onError }: Props) {
  const [sourceId, setSourceId] = useState<string>("");
  const [topK, setTopK] = useState(5);
  const [minConf, setMinConf] = useState(0);
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [searched, setSearched] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (selectedId && places.some((p) => p.id === selectedId)) {
      setSourceId(selectedId);
    } else if (!places.some((p) => p.id === sourceId)) {
      setSourceId(places.length > 0 ? places[0].id : "");
    }
  }, [selectedId, places, sourceId]);

  async function runSearch() {
    const source = places.find((p) => p.id === sourceId);
    if (!source) {
      onError("Pick a source place first.");
      return;
    }
    setBusy(true);
    try {
      const res = await api.search({
        agent_id: source.agent_id,
        vector: source.vector,
        top_k: topK,
        min_confidence: minConf,
      });
      setHits(res);
      setSearched(true);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
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
              {p.id}
            </option>
          ))}
        </select>
      </label>

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
        <button className="primary" onClick={runSearch} disabled={busy || !sourceId}>
          {busy ? "Searching" : "Find similar"}
        </button>
        {searched && (
          <button
            onClick={() => {
              setHits([]);
              setSearched(false);
            }}
          >
            Clear
          </button>
        )}
      </div>

      {searched && (
        <div style={{ marginTop: 10 }}>
          {hits.length === 0 ? (
            <p style={{ color: "var(--muted)" }}>No matches found.</p>
          ) : (
            <table className="grid">
              <thead>
                <tr>
                  <th>Match</th>
                  <th>Score</th>
                  <th>Zone</th>
                </tr>
              </thead>
              <tbody>
                {hits.map((h) => (
                  <tr
                    key={h.id}
                    onClick={() => onSelect(h.id)}
                    style={{ cursor: "pointer" }}
                  >
                    <td>{h.id}</td>
                    <td className="score">{h.score.toFixed(3)}</td>
                    <td>{h.place.payload.zone || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
