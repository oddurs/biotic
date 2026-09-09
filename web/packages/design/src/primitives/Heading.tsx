import * as stylex from "@stylexjs/stylex";
import type { ComponentPropsWithoutRef } from "react";
import { color } from "../tokens/generated/color.stylex";
import { fluidType } from "../tokens/generated/fluid.stylex";
import { displayAxes, font, leading, tracking, weight } from "../tokens/type.stylex";

type Level = 1 | 2 | 3 | 4 | 5 | 6;

const styles = stylex.create({
  base: {
    color: color.inkPrimary,
    fontFamily: font.display,
    fontVariationSettings: displayAxes.variation,
    fontWeight: weight.medium,
    letterSpacing: tracking.tight,
    lineHeight: leading.tight,
  },
  text: {
    fontFamily: font.text,
    fontVariationSettings: "normal",
    fontWeight: weight.semibold,
    letterSpacing: tracking.normal,
  },
});
const sizes = stylex.create({
  "1": { fontSize: fluidType.step2 },
  "2": { fontSize: fluidType.step3 },
  "3": { fontSize: fluidType.step4 },
  "4": { fontSize: fluidType.step5 },
  "5": { fontSize: fluidType.step6 },
  "6": { fontSize: fluidType.step1, lineHeight: leading.snug },
  "7": { fontSize: fluidType.step0, lineHeight: leading.snug },
});
const defaultSize: Record<Level, keyof typeof sizes> = {
  1: "5",
  2: "4",
  3: "3",
  4: "2",
  5: "6",
  6: "7",
};

export type HeadingProps = Omit<ComponentPropsWithoutRef<"h1">, "style" | "className"> & {
  /** Semantic level; sets the element. */
  level: Level;
  /** Visual size, decoupled from the level. 1 is smallest. */
  size?: keyof typeof sizes;
  /** Use the text face instead of the display serif. */
  plain?: boolean;
  style?: stylex.StyleXStyles;
};

/** Headings in the display serif. Level is semantics; size is appearance. */
export function Heading({ level, size, plain, style, ...rest }: HeadingProps) {
  const Tag = `h${level}` as const;
  return (
    <Tag
      {...rest}
      {...stylex.props(styles.base, plain && styles.text, sizes[size ?? defaultSize[level]], style)}
    />
  );
}
