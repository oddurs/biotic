import { Card, Grid, Heading, Link, Text } from "@biotic/design";
import { designNav } from "./nav";
import { Section } from "./Section";

const principles = [
  [
    "An instrument, not a brand",
    "The palette is the dish's own: agar, pheromone, glass, nutrient, lysis. Type is editorial because the audience reads.",
  ],
  [
    "Tokens or nothing",
    "Every colour, size, and rhythm is a StyleX variable. A component that needs a value the system lacks gets a token first.",
  ],
  [
    "Two faces, one vocabulary",
    "Light and dark are the same semantic names with different values. Components never know which face they are on.",
  ],
  [
    "Derived, not typed",
    "The palette ramps and the fluid scales are generated from a few numbers. A test fails if the checked-in output drifts.",
  ],
  [
    "Static by default",
    "Pages ship no JavaScript unless a component needs it, and then only that component hydrates.",
  ],
  [
    "Audited in a browser",
    "Each primitive renders in Chromium under test with an axe pass, so regressions in contrast or semantics fail the gate.",
  ],
] as const;

export function Overview() {
  return (
    <>
      <Section id="principles" title="Principles">
        <Grid min="18rem" gap="md">
          {principles.map(([title, body]) => (
            <Card key={title} variant="sunken">
              <Heading level={3} size="1" plain>
                {title}
              </Heading>
              <Text tone="secondary" size="n1">
                {body}
              </Text>
            </Card>
          ))}
        </Grid>
      </Section>
      <Section
        id="map"
        title="What is here"
        intro="The system documents itself: every page renders the real tokens and components."
      >
        <ul>
          {designNav.slice(1).map((item) => (
            <li key={item.href}>
              <Link href={item.href}>{item.label}</Link>
            </li>
          ))}
        </ul>
      </Section>
      <Section id="using" title="Using it" intro="From any component in the site:">
        <Text as="pre" font="mono" size="n1">
          {`import * as stylex from "@stylexjs/stylex";
import { Button, Card } from "@biotic/design";
import { color } from "@biotic/design/tokens/color.stylex";
import { space } from "@biotic/design/tokens/space.stylex";

const styles = stylex.create({
  panel: { backgroundColor: color.surfaceSunken, padding: space.lg },
});`}
        </Text>
      </Section>
    </>
  );
}
