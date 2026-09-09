import * as stylex from "@stylexjs/stylex";
import { fluidTypeMeta, Heading, Stack, Table, Text } from "@biotic/design";
import { color } from "@biotic/design/tokens/color.stylex";
import { border } from "@biotic/design/tokens/shape.stylex";
import { space } from "@biotic/design/tokens/space.stylex";
import { font } from "@biotic/design/tokens/type.stylex";
import { Section } from "./Section";

const styles = stylex.create({
  row: {
    gap: space.md,
    paddingBlock: space.sm,
    alignItems: "baseline",
    display: "grid",
    gridTemplateColumns: "5rem minmax(0, 1fr)",
    borderBottomColor: color.edgeSubtle,
    borderBottomStyle: "solid",
    borderBottomWidth: border.hairline,
  },
  mono: { fontFamily: font.mono, fontSize: "0.75rem" },
});

const sample = "The culture entered stationary phase";
const stepOrder = [
  "step6",
  "step5",
  "step4",
  "step3",
  "step2",
  "step1",
  "step0",
  "stepn1",
  "stepn2",
] as const;
const sizeFor = (k: string) =>
  k.startsWith("stepn")
    ? (`n${k.slice(5)}` as "n1" | "n2")
    : (k.slice(4) as "0" | "1" | "2" | "3" | "4" | "5" | "6");

export function TypePage() {
  return (
    <>
      <Section
        id="faces"
        title="Faces"
        intro="A display serif for headings, a humanist sans for reading, a mono for genomes. All three are variable fonts, self-hosted."
      >
        <Stack gap="lg">
          <div>
            <Text as="p" caps tone="muted">
              Fraunces, display
            </Text>
            <Heading level={2} size="5">
              {sample}
            </Heading>
          </div>
          <div>
            <Text as="p" caps tone="muted">
              Inter, text
            </Text>
            <Text size="2">{sample}</Text>
          </div>
          <div>
            <Text as="p" caps tone="muted">
              JetBrains Mono, code
            </Text>
            <Text size="1" font="mono">
              def live(me): return &quot;eat&quot;
            </Text>
          </div>
        </Stack>
      </Section>
      <Section
        id="scale"
        title="Scale"
        intro="Nine steps that interpolate between a 20rem and an 80rem viewport, from a ratio of 1.2 to 1.25. Each is a clamp(); nothing snaps at a breakpoint."
      >
        {stepOrder.map((k) => (
          <div key={k} {...stylex.props(styles.row)}>
            <code {...stylex.props(styles.mono)}>{k}</code>
            <Text size={sizeFor(k)} leading="tight" truncate>
              {sample}
            </Text>
          </div>
        ))}
        <Table>
          <thead>
            <tr>
              <Table.Head>token</Table.Head>
              <Table.Head>value</Table.Head>
            </tr>
          </thead>
          <tbody>
            {Object.entries(fluidTypeMeta).map(([k, v]) => (
              <tr key={k}>
                <Table.Cell>
                  <code {...stylex.props(styles.mono)}>fluidType.{k}</code>
                </Table.Cell>
                <Table.Cell>
                  <code {...stylex.props(styles.mono)}>{v}</code>
                </Table.Cell>
              </tr>
            ))}
          </tbody>
        </Table>
      </Section>
    </>
  );
}
