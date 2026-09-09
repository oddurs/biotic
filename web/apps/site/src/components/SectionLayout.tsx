import * as stylex from "@stylexjs/stylex";
import { Container, Heading, Link, Text } from "@biotic/design";
import { color } from "@biotic/design/tokens/color.stylex";
import { fluidSpace } from "@biotic/design/tokens/fluid.stylex";
import { media } from "@biotic/design/tokens/media.stylex";
import { space } from "@biotic/design/tokens/space.stylex";
import { measure } from "@biotic/design/tokens/type.stylex";
import type { ReactNode } from "react";

const styles = stylex.create({
  grid: {
    gap: fluidSpace.xl,
    paddingBlock: fluidSpace.lg,
    display: "grid",
    gridTemplateColumns: { [media.md]: "14rem minmax(0, 1fr)", default: "minmax(0, 1fr)" },
  },
  aside: {
    alignSelf: "start",
    position: { [media.md]: "sticky", default: "static" },
    top: { [media.md]: "4.5rem", default: "auto" },
  },
  navList: {
    padding: 0,
    gap: space.xxs,
    listStyle: "none",
    display: "flex",
    flexDirection: "column",
  },
  navLink: {
    borderRadius: "0.375rem",
    paddingBlock: space.xxs,
    paddingInline: space.xs,
    backgroundColor: { default: "transparent", ":hover": color.surfaceSunken },
    color: color.inkSecondary,
    display: "block",
    textDecorationLine: "none",
  },
  navCurrent: { backgroundColor: color.accentSoft, color: color.accentHover },
  article: { maxWidth: measure.wide, minWidth: 0 },
  header: { marginBottom: fluidSpace.lg },
  lede: { marginTop: space.sm },
});

export interface SectionNavItem {
  label: string;
  href: string;
}

/** Sidebar plus article: the shape of every documentation-like section. */
export function SectionLayout({
  section,
  nav,
  current,
  title,
  lede,
  children,
}: {
  section: string;
  nav: SectionNavItem[];
  current: string;
  title: string;
  lede?: string;
  children: ReactNode;
}) {
  return (
    <Container>
      <div {...stylex.props(styles.grid)}>
        <aside {...stylex.props(styles.aside)}>
          <nav aria-label={section}>
            <Text as="p" caps tone="muted">
              {section}
            </Text>
            <ul {...stylex.props(styles.navList)}>
              {nav.map((item) => {
                const isCurrent = item.href === current;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      variant="nav"
                      aria-current={isCurrent ? "page" : undefined}
                      style={[styles.navLink, isCurrent && styles.navCurrent]}
                    >
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>
        </aside>
        <article {...stylex.props(styles.article)}>
          <header {...stylex.props(styles.header)}>
            <Heading level={1}>{title}</Heading>
            {lede && (
              <Text size="1" tone="secondary" style={styles.lede}>
                {lede}
              </Text>
            )}
          </header>
          {children}
        </article>
      </div>
    </Container>
  );
}
