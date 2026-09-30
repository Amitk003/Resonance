import { useState } from "react";
import { api } from "../api";

interface Props {
  value: number;
  onSaved: (next: number) => void;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
}

export default function ThresholdControl({ value, onSaved, onError, onNotice }: Props) {
  const [draft, setDraft] = useState(value.toFixed(2));

  async function save() {
    const parsed = Number(draft);
    if (Number.isNaN(parsed) || parsed < 0 || parsed > 1) {
      onError("Threshold must be a number from 0 to 1.");
      return;
    }
    try {
      const live = await api.setThreshold(parsed);
      onSaved(live.threshold);
      onNotice("Fuse threshold saved at " + live.threshold.toFixed(2) + ".");
    } catch (e) {
      onError(e instanceof Error ? e.message : "Save failed");
    }
  }

  return (
    <div className="slider-row">
      <label>Fuse threshold: {Number(draft || 0).toFixed(2)}</label>
      <input
        type="range"
        min={0}
        max={1}
        step={0.05}
        value={Number.isNaN(Number(draft)) ? value : Number(draft)}
        onChange={(e) => setDraft(e.target.value)}
        aria-label="Fuse threshold"
      />
      <button className="small" onClick={save}>
        Save
      </button>
    </div>
  );
}
