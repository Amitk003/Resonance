import { useEffect, useState } from "react";
import { api, formatTime, type Place } from "../api";

interface Props {
  place: Place | null;
  onChanged: (message: string) => void;
  onError: (message: string) => void;
}

export default function DetailPanel({ place, onChanged, onError }: Props) {
  const [editing, setEditing] = useState(false);
  const [zone, setZone] = useState("");
  const [sensor, setSensor] = useState("");
  const [note, setNote] = useState("");
  const [confidence, setConfidence] = useState("0.9");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setEditing(false);
    if (place) {
      setZone(place.payload.zone);
      setSensor(place.payload.sensor);
      setNote(place.payload.note);
      setConfidence(String(place.confidence));
    }
  }, [place]);

  if (!place) {
    return <p style={{ color: "var(--muted)" }}>Select a row to see details.</p>;
  }

  async function saveEdit() {
    const conf = Number(confidence);
    if (Number.isNaN(conf) || conf < 0 || conf > 1) {
      onError("Confidence must be a number from 0 to 1.");
      return;
    }
    setBusy(true);
    try {
      await api.updatePlace(place!.id, {
        ...place!,
        confidence: conf,
        payload: { zone: zone.trim(), sensor: sensor.trim(), note: note.trim() },
      });
      setEditing(false);
      onChanged("Place " + place!.id + " saved.");
    } catch (e) {
      onError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    const current = place;
    if (!current) return;
    if (!window.confirm("Delete place " + current.id + "? This cannot be undone.")) {
      return;
    }
    setBusy(true);
    try {
      await api.deletePlace(current.agent_id, current.id);
      onChanged("Place " + current.id + " deleted.");
    } catch (e) {
      onError(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <dl className="kv">
        <dt>ID</dt>
        <dd>{place.id}</dd>
        <dt>Agent</dt>
        <dd>{place.agent_id}</dd>
        <dt>Pose</dt>
        <dd>
          x {place.pose.x.toFixed(2)}, y {place.pose.y.toFixed(2)}, heading{" "}
          {place.pose.theta.toFixed(2)}
        </dd>
        <dt>Time</dt>
        <dd>{formatTime(place.timestamp)}</dd>
        {!editing && (
          <>
            <dt>Confidence</dt>
            <dd>{place.confidence.toFixed(2)}</dd>
            <dt>Zone</dt>
            <dd>{place.payload.zone || "-"}</dd>
            <dt>Sensor</dt>
            <dd>{place.payload.sensor || "-"}</dd>
            <dt>Note</dt>
            <dd>{place.payload.note || "-"}</dd>
          </>
        )}
      </dl>

      {editing ? (
        <div className="form-grid">
          <label>
            Zone
            <input value={zone} onChange={(e) => setZone(e.target.value)} />
          </label>
          <label>
            Sensor
            <input value={sensor} onChange={(e) => setSensor(e.target.value)} />
          </label>
          <label>
            Note
            <input value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          <label>
            Confidence (0 to 1)
            <input
              value={confidence}
              onChange={(e) => setConfidence(e.target.value)}
              inputMode="decimal"
            />
          </label>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="primary" onClick={saveEdit} disabled={busy}>
              {busy ? "Saving" : "Save"}
            </button>
            <button onClick={() => setEditing(false)} disabled={busy}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => setEditing(true)}>Edit</button>
          <button className="danger" onClick={remove} disabled={busy}>
            {busy ? "Working" : "Delete"}
          </button>
        </div>
      )}

      <h3 style={{ fontSize: 13, margin: "14px 0 6px" }}>Raw record</h3>
      <pre className="json">{JSON.stringify(place, null, 2)}</pre>
    </div>
  );
}
