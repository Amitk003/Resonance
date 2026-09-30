/* Values shared by dashboard pages. One place so Memory and Search
 * stay in sync on agent names and page keys.
 */

// Fixed pair for the demo. A third robot needs a backend agent-list
// endpoint first (no such contract yet), then this becomes dynamic.
export const AGENTS = ["robot-a", "robot-b"];

export type PageKey = "memory" | "search" | "merges" | "sync";

export const PAGES: { key: PageKey; label: string }[] = [
  { key: "memory", label: "Memory" },
  { key: "search", label: "Search results" },
  { key: "merges", label: "Merge history" },
  { key: "sync", label: "Sync status" },
];

export function downloadJson(filename: string, data: unknown): void {
  const text = JSON.stringify(data, null, 2);
  const blob = new Blob([text], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
