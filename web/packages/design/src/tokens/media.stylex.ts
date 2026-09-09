import * as stylex from "@stylexjs/stylex";

// Breakpoints are constants, not variables: they are inlined into @media rules.
export const media = stylex.defineConsts({
  sm: "@media (min-width: 40em)",
  md: "@media (min-width: 64em)",
  lg: "@media (min-width: 80em)",
  motionOk: "@media (prefers-reduced-motion: no-preference)",
  hover: "@media (hover: hover)",
});
