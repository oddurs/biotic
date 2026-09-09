import * as stylex from "@stylexjs/stylex";
import { Container, Link, Text } from "@biotic/design";
import { color } from "@biotic/design/tokens/color.stylex";
import { space } from "@biotic/design/tokens/space.stylex";
import { site } from "../../site.config";
import { href } from "../lib/url";

const styles = stylex.create({
  footer: {
    paddingBlock: space.xl,
    borderTopColor: color.edgeSubtle,
    borderTopStyle: "solid",
    borderTopWidth: "1px",
    marginTop: "auto",
  },
  row: {
    gap: space.md,
    display: "flex",
    flexWrap: "wrap",
    justifyContent: "space-between",
  },
  links: { gap: space.md, display: "flex", flexWrap: "wrap" },
});

export function Footer() {
  return (
    <footer {...stylex.props(styles.footer)}>
      <Container>
        <div {...stylex.props(styles.row)}>
          <Text as="p" size="n1" tone="muted">
            {site.name} · MIT license · {site.author}
          </Text>
          <nav aria-label="Footer" {...stylex.props(styles.links)}>
            <Link href={href("/about/")} variant="quiet">
              About
            </Link>
            <Link href={`${site.repo}/blob/main/CHANGELOG.md`} variant="quiet">
              Changelog
            </Link>
            <Link href={`${site.repo}/discussions`} variant="quiet">
              Discussions
            </Link>
            <Link href={site.repo} variant="quiet">
              GitHub
            </Link>
          </nav>
        </div>
      </Container>
    </footer>
  );
}
