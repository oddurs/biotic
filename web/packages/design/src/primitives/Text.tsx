import * as stylex from "@stylexjs/stylex";
import type { ElementType } from "react";
import { color } from "../tokens/generated/color.stylex";
import { fluidType } from "../tokens/generated/fluid.stylex";
import { font, leading, tracking, weight } from "../tokens/type.stylex";
import { Box, type BoxProps } from "./Box";

export const textSizes = stylex.create({
  "0": { fontSize: fluidType.step0 },
  "1": { fontSize: fluidType.step1 },
  "2": { fontSize: fluidType.step2 },
  "3": { fontSize: fluidType.step3 },
  "4": { fontSize: fluidType.step4 },
  "5": { fontSize: fluidType.step5 },
  "6": { fontSize: fluidType.step6 },
  n1: { fontSize: fluidType.stepn1 },
  n2: { fontSize: fluidType.stepn2 },
});
export const tones = stylex.create({
  accent: { color: color.accentBase },
  inverse: { color: color.inkInverse },
  muted: { color: color.inkMuted },
  negative: { color: color.negativeBase },
  primary: { color: color.inkPrimary },
  secondary: { color: color.inkSecondary },
});
export const weights = stylex.create({
  bold: { fontWeight: weight.bold },
  medium: { fontWeight: weight.medium },
  regular: { fontWeight: weight.regular },
  semibold: { fontWeight: weight.semibold },
});
export const fonts = stylex.create({
  display: { fontFamily: font.display },
  mono: { fontFamily: font.mono },
  text: { fontFamily: font.text },
});
export const leadings = stylex.create({
  normal: { lineHeight: leading.normal },
  relaxed: { lineHeight: leading.relaxed },
  snug: { lineHeight: leading.snug },
  tight: { lineHeight: leading.tight },
});
const styles = stylex.create({
  balance: { textWrap: "balance" },
  caps: {
    fontSize: fluidType.stepn1,
    fontWeight: weight.semibold,
    letterSpacing: tracking.caps,
    textTransform: "uppercase",
  },
  center: { textAlign: "center" },
  truncate: { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
});

export type TextProps<T extends ElementType = "p"> = BoxProps<T> & {
  size?: keyof typeof textSizes;
  tone?: keyof typeof tones;
  weight?: keyof typeof weights;
  font?: keyof typeof fonts;
  leading?: keyof typeof leadings;
  /** Small caps label style. */
  caps?: boolean;
  center?: boolean;
  balance?: boolean;
  truncate?: boolean;
};

/** Running text. Defaults to a paragraph at the base step in the primary ink. */
export function Text<T extends ElementType = "p">({
  as,
  size,
  tone,
  weight: w,
  font: f,
  leading: l,
  caps,
  center,
  balance,
  truncate,
  style,
  ...rest
}: TextProps<T>) {
  return (
    <Box
      as={as ?? "p"}
      {...(rest as BoxProps<T>)}
      style={[
        size && textSizes[size],
        tone && tones[tone],
        w && weights[w],
        f && fonts[f],
        l && leadings[l],
        caps && styles.caps,
        center && styles.center,
        balance && styles.balance,
        truncate && styles.truncate,
        style,
      ]}
    />
  );
}
