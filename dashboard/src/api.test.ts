/* Offline tests for the fuse verdict helper. Run: npm test */

import { describe, expect, it } from "vitest";
import { decideFuse } from "./api";

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
