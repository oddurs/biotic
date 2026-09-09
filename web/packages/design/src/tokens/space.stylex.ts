import * as stylex from "@stylexjs/stylex";

// A 4px ladder for components. For layout rhythm that should breathe with the viewport,
// use `fluidSpace` from ./generated/fluid.stylex.
export const space = stylex.defineVars({
  none: "0",
  xxxs: "0.125rem",
  xxs: "0.25rem",
  xs: "0.5rem",
  sm: "0.75rem",
  md: "1rem",
  lg: "1.5rem",
  xl: "2rem",
  xxl: "3rem",
  xxxl: "4rem",
  huge: "6rem",
});
