import * as stylex from "@stylexjs/stylex";

export const radius = stylex.defineVars({
  none: "0",
  sm: "0.25rem",
  md: "0.5rem",
  lg: "0.75rem",
  xl: "1.25rem",
  full: "9999px",
});

export const border = stylex.defineVars({
  hairline: "1px",
  thick: "2px",
});

// Shadows are ink at low alpha so they read on both faces.
export const shadow = stylex.defineVars({
  sm: "0 1px 2px oklch(15% 0.02 155 / 0.08)",
  md: "0 2px 6px oklch(15% 0.02 155 / 0.08), 0 8px 24px oklch(15% 0.02 155 / 0.06)",
  lg: "0 4px 12px oklch(15% 0.02 155 / 0.1), 0 24px 48px oklch(15% 0.02 155 / 0.12)",
  focus: "0 0 0 3px oklch(60% 0.15 152 / 0.35)",
});
