import * as stylex from "@stylexjs/stylex";
import type { ReactNode } from "react";
import { color } from "../tokens/generated/color.stylex";
import { border, radius } from "../tokens/shape.stylex";
import { space } from "../tokens/space.stylex";
import { weight } from "../tokens/type.stylex";
import { Icon, type IconName } from "./Icon";

const styles = stylex.create({
  base: {
    borderRadius: radius.md,
    gap: space.xs,
    paddingBlock: space.sm,
    paddingInline: space.md,
    borderInlineStartStyle: "solid",
    borderInlineStartWidth: border.thick,
    display: "grid",
    gridTemplateColumns: "auto 1fr",
  },
  title: { fontWeight: weight.semibold, gridColumnStart: "2" },
  body: { gridColumnStart: "2" },
  icon: { gridRowEnd: "span 2", gridRowStart: "1", marginTop: "0.15em" },
});
const tones = stylex.create({
  caution: {
    borderColor: color.cautionBase,
    backgroundColor: color.cautionSoft,
    color: color.inkPrimary,
  },
  info: { borderColor: color.infoBase, backgroundColor: color.infoSoft, color: color.inkPrimary },
  negative: {
    borderColor: color.negativeBase,
    backgroundColor: color.negativeSoft,
    color: color.inkPrimary,
  },
  positive: {
    borderColor: color.positiveBase,
    backgroundColor: color.positiveSoft,
    color: color.inkPrimary,
  },
});
const icons: Record<keyof typeof tones, IconName> = {
  caution: "warning",
  info: "info",
  negative: "close",
  positive: "check",
};

export interface CalloutProps {
  tone?: keyof typeof tones;
  title?: string;
  children: ReactNode;
  style?: stylex.StyleXStyles;
}

/** An aside that needs to be noticed: a note, a warning, a result. */
export function Callout({ tone = "info", title, children, style }: CalloutProps) {
  return (
    <aside role="note" {...stylex.props(styles.base, tones[tone], style)}>
      <span {...stylex.props(styles.icon)}>
        <Icon name={icons[tone]} />
      </span>
      {title && <p {...stylex.props(styles.title)}>{title}</p>}
      <div {...stylex.props(styles.body)}>{children}</div>
    </aside>
  );
}
