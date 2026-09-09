import * as stylex from "@stylexjs/stylex";

export const duration = stylex.defineVars({
  instant: "60ms",
  fast: "120ms",
  base: "200ms",
  slow: "320ms",
  glacial: "600ms",
});

export const easing = stylex.defineVars({
  standard: "cubic-bezier(0.2, 0, 0, 1)",
  emphasized: "cubic-bezier(0.3, 0, 0, 1)",
  exit: "cubic-bezier(0.4, 0, 1, 1)",
  spring: "cubic-bezier(0.34, 1.56, 0.64, 1)",
});
