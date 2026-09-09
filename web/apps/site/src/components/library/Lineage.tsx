import * as stylex from "@stylexjs/stylex";
import { strainColor } from "@biotic/design";
import { color } from "@biotic/design/tokens/color.stylex";
import { font } from "@biotic/design/tokens/type.stylex";
import type { Strain } from "../../lib/specimens";

const COL = 190;
const ROW = 34;
const PAD = 24;

const styles = stylex.create({
  svg: { display: "block", height: "auto", maxWidth: "100%" },
  link: { fill: "none", stroke: color.edgeStrong, strokeWidth: 1.25 },
  label: { fill: color.inkPrimary, fontFamily: font.mono, fontSize: "11px" },
  labelDead: { fill: color.inkMuted },
  gen: {
    fill: color.inkMuted,
    fontFamily: font.text,
    fontSize: "11px",
    letterSpacing: "0.08em",
    textTransform: "uppercase",
  },
  dead: { opacity: 0.45 },
});

/** Every strain as a node by generation, linked to its parent, coloured as the eyepiece paints it. */
export function Lineage({ strains }: { strains: Strain[] }) {
  const gens = new Map<number, Strain[]>();
  for (const s of [...strains].sort((a, b) => a.born - b.born)) {
    gens.set(s.generation, [...(gens.get(s.generation) ?? []), s]);
  }
  const genList = [...gens.keys()].sort((a, b) => a - b);
  const rows = Math.max(...genList.map((g) => gens.get(g)?.length ?? 0));
  const W = PAD * 2 + COL * genList.length;
  const H = PAD * 2 + ROW * rows + 16;
  const pos = new Map<string, { x: number; y: number }>();
  genList.forEach((g, gi) => {
    (gens.get(g) ?? []).forEach((s, i) =>
      pos.set(s.id, { x: PAD + gi * COL + 8, y: PAD + 16 + i * ROW + ROW / 2 }),
    );
  });
  const maxPeak = Math.max(1, ...strains.map((s) => s.peak));
  const radius = (s: Strain) => 4 + 7 * Math.sqrt(s.peak / maxPeak);

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      width={W}
      role="img"
      aria-label={`Lineage of ${strains.length} strains across ${genList.length} generations`}
      {...stylex.props(styles.svg)}
    >
      {genList.map((g, gi) => (
        <text key={g} x={PAD + gi * COL} y={PAD} {...stylex.props(styles.gen)}>
          gen {g}
        </text>
      ))}
      {strains.map((s) => {
        const to = pos.get(s.id);
        const from = s.parent ? pos.get(s.parent) : undefined;
        if (!to || !from) return null;
        const mx = (from.x + to.x) / 2;
        return (
          <path
            key={`l-${s.id}`}
            d={`M${from.x + 10},${from.y} C${mx},${from.y} ${mx},${to.y} ${to.x - 10},${to.y}`}
            {...stylex.props(styles.link)}
          />
        );
      })}
      {strains.map((s) => {
        const p = pos.get(s.id);
        if (!p) return null;
        const dead = s.extinct_at !== null;
        return (
          <g key={s.id} {...stylex.props(dead && styles.dead)}>
            <circle cx={p.x} cy={p.y} r={radius(s)} fill={strainColor(s.hue, dead ? 0.3 : 1)}>
              <title>{`${s.id} ${s.name}: peak ${s.peak}${dead ? `, extinct at tick ${s.extinct_at}` : ""}`}</title>
            </circle>
            <text
              x={p.x + 16}
              y={p.y + 4}
              {...stylex.props(styles.label, dead && styles.labelDead)}
            >
              {s.name.length > 22 ? `${s.name.slice(0, 21)}…` : s.name}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
