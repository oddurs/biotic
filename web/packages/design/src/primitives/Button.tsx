import * as stylex from "@stylexjs/stylex";
import type { ComponentPropsWithoutRef } from "react";
import { color } from "../tokens/generated/color.stylex";
import { duration, easing } from "../tokens/motion.stylex";
import { border, radius, shadow } from "../tokens/shape.stylex";
import { space } from "../tokens/space.stylex";
import { fluidType } from "../tokens/generated/fluid.stylex";
import { weight } from "../tokens/type.stylex";

const styles = stylex.create({
  base: {
    borderRadius: radius.md,
    borderStyle: "solid",
    borderWidth: border.hairline,
    gap: space.xs,
    outline: "none",
    alignItems: "center",
    boxShadow: { default: "none", ":focus-visible": shadow.focus },
    cursor: { default: "pointer", ":disabled": "not-allowed" },
    display: "inline-flex",
    fontWeight: weight.medium,
    justifyContent: "center",
    lineHeight: 1,
    opacity: { default: 1, ":disabled": 0.55 },
    textDecorationLine: "none",
    transitionDuration: duration.fast,
    transitionProperty: "background-color, border-color, color, box-shadow, transform",
    transitionTimingFunction: easing.standard,
    whiteSpace: "nowrap",
  },
  primary: {
    borderColor: "transparent",
    backgroundColor: { default: color.accentBase, ":hover": color.accentHover },
    color: color.accentInk,
  },
  secondary: {
    borderColor: color.edgeStrong,
    backgroundColor: { default: color.surfaceRaised, ":hover": color.surfaceSunken },
    color: color.inkPrimary,
  },
  ghost: {
    borderColor: "transparent",
    backgroundColor: { default: "transparent", ":hover": color.surfaceSunken },
    color: color.inkSecondary,
  },
});
const sizes = stylex.create({
  lg: { paddingBlock: space.sm, paddingInline: space.lg, fontSize: fluidType.step1 },
  md: { paddingBlock: space.xs, paddingInline: space.md, fontSize: fluidType.step0 },
  sm: { paddingBlock: space.xxs, paddingInline: space.sm, fontSize: fluidType.stepn1 },
});

interface Common {
  variant?: keyof typeof styles & ("primary" | "secondary" | "ghost");
  size?: keyof typeof sizes;
  style?: stylex.StyleXStyles;
}
export type ButtonProps =
  | (Common &
      Omit<ComponentPropsWithoutRef<"button">, "style" | "className"> & { href?: undefined })
  | (Common & Omit<ComponentPropsWithoutRef<"a">, "style" | "className"> & { href: string });

/** A button, or a link dressed as one when `href` is given. */
export function Button({
  variant = "primary",
  size = "md",
  style,
  children,
  ...rest
}: ButtonProps) {
  const sx = stylex.props(styles.base, styles[variant], sizes[size], style);
  if (rest.href !== undefined) {
    return (
      <a {...rest} {...sx}>
        {children}
      </a>
    );
  }
  const { type = "button", ...button } = rest;
  return (
    <button type={type} {...button} {...sx}>
      {children}
    </button>
  );
}
