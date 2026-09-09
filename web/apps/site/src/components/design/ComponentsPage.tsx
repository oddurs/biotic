import * as stylex from "@stylexjs/stylex";
import {
  Button,
  Callout,
  Card,
  Code,
  Divider,
  Grid,
  Heading,
  Icon,
  type IconName,
  Link,
  Sparkline,
  Stack,
  Table,
  Tag,
  Text,
} from "@biotic/design";
import { space } from "@biotic/design/tokens/space.stylex";
import { font } from "@biotic/design/tokens/type.stylex";
import { Section } from "./Section";

const styles = stylex.create({
  icons: { gap: space.md, display: "flex", flexWrap: "wrap" },
  icon: {
    gap: space.xxs,
    alignItems: "center",
    display: "flex",
    flexDirection: "column",
    fontSize: "1.5rem",
  },
  iconName: { fontFamily: font.mono, fontSize: "0.7rem" },
});

const icons: IconName[] = [
  "arrowRight",
  "arrowUpRight",
  "check",
  "close",
  "github",
  "info",
  "menu",
  "moon",
  "search",
  "sun",
  "warning",
];

export function ComponentsPage() {
  return (
    <>
      <Section
        id="button"
        title="Button"
        intro="Three variants, three sizes. With href it renders an anchor and keeps the look."
      >
        <Stack direction="row" gap="sm" wrap align="center">
          <Button>Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button size="sm">Small</Button>
          <Button size="lg">
            Large <Icon name="arrowRight" />
          </Button>
          <Button disabled>Disabled</Button>
          <Button href="#button" variant="secondary">
            As a link
          </Button>
        </Stack>
      </Section>
      <Section
        id="text"
        title="Text and Heading"
        intro="Level is semantics; size is appearance. Tone and weight are tokens."
      >
        <Stack gap="xs">
          <Heading level={3} size="4">
            Display heading
          </Heading>
          <Heading level={3} size="2" plain>
            Plain heading in the text face
          </Heading>
          <Text>Primary running text at the base step.</Text>
          <Text tone="secondary">Secondary tone for supporting copy.</Text>
          <Text tone="muted" size="n1">
            Muted, one step down.
          </Text>
          <Text caps tone="accent">
            A small-caps label
          </Text>
          <Text font="mono">me.energy &gt; 0.9</Text>
        </Stack>
      </Section>
      <Section
        id="link"
        title="Link"
        intro="External links open a new tab with the right rel; internal ones do not."
      >
        <Text>
          <Link href="#link">default</Link>,{" "}
          <Link href="#link" variant="quiet">
            quiet
          </Link>
          ,{" "}
          <Link href="#link" variant="nav">
            nav
          </Link>
          , and <Link href="https://github.com/oddurs/biotic">external</Link>.
        </Text>
      </Section>
      <Section id="card" title="Card" intro="A bounded surface in four variants.">
        <Grid min="12rem" gap="md">
          <Card>flat</Card>
          <Card variant="raised">raised</Card>
          <Card variant="interactive">interactive</Card>
          <Card variant="sunken">sunken</Card>
        </Grid>
      </Section>
      <Section
        id="callout"
        title="Callout"
        intro="Four tones. It is a note landmark with an icon that matches the tone."
      >
        <Stack gap="sm">
          <Callout tone="info" title="Info">
            The dish never waits on the mind.
          </Callout>
          <Callout tone="positive" title="Positive">
            The culture entered log phase.
          </Callout>
          <Callout tone="caution" title="Caution">
            Replenish is 0: this is a closed dish.
          </Callout>
          <Callout tone="negative" title="Negative">
            Sterilizing destroys the culture and the fossil record.
          </Callout>
        </Stack>
      </Section>
      <Section id="tag" title="Tag" intro="Labels for phases, tones, and identifiers.">
        <Stack direction="row" gap="xs" wrap>
          <Tag>neutral</Tag>
          <Tag tone="accent">accent</Tag>
          <Tag tone="positive">log</Tag>
          <Tag tone="caution">stationary</Tag>
          <Tag tone="negative">death</Tag>
          <Tag tone="info">lag</Tag>
          <Tag mono>3f1a</Tag>
        </Stack>
      </Section>
      <Section
        id="code"
        title="Code"
        intro="Inline only; blocks are rendered by the docs pipeline."
      >
        <Text>
          Run <Code>biotic seed &quot;tide&quot;</Code> then <Code>biotic live</Code>.
        </Text>
      </Section>
      <Section
        id="table"
        title="Table"
        intro="Scrolls horizontally when narrow. Numeric cells are tabular and right-aligned."
      >
        <Table>
          <thead>
            <tr>
              <Table.Head>strain</Table.Head>
              <Table.Head>note</Table.Head>
              <Table.Head numeric>n</Table.Head>
              <Table.Head numeric>share</Table.Head>
            </tr>
          </thead>
          <tbody>
            <tr>
              <Table.Cell>tide_drift</Table.Cell>
              <Table.Cell>leans into the current when kin are near</Table.Cell>
              <Table.Cell numeric>212</Table.Cell>
              <Table.Cell numeric>44%</Table.Cell>
            </tr>
            <tr>
              <Table.Cell>slack_water</Table.Cell>
              <Table.Cell>rests at the edge until the agar recovers</Table.Cell>
              <Table.Cell numeric>131</Table.Cell>
              <Table.Cell numeric>27%</Table.Cell>
            </tr>
          </tbody>
        </Table>
      </Section>
      <Section
        id="sparkline"
        title="Sparkline"
        intro="A word-sized trace, like the population history in the eyepiece."
      >
        <Stack direction="row" gap="md" align="center">
          <Sparkline
            values={[5, 9, 16, 31, 60, 110, 180, 260, 330, 380, 400, 405, 398, 390]}
            label="a growth curve: lag, log, stationary"
          />
          <Text tone="muted" size="n1">
            lag, log, stationary
          </Text>
        </Stack>
      </Section>
      <Section
        id="icon"
        title="Icon"
        intro="A small stroke set on a 24 grid that scales with text. Decorative unless given a label."
      >
        <div {...stylex.props(styles.icons)}>
          {icons.map((name) => (
            <div key={name} {...stylex.props(styles.icon)}>
              <Icon name={name} label={name} />
              <span {...stylex.props(styles.iconName)}>{name}</span>
            </div>
          ))}
        </div>
      </Section>
      <Section id="divider" title="Divider">
        <Divider />
      </Section>
    </>
  );
}
