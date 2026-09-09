import * as stylex from "@stylexjs/stylex";
import type { ComponentPropsWithoutRef } from "react";
import { color } from "../tokens/generated/color.stylex";
import { fluidType } from "../tokens/generated/fluid.stylex";
import { radius } from "../tokens/shape.stylex";
import { space } from "../tokens/space.stylex";
import { font, tracking, weight } from "../tokens/type.stylex";

const styles = stylex.create({
  base: {
    borderRadius: radius.full,
    gap: space.xxs,
    paddingBlock: space.xxs,
    paddingInline: space.xs,
    alignItems: "center",
    display: "inline-flex",
    fontFamily: font.text,
    fontSize: fluidType.stepn2,
    fontWeight: weight.medium,
    letterSpacing: tracking.wide,
    lineHeight: 1,
    textTransform: "uppercase",
  },
  mono: { fontFamily: font.mono, letterSpacing: tracking.normal, textTransform: "none" },
});
const tones = stylex.create({
  accent: { backgroundColor: color.accentSoft, color: color.accentHover },
  caution: { backgroundColor: color.cautionSoft, color: color.cautionBase },
  info: { backgroundColor: color.infoSoft, color: color.infoBase },
  negative: { backgroundColor: color.negativeSoft, color: color.negativeBase },
  neutral: { backgroundColor: color.surfaceSunken, color: color.inkSecondary },
  positive: { backgroundColor: color.positiveSoft, color: color.positiveBase },
});

export type TagProps = Omit<ComponentPropsWithoutRef<"span">, "style" | "className"> & {
  tone?: keyof typeof tones;
  /** For identifiers such as strain ids. */
  mono?: boolean;
  style?: stylex.StyleXStyles;
};

/** A small label. */
export function Tag({ tone = "neutral", mono, style, ...rest }: TagProps) {
  return <span {...rest} {...stylex.props(styles.base, tones[tone], mono && styles.mono, style)} />;
}
