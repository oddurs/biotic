import { describe, expect, test } from "vitest";
import { render } from "vitest-browser-react";
import { expectAccessible } from "../test/a11y";
import {
  Button,
  Callout,
  Card,
  Code,
  Container,
  Divider,
  Grid,
  Heading,
  Icon,
  Link,
  Sparkline,
  Stack,
  Table,
  Tag,
  Text,
  ThemeToggle,
  VisuallyHidden,
} from "./index";

describe("primitives render, carry styles, and pass axe", () => {
  test("Text and Heading", async () => {
    const screen = await render(
      <main>
        <Heading level={1}>A culture of cells</Heading>
        <Text size="1" tone="secondary" weight="medium">
          that write themselves
        </Text>
        <Text as="span" font="mono" caps>
          strain 3f1a
        </Text>
      </main>,
    );
    const h1 = screen.getByRole("heading", { level: 1 });
    await expect.element(h1).toBeVisible();
    expect(getComputedStyle(h1.element()).fontFamily).toMatch(/Fraunces/);
    await expectAccessible();
  });

  test("Link marks external links", async () => {
    const screen = await render(
      <p>
        <Link href="/docs">docs</Link> and{" "}
        <Link href="https://github.com/oddurs/biotic">github</Link>
      </p>,
    );
    const ext = screen.getByRole("link", { name: "github" });
    await expect.element(ext).toHaveAttribute("target", "_blank");
    await expect.element(ext).toHaveAttribute("rel", "noopener noreferrer");
    await expect.element(screen.getByRole("link", { name: "docs" })).not.toHaveAttribute("target");
    await expectAccessible();
  });

  test("Button is a button, or a link when given href", async () => {
    const screen = await render(
      <Stack direction="row" gap="sm">
        <Button>Seed</Button>
        <Button variant="secondary" size="sm">
          Observe
        </Button>
        <Button variant="ghost" href="/docs">
          Read the docs
        </Button>
        <Button disabled>Sterilize</Button>
      </Stack>,
    );
    await expect
      .element(screen.getByRole("button", { name: "Seed" }))
      .toHaveAttribute("type", "button");
    await expect
      .element(screen.getByRole("link", { name: "Read the docs" }))
      .toHaveAttribute("href", "/docs");
    await expect.element(screen.getByRole("button", { name: "Sterilize" })).toBeDisabled();
    await expectAccessible();
  });

  test("Layout primitives lay out", async () => {
    const screen = await render(
      <Container size="text">
        <Stack gap="lg" data-testid="stack">
          <Grid min="8rem" data-testid="grid">
            <Card>one</Card>
            <Card variant="raised">two</Card>
            <Card variant="interactive">three</Card>
          </Grid>
          <Divider />
        </Stack>
      </Container>,
    );
    expect(getComputedStyle(screen.getByTestId("stack").element()).display).toBe("flex");
    expect(getComputedStyle(screen.getByTestId("grid").element()).display).toBe("grid");
    await expectAccessible();
  });

  test("Callout, Tag, Code, Icon, VisuallyHidden", async () => {
    const screen = await render(
      <div>
        <Callout tone="caution" title="Closed dish">
          With replenish at 0 the culture blooms, crashes, and is done.
        </Callout>
        <Tag tone="positive">log phase</Tag>
        <Tag mono>3f1a</Tag>
        <p>
          Run <Code>biotic live</Code>
        </p>
        <Icon name="github" label="GitHub" />
        <VisuallyHidden>only for screen readers</VisuallyHidden>
      </div>,
    );
    await expect.element(screen.getByRole("note")).toBeVisible();
    await expect.element(screen.getByRole("img", { name: "GitHub" })).toBeInTheDocument();
    const hidden = screen.getByText("only for screen readers").element();
    expect(getComputedStyle(hidden).position).toBe("absolute");
    await expectAccessible();
  });

  test("Table and Sparkline", async () => {
    const screen = await render(
      <div>
        <Table>
          <thead>
            <tr>
              <Table.Head>strain</Table.Head>
              <Table.Head numeric>n</Table.Head>
            </tr>
          </thead>
          <tbody>
            <tr>
              <Table.Cell>tide_drift</Table.Cell>
              <Table.Cell numeric>212</Table.Cell>
            </tr>
          </tbody>
        </Table>
        <Sparkline values={[1, 4, 9, 16, 12, 7]} label="population over the last 6 samples" />
      </div>,
    );
    await expect.element(screen.getByRole("columnheader", { name: "strain" })).toBeVisible();
    await expect.element(screen.getByRole("img", { name: /population/ })).toBeInTheDocument();
    await expectAccessible();
  });

  test("ThemeToggle cycles auto, light, dark and persists", async () => {
    localStorage.removeItem("biotic.theme");
    const screen = await render(<ThemeToggle />);
    const button = screen.getByRole("button");
    await expect.element(button).toHaveAccessibleName(/System theme/);
    await button.click();
    await expect.element(button).toHaveAccessibleName(/Light theme/);
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem("biotic.theme")).toBe("light");
    await button.click();
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.classList.length).toBeGreaterThan(0);
    await button.click();
    expect(document.documentElement.dataset.theme).toBe("auto");
    expect(localStorage.getItem("biotic.theme")).toBeNull();
    await expectAccessible();
  });
});
