import * as stylex from "@stylexjs/stylex";
import { fluidSpaceMeta, Table } from "@biotic/design";
import { color } from "@biotic/design/tokens/color.stylex";
import { radius } from "@biotic/design/tokens/shape.stylex";
import { space } from "@biotic/design/tokens/space.stylex";
import { font } from "@biotic/design/tokens/type.stylex";
import { Section } from "./Section";

const ladder = {
  xxxs: "0.125rem",
  xxs: "0.25rem",
  xs: "0.5rem",
  sm: "0.75rem",
  md: "1rem",
  lg: "1.5rem",
  xl: "2rem",
  xxl: "3rem",
  xxxl: "4rem",
  huge: "6rem",
} as const;

const styles = stylex.create({
  row: {
    gap: space.md,
    alignItems: "center",
    display: "grid",
    gridTemplateColumns: "4rem 6rem minmax(0, 1fr)",
    marginBottom: space.xs,
  },
  bar: { borderRadius: radius.sm, backgroundColor: color.accentBase, height: "0.75rem" },
  mono: { fontFamily: font.mono, fontSize: "0.75rem" },
});
const bars = stylex.create({
  huge: { width: space.huge },
  lg: { width: space.lg },
  md: { width: space.md },
  sm: { width: space.sm },
  xl: { width: space.xl },
  xs: { width: space.xs },
  xxl: { width: space.xxl },
  xxs: { width: space.xxs },
  xxxl: { width: space.xxxl },
  xxxs: { width: space.xxxs },
});

export function SpacePage() {
  return (
    <>
      <Section
        id="ladder"
        title="Ladder"
        intro="Fixed steps on a 4px base for spacing inside components."
      >
        {(Object.keys(ladder) as (keyof typeof ladder)[]).map((k) => (
          <div key={k} {...stylex.props(styles.row)}>
            <code {...stylex.props(styles.mono)}>space.{k}</code>
            <code {...stylex.props(styles.mono)}>{ladder[k]}</code>
            <div {...stylex.props(styles.bar, bars[k])} />
          </div>
        ))}
      </Section>
      <Section
        id="fluid"
        title="Fluid"
        intro="For rhythm between sections, which should breathe with the viewport. Same clamp() construction as the type scale."
      >
        <Table>
          <thead>
            <tr>
              <Table.Head>token</Table.Head>
              <Table.Head>value</Table.Head>
            </tr>
          </thead>
          <tbody>
            {Object.entries(fluidSpaceMeta).map(([k, v]) => (
              <tr key={k}>
                <Table.Cell>
                  <code {...stylex.props(styles.mono)}>fluidSpace.{k}</code>
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
