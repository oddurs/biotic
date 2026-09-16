import * as stylex from "@stylexjs/stylex";
import { Card, Container, Heading, Link, Stack, Text } from "@biotic/design";
import { fluidSpace } from "@biotic/design/tokens/fluid.stylex";
import { measure } from "@biotic/design/tokens/type.stylex";
import type { ReactNode } from "react";

const styles = stylex.create({
  page: { paddingBlock: fluidSpace.lg },
  article: { maxWidth: measure.text },
});

export interface NoteSummary {
  title: string;
  description: string;
  date: Date;
  href: string;
}

const fmt = (d: Date) => d.toISOString().slice(0, 10);

export function NotesIndex({ notes, rssHref }: { notes: NoteSummary[]; rssHref: string }) {
  return (
    <Container size="text">
      <Stack gap="lg" style={styles.page}>
        <div>
          <Heading level={1}>Field notes</Heading>
          <Text tone="secondary" size="1">
            Dated entries from the bench. <Link href={rssHref}>RSS</Link>.
          </Text>
        </div>
        {notes.map((n) => (
          <Card key={n.href} variant="flat">
            <Text as="p" size="n1" tone="muted" font="mono">
              {fmt(n.date)}
            </Text>
            <Heading level={2} size="2">
              <Link href={n.href} variant="quiet">
                {n.title}
              </Link>
            </Heading>
            <Text tone="secondary">{n.description}</Text>
          </Card>
        ))}
      </Stack>
    </Container>
  );
}

export function NoteArticle({
  title,
  date,
  children,
}: {
  title: string;
  date: Date;
  children: ReactNode;
}) {
  return (
    <Container size="text">
      <Stack gap="md" style={styles.page}>
        <Text as="p" size="n1" tone="muted" font="mono">
          {fmt(date)}
        </Text>
        <Heading level={1}>{title}</Heading>
        <article {...stylex.props(styles.article)} data-pagefind-body>
          {children}
        </article>
      </Stack>
    </Container>
  );
}
