import * as stylex from "@stylexjs/stylex";
import { Icon, Link, Text } from "@biotic/design";
import { color } from "@biotic/design/tokens/color.stylex";
import { fluidSpace } from "@biotic/design/tokens/fluid.stylex";
import { media } from "@biotic/design/tokens/media.stylex";
import { border } from "@biotic/design/tokens/shape.stylex";
import { space } from "@biotic/design/tokens/space.stylex";
import type { ReactNode } from "react";

export interface TocEntry {
  depth: number;
  slug: string;
  text: string;
}
export interface DocLink {
  title: string;
  href: string;
}

const styles = stylex.create({
  frame: {
    gap: fluidSpace.lg,
    display: "grid",
    gridTemplateColumns: { [media.lg]: "minmax(0, 1fr) 12rem", default: "minmax(0, 1fr)" },
  },
  toc: {
    alignSelf: "start",
    display: { [media.lg]: "block", default: "none" },
    position: "sticky",
    top: "4.5rem",
  },
  tocList: { margin: 0, padding: 0, listStyle: "none" },
  tocItem: (depth: number) => ({ paddingInlineStart: `${(depth - 2) * 0.75}rem` }),
  tocLink: {
    paddingBlock: space.xxxs,
    color: { default: color.inkSecondary, ":hover": color.inkPrimary },
    display: "block",
    textDecorationLine: "none",
  },
  footer: {
    gap: space.md,
    display: "flex",
    flexWrap: "wrap",
    justifyContent: "space-between",
    borderTopColor: color.edgeSubtle,
    borderTopStyle: "solid",
    borderTopWidth: border.hairline,
    marginTop: fluidSpace.xl,
    paddingTop: space.lg,
  },
  pager: { gap: space.xs, alignItems: "center", display: "inline-flex" },
  flipped: { transform: "rotate(180deg)" },
  edit: { marginTop: space.md },
});

/** Article body with a table of contents beside it and prev/next below. */
export function DocsFrame({
  toc,
  prev,
  next,
  editHref,
  children,
}: {
  toc: TocEntry[];
  prev?: DocLink;
  next?: DocLink;
  editHref: string;
  children: ReactNode;
}) {
  const entries = toc.filter((h) => h.depth === 2 || h.depth === 3);
  return (
    <div {...stylex.props(styles.frame)}>
      <div data-pagefind-body>
        {children}
        <footer {...stylex.props(styles.footer)} data-pagefind-ignore>
          {prev ? (
            <Link href={prev.href} variant="quiet" style={styles.pager} rel="prev">
              <Icon name="arrowRight" style={styles.flipped} /> {prev.title}
            </Link>
          ) : (
            <span />
          )}
          {next && (
            <Link href={next.href} variant="quiet" style={styles.pager} rel="next">
              {next.title} <Icon name="arrowRight" />
            </Link>
          )}
        </footer>
        <Text as="p" size="n1" tone="muted" style={styles.edit} data-pagefind-ignore>
          <Link href={editHref} variant="quiet">
            Edit this page on GitHub
          </Link>
        </Text>
      </div>
      {entries.length > 1 && (
        <nav aria-label="On this page" {...stylex.props(styles.toc)} data-pagefind-ignore>
          <Text as="p" caps tone="muted">
            On this page
          </Text>
          <ul {...stylex.props(styles.tocList)}>
            {entries.map((h) => (
              <li key={h.slug} {...stylex.props(styles.tocItem(h.depth))}>
                <a href={`#${h.slug}`} {...stylex.props(styles.tocLink)}>
                  {h.text}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      )}
    </div>
  );
}
