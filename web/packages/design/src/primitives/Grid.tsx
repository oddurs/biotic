import * as stylex from "@stylexjs/stylex";
import type { ComponentPropsWithoutRef } from "react";
import { space } from "../tokens/space.stylex";

const styles = stylex.create({
  base: { display: "grid" },
  auto: (min: string) => ({
    gridTemplateColumns: `repeat(auto-fit, minmax(min(${min}, 100%), 1fr))`,
  }),
});
const gaps = stylex.create({
  lg: { gap: space.lg },
  md: { gap: space.md },
  sm: { gap: space.sm },
  xl: { gap: space.xl },
  xs: { gap: space.xs },
});

export type GridProps = Omit<ComponentPropsWithoutRef<"div">, "style" | "className"> & {
  /** Minimum column width; as many columns as fit. */
  min?: string;
  gap?: keyof typeof gaps;
  style?: stylex.StyleXStyles;
};

/** A responsive grid without breakpoints: columns fill to a minimum width. */
export function Grid({ min = "16rem", gap = "md", style, ...rest }: GridProps) {
  return <div {...rest} {...stylex.props(styles.base, styles.auto(min), gaps[gap], style)} />;
}
