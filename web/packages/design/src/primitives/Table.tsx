import * as stylex from "@stylexjs/stylex";
import type { ComponentPropsWithoutRef } from "react";
import { color } from "../tokens/generated/color.stylex";
import { fluidType } from "../tokens/generated/fluid.stylex";
import { border } from "../tokens/shape.stylex";
import { space } from "../tokens/space.stylex";
import { font, weight } from "../tokens/type.stylex";

const styles = stylex.create({
  wrap: { overflowX: "auto", width: "100%" },
  table: { borderCollapse: "collapse", fontSize: fluidType.stepn1, width: "100%" },
  th: {
    paddingBlock: space.xs,
    paddingInline: space.sm,
    color: color.inkSecondary,
    fontWeight: weight.semibold,
    textAlign: "start",
    borderBottomColor: color.edgeStrong,
    borderBottomStyle: "solid",
    borderBottomWidth: border.hairline,
  },
  td: {
    paddingBlock: space.xs,
    paddingInline: space.sm,
    verticalAlign: "top",
    borderBottomColor: color.edgeSubtle,
    borderBottomStyle: "solid",
    borderBottomWidth: border.hairline,
  },
  num: { fontFamily: font.mono, fontVariantNumeric: "tabular-nums", textAlign: "end" },
});

type Strip<T extends keyof React.JSX.IntrinsicElements> = Omit<
  ComponentPropsWithoutRef<T>,
  "style" | "className"
> & {
  style?: stylex.StyleXStyles;
};

/** A data table. Compose: Table > thead/tbody > tr > Table.Head / Table.Cell. */
export function Table({ style, ...rest }: Strip<"table">) {
  return (
    <div {...stylex.props(styles.wrap)}>
      <table {...rest} {...stylex.props(styles.table, style)} />
    </div>
  );
}
function Head({ style, numeric, ...rest }: Strip<"th"> & { numeric?: boolean }) {
  return <th scope="col" {...rest} {...stylex.props(styles.th, numeric && styles.num, style)} />;
}
function Cell({ style, numeric, ...rest }: Strip<"td"> & { numeric?: boolean }) {
  return <td {...rest} {...stylex.props(styles.td, numeric && styles.num, style)} />;
}
Table.Head = Head;
Table.Cell = Cell;
