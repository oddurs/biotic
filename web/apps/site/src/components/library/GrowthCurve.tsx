import * as stylex from "@stylexjs/stylex";
import { Text } from "@biotic/design";
import { color } from "@biotic/design/tokens/color.stylex";
import { font } from "@biotic/design/tokens/type.stylex";
import type { CurveRow } from "../../lib/specimens";

const W = 640;
const H = 220;
const PAD = { top: 18, right: 12, bottom: 28, left: 40 };

const styles = stylex.create({
  svg: { display: "block", height: "auto", width: "100%" },
  axis: { fill: color.inkMuted, fontFamily: font.mono, fontSize: "10px" },
  grid: { stroke: color.edgeSubtle },
  population: { fill: "none", stroke: color.accentBase, strokeWidth: 2 },
  strains: { fill: "none", stroke: color.infoBase, strokeDasharray: "4 3", strokeWidth: 1.5 },
  nutrient: { fill: color.cautionSoft, opacity: 0.6 },
  legend: {
    gap: "1rem",
    alignItems: "center",
    display: "flex",
    flexWrap: "wrap",
    marginTop: "0.5rem",
  },
  key: {
    display: "inline-block",
    marginInlineEnd: "0.35rem",
    verticalAlign: "middle",
    height: "0.6rem",
    width: "1.25rem",
  },
  keyPop: { backgroundColor: color.accentBase },
  keyStrains: { backgroundColor: color.infoBase },
  keyNutrient: { backgroundColor: color.cautionSoft },
});
const phaseFill = stylex.create({
  lag: { fill: color.infoSoft },
  log: { fill: color.positiveSoft },
  stationary: { fill: color.cautionSoft },
  death: { fill: color.negativeSoft },
  sterile: { fill: color.surfaceSunken },
});

const path = (pts: [number, number][]) =>
  pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");

/** Population, living strains, and mean nutrient over ticks, with the phase as a band. */
export function GrowthCurve({ curve }: { curve: CurveRow[] }) {
  const maxTick = curve[curve.length - 1]?.tick ?? 1;
  const maxPop = Math.max(1, ...curve.map((r) => r.population));
  const maxStrains = Math.max(1, ...curve.map((r) => r.strains));
  const x = (t: number) => PAD.left + (t / maxTick) * (W - PAD.left - PAD.right);
  const plotH = H - PAD.top - PAD.bottom;
  const yPop = (p: number) => PAD.top + plotH - (p / maxPop) * plotH;
  const yStr = (s: number) => PAD.top + plotH - (s / maxStrains) * plotH;
  const yNut = (n: number) => PAD.top + plotH - n * plotH;

  const bands: { phase: string; from: number; to: number }[] = [];
  for (const r of curve) {
    const last = bands[bands.length - 1];
    if (last?.phase === r.phase) last.to = r.tick;
    else bands.push({ phase: r.phase, from: r.tick, to: r.tick });
  }
  const nutrientArea = `${path(curve.map((r) => [x(r.tick), yNut(r.nutrient)]))} L${x(maxTick).toFixed(1)},${(PAD.top + plotH).toFixed(1)} L${x(0).toFixed(1)},${(PAD.top + plotH).toFixed(1)} Z`;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(f * maxTick));

  return (
    <figure>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Growth curve over ${maxTick} ticks; peak population ${maxPop}`}
        {...stylex.props(styles.svg)}
      >
        {bands.map((b) => (
          <rect
            key={b.from}
            x={x(b.from)}
            y={2}
            width={Math.max(1, x(b.to) - x(b.from))}
            height={10}
            {...stylex.props(phaseFill[b.phase as keyof typeof phaseFill] ?? phaseFill.sterile)}
          />
        ))}
        {[0.5, 1].map((f) => (
          <line
            key={f}
            x1={PAD.left}
            x2={W - PAD.right}
            y1={yPop(f * maxPop)}
            y2={yPop(f * maxPop)}
            {...stylex.props(styles.grid)}
          />
        ))}
        <path d={nutrientArea} {...stylex.props(styles.nutrient)} />
        <path
          d={path(curve.map((r) => [x(r.tick), yStr(r.strains)]))}
          {...stylex.props(styles.strains)}
        />
        <path
          d={path(curve.map((r) => [x(r.tick), yPop(r.population)]))}
          {...stylex.props(styles.population)}
        />
        {ticks.map((t) => (
          <text key={t} x={x(t)} y={H - 10} textAnchor="middle" {...stylex.props(styles.axis)}>
            {t}
          </text>
        ))}
        <text x={PAD.left - 6} y={yPop(maxPop) + 4} textAnchor="end" {...stylex.props(styles.axis)}>
          {maxPop}
        </text>
        <text x={PAD.left - 6} y={yPop(0) + 4} textAnchor="end" {...stylex.props(styles.axis)}>
          0
        </text>
      </svg>
      <figcaption {...stylex.props(styles.legend)}>
        <Text as="span" size="n2" tone="muted">
          <span {...stylex.props(styles.key, styles.keyPop)} /> population
        </Text>
        <Text as="span" size="n2" tone="muted">
          <span {...stylex.props(styles.key, styles.keyStrains)} /> living strains
        </Text>
        <Text as="span" size="n2" tone="muted">
          <span {...stylex.props(styles.key, styles.keyNutrient)} /> mean nutrient
        </Text>
        <Text as="span" size="n2" tone="muted">
          band: lag, log, stationary, death
        </Text>
      </figcaption>
    </figure>
  );
}
