// A port of bio/dish.py: the agar, the cells, and the physics, running the built-in founder.
// Same rules and constants as the apparatus; a different random generator, so a run here is
// not tick-for-tick the run the Python dish would make from the same seed.

export const physics = {
  basalCost: 0.01,
  moveCost: 0.025,
  eatRate: 0.06,
  divideThreshold: 1.0,
  initialEnergy: 0.6,
  maxEnergy: 2.0,
  maxAge: 600,
  necromass: 0.35,
  corpseNutrient: 0.12,
  agarMean: 0.45,
  agarPatchiness: 0.35,
  diffusion: 0.04,
  replenish: 0.0025,
  pheromoneDecay: 0.06,
  pheromoneDiffusion: 0.1,
  inoculum: 5,
} as const;

// clockwise from north, as in the dish
export const DIRS: readonly [number, number][] = [
  [0, -1],
  [1, -1],
  [1, 0],
  [1, 1],
  [0, 1],
  [-1, 1],
  [-1, 0],
  [-1, -1],
];

export interface Cell {
  x: number;
  y: number;
  energy: number;
  age: number;
}

/** A small seeded generator (mulberry32) keyed by a string, with the draws the dish needs. */
export class Rng {
  private state: number;
  constructor(seed: string) {
    let h = 1779033703 ^ seed.length;
    for (let i = 0; i < seed.length; i++) {
      h = Math.imul(h ^ seed.charCodeAt(i), 3432918353);
      h = (h << 13) | (h >>> 19);
    }
    this.state = h >>> 0;
  }
  random(): number {
    this.state = (this.state + 0x6d2b79f5) >>> 0;
    let t = this.state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }
  uniform(a: number, b: number): number {
    return a + (b - a) * this.random();
  }
  randint(a: number, b: number): number {
    return a + Math.floor(this.random() * (b - a + 1));
  }
  gauss(mu: number, sigma: number): number {
    const u = 1 - this.random();
    const v = this.random();
    return mu + sigma * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }
  shuffle<T>(arr: T[]): void {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(this.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j] as T, arr[i] as T];
    }
  }
}

type Action = ["eat"] | ["rest"] | ["divide"] | ["move", number];

export class Dish {
  readonly w: number;
  readonly h: number;
  readonly mask: boolean[][];
  nutrient: number[][];
  pheromone: number[][];
  cells = new Map<number, Cell>();
  tick = 0;
  births = 0;
  deaths = { starved: 0, senescent: 0 };
  history: number[] = [];
  private rng: Rng;

  constructor(seed: string, w = 72, h = 34) {
    this.w = w;
    this.h = h;
    this.rng = new Rng(`${seed}::dish`);
    this.mask = this.makeMask();
    this.nutrient = this.makeAgar(seed);
    this.pheromone = Array.from({ length: h }, () => new Array<number>(w).fill(0));
  }

  private key(x: number, y: number): number {
    return y * this.w + x;
  }
  private makeMask(): boolean[][] {
    const cx = (this.w - 1) / 2;
    const cy = (this.h - 1) / 2;
    const rx = this.w / 2;
    const ry = this.h / 2;
    return Array.from({ length: this.h }, (_, y) =>
      Array.from({ length: this.w }, (_, x) => ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1),
    );
  }
  private makeAgar(seed: string): number[][] {
    const rng = new Rng(`${seed}::agar`);
    const blobs = Array.from(
      { length: 9 },
      () =>
        [
          rng.uniform(0, this.w),
          rng.uniform(0, this.h),
          rng.uniform(4, 14),
          rng.uniform(0.3, 1),
        ] as const,
    );
    return this.mask.map((row, y) =>
      row.map((inside, x) => {
        if (!inside) return 0;
        let v = physics.agarMean * (1 - physics.agarPatchiness);
        for (const [bx, by, br, bs] of blobs) {
          const d2 = ((x - bx) / 2) ** 2 + (y - by) ** 2; // terminal cells are 2:1
          v += physics.agarPatchiness * bs * Math.exp(-d2 / (br * br));
        }
        v += rng.gauss(0, 0.04);
        return Math.max(0, Math.min(1, v));
      }),
    );
  }

  inside(x: number, y: number): boolean {
    return x >= 0 && x < this.w && y >= 0 && y < this.h && (this.mask[y]?.[x] ?? false);
  }
  get population(): number {
    return this.cells.size;
  }
  nutrientMean(): number {
    let tot = 0;
    let n = 0;
    for (let y = 0; y < this.h; y++) {
      for (let x = 0; x < this.w; x++) {
        if (!this.mask[y]?.[x]) continue;
        tot += this.nutrient[y]?.[x] ?? 0;
        n++;
      }
    }
    return n ? tot / n : 0;
  }

  place(x: number, y: number, energy: number = physics.initialEnergy): Cell | null {
    if (!this.inside(x, y) || this.cells.has(this.key(x, y))) return null;
    const c: Cell = { x, y, energy, age: 0 };
    this.cells.set(this.key(x, y), c);
    return c;
  }
  inoculate(n = physics.inoculum): number {
    const cx = Math.floor(this.w / 2);
    const cy = Math.floor(this.h / 2);
    let placed = 0;
    for (let tries = 0; placed < n && tries < 200; tries++) {
      if (this.place(cx + this.rng.randint(-2, 2), cy + this.rng.randint(-1, 1))) placed++;
    }
    return placed;
  }

