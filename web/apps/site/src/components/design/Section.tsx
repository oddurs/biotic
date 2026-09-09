import * as stylex from "@stylexjs/stylex";
import { Heading, Text } from "@biotic/design";
import { fluidSpace } from "@biotic/design/tokens/fluid.stylex";
import { space } from "@biotic/design/tokens/space.stylex";
import type { ReactNode } from "react";

const styles = stylex.create({
  section: { marginBlock: fluidSpace.lg },
  heading: { marginBottom: space.xs },
  intro: { marginBottom: space.md },
});

/** A titled block within a design page; headings get ids so they can be linked. */
export function Section({
  id,
  title,
  intro,
  children,
}: {
  id: string;
  title: string;
  intro?: string;
  children: ReactNode;
}) {
  return (
    <section id={id} {...stylex.props(styles.section)}>
      <Heading level={2} size="2" style={styles.heading}>
        {title}
      </Heading>
      {intro && (
        <Text tone="secondary" style={styles.intro}>
          {intro}
        </Text>
      )}
      {children}
    </section>
  );
}
