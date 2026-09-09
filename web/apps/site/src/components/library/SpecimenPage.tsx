import * as stylex from "@stylexjs/stylex";
import { Card, Grid, Heading, Stack, Table, Tag, Text } from "@biotic/design";
import { fluidSpace } from "@biotic/design/tokens/fluid.stylex";
import { space } from "@biotic/design/tokens/space.stylex";
import type { ReactNode } from "react";
import { summarize, type Specimen } from "../../lib/specimens";
import { GenomeDiff } from "./GenomeDiff";
import { GrowthCurve } from "./GrowthCurve";
import { Lineage } from "./Lineage";

const styles = stylex.create({
  section: { marginBlock: fluidSpace.lg },
  heading: { marginBottom: space.sm },
  scroll: { overflowX: "auto" },
  stat: { textAlign: "center" },
});

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <Card variant="sunken" style={styles.stat}>
      <Text as="div" size="3" font="display" leading="tight">
        {value}
      </Text>
      <Text as="div" size="n1" tone="muted" caps>
        {label}
      </Text>
    </Card>
  );
}

/** `discussion` is a slot for the hydrated giscus island. */
export function SpecimenPage({ data, discussion }: { data: Specimen; discussion?: ReactNode }) {
  const s = summarize(data);
  const living = data.strains.filter((x) => x.extinct_at === null).sort((a, b) => b.peak - a.peak);
  return (
    <>
      <Grid min="7rem" gap="sm">
        <Stat label="ticks" value={s.ticks} />
        <Stat label="peak population" value={s.peak} />
        <Stat label="strains arose" value={s.strainsTotal} />
        <Stat label="living" value={s.living} />
        <Stat label="generations" value={s.generations} />
        <Stat label="outcome" value={s.outcome} />
      </Grid>
      <section {...stylex.props(styles.section)}>
        <Heading level={2} size="2" style={styles.heading}>
          Growth curve
        </Heading>
        <GrowthCurve curve={data.curve} />
      </section>
      <section {...stylex.props(styles.section)}>
        <Heading level={2} size="2" style={styles.heading}>
          Lineage
        </Heading>
        <div {...stylex.props(styles.scroll)}>
          <Lineage strains={data.strains} />
        </div>
      </section>
      <section {...stylex.props(styles.section)}>
        <Heading level={2} size="2" style={styles.heading}>
          Census at the end
        </Heading>
        <Table>
          <thead>
            <tr>
              <Table.Head>id</Table.Head>
              <Table.Head>strain</Table.Head>
              <Table.Head>note</Table.Head>
              <Table.Head numeric>gen</Table.Head>
              <Table.Head numeric>born</Table.Head>
              <Table.Head numeric>peak</Table.Head>
            </tr>
          </thead>
          <tbody>
            {living.map((x) => (
              <tr key={x.id}>
                <Table.Cell>
                  <Tag mono>{x.id}</Tag>
                </Table.Cell>
                <Table.Cell>{x.name}</Table.Cell>
                <Table.Cell>{x.note}</Table.Cell>
                <Table.Cell numeric>{x.generation}</Table.Cell>
                <Table.Cell numeric>{x.born}</Table.Cell>
                <Table.Cell numeric>{x.peak}</Table.Cell>
              </tr>
            ))}
          </tbody>
        </Table>
      </section>
      <section {...stylex.props(styles.section)}>
        <Stack gap="xs" style={styles.heading}>
          <Heading level={2} size="2">
            Genomes
          </Heading>
          <Text tone="secondary" size="n1">
            Each strain as the change from its parent. The founder is shown whole.
          </Text>
        </Stack>
        <GenomeDiff strains={data.strains} />
      </section>
      <section {...stylex.props(styles.section)}>
        <Heading level={2} size="2" style={styles.heading}>
          Discussion
        </Heading>
        {discussion}
      </section>
    </>
  );
}
