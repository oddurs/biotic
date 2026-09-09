// Generates the reference palette and the fluid scales. StyleX needs literal values, so the
// numbers are computed here once and written into src/tokens/generated/. Rerun with
// `pnpm generate`; the test in src/tokens/generated.test.ts fails if the files drift.
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const out =
  process.env.OUT ?? join(dirname(fileURLToPath(import.meta.url)), "../src/tokens/generated");

// --- palette -----------------------------------------------------------------------
// Eleven steps per hue in OKLCH. Lightness is the same ladder for every hue so steps line
// up across ramps; chroma follows a bell that peaks in the middle, scaled per hue.
const steps = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950] as const;
const lightness = [97.5, 94, 88, 79, 70, 60, 51, 43, 35, 27, 19] as const;
const hues = {
  // the instrument's own colours: agar green, pheromone violet, the glass of the dish,
  // nutrient amber, and the red of lysis
  glass: { hue: 155, chroma: 0.012 },
  agar: { hue: 152, chroma: 0.15 },
  pheromone: { hue: 300, chroma: 0.16 },
  nutrient: { hue: 78, chroma: 0.14 },
  lysis: { hue: 25, chroma: 0.17 },
} as const;
const bell = (i: number) => Math.sin((Math.PI * (i + 0.5)) / steps.length) ** 1.15;
const r = (n: number, d = 3) => Number(n.toFixed(d));
const oklch = (l: number, c: number, h: number) => `oklch(${r(l, 1)}% ${r(c)} ${h})`;

const palette: Record<string, string> = {};
const paletteMeta: Record<string, Record<number, string>> = {};
for (const [name, { hue, chroma }] of Object.entries(hues)) {
  paletteMeta[name] = {};
  steps.forEach((step, i) => {
    const l = lightness[i] as number;
    const value = oklch(l, chroma * bell(i), hue);
    palette[`${name}${step}`] = value;
    (paletteMeta[name] as Record<number, string>)[step] = value;
  });
}

// --- semantic colour ----------------------------------------------------------------
// Components use these names, never the palette. The two faces are the same vocabulary;
// `color` follows the system preference and the generated themes force one face.
const ref = (name: string) => `p.${name}`;
const faces = {
  light: {
    surfaceCanvas: ref("glass50"),
    surfaceRaised: '"oklch(100% 0 0)"',
    surfaceSunken: ref("glass100"),
    surfaceInverse: ref("glass950"),
    inkPrimary: ref("glass950"),
    inkSecondary: ref("glass700"),
    inkMuted: ref("glass500"),
    inkInverse: ref("glass50"),
    edgeSubtle: ref("glass200"),
    edgeStrong: ref("glass300"),
    edgeFocus: ref("agar600"),
    accentBase: ref("agar600"),
    accentHover: ref("agar700"),
    accentSoft: ref("agar100"),
    accentInk: '"oklch(100% 0 0)"',
    positiveBase: ref("agar600"),
    positiveSoft: ref("agar100"),
    cautionBase: ref("nutrient600"),
    cautionSoft: ref("nutrient100"),
    negativeBase: ref("lysis600"),
    negativeSoft: ref("lysis100"),
    infoBase: ref("pheromone600"),
    infoSoft: ref("pheromone100"),
    selection: ref("agar200"),
  },
  dark: {
    surfaceCanvas: ref("glass950"),
    surfaceRaised: ref("glass900"),
    surfaceSunken: '"oklch(15% 0.008 155)"',
    surfaceInverse: ref("glass50"),
    inkPrimary: ref("glass50"),
    inkSecondary: ref("glass300"),
    inkMuted: ref("glass500"),
    inkInverse: ref("glass950"),
    edgeSubtle: ref("glass800"),
    edgeStrong: ref("glass700"),
    edgeFocus: ref("agar400"),
    accentBase: ref("agar400"),
    accentHover: ref("agar300"),
    accentSoft: ref("agar900"),
    accentInk: ref("glass950"),
    positiveBase: ref("agar400"),
    positiveSoft: ref("agar900"),
    cautionBase: ref("nutrient400"),
    cautionSoft: ref("nutrient900"),
    negativeBase: ref("lysis400"),
    negativeSoft: ref("lysis900"),
    infoBase: ref("pheromone400"),
    infoSoft: ref("pheromone900"),
    selection: ref("agar800"),
  },
} as const;
const semanticNames = Object.keys(faces.light) as (keyof typeof faces.light)[];
// Resolve a face entry to its literal value for documentation.
const literal = (v: string) => (v.startsWith("p.") ? palette[v.slice(2)] : JSON.parse(v)) as string;

