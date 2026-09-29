import { useState } from "react";
import {
  api,
  VECTOR_DIM,
  type Place,
} from "../api";
import { nextSuffix, noisyCopy, randomVector, seededRandom } from "../demo";

interface Props {
  agent: string;
  places: Place[];
  seedPlace: Place | null;
  onAdded: (message: string) => void;
  onError: (message: string) => void;
  onClose: () => void;
}

export default function AddPlaceForm({
  agent,
  places,
  seedPlace,
  onAdded,
  onError,
  onClose,
}: Props) {
  const [id, setId] = useState(agent + "-" + nextSuffix(agent, places));
  const [zone, setZone] = useState("hall");
  const [sensor, setSensor] = useState("cam");
  const [note, setNote] = useState("");
  const [x, setX] = useState("1.0");
  const [y, setY] = useState("2.0");
  const [theta, setTheta] = useState("0.0");
  const [confidence, setConfidence] = useState("0.9");
  const [mode, setMode] = useState<"random" | "near">("random");
  const [busy, setBusy] = useState(false);

  async function save() {
    const px = Number(x);
    const py = Number(y);
    const th = Number(theta);
    const conf = Number(confidence);
    if (!id.trim()) {
      onError("ID must not be empty.");
      return;
    }
    if ([px, py, th].some((v) => Number.isNaN(v))) {
      onError("Pose x, y, and heading must be numbers.");
      return;
    }
    if (Number.isNaN(conf) || conf < 0 || conf > 1) {
      onError("Confidence must be a number from 0 to 1.");
      return;
    }
    let vector: number[];
    if (mode === "near") {
      if (!seedPlace) {
        onError("Select a place first to copy a near vector.");
        return;
      }
      vector = noisyCopy(seedPlace.vector, 0.05, seededRandom(Date.now() % 100000));
    } else {
      vector = randomVector();
    }
    if (vector.length !== VECTOR_DIM) {
      onError("Vector must have 512 values.");
      return;
    }
    setBusy(true);
    try {
      await api.addPlace({
        id: id.trim(),
        agent_id: agent,
        vector,
        pose: { x: px, y: py, theta: th },
        timestamp: Math.floor(Date.now() / 1000),
        confidence: conf,
        payload: { zone: zone.trim(), sensor: sensor.trim(), note: note.trim() },
      });
      onAdded("Place " + id.trim() + " saved.");
      onClose();
    } catch (e) {
      onError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="form-grid">
      <label>
        ID
        <input value={id} onChange={(e) => setId(e.target.value)} />
      </label>
      <div className="form-row">
        <label>
          X
          <input value={x} onChange={(e) => setX(e.target.value)} inputMode="decimal" />
        </label>
        <label>
          Y
          <input value={y} onChange={(e) => setY(e.target.value)} inputMode="decimal" />
        </label>
        <label>
          Heading
          <input
            value={theta}
            onChange={(e) => setTheta(e.target.value)}
            inputMode="decimal"
          />
        </label>
      </div>
      <div className="form-row">
        <label>
          Zone
          <input value={zone} onChange={(e) => setZone(e.target.value)} />
        </label>
        <label>
          Sensor
          <input value={sensor} onChange={(e) => setSensor(e.target.value)} />
        </label>
        <label>
          Confidence
          <input
            value={confidence}
            onChange={(e) => setConfidence(e.target.value)}
            inputMode="decimal"
          />
        </label>
      </div>
      <label>
        Note
        <input value={note} onChange={(e) => setNote(e.target.value)} />
      </label>
      <label>
        Vector
        <select value={mode} onChange={(e) => setMode(e.target.value as "random" | "near")}>
          <option value="random">Fresh random vector</option>
          <option value="near">
            Near selected place{seedPlace ? " (" + seedPlace.id + ")" : " (none selected)"}
          </option>
        </select>
      </label>
      <div style={{ display: "flex", gap: 8 }}>
        <button className="primary" onClick={save} disabled={busy}>
          {busy ? "Saving" : "Save place"}
        </button>
        <button onClick={onClose} disabled={busy}>
          Cancel
        </button>
      </div>
    </div>
  );
}