  private die(cell: Cell, cause: keyof Dish["deaths"]): void {
    this.cells.delete(this.key(cell.x, cell.y));
    this.deaths[cause]++;
    const back = Math.max(0, cell.energy) * physics.necromass + physics.corpseNutrient;
    const row = this.nutrient[cell.y];
    if (row) row[cell.x] = Math.min(1, (row[cell.x] ?? 0) + back);
  }

  /** The built-in founder: eats where it stands, divides when full, drifts uphill. */
  private founder(cell: Cell): Action {
    const free: number[] = [];
    const around: number[] = [];
    for (let d = 0; d < 8; d++) {
      const [dx, dy] = DIRS[d] as [number, number];
      const x = cell.x + dx;
      const y = cell.y + dy;
      const occupied = !this.inside(x, y) || this.cells.has(this.key(x, y));
      if (!occupied) free.push(d);
      around.push(this.inside(x, y) ? (this.nutrient[y]?.[x] ?? 0) : 0);
    }
    const here = this.nutrient[cell.y]?.[cell.x] ?? 0;
    if (cell.energy > 1.0 && free.length) return ["divide"];
    if (here > 0.04) return ["eat"];
    if (free.length) {
      let best = free[0] as number;
      for (const d of free) if ((around[d] ?? 0) > (around[best] ?? 0)) best = d;
      if ((around[best] ?? 0) > here + 0.02) return ["move", best];
    }
    return ["rest"];
  }

  private apply(cell: Cell, action: Action): void {
    const row = this.nutrient[cell.y];
    if (!row) return;
    switch (action[0]) {
      case "eat": {
        const avail = row[cell.x] ?? 0;
        const take = Math.min(avail, physics.eatRate);
        row[cell.x] = avail - take;
        cell.energy += take;
        break;
      }
      case "move": {
        cell.energy -= physics.moveCost;
        const [dx, dy] = DIRS[action[1]] as [number, number];
        const nx = cell.x + dx;
        const ny = cell.y + dy;
        if (this.inside(nx, ny) && !this.cells.has(this.key(nx, ny))) {
          this.cells.delete(this.key(cell.x, cell.y));
          cell.x = nx;
          cell.y = ny;
          this.cells.set(this.key(nx, ny), cell);
        }
        break;
      }
      case "divide": {
        if (cell.energy < physics.divideThreshold) return;
        const order = [0, 1, 2, 3, 4, 5, 6, 7];
        this.rng.shuffle(order);
        for (const d of order) {
          const [dx, dy] = DIRS[d] as [number, number];
          const nx = cell.x + dx;
          const ny = cell.y + dy;
          if (this.inside(nx, ny) && !this.cells.has(this.key(nx, ny))) {
            cell.energy /= 2;
            this.place(nx, ny, cell.energy);
            this.births++;
            return;
          }
        }
        break;
      }
      case "rest":
        break;
    }
  }

  step(): void {
    const order = [...this.cells.values()];
    this.rng.shuffle(order);
    for (const cell of order) {
      if (this.cells.get(this.key(cell.x, cell.y)) !== cell) continue; // died earlier this tick
      cell.age += 1;
      cell.energy -= physics.basalCost;
      this.apply(cell, this.founder(cell));
      if (cell.energy <= 0) this.die(cell, "starved");
      else if (cell.age > physics.maxAge) this.die(cell, "senescent");
      else if (cell.energy > physics.maxEnergy) cell.energy = physics.maxEnergy;
    }
    this.diffuse();
    this.tick++;
    this.history.push(this.cells.size);
    if (this.history.length > 600) this.history.shift();
  }

  private diffuse(): void {
    const { diffusion: D, pheromoneDiffusion: PD, pheromoneDecay: decay, replenish: rep } = physics;
    const nut = this.nutrient;
    const ph = this.pheromone;
    const newN = nut.map((r) => r.slice());
    const newP = ph.map((r) => r.slice());
    for (let y = 0; y < this.h; y++) {
      for (let x = 0; x < this.w; x++) {
        if (!this.mask[y]?.[x]) continue;
        let sn = 0;
        let sp = 0;
        let k = 0;
        for (const [dx, dy] of [
          [0, -1],
          [1, 0],
          [0, 1],
          [-1, 0],
        ] as const) {
          const xx = x + dx;
          const yy = y + dy;
          if (this.inside(xx, yy)) {
            sn += nut[yy]?.[xx] ?? 0;
            sp += ph[yy]?.[xx] ?? 0;
            k++;
          }
        }
        const rowN = newN[y] as number[];
        const rowP = newP[y] as number[];
        if (k) {
          rowN[x] = (nut[y]?.[x] ?? 0) * (1 - D) + (D * sn) / k;
          rowP[x] = ((ph[y]?.[x] ?? 0) * (1 - PD) + (PD * sp) / k) * (1 - decay);
        }
        if (rep) rowN[x] = Math.min(1, (rowN[x] ?? 0) + rep);
      }
    }
    this.nutrient = newN;
    this.pheromone = newP;
  }

  /** Read the growth curve the way a microbiologist would. */
  phase(): "lag" | "log" | "stationary" | "death" | "sterile" {
    const h = this.history;
    const now = h[h.length - 1];
    if (now === undefined) return "lag";
    if (now === 0) return "sterile";
    if (h.length < 60) return now < 40 ? "lag" : "log";
    const mean = (a: number[]) => a.reduce((s, v) => s + v, 0) / a.length;
    const recent = mean(h.slice(-10));
    const before = mean(h.slice(-60, -50)) || 1;
    const r = (recent - before) / before;
    if (now < 12 && Math.abs(r) < 0.5) return "lag";
    if (r > 0.1) return "log";
    if (r < -0.1) return "death";
    return "stationary";
  }
}
