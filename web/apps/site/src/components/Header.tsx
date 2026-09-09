import * as stylex from "@stylexjs/stylex";
import { Container, Icon, Link, VisuallyHidden } from "@biotic/design";
import type { ReactNode } from "react";
import { color } from "@biotic/design/tokens/color.stylex";
import { media } from "@biotic/design/tokens/media.stylex";
import { space } from "@biotic/design/tokens/space.stylex";
import { font, weight } from "@biotic/design/tokens/type.stylex";
import { site } from "../../site.config";
import { href } from "../lib/url";

const styles = stylex.create({
  header: {
    backdropFilter: "blur(8px)",
    backgroundColor: color.surfaceCanvas,
    position: "sticky",
    zIndex: 100,
    borderBottomColor: color.edgeSubtle,
    borderBottomStyle: "solid",
    borderBottomWidth: "1px",
    top: 0,
  },
  bar: {
    gap: space.lg,
    alignItems: "center",
    display: "flex",
    minHeight: "3.5rem",
  },
  brand: {
    color: color.inkPrimary,
    fontFamily: font.display,
    fontSize: "1.25rem",
    fontVariationSettings: '"opsz" 48, "SOFT" 50',
    fontWeight: weight.medium,
    letterSpacing: "-0.01em",
    textDecorationLine: "none",
  },
  nav: {
    gap: space.md,
    alignItems: "center",
    display: { [media.sm]: "flex", default: "none" },
    marginInlineStart: "auto",
  },
  tools: {
    gap: space.xs,
    alignItems: "center",
    display: "flex",
    marginInlineStart: { [media.sm]: 0, default: "auto" },
  },
  icon: { fontSize: "1.25rem" },
});

/** `tools` is a slot for hydrated islands (the theme toggle) the static header cannot own. */
export function Header({ current, tools }: { current?: string; tools?: ReactNode }) {
  return (
    <header {...stylex.props(styles.header)}>
      <Container>
        <div {...stylex.props(styles.bar)}>
          <a href={href("/")} {...stylex.props(styles.brand)}>
            {site.name}
          </a>
          <nav aria-label="Primary" {...stylex.props(styles.nav)}>
            {site.nav.map((item) => (
              <Link
                key={item.href}
                href={href(item.href)}
                variant="nav"
                aria-current={current?.startsWith(item.href) ? "page" : undefined}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div {...stylex.props(styles.tools)}>
            <Link href={site.repo} variant="nav" style={styles.icon}>
              <Icon name="github" />
              <VisuallyHidden>Source on GitHub</VisuallyHidden>
            </Link>
            {tools}
          </div>
        </div>
      </Container>
    </header>
  );
}
