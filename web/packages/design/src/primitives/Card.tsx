import * as stylex from "@stylexjs/stylex";
import type { ElementType } from "react";
import { color } from "../tokens/generated/color.stylex";
import { duration, easing } from "../tokens/motion.stylex";
import { border, radius, shadow } from "../tokens/shape.stylex";
import { space } from "../tokens/space.stylex";
import { Box, type BoxProps } from "./Box";

const styles = stylex.create({
  base: {
    padding: space.lg,
    borderColor: color.edgeSubtle,
    borderRadius: radius.lg,
    borderStyle: "solid",
    borderWidth: border.hairline,
    backgroundColor: color.surfaceRaised,
  },
  raised: { boxShadow: shadow.md },
  interactive: {
    borderColor: { default: color.edgeSubtle, ":hover": color.edgeStrong },
    boxShadow: { default: shadow.sm, ":hover": shadow.md },
    transitionDuration: duration.base,
    transitionProperty: "box-shadow, border-color, transform",
    transitionTimingFunction: easing.standard,
  },
  sunken: { borderColor: "transparent", backgroundColor: color.surfaceSunken },
});

export type CardProps<T extends ElementType = "div"> = BoxProps<T> & {
  variant?: "flat" | "raised" | "interactive" | "sunken";
};

/** A bounded surface. */
export function Card<T extends ElementType = "div">({
  variant = "flat",
  style,
  ...rest
}: CardProps<T>) {
  return (
    <Box
      {...(rest as BoxProps<T>)}
      style={[
        styles.base,
        variant === "raised" && styles.raised,
        variant === "interactive" && styles.interactive,
        variant === "sunken" && styles.sunken,
        style,
      ]}
    />
  );
}
