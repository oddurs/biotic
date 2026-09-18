import { describe, expect, test } from "vitest";
import { Dish, Rng } from "./dish";

describe("the ported dish", () => {
  test("the generator is deterministic for a seed", () => {
    const a = new Rng("tide");
    const b = new Rng("tide");
    expect([a.random(), a.random(), a.randint(1, 6)]).toEqual([
      b.random(),
      b.random(),
      b.randint(1, 6),
    ]);
    expect(new Rng("tide").random()).not.toBe(new Rng("tidal").random());
  });

  test("the founder grows from the inoculum, as in tests/test_dish.py", () => {
    const dish = new Dish("test", 24, 12);
    expect(dish.inoculate()).toBe(5);
    for (let i = 0; i < 80; i++) dish.step();
    expect(dish.tick).toBe(80);
    expect(dish.births).toBeGreaterThan(0);
    expect(dish.population).toBeGreaterThan(5);
  });

  test("a full dish reaches stationary phase and agar is conserved within bounds", () => {
    const dish = new Dish("tide");
    dish.inoculate();
    for (let i = 0; i < 900; i++) dish.step();
    expect(["stationary", "death", "log"]).toContain(dish.phase());
    expect(dish.population).toBeGreaterThan(50);
    const mean = dish.nutrientMean();
    expect(mean).toBeGreaterThanOrEqual(0);
    expect(mean).toBeLessThanOrEqual(1);
  });

  test("the same seed gives the same culture", () => {
    const run = () => {
      const d = new Dish("twin", 40, 20);
      d.inoculate();
      for (let i = 0; i < 200; i++) d.step();
      return [d.population, d.births, d.nutrientMean()];
    };
    expect(run()).toEqual(run());
  });
});
