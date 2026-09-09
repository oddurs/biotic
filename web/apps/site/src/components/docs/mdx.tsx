import * as stylex from "@stylexjs/stylex";
import { Callout, Code, Divider, Heading, Link, Table, Text } from "@biotic/design";
import { color } from "@biotic/design/tokens/color.stylex";
import { border, radius } from "@biotic/design/tokens/shape.stylex";
import { space } from "@biotic/design/tokens/space.stylex";
import { leading, measure } from "@biotic/design/tokens/type.stylex";
import type { ComponentPropsWithoutRef } from "react";
import { href as withBase } from "../../lib/url";

// MDX renders through the design system: every element maps to a primitive, so content
// never carries its own styling and looks like the rest of the site.
const styles = stylex.create({
  h2: { marginBottom: space.sm, marginTop: space.xxl },
  h3: { marginBottom: space.xs, marginTop: space.xl },
  h4: { marginBottom: space.xs, marginTop: space.lg },
  p: { lineHeight: leading.relaxed, marginBottom: space.md, maxWidth: measure.text },
  list: {
    lineHeight: leading.relaxed,
    paddingInlineStart: space.lg,
    marginBottom: space.md,
    maxWidth: measure.text,
  },
  li: { marginBottom: space.xxs },
  quote: {
    marginBlock: space.md,
    marginInline: 0,
    borderInlineStartColor: color.edgeStrong,
    borderInlineStartStyle: "solid",
    borderInlineStartWidth: border.thick,
    color: color.inkSecondary,
    paddingInlineStart: space.md,
  },
  img: { borderRadius: radius.md, marginBlock: space.md },
  table: { marginBottom: space.md },
});

// MDX passes className and style as strings; primitives take neither, so they are dropped.
type P<T extends keyof React.JSX.IntrinsicElements> = ComponentPropsWithoutRef<T>;
function clean<T extends object>(props: T): Omit<T, "className" | "style"> {
  const {
    className: _c,
    style: _s,
    ...rest
  } = props as T & { className?: unknown; style?: unknown };
  return rest;
}

export const mdxComponents = {
  h1: (p: P<"h1">) => <Heading level={1} {...clean(p)} />,
  h2: (p: P<"h2">) => <Heading level={2} size="3" {...p} style={styles.h2} />,
  h3: (p: P<"h3">) => <Heading level={3} size="2" {...p} style={styles.h3} />,
  h4: (p: P<"h4">) => <Heading level={4} size="1" plain {...clean(p)} style={styles.h4} />,
  p: (p: P<"p">) => <Text {...clean(p)} style={styles.p} />,
  // Content links are root-relative; the deploy base is applied here, not in the prose.
  a: ({ href = "#", ...p }: P<"a">) => (
    <Link href={href.startsWith("/") ? withBase(href) : href} {...clean(p)} />
  ),
  ul: (p: P<"ul">) => <ul {...clean(p)} {...stylex.props(styles.list)} />,
  ol: (p: P<"ol">) => <ol {...clean(p)} {...stylex.props(styles.list)} />,
  li: (p: P<"li">) => <li {...clean(p)} {...stylex.props(styles.li)} />,
  blockquote: (p: P<"blockquote">) => <blockquote {...clean(p)} {...stylex.props(styles.quote)} />,
  code: (p: P<"code">) => <Code {...clean(p)} />,
  hr: () => <Divider />,
  img: ({ alt = "", ...p }: P<"img">) => (
    <img alt={alt} {...clean(p)} {...stylex.props(styles.img)} />
  ),
  table: (p: P<"table">) => <Table {...clean(p)} style={styles.table} />,
  th: (p: P<"th">) => <Table.Head {...clean(p)} />,
  td: (p: P<"td">) => <Table.Cell {...clean(p)} />,
  Callout,
};
