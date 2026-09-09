// The TUI's strain colour, ported from bio/strains.py so the site paints a lineage the way the
// eyepiece does: hue from the strain, lightness from energy, fixed saturation.

function hlsToRgb(h: number, l: number, s: number): [number, number, number] {
  if (s === 0) return [l, l, l];
  const m2 = l <= 0.5 ? l * (1 + s) : l + s - l * s;
  const m1 = 2 * l - m2;
  const v = (hue: number) => {
    hue = ((hue % 1) + 1) % 1;
    if (hue < 1 / 6) return m1 + (m2 - m1) * hue * 6;
    if (hue < 0.5) return m2;
    if (hue < 2 / 3) return m1 + (m2 - m1) * (2 / 3 - hue) * 6;
    return m1;
  };
  return [v(h + 1 / 3), v(h), v(h - 1 / 3)];
}

/** `hue` in 0..1 as stored in strains.json; `energy` in 0..2 as a cell carries it. */
export function strainColor(hue: number, energy = 1): string {
  const light = 0.38 + 0.28 * Math.max(0, Math.min(1, energy / 1.2));
  const [r, g, b] = hlsToRgb(hue, light, 0.72);
  const hex = (x: number) =>
    Math.floor(x * 255)
      .toString(16)
      .padStart(2, "0");
  return `#${hex(r)}${hex(g)}${hex(b)}`;
}
