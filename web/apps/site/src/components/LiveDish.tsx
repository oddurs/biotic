import * as stylex from "@stylexjs/stylex";
import { Button, strainColor, Text } from "@biotic/design";
import { color } from "@biotic/design/tokens/color.stylex";
import { palette } from "@biotic/design/tokens/palette.stylex";
import { radius } from "@biotic/design/tokens/shape.stylex";
import { space } from "@biotic/design/tokens/space.stylex";
import { font } from "@biotic/design/tokens/type.stylex";
import { useEffect, useRef, useState } from "react";
import { Dish } from "../lib/dish";

const W = 72;
const H = 34;
const CELL = 8; // canvas pixels per tile; the canvas scales to its box
const TICK_MS = 120;
const seeds = ["tide", "moss", "brine", "ember", "quiet", "drift", "salt", "loam"];

const styles = stylex.create({
  frame: {
    padding: space.md,
    borderRadius: radius.xl,
    overflow: "hidden",
    backgroundColor: color.surfaceInverse,
    color: color.inkInverse,
  },
  canvas: { aspectRatio: `${W} / ${H * 2}`, display: "block", height: "auto", width: "100%" },
  bar: {
    gap: space.sm,
    alignItems: "center",
    display: "flex",
    flexWrap: "wrap",
    justifyContent: "space-between",
    marginTop: space.sm,
  },
  vitals: { color: color.inkInverse, fontFamily: font.mono, fontSize: "0.8rem", opacity: 0.85 },
  seed: { fontStyle: "italic" },
  // The frame is the inverse surface, so the button takes the inverse ink explicitly.
  reseed: { color: { default: color.inkInverse, ":hover": color.inkInverse } },
});

/** Reads a StyleX variable's current value off an element, so the canvas paints with tokens. */
function tokenValue(el: Element, ref: string): string {
  const name = /var\((--[^)]+)\)/.exec(ref)?.[1];
  return name ? getComputedStyle(el).getPropertyValue(name).trim() || "#000" : ref;
}

/** The dish, alive, in the browser: the same physics as the apparatus running the built-in founder. */
export function LiveDish() {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [seed, setSeed] = useState(seeds[0] ?? "tide");
  const [vitals, setVitals] = useState({ tick: 0, population: 0, phase: "lag" });

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const ctx = el.getContext("2d");
    if (!ctx) return;
    const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const glass = tokenValue(el, palette.glass900);
    const agar = [palette.agar900, palette.agar800, palette.agar700, palette.agar600].map((v) =>
      tokenValue(el, v),
    );
    const violet = tokenValue(el, palette.pheromone700);
    const dish = new Dish(seed, W, H);
    dish.inoculate();

    const paint = () => {
      ctx.fillStyle = glass;
      ctx.fillRect(0, 0, W * CELL, H * CELL * 2);
      for (let y = 0; y < H; y++) {
        for (let x = 0; x < W; x++) {
          if (!dish.mask[y]?.[x]) continue;
          const n = dish.nutrient[y]?.[x] ?? 0;
          const p = dish.pheromone[y]?.[x] ?? 0;
          ctx.fillStyle = p > 0.12 ? violet : (agar[Math.min(3, Math.floor(n * 4.5))] ?? glass);
          ctx.globalAlpha = p > 0.12 ? 0.6 : 0.25 + n * 0.75;
          ctx.fillRect(x * CELL, y * CELL * 2, CELL, CELL * 2);
        }
      }
      ctx.globalAlpha = 1;
      for (const c of dish.cells.values()) {
        ctx.fillStyle = strainColor(0.33, c.energy);
        ctx.beginPath();
        ctx.arc(c.x * CELL + CELL / 2, c.y * CELL * 2 + CELL, CELL * 0.42, 0, Math.PI * 2);
        ctx.fill();
      }
      setVitals({ tick: dish.tick, population: dish.population, phase: dish.phase() });
    };

    if (reduceMotion) {
      // One still frame of a culture that has settled, instead of animation.
      for (let i = 0; i < 400; i++) dish.step();
      paint();
      return;
    }
    let raf = 0;
    let last = 0;
    const loop = (t: number) => {
      if (t - last >= TICK_MS) {
        dish.step();
        paint();
        last = t;
      }
      raf = requestAnimationFrame(loop);
    };
    paint();
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [seed]);

  return (
    <figure {...stylex.props(styles.frame)}>
      <canvas ref={canvas} width={W * CELL} height={H * CELL * 2} {...stylex.props(styles.canvas)}>
        A living culture seeded with “{seed}”: {vitals.population} cells at tick {vitals.tick},{" "}
        {vitals.phase} phase.
      </canvas>
      <figcaption {...stylex.props(styles.bar)}>
        <Text as="span" style={styles.vitals}>
          seed <span {...stylex.props(styles.seed)}>“{seed}”</span> · tick {vitals.tick} ·{" "}
          {vitals.population} cells · {vitals.phase}
        </Text>
        <Button
          variant="ghost"
          size="sm"
          style={styles.reseed}
          onClick={() => setSeed(seeds[(seeds.indexOf(seed) + 1) % seeds.length] ?? "tide")}
          aria-label="Reseed the dish"
        >
          Reseed
        </Button>
      </figcaption>
    </figure>
  );
}