// --- fluid type and space -----------------------------------------------------------
// A clamp() per step between a 20rem and an 80rem viewport, in the manner of Utopia.
const vw = { min: 20, max: 80 };
const type = { minBase: 1, maxBase: 1.125, minRatio: 1.2, maxRatio: 1.25 };
const clampBetween = (min: number, max: number) => {
  const slope = (max - min) / (vw.max - vw.min);
  const intercept = min - slope * vw.min;
  return `clamp(${r(min, 4)}rem, ${r(intercept, 4)}rem + ${r(slope * 100, 4)}vw, ${r(max, 4)}rem)`;
};
const typeSteps = [-2, -1, 0, 1, 2, 3, 4, 5, 6] as const;
const fluidType: Record<string, string> = {};
for (const step of typeSteps) {
  const key = step < 0 ? `n${-step}` : `${step}`;
  fluidType[`step${key}`] = clampBetween(
    type.minBase * type.minRatio ** step,
    type.maxBase * type.maxRatio ** step,
  );
}
// Space pairs in rem at the small and large viewport.
const spacePairs: Record<string, [number, number]> = {
  xs: [0.5, 0.625],
  sm: [0.75, 1],
  md: [1, 1.5],
  lg: [1.5, 2.25],
  xl: [2, 3.5],
  xxl: [3, 5.5],
  xxxl: [4, 8],
};
const fluidSpace: Record<string, string> = {};
for (const [k, [min, max]] of Object.entries(spacePairs)) fluidSpace[k] = clampBetween(min, max);

// --- emit --------------------------------------------------------------------------
const header = "// Generated by scripts/generate.ts. Do not edit; run `pnpm generate`.\n";
const vars = (name: string, obj: Record<string, string>) =>
  `export const ${name} = stylex.defineVars({\n${Object.entries(obj)
    .map(([k, v]) => `  ${k}: "${v}",`)
    .join("\n")}\n});\n`;
mkdirSync(out, { recursive: true });
writeFileSync(
  join(out, "palette.stylex.ts"),
  `${header}import * as stylex from "@stylexjs/stylex";\n\n${vars("palette", palette)}`,
);
writeFileSync(
  join(out, "fluid.stylex.ts"),
  `${header}import * as stylex from "@stylexjs/stylex";\n\n${vars("fluidType", fluidType)}\n${vars("fluidSpace", fluidSpace)}`,
);
const DARK = "@media (prefers-color-scheme: dark)";
writeFileSync(
  join(out, "color.stylex.ts"),
  `${header}import * as stylex from "@stylexjs/stylex";\nimport { palette as p } from "./palette.stylex";\n\n` +
    `export const color = stylex.defineVars({\n${semanticNames
      .map((k) => `  ${k}: { default: ${faces.light[k]}, "${DARK}": ${faces.dark[k]} },`)
      .join("\n")}\n});\n`,
);
const theme = (name: string, face: "light" | "dark") =>
  `/** Forces the ${face} face regardless of system preference. Apply to <html>. */\n` +
  `export const ${name} = stylex.createTheme(color, {\n${semanticNames
    .map((k) => `  ${k}: ${faces[face][k]},`)
    .join("\n")}\n});\n`;
writeFileSync(
  join(out, "faces.ts"),
  `${header}import * as stylex from "@stylexjs/stylex";\nimport { color } from "./color.stylex";\nimport { palette as p } from "./palette.stylex";\n\n${theme("lightTheme", "light")}\n${theme("darkTheme", "dark")}`,
);
const colorMeta = Object.fromEntries(
  semanticNames.map((k) => [k, { light: literal(faces.light[k]), dark: literal(faces.dark[k]) }]),
);
writeFileSync(
  join(out, "meta.ts"),
  `${header}// Raw values for documentation and tests; the .stylex.ts files are what components use.\n` +
    `export const paletteMeta = ${JSON.stringify(paletteMeta, null, 2)} as const;\n` +
    `export const fluidTypeMeta = ${JSON.stringify(fluidType, null, 2)} as const;\n` +
    `export const fluidSpaceMeta = ${JSON.stringify(fluidSpace, null, 2)} as const;\n` +
    `export const colorMeta = ${JSON.stringify(colorMeta, null, 2)} as const;\n`,
);
console.log(
  `wrote ${Object.keys(palette).length} palette tokens, ${typeSteps.length} type steps, ${Object.keys(spacePairs).length} space steps to ${out}`,
);
