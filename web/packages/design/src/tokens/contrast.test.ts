import { expect, test } from "vitest";
import { contrast } from "../lib/color-math";
import { colorMeta } from "./generated/meta";

// WCAG AA: 4.5:1 for text. Every ink that is used for text on every surface it can sit on,
// on both faces. If this fails, tune the generator, not the component.
const inks = ["inkPrimary", "inkSecondary", "inkMuted", "accentBase", "accentHover"] as const;
const surfaces = ["surfaceCanvas", "surfaceRaised", "surfaceSunken"] as const;
const tinted = [
  ["accentInk", "accentBase"],
  ["accentHover", "accentSoft"],
  ["positiveBase", "positiveSoft"],
  ["cautionBase", "cautionSoft"],
  ["negativeBase", "negativeSoft"],
  ["infoBase", "infoSoft"],
  ["inkPrimary", "positiveSoft"],
  ["inkPrimary", "cautionSoft"],
  ["inkPrimary", "negativeSoft"],
  ["inkPrimary", "infoSoft"],
  ["inkPrimary", "accentSoft"],
] as const;

for (const face of ["light", "dark"] as const) {
  test(`${face}: text inks reach AA on every surface`, () => {
    const failures: string[] = [];
    for (const ink of inks) {
      for (const surface of surfaces) {
        const ratio = contrast(colorMeta[ink][face], colorMeta[surface][face]);
        if (ratio < 4.5) failures.push(`${ink} on ${surface}: ${ratio.toFixed(2)}`);
      }
    }
    expect(failures).toEqual([]);
  });
  test(`${face}: tinted pairs reach AA`, () => {
    const failures: string[] = [];
    for (const [fg, bg] of tinted) {
      const ratio = contrast(colorMeta[fg][face], colorMeta[bg][face]);
      if (ratio < 4.5) failures.push(`${fg} on ${bg}: ${ratio.toFixed(2)}`);
    }
    expect(failures).toEqual([]);
  });
}
