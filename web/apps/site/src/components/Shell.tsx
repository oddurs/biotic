import * as stylex from "@stylexjs/stylex";
import { page } from "@biotic/design";
import { color } from "@biotic/design/tokens/color.stylex";
import { radius } from "@biotic/design/tokens/shape.stylex";
import { space } from "@biotic/design/tokens/space.stylex";
import type { ReactNode } from "react";
import { Footer } from "./Footer";
import { Header } from "./Header";

const styles = stylex.create({
  body: { display: "flex", flexDirection: "column", minHeight: "100dvh" },
  skip: {
    padding: space.sm,
    borderRadius: radius.md,
    backgroundColor: color.accentBase,
    color: color.accentInk,
    insetInlineStart: space.md,
    position: "absolute",
    transform: { default: "translateY(-200%)", ":focus": "translateY(0)" },
    zIndex: 1000,
    top: space.md,
  },
  main: { flexGrow: 1 },
});

/** Everything between <body> and </body>. The Astro layout owns the document. */
export function Shell({
  current,
  tools,
  children,
}: {
  current?: string;
  tools?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div {...stylex.props(page.body, styles.body)}>
      <a href="#main" {...stylex.props(styles.skip)}>
        Skip to content
      </a>
      <Header current={current} tools={tools} />
      <main id="main" tabIndex={-1} {...stylex.props(styles.main)}>
        {children}
      </main>
      <Footer />
    </div>
  );
}
export const bodyStyle = stylex.props(page.body, page.selection);
