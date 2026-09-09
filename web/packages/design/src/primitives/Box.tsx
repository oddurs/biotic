import * as stylex from "@stylexjs/stylex";
import { createElement, type ComponentPropsWithoutRef, type ElementType } from "react";

export type BoxProps<T extends ElementType = "div"> = {
  as?: T;
  style?: stylex.StyleXStyles;
} & Omit<ComponentPropsWithoutRef<T>, "style" | "className">;

/** The lowest primitive: an element with StyleX styles and nothing else. */
export function Box<T extends ElementType = "div">({ as, style, ...rest }: BoxProps<T>) {
  return createElement(as ?? "div", { ...rest, ...stylex.props(style) });
}
