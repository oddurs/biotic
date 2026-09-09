import { expect, test } from "vitest";
import { strainColor } from "./strain-color";

test("matches the Python implementation for known inputs", () => {
  // Registry.color(hue=0.0, energy=1.0): light = 0.38 + 0.28 * (1/1.2)
  expect(strainColor(0, 1)).toBe("#e35555");
  expect(strainColor(0.5, 0)).toBe("#1ba6a6");
  expect(strainColor(0.25, 2)).toBe("#a8e669");
});

test("clamps energy into range", () => {
  expect(strainColor(0.1, 99)).toBe(strainColor(0.1, 1.2));
  expect(strainColor(0.1, -5)).toBe(strainColor(0.1, 0));
});
