import * as stylex from "@stylexjs/stylex";
import type { ComponentPropsWithoutRef } from "react";
import { color } from "../tokens/generated/color.stylex";
import { duration, easing } from "../tokens/motion.stylex";
import { radius } from "../tokens/shape.stylex";
import { weight } from "../tokens/type.stylex";

const styles = stylex.create({
  base: {
    borderRadius: radius.sm,
    color: { default: color.accentBase, ":hover": color.accentHover },
    outlineColor: color.edgeFocus,
    textDecorationColor: { default: color.accentSoft, ":hover": color.accentHover },
    textDecorationLine: "underline",
    textDecorationThickness: "0.08em",
    textUnderlineOffset: "0.15em",
    transitionDuration: duration.fast,
    transitionProperty: "color, text-decoration-color",
    transitionTimingFunction: easing.standard,
  },
  quiet: {
    color: { default: "inherit", ":hover": color.accentBase },
    fontWeight: weight.medium,
    textDecorationColor: { default: "transparent", ":hover": color.accentBase },
  },
  nav: {
    color: { default: color.inkSecondary, ":hover": color.inkPrimary },
    textDecorationLine: "none",
  },
});

export type LinkProps = Omit<ComponentPropsWithoutRef<"a">, "style" | "className"> & {
  href: string;
  /** `quiet` inherits colour until hovered; `nav` is for chrome. */
  variant?: "default" | "quiet" | "nav";
  style?: stylex.StyleXStyles;
};

const isExternal = (href: string) => /^(https?:)?\/\//.test(href);

/** An anchor. External links open in a new tab with the right rel; internal ones are plain. */
export function Link({ href, variant = "default", style, children, ...rest }: LinkProps) {
  const external = isExternal(href);
  return (
    <a
      href={href}
      {...(external ? { rel: "noopener noreferrer", target: "_blank" } : {})}
      {...rest}
      {...stylex.props(
        styles.base,
        variant === "quiet" && styles.quiet,
        variant === "nav" && styles.nav,
        style,
      )}
    >
      {children}
    </a>
  );
}
