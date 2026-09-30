/* Typed client for the Resonance backend REST API.
 * Base URL is http://localhost:8000 by default and can be changed
 * from the dashboard header. It is saved in localStorage.
 * See docs/api.md for the endpoint contracts.
 */

export interface Pose {
  x: number;
  y: number;
  theta: number;
}

export interface Payload {
  zone: string;
  sensor: string;
  note: string;
}

export interface Place {
  id: string;
  agent_id: string;
  vector: number[];
  pose: Pose;
  timestamp: number;
  confidence: number;
  payload: Payload;
}

export interface SearchHit {
  id: string;
  score: number;
  place: Place;
}

export interface Transform {
  dx: number;
  dy: number;
  dtheta: number;
}

export interface MergeRecord {
  id: string;
  timestamp: number;
  agent_a: string;
  agent_b: string;
  pairs_total: number;
  inliers: number;
  mean_score: number;
  score: number;
  transform: Transform;
  anchor_ids: string[];
}

export interface PlaceList {
  places: Place[];
  next_offset: unknown;
  total: number;
}

export const VECTOR_DIM = 512;
/* Build time default for custom domains. Set VITE_API_BASE at build. */
export const DEFAULT_API_BASE =
  (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_BASE ||
  "http://localhost:8000";
const STORAGE_KEY = "resonance.apiBase";

export function getApiBase(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) || DEFAULT_API_BASE;
  } catch {
    return DEFAULT_API_BASE;
  }
}

export function setApiBase(url: string): void {
  try {
    localStorage.setItem(STORAGE_KEY, url.replace(/\/+$/, ""));
  } catch {
    /* storage unavailable, keep memory only */
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(getApiBase() + path, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    });
  } catch {
    throw new ApiError(0, "Cannot reach backend. Is it running on " + getApiBase() + "?");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (Array.isArray(body?.detail)) {
        detail = body.detail
          .map((d: { loc?: (string | number)[]; msg?: string }) => {
            const field = d.loc ? d.loc.filter((x) => x !== "query").join(".") : "";
            return (field ? field + ": " : "") + (d.msg || "bad input");
          })
          .join("; ");
      }
    } catch {
      /* keep status text */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  health(): Promise<{ status: string }> {
    return request("/health");
  },
  addPlace(place: Place): Promise<{ id: string }> {
    return request("/memory/add", { method: "POST", body: JSON.stringify(place) });
  },
  bulkAddPlaces(places: Place[]): Promise<{ ids: string[] }> {
    return request("/memory/bulk", { method: "POST", body: JSON.stringify(places) });
  },
  search(params: {
    agent_id: string;
    vector: number[];
    top_k: number;
    min_confidence: number;
    zones?: string[];
    sensors?: string[];
    since?: number;
    until?: number;
  }): Promise<SearchHit[]> {
    return request("/memory/search", { method: "POST", body: JSON.stringify(params) });
  },
  listPlaces(agent_id: string, limit: number, offset?: unknown): Promise<PlaceList> {
    if (!agent_id || !agent_id.trim()) throw new ApiError(422, "agent_id: Field required");
    const q = new URLSearchParams({ agent_id, limit: String(limit) });
    if (offset !== undefined && offset !== null) q.set("offset", String(offset));
    return request("/memory/list?" + q.toString());
  },
  getPlace(agent_id: string, place_id: string): Promise<Place> {
    if (!agent_id || !agent_id.trim()) throw new ApiError(422, "agent_id: Field required");
    const q = new URLSearchParams({ agent_id });
    return request("/memory/" + encodeURIComponent(place_id) + "?" + q.toString());
  },
  updatePlace(place_id: string, place: Place): Promise<{ id: string }> {
    return request("/memory/" + encodeURIComponent(place_id), {
      method: "PUT",
      body: JSON.stringify(place),
    });
  },
  deletePlace(agent_id: string, place_id: string): Promise<{ deleted: boolean }> {
    if (!agent_id || !agent_id.trim()) throw new ApiError(422, "agent_id: Field required");
    const q = new URLSearchParams({ agent_id });
    return request("/memory/" + encodeURIComponent(place_id) + "?" + q.toString(), {
      method: "DELETE",
    });
  },
  runAlign(params: {
    agent_a: string;
    agent_b: string;
    swap_limit?: number;
    top_k?: number;
    min_score?: number;
  }): Promise<MergeRecord> {
    return request("/meet/align", { method: "POST", body: JSON.stringify(params) });
  },
  listMerges(limit = 50): Promise<MergeRecord[]> {
    const q = new URLSearchParams({ limit: String(limit) });
    return request("/merges?" + q.toString());
  },
  syncQueue(agent_id: string, limit = 20): Promise<SyncItem[]> {
    if (!agent_id || !agent_id.trim()) throw new ApiError(422, "agent_id: Field required");
    const q = new URLSearchParams({ agent_id, limit: String(limit) });
    return request("/sync/queue?" + q.toString());
  },
  pushSync(agent_id: string, limit = 20): Promise<SyncPushResponse> {
    return request("/sync/push", {
      method: "POST",
      body: JSON.stringify({ agent_id, limit }),
    });
  },
  getThreshold(): Promise<{ threshold: number }> {
    return request("/fuse/threshold");
  },
  setThreshold(threshold: number): Promise<{ threshold: number }> {
    return request("/fuse/threshold", {
      method: "PUT",
      body: JSON.stringify({ threshold }),
    });
  },
  listAgents(): Promise<string[]> {
    return request("/agents");
  },
  listConflicts(place_id: string): Promise<ConflictEntry[]> {
    const q = new URLSearchParams({ place_id });
    return request("/sync/conflicts?" + q.toString());
  },
};

export function formatTime(timestamp: number): string {
  try {
    return new Date(timestamp * 1000).toLocaleString();
  } catch {
    return String(timestamp);
  }
}

export interface SyncItem {
  place: Place;
  score: number;
  reasons: string[];
}

export interface ConflictEntry {
  id: string;
  winner_id: string;
  loser_id: string;
  reason: string;
}

export interface SyncPushResponse {
  uploaded: number;
  unchanged: number;
  kept: number;
  conflicts: ConflictEntry[];
}

export function decideFuse(score: number, threshold: number): boolean {
  return score >= threshold;
}
