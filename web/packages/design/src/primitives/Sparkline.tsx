import * as stylex from "@stylexjs/stylex";
import { color } from "../tokens/generated/color.stylex";

const styles = stylex.create({
  base: { overflow: "visible", color: color.accentBase, display: "block" },
});

export interface SparklineProps {
  values: readonly number[];
  width?: number;
  height?: number;
  /** Accessible summary; the numbers themselves are not read out. */
  label: string;
  style?: stylex.StyleXStyles;
}

/** A word-sized line chart, like the population trace in the eyepiece. */
export function Sparkline({ values, width = 120, height = 24, label, style }: SparklineProps) {
  const max = Math.max(1, ...values);
  const n = Math.max(1, values.length - 1);
  const points = values.map(
    (v, i) => `${((i / n) * width).toFixed(1)},${(height - (v / max) * height).toFixed(1)}`,
  );
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      role="img"
      aria-label={label}
      {...stylex.props(styles.base, style)}
    >
      <polyline
        points={points.join(" ")}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        strokeLinejoin="round"
      />
    </svg>
  );
}
