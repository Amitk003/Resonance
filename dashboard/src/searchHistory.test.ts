/* Offline tests for the search history helpers. Run: npm test */

import { beforeEach, describe, expect, it } from "vitest";
import {
  clearHistory,
  deleteRecord,
  describeQuery,
  HISTORY_LIMIT,
  loadHistory,
  overwriteRawHistory,
  resetHistoryStorage,
  saveRecord,
  type SearchQuery,
  type SearchRecord,
} from "./searchHistory";

const QUERY: SearchQuery = {
  source: "place",
  sourceId: "robot-a-1",
  topK: 5,
  minConf: 0,
  zones: [],
  sensors: [],
  sinceInput: "",
  untilInput: "",
};

function record(id: string, n = 3): SearchRecord {
  return {
    id,
    time: 1727000000 + n,
    agent: "robot-a",
    sourceLabel: "place robot-a-1",
    filterLabel: "robot-a | top 5",
    resultCount: n,
    topScore: 0.99,
    query: { ...QUERY },
  };
}

beforeEach(() => {
  resetHistoryStorage();
});

describe("saveRecord and loadHistory", () => {
  it("round trips records newest first", () => {
    saveRecord(record("a", 1));
    saveRecord(record("b", 2));
    const loaded = loadHistory();
    expect(loaded.map((r) => r.id)).toEqual(["b", "a"]);
  });

  it("replaces a record with the same id", () => {
    saveRecord(record("a", 1));
    saveRecord(record("a", 9));
    const loaded = loadHistory();
    expect(loaded).toHaveLength(1);
    expect(loaded[0].resultCount).toBe(9);
  });

  it("caps the list at the history limit", () => {
    for (let i = 0; i < HISTORY_LIMIT + 5; i++) {
      saveRecord(record("r" + i, i));
    }
    expect(loadHistory()).toHaveLength(HISTORY_LIMIT);
  });

  it("tolerates corrupt storage", () => {
    overwriteRawHistory("not json{{{");
    expect(loadHistory()).toEqual([]);
  });
});

describe("deleteRecord and clearHistory", () => {
  it("removes one entry and keeps the rest", () => {
    saveRecord(record("a", 1));
    saveRecord(record("b", 2));
    expect(deleteRecord("a").map((r) => r.id)).toEqual(["b"]);
  });

  it("clears everything", () => {
    saveRecord(record("a", 1));
    expect(clearHistory()).toEqual([]);
    expect(loadHistory()).toEqual([]);
  });
});

describe("describeQuery", () => {
  it("names the agent, limits, and active filters", () => {
    const text = describeQuery("robot-b", {
      ...QUERY,
      topK: 10,
      zones: ["hall"],
      minConf: 0.5,
      sinceInput: "2026-01-01",
    });
    expect(text).toContain("robot-b");
    expect(text).toContain("top 10");
    expect(text).toContain("hall");
    expect(text).toContain("0.50");
    expect(text).toContain("2026-01-01");
  });

  it("skips blank filters", () => {
    expect(describeQuery("robot-a", QUERY)).toBe("robot-a | top 5");
  });
});
