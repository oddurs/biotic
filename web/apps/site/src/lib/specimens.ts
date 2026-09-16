import type { Loader } from "astro/loaders";
import { z } from "astro/zod";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

// A specimen is one culture, shared as the bundle `biotic export` writes:
//   manifest.json   who, when, seed, model, a sentence
//   strains.json    the registry: every strain that ever arose, with its source
//   curve.csv       the growth curve the culture logged
//   genesis.py      the founding genome
// The loader reads a directory per specimen and the schema validates it at build, so a bad
// submission fails CI instead of publishing.

export const strainSchema = z.object({
  id: z.string(),
  parent: z.string().nullable(),
  name: z.string(),
  note: z.string(),
  source: z.string(),
  born: z.number().int(),
  hue: z.number(),
  extinct_at: z.number().int().nullable(),
  peak: z.number().int(),
  generation: z.number().int(),
});

export const curveRowSchema = z.object({
  tick: z.number().int(),
  population: z.number().int(),
  strains: z.number().int(),
  nutrient: z.number(),
  phase: z.string(),
  births: z.number().int(),
  starved: z.number().int(),
  lysed: z.number().int(),
  senescent: z.number().int(),
});

export const specimenSchema = z.object({
  seed: z.string().min(1),
  model: z.string().min(1),
  submitted: z.coerce.date(),
  by: z.string().min(1),
  summary: z.string().min(1).max(400),
  strains: z.array(strainSchema).min(1),
  curve: z.array(curveRowSchema).min(2),
  genesis: z.string().min(1),
});
export type Specimen = z.infer<typeof specimenSchema>;
export type Strain = z.infer<typeof strainSchema>;
export type CurveRow = z.infer<typeof curveRowSchema>;

function parseCurve(csv: string): unknown[] {
  const [head, ...rows] = csv.trim().split(/\r?\n/);
  const cols = (head ?? "").split(",");
  return rows.map((line) => {
    const cells = line.split(",");
    return Object.fromEntries(cols.map((c, i) => [c, c === "phase" ? cells[i] : Number(cells[i])]));
  });
}

export function specimenLoader(base: string): Loader {
  return {
    name: "specimens",
    async load(ctx) {
      ctx.store.clear();
      for (const dir of readdirSync(base)) {
        const path = join(base, dir);
        if (!statSync(path).isDirectory()) continue;
        const read = (f: string) => readFileSync(join(path, f), "utf8");
        const manifest = JSON.parse(read("manifest.json")) as Record<string, unknown>;
        const registry = JSON.parse(read("strains.json")) as { strains: unknown[] };
        const raw = {
          ...manifest,
          strains: registry.strains,
          curve: parseCurve(read("curve.csv")),
          genesis: read("genesis.py"),
        };
        const data = await ctx.parseData({ id: dir, data: raw });
        ctx.store.set({ id: dir, data, digest: ctx.generateDigest(raw) });
        ctx.logger.info(`specimen ${dir}: ${registry.strains.length} strains`);
      }
    },
  };
}

/** Derived facts every view needs. */
export function summarize(s: Specimen) {
  const last = s.curve[s.curve.length - 1];
  return {
    ticks: last?.tick ?? 0,
    peak: Math.max(...s.curve.map((r) => r.population)),
    outcome: last?.phase ?? "unknown",
    living: s.strains.filter((x) => x.extinct_at === null).length,
    generations: Math.max(...s.strains.map((x) => x.generation)),
    strainsTotal: s.strains.length,
  };
}
