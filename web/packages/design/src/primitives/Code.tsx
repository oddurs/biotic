import * as stylex from "@stylexjs/stylex";
import type { ComponentPropsWithoutRef } from "react";
import { color } from "../tokens/generated/color.stylex";
import { radius } from "../tokens/shape.stylex";
import { space } from "../tokens/space.stylex";
import { font } from "../tokens/type.stylex";

const styles = stylex.create({
  inline: {
    borderRadius: radius.sm,
    paddingBlock: "0.1em",
    paddingInline: space.xxs,
    backgroundColor: color.surfaceSunken,
    fontFamily: font.mono,
    fontSize: "0.9em",
  },
});

export type CodeProps = Omit<ComponentPropsWithoutRef<"code">, "style" | "className"> & {
  style?: stylex.StyleXStyles;
};

/** Inline code. Blocks are rendered by Expressive Code in the app. */
export function Code({ style, ...rest }: CodeProps) {
  return <code {...rest} {...stylex.props(styles.inline, style)} />;
}
