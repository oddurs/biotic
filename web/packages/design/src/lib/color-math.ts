// Enough colour science to check the palette: OKLCH to sRGB, relative luminance, WCAG contrast.

export function oklchToSrgb(l: number, c: number, h: number): [number, number, number] {
  const hr = (h * Math.PI) / 180;
  const a = c * Math.cos(hr);
  const b = c * Math.sin(hr);
  const l_ = l + 0.3963377774 * a + 0.2158037573 * b;
  const m_ = l - 0.1055613458 * a - 0.0638541728 * b;
  const s_ = l - 0.0894841775 * a - 1.291485548 * b;
  const L = l_ ** 3;
  const M = m_ ** 3;
  const S = s_ ** 3;
  const lin: [number, number, number] = [
    4.0767416621 * L - 3.3077115913 * M + 0.2309699292 * S,
    -1.2684380046 * L + 2.6097574011 * M - 0.3413193965 * S,
    -0.0041960863 * L - 0.7034186147 * M + 1.707614701 * S,
  ];
  return lin.map((v) => Math.min(1, Math.max(0, v))) as [number, number, number];
}

/** Parses `oklch(L% C H)` as the generator writes it. */
export function parseOklch(value: string): [number, number, number] {
  const m = /oklch\(([\d.]+)%\s+([\d.]+)\s+([\d.]+)\)/.exec(value);
  if (!m) throw new Error(`not an oklch() literal: ${value}`);
  return [Number(m[1]) / 100, Number(m[2]), Number(m[3])];
}

export function luminance(value: string): number {
  const [r, g, b] = oklchToSrgb(...parseOklch(value));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** WCAG 2 contrast ratio between two oklch() literals. */
export function contrast(a: string, b: string): number {
  const la = luminance(a);
  const lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}
