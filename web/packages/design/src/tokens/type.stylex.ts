import * as stylex from "@stylexjs/stylex";

export const font = stylex.defineVars({
  display: '"Fraunces Variable", "Iowan Old Style", Georgia, serif',
  text: '"Inter Variable", "Helvetica Neue", Arial, sans-serif',
  mono: '"JetBrains Mono Variable", ui-monospace, "SF Mono", Menlo, monospace',
});

export const weight = stylex.defineVars({
  regular: "400",
  medium: "500",
  semibold: "600",
  bold: "700",
});

export const leading = stylex.defineVars({
  tight: "1.1",
  snug: "1.25",
  normal: "1.5",
  relaxed: "1.65",
});

export const tracking = stylex.defineVars({
  tight: "-0.02em",
  normal: "0",
  wide: "0.04em",
  caps: "0.08em",
});

// Line-length limits, in characters of the current font.
export const measure = stylex.defineVars({
  narrow: "45ch",
  text: "66ch",
  wide: "84ch",
});

// Fraunces' optical size and "wonk" axes: a little softer at display sizes.
export const displayAxes = stylex.defineVars({
  variation: '"opsz" 96, "SOFT" 30, "WONK" 0',
});
