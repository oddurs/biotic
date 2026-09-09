import * as stylex from "@stylexjs/stylex";
import { Card, Grid, Heading, Link, Sparkline, Stack, Tag, Text } from "@biotic/design";
import { space } from "@biotic/design/tokens/space.stylex";
import { summarize, type Specimen } from "../../lib/specimens";

const styles = stylex.create({
  facts: { marginTop: space.sm },
});
const outcomeTone = {
  lag: "info",
  log: "positive",
  stationary: "caution",
  death: "negative",
  sterile: "neutral",
} as const;

export interface GalleryItem {
  id: string;
  href: string;
  data: Specimen;
}

/** Every specimen as a card: seed, who, a trace of the curve, and the numbers that matter. */
export function Gallery({ items }: { items: GalleryItem[] }) {
  return (
    <Grid min="18rem" gap="lg">
      {items.map(({ id, href, data }) => {
        const s = summarize(data);
        const tone = outcomeTone[s.outcome as keyof typeof outcomeTone] ?? "neutral";
        return (
          <Card key={id} variant="interactive">
            <Stack gap="xs">
              <Heading level={2} size="3">
                <Link href={href} variant="quiet">
                  “{data.seed}”
                </Link>
              </Heading>
              <Text size="n1" tone="muted">
                {data.by} · {data.submitted.toISOString().slice(0, 10)} · {data.model}
              </Text>
              <Sparkline
                values={data.curve.map((r) => r.population)}
                width={200}
                height={28}
                label={`population over ${s.ticks} ticks`}
              />
              <Text size="n1" tone="secondary">
                {data.summary}
              </Text>
              <Stack direction="row" gap="xs" wrap style={styles.facts}>
                <Tag tone={tone}>{s.outcome}</Tag>
                <Tag>{s.ticks} ticks</Tag>
                <Tag>peak {s.peak}</Tag>
                <Tag>
                  {s.living}/{s.strainsTotal} strains
                </Tag>
                <Tag>gen {s.generations}</Tag>
              </Stack>
            </Stack>
          </Card>
        );
      })}
    </Grid>
  );
}
