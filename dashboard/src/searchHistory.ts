/* Search history for the Search results page.
 * Pure helpers plus a thin localStorage layer, so past runs can be
 * re-run or cleared. Kept separate for easy unit tests.
 */

export type QuerySource = "place" | "random" | "near";

export interface SearchQuery {
  source: QuerySource;
  sourceId: string;
  topK: number;
  minConf: number;
  zones: string[];
  sensors: string[];
  sinceInput: string;
  untilInput: string;
}

export interface SearchRecord {
  id: string;
  time: number;
  agent: string;
  sourceLabel: string;
  filterLabel: string;
  resultCount: number;
  topScore: number | null;
  query: SearchQuery;
}

const STORAGE_KEY = "resonance.searchHistory";
export const HISTORY_LIMIT = 20;

interface KeyStore {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

const memory: Record<string, string> = {};
const memoryStore: KeyStore = {
  getItem: (key) => (key in memory ? memory[key] : null),
  setItem: (key, value) => {
    memory[key] = value;
  },
  removeItem: (key) => {
    delete memory[key];
  },
};

/** Browser store when present, memory fallback otherwise (tests, SSR). */
function activeStore(): KeyStore {
  try {
    if (typeof localStorage !== "undefined") {
      localStorage.getItem(STORAGE_KEY);
      return localStorage;
    }
  } catch {
    /* storage blocked, use memory */
  }
  return memoryStore;
}

function readRaw(): unknown {
  try {
    const raw = activeStore().getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

function isRecord(x: unknown): x is SearchRecord {
  if (typeof x !== "object" || x === null) return false;
  const r = x as Record<string, unknown>;
  return (
    typeof r.id === "string" &&
    typeof r.time === "number" &&
    typeof r.agent === "string" &&
    typeof r.query === "object" &&
    r.query !== null
  );
}

function writeAll(records: SearchRecord[]): void {
  try {
    activeStore().setItem(STORAGE_KEY, JSON.stringify(records));
  } catch {
    /* storage unavailable, history just stays in memory */
  }
}

/** Clear every store. Used by tests to start clean. */
export function resetHistoryStorage(): void {
  for (const key of Object.keys(memory)) delete memory[key];
  try {
    activeStore().removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

/** Overwrite the raw stored text. Used by tests to plant corrupt data. */
export function overwriteRawHistory(text: string): void {
  activeStore().setItem(STORAGE_KEY, text);
}

export function loadHistory(): SearchRecord[] {
  const raw = readRaw();
  if (!Array.isArray(raw)) return [];
  return raw.filter(isRecord);
}

export function saveRecord(record: SearchRecord): SearchRecord[] {
  const kept = [record, ...loadHistory().filter((r) => r.id !== record.id)];
  const trimmed = kept.slice(0, HISTORY_LIMIT);
  writeAll(trimmed);
  return trimmed;
}

export function deleteRecord(id: string): SearchRecord[] {
  const kept = loadHistory().filter((r) => r.id !== id);
  writeAll(kept);
  return kept;
}

export function clearHistory(): SearchRecord[] {
  writeAll([]);
  return [];
}

export function describeQuery(agent: string, q: SearchQuery): string {
  const parts = ["top " + q.topK];
  if (q.zones.length > 0) parts.push("zones " + q.zones.join(", "));
  if (q.sensors.length > 0) parts.push("sensors " + q.sensors.join(", "));
  if (q.minConf > 0) parts.push("confidence over " + q.minConf.toFixed(2));
  if (q.sinceInput !== "") parts.push("since " + q.sinceInput);
  if (q.untilInput !== "") parts.push("until " + q.untilInput);
  return agent + " | " + parts.join(" | ");
}
