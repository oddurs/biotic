import * as stylex from "@stylexjs/stylex";
import type { ElementType } from "react";
import { space } from "../tokens/space.stylex";
import { Box, type BoxProps } from "./Box";

type Gap = "none" | "xxxs" | "xxs" | "xs" | "sm" | "md" | "lg" | "xl" | "xxl" | "xxxl" | "huge";
type Align = "start" | "center" | "end" | "stretch" | "baseline";
type Justify = "start" | "center" | "end" | "between";

const styles = stylex.create({
  base: { display: "flex" },
  column: { flexDirection: "column" },
  row: { flexDirection: "row" },
  wrap: { flexWrap: "wrap" },
});
const gaps = stylex.create({
  huge: { gap: space.huge },
  lg: { gap: space.lg },
  md: { gap: space.md },
  none: { gap: space.none },
  sm: { gap: space.sm },
  xl: { gap: space.xl },
  xs: { gap: space.xs },
  xxl: { gap: space.xxl },
  xxs: { gap: space.xxs },
  xxxl: { gap: space.xxxl },
  xxxs: { gap: space.xxxs },
});
const aligns = stylex.create({
  baseline: { alignItems: "baseline" },
  center: { alignItems: "center" },
  end: { alignItems: "flex-end" },
  start: { alignItems: "flex-start" },
  stretch: { alignItems: "stretch" },
});
const justifies = stylex.create({
  between: { justifyContent: "space-between" },
  center: { justifyContent: "center" },
  end: { justifyContent: "flex-end" },
  start: { justifyContent: "flex-start" },
});

export type StackProps<T extends ElementType = "div"> = BoxProps<T> & {
  direction?: "row" | "column";
  gap?: Gap;
  align?: Align;
  justify?: Justify;
  wrap?: boolean;
};

/** Flex layout in one axis with a token gap. */
export function Stack<T extends ElementType = "div">({
  direction = "column",
  gap = "md",
  align,
  justify,
  wrap,
  style,
  ...rest
}: StackProps<T>) {
  return (
    <Box
      {...(rest as BoxProps<T>)}
      style={[
        styles.base,
        styles[direction],
        gaps[gap],
        align && aligns[align],
        justify && justifies[justify],
        wrap && styles.wrap,
        style,
      ]}
    />
  );
}
