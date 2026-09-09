import * as stylex from "@stylexjs/stylex";
import { useSyncExternalStore } from "react";
import { applyTheme, readTheme, subscribeTheme, type ThemeChoice } from "../themes";
import { color } from "../tokens/generated/color.stylex";
import { duration, easing } from "../tokens/motion.stylex";
import { border, radius, shadow } from "../tokens/shape.stylex";
import { space } from "../tokens/space.stylex";
import { Icon } from "./Icon";
import { VisuallyHidden } from "./VisuallyHidden";

const order: ThemeChoice[] = ["auto", "light", "dark"];
const serverChoice = (): ThemeChoice => "auto";
const labels: Record<ThemeChoice, string> = {
  auto: "System theme",
  dark: "Dark theme",
  light: "Light theme",
};

const styles = stylex.create({
  button: {
    padding: space.xs,
    borderColor: "transparent",
    borderRadius: radius.full,
    borderStyle: "solid",
    borderWidth: border.hairline,
    outline: "none",
    alignItems: "center",
    backgroundColor: { default: "transparent", ":hover": color.surfaceSunken },
    boxShadow: { default: "none", ":focus-visible": shadow.focus },
    color: color.inkSecondary,
    cursor: "pointer",
    display: "inline-flex",
    fontSize: "1.1rem",
    justifyContent: "center",
    transitionDuration: duration.fast,
    transitionProperty: "background-color, color",
    transitionTimingFunction: easing.standard,
  },
});

/** Cycles system, light, dark. Hydrate as an island; renders the stored choice after mount. */
export function ThemeToggle() {
  // Server renders "auto"; the client reads the stored choice after hydration without a flash
  // because the boot script already applied it to <html>.
  const choice = useSyncExternalStore(subscribeTheme, readTheme, serverChoice);
  const next = order[(order.indexOf(choice) + 1) % order.length] ?? "auto";
  return (
    <button
      type="button"
      onClick={() => applyTheme(next)}
      title={labels[choice]}
      aria-label={`${labels[choice]}. Switch to ${labels[next].toLowerCase()}`}
      {...stylex.props(styles.button)}
    >
      <Icon name={choice === "dark" ? "moon" : "sun"} />
      <VisuallyHidden>{labels[choice]}</VisuallyHidden>
    </button>
  );
}
