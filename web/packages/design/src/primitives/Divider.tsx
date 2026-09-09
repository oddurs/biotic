import * as stylex from "@stylexjs/stylex";
import { color } from "../tokens/generated/color.stylex";
import { border } from "../tokens/shape.stylex";
import { space } from "../tokens/space.stylex";

const styles = stylex.create({
  base: {
    marginBlock: space.lg,
    borderBlockStartColor: color.edgeSubtle,
    borderBlockStartStyle: "solid",
    borderBlockStartWidth: border.hairline,
    borderBottomWidth: 0,
  },
});

/** A horizontal rule. */
export function Divider({ style }: { style?: stylex.StyleXStyles }) {
  return <hr {...stylex.props(styles.base, style)} />;
}
