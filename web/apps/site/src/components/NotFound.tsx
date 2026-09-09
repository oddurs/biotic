import * as stylex from "@stylexjs/stylex";
import { Button, Container, Heading, Stack, Text } from "@biotic/design";
import { fluidSpace } from "@biotic/design/tokens/fluid.stylex";
import { href } from "../lib/url";

const styles = stylex.create({
  block: { paddingBlock: fluidSpace.xxxl },
});

export function NotFound() {
  return (
    <Container size="text">
      <Stack gap="md" style={styles.block}>
        <Heading level={1}>Sterile</Heading>
        <Text tone="secondary">Nothing grew at this address.</Text>
        <div>
          <Button href={href("/")} variant="secondary">
            Back to the dish
          </Button>
        </div>
      </Stack>
    </Container>
  );
}
