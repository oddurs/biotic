import * as stylex from "@stylexjs/stylex";
import type { ReactNode } from "react";

const styles = stylex.create({
  base: {
    margin: "-1px",
    padding: 0,
    borderWidth: 0,
    overflow: "hidden",
    clip: "rect(0 0 0 0)",
    position: "absolute",
    whiteSpace: "nowrap",
    height: "1px",
    width: "1px",
  },
});

/** Text for assistive technology only. */
export function VisuallyHidden({ children }: { children: ReactNode }) {
  return <span {...stylex.props(styles.base)}>{children}</span>;
}
