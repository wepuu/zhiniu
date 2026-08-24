import { readFileSync, readdirSync } from "node:fs";
import { extname, join } from "node:path";
import { describe, expect, it } from "vitest";

const sourceRoots = [
  join(process.cwd(), "src", "app"),
  join(process.cwd(), "src", "components"),
];

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    if (extname(path) !== ".tsx" || path.endsWith(".test.tsx")) return [];
    return [path];
  });
}

const retiredVisibleCopy = [
  "Personal research desk",
  "Evidence comparison",
  "Saved definitions",
  "Recent research",
  "Company comparison",
  "Deterministic limits",
  "AI generated content",
  "Research coverage",
  "Research Screener",
  "Saved Research Workspace",
  "Secure research workspace",
  "Managed configuration",
  "CORPORATE DISCLOSURE",
  "EVENT THREAD",
  "Peer benchmark",
  "请检查 API 服务",
  "内部 beta 额度",
  "Version {",
  ">Median<",
  ">Conditions<",
  ">Preferences<",
  ">Security<",
  ">Access<",
] as const;

describe("visible UI copy guard", () => {
  it("does not reintroduce retired English headings", () => {
    const source = sourceRoots
      .flatMap(sourceFiles)
      .map((path) => readFileSync(path, "utf8"))
      .join("\n");

    for (const text of retiredVisibleCopy) {
      expect(source, `retired visible copy: ${text}`).not.toContain(text);
    }
  });
});
