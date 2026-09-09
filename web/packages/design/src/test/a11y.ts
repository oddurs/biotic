import axe from "axe-core";
import { expect } from "vitest";

/** Fails the test on any axe violation inside `root`, printing the offending nodes. */
export async function expectAccessible(root: Element = document.body): Promise<void> {
  // `region` is a page rule (content inside landmarks); components are tested in isolation.
  const result = await axe.run(root, {
    resultTypes: ["violations"],
    rules: { region: { enabled: false } },
  });
  const report = result.violations.map(
    (v) => `${v.id} (${v.impact ?? "?"}): ${v.help}\n  ${v.nodes.map((n) => n.html).join("\n  ")}`,
  );
  expect(report, report.join("\n\n")).toEqual([]);
}
