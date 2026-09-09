import * as stylex from "@stylexjs/stylex";
import { Button, Card, Container, Grid, Heading, Icon, Stack, Text } from "@biotic/design";
import { color } from "@biotic/design/tokens/color.stylex";
import { fluidSpace } from "@biotic/design/tokens/fluid.stylex";
import { media } from "@biotic/design/tokens/media.stylex";
import { radius } from "@biotic/design/tokens/shape.stylex";
import { space } from "@biotic/design/tokens/space.stylex";
import { font } from "@biotic/design/tokens/type.stylex";
import { site } from "../../site.config";
import { href } from "../lib/url";

const styles = stylex.create({
  hero: { paddingBlock: fluidSpace.xxl },
  heroGrid: {
    gap: fluidSpace.xl,
    alignItems: "center",
    display: "grid",
    gridTemplateColumns: { [media.md]: "minmax(0, 5fr) minmax(0, 6fr)", default: "1fr" },
  },
  title: { fontSize: "clamp(2.5rem, 1.5rem + 4vw, 4.5rem)" },
  dish: {
    padding: space.lg,
    borderRadius: radius.xl,
    overflow: "hidden",
    backgroundColor: color.surfaceInverse,
    color: color.inkInverse,
    fontFamily: font.mono,
    fontSize: "clamp(0.55rem, 0.4rem + 0.6vw, 0.8rem)",
    lineHeight: 1.25,
    whiteSpace: "pre",
  },
  section: { paddingBlock: fluidSpace.xl },
  cardTitle: { marginBottom: space.xs },
});

// A frame from the eyepiece. A live dish replaces this in a later change.
const frame = String.raw` biotic   seed “tide”   tick 1204   0h10m02s   ♥
╭─ agar ──────────────────────────╮ ╭─ vitals ───────────────────╮
│          ·:·∷∷∷:·               │ │ population  483  25% agar  │
│       ·:∷●●●●●●∷:·              │ │             ▁▂▃▅▆▇█████▇▇ │
│     ·:∷●●●●●●●●●●●∷:            │ │      phase  stationary     │
│    ·∷●●●●●●●●●●●●●●●:·          │ │    strains  6 living · 14  │
│    ∷●●●●●●●●●●●●●●●●●∷          │ │       agar  ████████░░ 0.41│
│    :●●●●●●●●●●●●●●●●●:          │ │    mutagen  ◐ thinking     │
│     ·∷●●●●●●●●●●●●∷·            │ ╰────────────────────────────╯
│        ·:∷∷●●●∷∷:·              │
╰─────────────────────────────────╯`;

const pillars = [
  {
    title: "The dish",
    body: "An elliptical agar grid with nutrient diffusion, pheromone, energetics, senescence, and lysis. Physics only; it knows nothing about language models.",
  },
  {
    title: "The membrane",
    body: "Every genome is untrusted code. Static rules, a restricted builtins table, a wall-clock budget, and forty ticks of smoke test stand between it and the dish.",
  },
  {
    title: "The mutagen",
    body: "On a fraction of divisions, a model rewrites the daughter's genome by one small heritable change. It never scores anything. Selection decides.",
  },
];

export function Landing() {
  return (
    <>
      <section {...stylex.props(styles.hero)}>
        <Container>
          <div {...stylex.props(styles.heroGrid)}>
            <Stack gap="lg">
              <Text caps tone="accent" as="p">
                Open-ended evolution with semantic mutation
              </Text>
              <Heading level={1} style={styles.title}>
                A culture of cells that write themselves, in a dish you can watch.
              </Heading>
              <Text size="1" tone="secondary" leading="relaxed">
                {site.tagline} Place a seed. A language model writes the founding cell. After that,
                you mostly watch.
              </Text>
              <Stack direction="row" gap="sm" wrap>
                <Button href={href("/docs/")} size="lg">
                  Read the docs <Icon name="arrowRight" />
                </Button>
                <Button href={site.repo} variant="secondary" size="lg">
                  <Icon name="github" /> Source
                </Button>
              </Stack>
            </Stack>
            <div {...stylex.props(styles.dish)} aria-hidden="true">
              {frame}
            </div>
          </div>
        </Container>
      </section>
      <section {...stylex.props(styles.section)}>
        <Container>
          <Grid min="18rem" gap="lg">
            {pillars.map((p) => (
              <Card key={p.title}>
                <Heading level={2} size="2" style={styles.cardTitle}>
                  {p.title}
                </Heading>
                <Text tone="secondary">{p.body}</Text>
              </Card>
            ))}
          </Grid>
        </Container>
      </section>
    </>
  );
}
