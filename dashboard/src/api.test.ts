/* Offline tests for the api client helpers and fuse verdict. Fetch is
 * stubbed, no backend. Run: npm test */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, DEFAULT_API_BASE, decideFuse, type Place } from "./api";

const VECTOR = Array.from({ length: 512 }, (_, i) => (i % 7) / 7);

function place(id: string): Place {
  return {
    id,
    agent_id: "robot-a",
    vector: VECTOR,
    pose: { x: 1, y: 2, theta: 0.5 },
    timestamp: 1727000000,
    confidence: 0.9,
    payload: { zone: "hall", sensor: "cam", note: "" },
  };
}

/* Each call gets a fresh Response so bodies are never read twice. */
function fetchJson(status: number, body: unknown) {
  return vi.fn().mockImplementation(async () => {
    return new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  });
}

beforeEach(() => {
  /* The vitest node env has no localStorage, so the api client keeps
   * its default base. Assert against that, not a custom base. */
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("decideFuse", () => {
  it("fuses at or above the threshold", () => {
    expect(decideFuse(0.9, 0.8)).toBe(true);
    expect(decideFuse(0.8, 0.8)).toBe(true);
  });

  it("logs below the threshold", () => {
    expect(decideFuse(0.5, 0.8)).toBe(false);
  });

  it("follows a moved threshold live", () => {
    expect(decideFuse(0.5, 0.8)).toBe(false);
    expect(decideFuse(0.5, 0.4)).toBe(true);
  });
});

describe("listAgents", () => {
  it("hits GET /agents and returns the agent list", async () => {
    const f = fetchJson(200, ["robot-a", "robot-b"]);
    vi.stubGlobal("fetch", f);
    const res = await api.listAgents();
    expect(res).toEqual(["robot-a", "robot-b"]);
    const url = String(f.mock.calls[0][0]);
    expect(url).toBe(DEFAULT_API_BASE + "/agents");
  });
});

describe("bulkAddPlaces", () => {
  it("POSTs one request with the full place list", async () => {
    const f = fetchJson(200, { ids: ["robot-a-1", "robot-a-2"] });
    vi.stubGlobal("fetch", f);
    const res = await api.bulkAddPlaces([place("robot-a-1"), place("robot-a-2")]);
    expect(res.ids).toHaveLength(2);
    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(DEFAULT_API_BASE + "/memory/bulk");
    expect(init.method).toBe("POST");
    const sent = JSON.parse(String(init.body));
    expect(sent).toHaveLength(2);
  });

  it("surfaces backend 422 errors as ApiError", async () => {
    vi.stubGlobal("fetch", fetchJson(422, { detail: "body must hold 1 to 200 places" }));
    await expect(api.bulkAddPlaces([])).rejects.toThrow(/1 to 200/);
  });
});

describe("listPlaces paging", () => {
  it("sends offset only when given", async () => {
    const f = fetchJson(200, { places: [], next_offset: null, total: 0 });
    vi.stubGlobal("fetch", f);
    await api.listPlaces("robot-a", 50);
    let url = String(f.mock.calls[0][0]);
    expect(url).toContain("agent_id=robot-a");
    expect(url).toContain("limit=50");
    expect(url).not.toContain("offset=");

    await api.listPlaces("robot-a", 50, "abc-123");
    url = String(f.mock.calls[1][0]);
    expect(url).toContain("offset=abc-123");
  });
});
