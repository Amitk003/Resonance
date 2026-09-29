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

export interface PlaceList {
  places: Place[];
  next_offset: unknown;
  total: number;
}

export const VECTOR_DIM = 512;
export const DEFAULT_API_BASE = "http://localhost:8000";
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
        detail = body.detail.map((d: { msg?: string }) => d.msg || "bad input").join("; ");
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
  listPlaces(agent_id: string, limit: number): Promise<PlaceList> {
    const q = new URLSearchParams({ agent_id, limit: String(limit) });
    return request("/memory/list?" + q.toString());
  },
  getPlace(agent_id: string, place_id: string): Promise<Place> {
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
    const q = new URLSearchParams({ agent_id });
    return request("/memory/" + encodeURIComponent(place_id) + "?" + q.toString(), {
      method: "DELETE",
    });
  },
};

export function formatTime(timestamp: number): string {
  try {
    return new Date(timestamp * 1000).toLocaleString();
  } catch {
    return String(timestamp);
  }
}
