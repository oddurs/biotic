import * as stylex from "@stylexjs/stylex";
import type { ElementType } from "react";
import { fluidSpace } from "../tokens/generated/fluid.stylex";
import { measure } from "../tokens/type.stylex";
import { Box, type BoxProps } from "./Box";

const styles = stylex.create({
  base: {
    marginInline: "auto",
    paddingInline: fluidSpace.md,
    width: "100%",
  },
});
const sizes = stylex.create({
  full: { maxWidth: "none" },
  narrow: { maxWidth: measure.narrow },
  site: { maxWidth: "72rem" },
  text: { maxWidth: measure.text },
  wide: { maxWidth: measure.wide },
});

export type ContainerProps<T extends ElementType = "div"> = BoxProps<T> & {
  size?: keyof typeof sizes;
};

/** Centres content at a named measure with fluid side padding. */
export function Container<T extends ElementType = "div">({
  size = "site",
  style,
  ...rest
}: ContainerProps<T>) {
  return <Box {...(rest as BoxProps<T>)} style={[styles.base, sizes[size], style]} />;
}
