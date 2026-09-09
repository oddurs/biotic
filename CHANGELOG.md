# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). `scripts/release`
turns the `Unreleased` section into a dated release.

## [Unreleased]

### Added

- The project site at https://oddurs.github.io/biotic/: a StyleX design system, docs with search and a generated CLI reference, the specimen library, field notes with RSS, and Open Graph images. Lives in `web/` and is checked by the same `scripts/task check`.

### Added

- Diversity and turnover in the growth curve: `vessel/curve.csv` gains `killed`, `shannon`, `dominance`,
  `mean_gen`, `arisen`, `extinct`, `pheromone`, `mutations_ready` and `mutations_taken`, sampled every
  10 ticks like the rest. `Dish.metrics()`, `Culture.metrics()` and `bio.curve.read()` expose them; the
  vitals panel and `biotic status` show diversity next to the strain count, and `biotic run` prints H in
  its progress line. See `docs/curve.md`.
- A test suite for the membrane, `parse_action`, the physics and persistence (`scripts/task test`): one genome
  per escape class, ten fossils from a real run as the positive control, growth phases and carrying capacity
  under the built-in founder, determinism under a seed, and an exact resume from `dish.json`. Tests never touch
  the network or the real `vessel/`.
- `docs/membrane.md`: every rule with its reason string, what a burst is and why a genome cannot catch it, and
  the membrane's known limits.

### Changed

- A `curve.csv` written before this release is widened in place the first time the culture appends to
  it: older rows keep their values and have empty cells in the new columns. Logged once as a `curve` event
  (`≡` in the incubator log). A file re-saved by a spreadsheet, with a byte-order mark, is recognised.
- A `curve.csv` the culture cannot read or write no longer stops the dish: the failure is logged once as a
  `curve` event, every later row is tried again, and a `resumed` event says when writing works.
- The vitals `strains` row reads `living  arisen  extinct`; the maximum generation it used to show is
  replaced by the cell-weighted mean generation on the new `diversity` row.
- The membrane rejects attributes beginning with `_` (`random._os`), `.format`, `.format_map` and `.mro`,
  `finally`, `except*`, bare `except:`, and `except` clauses that name anything but the six built-in exceptions
  a genome can see. Inside a genome, `random` is the dish's own seeded generator rather than the module, so a
  culture is deterministic under its seed and `random.Random`/`random.SystemRandom` no longer exist there.
- A genome can no longer catch or outlive its time budget: `Lysis` is a `BaseException`, and with no `finally`,
  no bare `except` and no `except` outside that list, nothing in a genome runs after it is raised. The smoke
  test also budgets module-level code.
- A genome longer than `GENOME_MAX_CHARS` is rejected before it is parsed.
- The mutagen's prompt states the rules the membrane enforces.

### Fixed

- An empty `curve.csv`, or one holding only blank lines, is given its header with the next row instead
  of being appended to without one.
- `dish.json` no longer rounds cell energy, so a resumed dish follows exactly the trajectory the running one
  would have.
- `parse_action` returns `None` instead of raising on `nan`, `inf` and other values it cannot coerce, and no
  longer turns `("emit", nan)` into a full emission.

## [0.1.0] - 2026-09-09

### Added

- The dish: an elliptical agar grid with nutrient diffusion, pheromone, energetics, senescence, and lysis.
- Genomes as `live(me)` functions, gated by the membrane (static AST rules, a wall-clock budget, a smoke test).
- The mutagen: a background thread that asks any OpenAI-compatible model for daughter genomes on division.
- The eyepiece: a live terminal view of the culture, its vitals, census, and incubator log.
- `biotic seed | live | run | status | strains | genome | log | whisper | drop | minds | probe | sterilize`.
- The fossil record: every strain that ever arose is written to `soma/`.

[Unreleased]: https://github.com/oddurs/biotic/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/oddurs/biotic/releases/tag/v0.1.0
