import * as stylex from "@stylexjs/stylex";
import { colorMeta, paletteMeta, Table, Text } from "@biotic/design";
import { color } from "@biotic/design/tokens/color.stylex";
import { border, radius } from "@biotic/design/tokens/shape.stylex";
import { space } from "@biotic/design/tokens/space.stylex";
import { font } from "@biotic/design/tokens/type.stylex";
import { Section } from "./Section";

const styles = stylex.create({
  ramp: {
    gap: space.xxs,
    display: "grid",
    gridTemplateColumns: "repeat(11, minmax(0, 1fr))",
    marginBottom: space.md,
  },
  cell: { borderRadius: radius.sm, aspectRatio: "1 / 1.2" },
  step: { fontFamily: font.mono, fontSize: "0.65rem", textAlign: "center", marginTop: space.xxxs },
  chip: {
    borderColor: color.edgeSubtle,
    borderRadius: radius.sm,
    borderStyle: "solid",
    borderWidth: border.hairline,
    display: "inline-block",
    marginInlineEnd: space.xs,
    verticalAlign: "middle",
    height: "1.25rem",
    width: "2.5rem",
  },
  value: { fontFamily: font.mono, fontSize: "0.75rem" },
});

/** Swatches show literal values on purpose: this page documents what the tokens resolve to. */
function Swatch({ value }: { value: string }) {
  return (
    <span aria-hidden="true" style={{ backgroundColor: value }} {...stylex.props(styles.chip)} />
  );
}

export function ColorPage() {
  const hues = Object.entries(paletteMeta);
  const semantic = Object.entries(colorMeta);
  return (
    <>
      <Section
        id="palette"
        title="Palette"
        intro="Five hues, eleven steps each, in OKLCH. Lightness is the same ladder for every hue; chroma follows a bell that peaks mid-ramp. Generated, never hand-tuned."
      >
        {hues.map(([hue, steps]) => (
          <div key={hue}>
            <Text as="p" caps tone="muted">
              {hue}
            </Text>
            <div {...stylex.props(styles.ramp)}>
              {Object.entries(steps).map(([step, value]) => (
                <div key={step}>
                  <div
                    title={value}
                    style={{ backgroundColor: value }}
                    {...stylex.props(styles.cell)}
                  />
                  <div {...stylex.props(styles.step)}>{step}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </Section>
      <Section
        id="semantic"
        title="Semantic colour"
        intro="What components actually use. Each name has a value on the light face and the dark face; the variable follows the system preference and a theme class can force either."
      >
        <Table>
          <thead>
            <tr>
              <Table.Head>token</Table.Head>
              <Table.Head>light</Table.Head>
              <Table.Head>dark</Table.Head>
            </tr>
          </thead>
          <tbody>
            {semantic.map(([name, faces]) => (
              <tr key={name}>
                <Table.Cell>
                  <code {...stylex.props(styles.value)}>color.{name}</code>
                </Table.Cell>
                <Table.Cell>
                  <Swatch value={faces.light} />
                  <span {...stylex.props(styles.value)}>{faces.light}</span>
                </Table.Cell>
                <Table.Cell>
                  <Swatch value={faces.dark} />
                  <span {...stylex.props(styles.value)}>{faces.dark}</span>
                </Table.Cell>
              </tr>
            ))}
          </tbody>
        </Table>
      </Section>
    </>
  );
}
