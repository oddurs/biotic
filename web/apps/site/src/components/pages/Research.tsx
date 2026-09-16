import { Callout, Container, Heading, Link, Stack, Table, Text } from "@biotic/design";
import { href } from "../../lib/url";

const works = [
  ["Ray, T. S.", "1991", "An approach to the synthesis of life (Tierra)", "Artificial Life II"],
  [
    "Ofria, C. & Wilke, C. O.",
    "2004",
    "Avida: a software platform for research in computational evolutionary biology",
    "Artificial Life 10(2)",
  ],
  [
    "Lehman, J., Gordon, J., Jain, S., Ndousse, K., Yeh, C. & Stanley, K. O.",
    "2022",
    "Evolution through Large Models",
    "arXiv:2206.08896",
  ],
  [
    "Romera-Paredes, B. et al.",
    "2024",
    "Mathematical discoveries from program search with large language models (FunSearch)",
    "Nature 625",
  ],
  [
    "Novikov, A. et al.",
    "2025",
    "AlphaEvolve: a coding agent for scientific and algorithmic discovery",
    "DeepMind",
  ],
  [
    "Zhang, J., Hu, S., Lu, C., Lange, R. & Clune, J.",
    "2025",
    "Darwin Gödel Machine: open-ended evolution of self-improving agents",
    "arXiv:2505.22954",
  ],
  ["Chan, B. W.-C.", "2019", "Lenia: biology of artificial life", "Complex Systems 28(3)"],
] as const;

export function Research() {
  return (
    <Container size="wide">
      <Stack gap="lg">
        <Heading level={1}>Research</Heading>
        <Text size="1" tone="secondary" leading="relaxed">
          Systems that evolve code sit on two axes: how mutation happens, and what selects.
        </Text>
        <Table>
          <thead>
            <tr>
              <Table.Head />
              <Table.Head>random mutation</Table.Head>
              <Table.Head>semantic mutation (a model)</Table.Head>
            </tr>
          </thead>
          <tbody>
            <tr>
              <Table.Cell>
                <strong>objective, a score</strong>
              </Table.Cell>
              <Table.Cell>genetic programming</Table.Cell>
              <Table.Cell>FunSearch, AlphaEvolve, the Darwin Gödel Machine</Table.Cell>
            </tr>
            <tr>
              <Table.Cell>
                <strong>ecology, no score</strong>
              </Table.Cell>
              <Table.Cell>Tierra, Avida, Lenia</Table.Cell>
              <Table.Cell>
                <strong>this project</strong>
              </Table.Cell>
            </tr>
          </tbody>
        </Table>
        <Text leading="relaxed">
          Random-mutation artificial life produced real things, parasites and hyperparasites among
          them, and then plateaued in simple environments. Model-driven program search produces
          software because it is search: a score, an archive, a best so far. The empty quadrant is
          semantic mutation with nothing to optimise. That is the experiment here. The{" "}
          <Link href={href("/docs/instrument/mutagen/")}>mutagen</Link> is told it does not know
          what will work; the <Link href={href("/docs/instrument/dish/")}>dish</Link> decides.
        </Text>
        <Callout tone="info" title="Results">
          Cultures and their full fossil record are shared in the{" "}
          <Link href={href("/library/")}>library</Link>. Write-ups appear in the{" "}
          <Link href={href("/notes/")}>field notes</Link>.
        </Callout>
        <Heading level={2} size="2">
          Bibliography
        </Heading>
        <Table>
          <thead>
            <tr>
              <Table.Head>authors</Table.Head>
              <Table.Head>year</Table.Head>
              <Table.Head>title</Table.Head>
              <Table.Head>venue</Table.Head>
            </tr>
          </thead>
          <tbody>
            {works.map(([authors, year, title, venue]) => (
              <tr key={title}>
                <Table.Cell>{authors}</Table.Cell>
                <Table.Cell>{year}</Table.Cell>
                <Table.Cell>{title}</Table.Cell>
                <Table.Cell>{venue}</Table.Cell>
              </tr>
            ))}
          </tbody>
        </Table>
      </Stack>
    </Container>
  );
}
