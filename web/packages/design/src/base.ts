import * as stylex from "@stylexjs/stylex";
import { color } from "./tokens/generated/color.stylex";
import { font, leading } from "./tokens/type.stylex";

// Applied to <body> by the app layout. Everything a page inherits comes from here.
export const page = stylex.create({
  body: {
    backgroundColor: color.surfaceCanvas,
    color: color.inkPrimary,
    fontFamily: font.text,
    lineHeight: leading.normal,
  },
  selection: {
    "::selection": { backgroundColor: color.selection },
  },
});
