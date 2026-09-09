import * as stylex from "@stylexjs/stylex";
import { darkTheme, lightTheme } from "../tokens/generated/faces";

export type ThemeChoice = "auto" | "light" | "dark";
export const THEME_STORAGE_KEY = "biotic.theme";
const THEME_EVENT = "biotic:theme";

/** Class names that force a face when applied to <html>. `auto` applies nothing. */
export const themeClass: Record<ThemeChoice, string> = {
  auto: "",
  light: stylex.props(lightTheme).className ?? "",
  dark: stylex.props(darkTheme).className ?? "",
};

/**
 * Inline script for <head>: applies the stored choice before first paint so a forced face
 * never flashes. Kept tiny and dependency-free on purpose.
 */
export const themeBootScript = `(function(){try{var t=localStorage.getItem(${JSON.stringify(THEME_STORAGE_KEY)});var c=${JSON.stringify(themeClass)};if(t&&c[t]){var l=document.documentElement.classList;c[t].split(" ").forEach(function(x){l.add(x)});document.documentElement.dataset.theme=t;}}catch(e){}})();`;

export function applyTheme(choice: ThemeChoice): void {
  const root = document.documentElement;
  // A theme's className may be several classes; DOMTokenList wants them one at a time.
  const tokens = (cls: string) => cls.split(" ").filter(Boolean);
  for (const cls of Object.values(themeClass)) root.classList.remove(...tokens(cls));
  root.classList.add(...tokens(themeClass[choice]));
  root.dataset.theme = choice;
  try {
    if (choice === "auto") localStorage.removeItem(THEME_STORAGE_KEY);
    else localStorage.setItem(THEME_STORAGE_KEY, choice);
  } catch {
    // storage may be unavailable; the choice still applies for this page
  }
  // After storage is written, so subscribers reading the snapshot see the new choice.
  document.dispatchEvent(new CustomEvent(THEME_EVENT));
}

export function readTheme(): ThemeChoice {
  try {
    const t = localStorage.getItem(THEME_STORAGE_KEY);
    if (t === "light" || t === "dark") return t;
  } catch {
    // ignore
  }
  return "auto";
}

/** Subscribe to theme changes from this tab (applyTheme) or another (storage). */
export function subscribeTheme(onChange: () => void): () => void {
  document.addEventListener(THEME_EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    document.removeEventListener(THEME_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}
