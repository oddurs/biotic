import { Code, Container, Heading, Link, Stack, Text } from "@biotic/design";
import { site } from "../../../site.config";
import { href } from "../../lib/url";

export function About() {
  return (
    <Container size="text">
      <Stack gap="lg">
        <Heading level={1}>About</Heading>
        <Text size="1" tone="secondary" leading="relaxed">
          {site.name} is a research instrument for open-ended evolution with semantic mutation: a
          petri dish whose cells are small programs, and whose mutation operator is a language model
          that rewrites a genome by one heritable change. There is no objective and no score.
          Whatever persists, persists.
        </Text>
        <Text leading="relaxed">
          It is built and maintained by {site.author} and published under the MIT license. The
          apparatus is Python; this site is an Astro app on a StyleX design system. Both live in{" "}
          <Link href={site.repo}>one repository</Link>, and both change only through pull requests
          that pass the same gate.
        </Text>
        <Heading level={2} size="2">
          Citing
        </Heading>
        <Text leading="relaxed">
          Cite the repository and the version you used. The <Link href={href("/docs/")}>docs</Link>{" "}
          describe the physics and the membrane in enough detail to reproduce a run; a{" "}
          <Link href={href("/library/")}>specimen</Link> carries the seed, the model, and every
          genome.
        </Text>
        <Text as="pre" font="mono" size="n1">
          {`@software{${site.name}2026,
  author = {${site.author}},
  title = {${site.name}: ${site.tagline}},
  year = {2026},
  url = {${site.repo}}
}`}
        </Text>
        <Heading level={2} size="2">
          Contact
        </Heading>
        <Text leading="relaxed">
          Questions and results go to <Link href={`${site.repo}/discussions`}>Discussions</Link>.
          Bugs go to <Link href={`${site.repo}/issues`}>Issues</Link>. A way through the membrane is
          a security bug: report it privately, as <Code>SECURITY.md</Code> describes.
        </Text>
      </Stack>
    </Container>
  );
}
