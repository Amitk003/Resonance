/* Offline tests for the demo data helpers. Run: npm test */

import { describe, expect, it } from "vitest";
import { VECTOR_DIM } from "./api";
import {
  buildDemoPlaces,
  nextSuffix,
  noisyCopy,
  randomVector,
  seededRandom,
} from "./demo";

describe("seededRandom", () => {
  it("replays the same sequence for the same seed", () => {
    const a = seededRandom(7);
    const b = seededRandom(7);
    expect([a(), a(), a()]).toEqual([b(), b(), b()]);
  });

  it("differs across seeds", () => {
    expect(seededRandom(7)()).not.toBe(seededRandom(8)());
  });
});

describe("randomVector", () => {
  it("has 512 values in [0, 1)", () => {
    expect(VECTOR_DIM).toBe(512);
    const v = randomVector(seededRandom(1));
    expect(v).toHaveLength(512);
    for (const x of v) {
      expect(x).toBeGreaterThanOrEqual(0);
      expect(x).toBeLessThan(1);
    }
  });
});

describe("noisyCopy", () => {
  it("stays within the noise band", () => {
    const base = randomVector(seededRandom(2));
    const copy = noisyCopy(base, 0.05, seededRandom(3));
    expect(copy).toHaveLength(base.length);
    for (let i = 0; i < base.length; i++) {
      expect(Math.abs(copy[i] - base[i])).toBeLessThanOrEqual(0.05);
    }
  });
});

describe("nextSuffix", () => {
  it("returns 1 when nothing is stored", () => {
    expect(nextSuffix("robot-a", [])).toBe(1);
  });

  it("continues after the highest numeric suffix", () => {
    const places = buildDemoPlaces("robot-a", [], 7);
    expect(nextSuffix("robot-a", places)).toBe(places.length + 1);
  });

  it("ignores ids from other agents and odd shapes", () => {
    const places = buildDemoPlaces("robot-a", [], 7);
    const mixed = [
      ...places,
      { ...places[0], id: "robot-b-99", agent_id: "robot-b" },
      { ...places[0], id: "robot-a-temp" },
    ];
    expect(nextSuffix("robot-a", mixed)).toBe(places.length + 1);
  });
});

describe("buildDemoPlaces", () => {
  it("builds 18 clustered places with valid fields", () => {
    const places = buildDemoPlaces("robot-a", [], 7);
    expect(places).toHaveLength(18);
    const ids = places.map((p) => p.id);
    expect(new Set(ids).size).toBe(18);
    for (const p of places) {
      expect(p.agent_id).toBe("robot-a");
      expect(p.vector).toHaveLength(512);
      expect(p.confidence).toBeGreaterThanOrEqual(0.5);
      expect(p.confidence).toBeLessThan(1);
    }
  });

  it("is deterministic for the same seed", () => {
    const a = buildDemoPlaces("robot-a", [], 7);
    const b = buildDemoPlaces("robot-a", [], 7);
    expect(a).toEqual(b);
  });
});
