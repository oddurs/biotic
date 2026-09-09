import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "vitest";

const here = fileURLToPath(new URL(".", import.meta.url));
const generated = join(here, "generated");
const script = join(here, "../../scripts/generate.ts");

test("generated tokens match the generator (run `pnpm generate` if not)", () => {
  const out = mkdtempSync(join(tmpdir(), "biotic-tokens-"));
  execFileSync(process.execPath, [script], { env: { ...process.env, OUT: out } });
  for (const file of readdirSync(generated)) {
    expect(readFileSync(join(generated, file), "utf8"), file).toBe(
      readFileSync(join(out, file), "utf8"),
    );
  }
});

test("palette lightness ladders line up across hues", async () => {
  const { paletteMeta } = await import("./generated/meta");
  const L = (v: string) => Number(/oklch\(([\d.]+)%/.exec(v)?.[1]);
  const ramps = Object.values(paletteMeta);
  for (const step of [50, 500, 950] as const) {
    const ls = ramps.map((r) => L(r[step]));
    expect(new Set(ls).size).toBe(1);
  }
});
