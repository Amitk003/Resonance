/* Demo data helpers for the Memory view.
 * Generates clustered 512-d vectors with a seeded random source so
 * similar search shows clear high and low scores. All plain TypeScript,
 * no extra packages.
 */

import { VECTOR_DIM, type Place } from "./api";

const ZONES = ["hall", "lab", "store"];
const SENSORS = ["cam", "lidar"];

/** Small seeded random source (mulberry32). Same seed gives same data. */
export function seededRandom(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state |= 0;
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** One random 512-d vector with values in [0, 1). */
export function randomVector(rand: () => number = Math.random): number[] {
  const v: number[] = new Array(VECTOR_DIM);
  for (let i = 0; i < VECTOR_DIM; i++) v[i] = rand();
  return v;
}

/** Copy of a base vector with uniform noise in [-amount, amount]. */
export function noisyCopy(base: number[], amount: number, rand: () => number): number[] {
  return base.map((x) => x + (rand() * 2 - 1) * amount);
}

/** Next free numeric suffix for ids shaped like "agent-12". */
export function nextSuffix(agent: string, places: Place[]): number {
  let max = 0;
  for (const p of places) {
    const m = new RegExp("^" + agent + "-(\\d+)$").exec(p.id);
    if (m) max = Math.max(max, Number(m[1]));
  }
  return max + 1;
}

/** Build a small clustered demo set for one agent. */
export function buildDemoPlaces(
  agent: string,
  existing: Place[],
  seed = 7,
): Place[] {
  const rand = seededRandom(seed);
  const now = Math.floor(Date.now() / 1000);
  const out: Place[] = [];
  let n = nextSuffix(agent, existing);
  const perCluster = 6;
  for (let c = 0; c < 3; c++) {
    const base = randomVector(rand);
    const cx = c * 4;
    const cy = c % 2 === 0 ? 0 : 3;
    for (let i = 0; i < perCluster; i++) {
      const id = `${agent}-${n++}`;
      out.push({
        id,
        agent_id: agent,
        vector: noisyCopy(base, 0.05, rand),
        pose: {
          x: cx + rand() * 2,
          y: cy + rand() * 2,
          theta: rand() * Math.PI * 2,
        },
        timestamp: now - (c * perCluster + i) * 600,
        confidence: 0.5 + rand() * 0.49,
        payload: {
          zone: ZONES[(c + i) % ZONES.length],
          sensor: SENSORS[i % SENSORS.length],
          note: "demo cluster " + (c + 1),
        },
      });
    }
  }
  return out;
}
