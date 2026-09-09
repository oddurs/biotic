import * as stylex from "@stylexjs/stylex";
import { Tag, Text } from "@biotic/design";
import { color } from "@biotic/design/tokens/color.stylex";
import { radius } from "@biotic/design/tokens/shape.stylex";
import { space } from "@biotic/design/tokens/space.stylex";
import { font } from "@biotic/design/tokens/type.stylex";
import { diffLines } from "diff";
import type { Strain } from "../../lib/specimens";

const styles = stylex.create({
  details: {
    borderColor: color.edgeSubtle,
    borderRadius: radius.md,
    borderStyle: "solid",
    borderWidth: "1px",
    marginBottom: space.sm,
  },
  summary: {
    padding: space.sm,
    gap: space.sm,
    alignItems: "center",
    cursor: "pointer",
    display: "flex",
    flexWrap: "wrap",
  },
  note: { color: color.inkSecondary, fontStyle: "italic" },
  pre: {
    margin: 0,
    padding: space.sm,
    backgroundColor: color.surfaceSunken,
    fontFamily: font.mono,
    fontSize: "0.8rem",
    lineHeight: 1.5,
    borderBottomLeftRadius: radius.md,
    borderBottomRightRadius: radius.md,
    overflowX: "auto",
  },
  line: { paddingInline: space.xs, display: "block", whiteSpace: "pre" },
  added: { backgroundColor: color.positiveSoft },
  removed: { backgroundColor: color.negativeSoft, textDecorationLine: "line-through" },
});

function Diff({ from, to }: { from: string; to: string }) {
  const parts = diffLines(from, to);
  return (
    <pre {...stylex.props(styles.pre)}>
      {parts.flatMap((part, i) =>
        part.value
          .replace(/\n$/, "")
          .split("\n")
          .map((line, j) => (
            <span
              key={`${i}-${j}`}
              {...stylex.props(
                styles.line,
                part.added && styles.added,
                part.removed && styles.removed,
              )}
            >
              {part.added ? "+ " : part.removed ? "- " : "  "}
              {line}
            </span>
          )),
      )}
    </pre>
  );
}

/** Every strain's genome, shown as the change from its parent. The founder is shown whole. */
export function GenomeDiff({ strains }: { strains: Strain[] }) {
  const byId = new Map(strains.map((s) => [s.id, s]));
  return (
    <div>
      {[...strains]
        .sort((a, b) => a.born - b.born)
        .map((s) => {
          const parent = s.parent ? byId.get(s.parent) : undefined;
          return (
            <details key={s.id} {...stylex.props(styles.details)} open={!parent}>
              <summary {...stylex.props(styles.summary)}>
                <Tag mono>{s.id}</Tag>
                <Text as="span" weight="medium">
                  {s.name}
                </Text>
                <Text as="span" size="n1" tone="muted">
                  gen {s.generation} · born {s.born} · peak {s.peak}
                  {s.extinct_at !== null ? ` · extinct ${s.extinct_at}` : ""}
                </Text>
                {s.note && (
                  <Text as="span" size="n1" style={styles.note}>
                    {s.note}
                  </Text>
                )}
              </summary>
              {parent ? (
                <Diff from={parent.source} to={s.source} />
              ) : (
                <pre {...stylex.props(styles.pre)}>{s.source}</pre>
              )}
            </details>
          );
        })}
    </div>
  );
}
