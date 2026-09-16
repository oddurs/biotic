# the eyepiece

`biotic live` puts the dish on the terminal and redraws it six times a second.
This note says what each panel shows and how the eyepiece fits a dish onto the
window it is watched from, which is not always the window it was poured on.

## the panels

```
 biotic   seed “tide”   tick 1204   0h10m02s   ♥
╭─ agar ────────────────────────────────╮ ╭─ vitals ───────────────────────────────────╮
│          ·:·∷∷∷:·                     │ │ population 483  25% of agar                │
│       ·:∷●●●●●●∷:·                    │ │            ▁▂▃▅▆▇█████▇▇▇▇                 │
│     ·:∷●●●●●●●●●●●∷:                  │ │      phase stationary                      │
│    ·∷●●●●●●●●●●●●●●●:·                │ │    strains 6  14 arisen  8 extinct         │
│    ∷●●●●●●●●●●●●●●●●●∷                │ │  diversity H 1.24  dominance 61%  gen 2.3  │
│    :●●●●●●●●●●●●●●●●●:                │ │       agar ████████░░░░ 0.41               │
│     ·∷●●●●●●●●●●●●∷·                  │ │    mutagen ◐ thinking  2 ready             │
│        ·:∷∷●●●∷∷:·                    │ ╰────────────────────────────────────────────╯
│           ·:∷:·                       │ ╭─ census ───────────────────────────────────╮
╰───────────────────────────────────────╯ │ ● 3f1a tide_drift 212 ▇▇▇▇▇▇▇▇▇▇▇▇         │
╭─ incubator log ──────────────────────────────────────────────────────────────────────╮
│ 14:02:11   1180 ✚ tide_drift arose from slack_water — “now leans into the scent …    │
╰──────────────────────────────────────────────────────────────────────────────────────╯
```

The sketch is abridged: the vitals panel has more rows than it shows. The
list below is the reference.

- **header**: the seed, the tick, the wall-clock uptime of this sitting, and a
  heartbeat that flips between `♥` and `♡` every two ticks. If it stops, either
  the dish has stopped or the eyepiece could not draw a frame; `biotic log`
  tells the two apart (see the last section). The header is one row whatever
  the width: when the window is too narrow the seed is cut with an ellipsis,
  then dropped, then the uptime, then the tick. The heartbeat is never dropped.
- **agar**: one glyph per tile. Agar shows as ` · : ∷` by richness. A cell is
  `●`, coloured by strain; daughters get a hue near the parent's, and a dim
  cell is a hungry one. Pheromone shows violet. The ellipse is the glass wall.
- **vitals**: population and its share of the agar, the growth curve as a
  sparkline, the phase (read from the curve the way a microbiologist would),
  strains living, arisen and extinct, diversity, mean agar richness, births
  and deaths by cause, what the mutagen is doing, the mind's call count, and
  what it has spent against the dish's budget.
- **census**: living strains by population, largest first, with each strain's
  colour, id, count and a bar against the largest; nine at most, then
  `… n more`. In a small window it lists as many as fit in the rows the vitals
  leave beside the agar, and its last line counts the rest. `biotic strains`
  prints all of them with the mutagen's note.
- **incubator log**: the last events: strains arising and going extinct,
  nonviable mutations, drops, whispers, phase changes. `biotic log` has more.
- **footer**: the interventions you can make from another shell, and how to
  leave. One row: a narrow window drops the commands from the left, and
  `ctrl-c to incubate` is the last thing to go.

## fitting the window

A dish is sized once, at `biotic seed`, to the terminal it was poured on:
between 40×18 and 96×44 tiles, whatever is left after 52 columns for the side
panel and 15 rows for the header, the log and the footer. `BIOTIC_WIDTH` and
`BIOTIC_HEIGHT` override this. A 150×50 terminal pours 96×35; anything of 92
columns or 33 rows or fewer pours the minimum 40×18. The dish never changes
size after that. The eyepiece does.

On every frame the eyepiece reads the terminal size and decides the layout
again, in this order of priority:

1. **The agar, at the highest resolution that fits** between the header and
   the footer. Full resolution first. If that does not fit, half: each 2×2
   block of tiles becomes one glyph. Then a third, then a quarter. The agar
   panel's title carries the resolution as a badge, `½`, `⅓` or `¼`; at full
   resolution there is none.
2. **The side panel**, kept when at least 36 columns remain beside the agar
   and the vitals panel fits above the footer with at least one census row
   under it. Otherwise the vitals fold into one line above the log, most
   important first: population, share of agar, phase, agar richness, the
   mutagen's state, ready daughters, strains living and arisen, H, and the
   dominant strain with its count. A narrow window cuts the tail of that
   line. The census is then `biotic strains`.
3. **The log**, with the rows that remain under the taller of the agar and
   the side panel: nine when there is room, down to three (one line inside
   the border), and dropped below that.
4. **The census**, with the rows beside the agar that the vitals leave. It
   lists as many strains as fit, nine at most, and when it cannot list them
   all its last line is `… n more`, so the panel always closes on screen and
   nothing is cut off silently. The vitals panel is measured as it will be
   drawn, because its rows wrap in a narrow side column.
5. When not even a quarter fits, one line: `biotic · 24×10 is too small an
   eyepiece for a 96×35 dish`.

The agar is the observation; everything else is also in `biotic status`,
`biotic strains` and `biotic log`. That is why the log goes before the side
panel and the side panel before a step of agar resolution, and why the
minimum 40×18 dish on a classic 80×24 terminal is shown whole with its side
panel and no log, rather than as a thumbnail with one.

For a 96×35 dish:

| window | agar | side panel | log |
| --- | --- | --- | --- |
| 150×50 | full | yes | 9 rows |
| 100×30 | ½ | yes | 8 rows |
| 80×24 | ½ | strip | none |
| 60×20 | ⅓ | strip | 3 rows |
| 30×14 | ¼ | strip | none |
| 24×10 | too small | | |

For the minimum 40×18 dish, 80×24 shows the whole agar with the side panel
and no log; 60×40 shows it with the strip and a full log. A dish is watched
at full resolution with today's layout on the terminal that poured it.

At 80×24 the side panel is as narrow as one is ever drawn, 36 columns, and
it degrades: the vitals rows wrap, the sparkline loses its right end, and
the census has one row, which is `… n more` as soon as a second strain
lives. Nothing is cut off, but `biotic status` and `biotic strains` are the
better view of the vitals and the census from a window that small.

## reduced resolution

At `½`, `⅓` or `¼` a glyph stands for a block of tiles, and the block is
summarised rather than sampled:

- A block with cells shows its **dominant strain**, the one with the most
  cells in the block; ties go to the smaller strain id, so a given state
  always draws the same frame. `▪` means the block holds exactly one cell,
  `●` two or more. The colour is the dominant strain's, at the mean energy of
  its cells in the block, so a hungry region is still dim.
- Minority strains inside a block are not drawn. A mutant arising inside a
  dominant colony is invisible at `½` until it holds a block of its own, and
  a strain that lives scattered among another can vanish from the reduced
  view while it is alive in the census. The vitals' strain count and
  `biotic strains` are the record; watch from a window that fits the dish
  when the moment matters.
- A block with no cells shows the mean richness of its tiles, and turns violet
  when their mean pheromone is above the visible threshold.
- Tiles outside the glass wall do not count toward a block; a block entirely
  outside it is blank.

## resizing

Resizing mid-run re-fits on the next frame. There is no handler for the
resize signal: the render thread reads the terminal size before each frame,
and the alternate screen is repainted whole from the top-left on every frame,
so a new size is on screen within a sixth of a second of the resize. In the
instant between, the terminal reflows the previous frame itself; that is the
flicker you may see. Nothing else paints: the eyepiece runs rich's `Live`
without its own refresh thread, which would otherwise redraw the previous
frame at the new size until the next one arrived.

The culture runs on the main thread and already uses `SIGALRM` for the
membrane's per-call budget; a `SIGWINCH` handler could only live there too,
and is not needed.

If `COLUMNS` and `LINES` are exported in the environment, rich takes them as
the terminal size and the eyepiece does not follow the window. Unset them to
watch a dish from a window you mean to resize.

## when a frame cannot be drawn

A frame that raises is dropped: the previous frame stays on screen and the
dish runs on. The first failure in a sitting is written to the incubator log
as an `eyepiece` event (`!`), with the exception and the function, file and
line it was raised in; later failures are not repeated. So a heartbeat that
has stopped with an `eyepiece` line in `biotic log` is an eyepiece bug worth
reporting, and one without is a dish that has stopped.

## in code

    from bio.tui import build, fit, plan, render_dish
    fit(96, 35, 100, 30)        # Fit(scale=2, side=True, log_h=8, census_rows=5, view_w=48, view_h=18)
    plan(culture, culture.snapshot(), (100, 30))   # the same, with this culture's vitals panel measured
    build(culture, (100, 30))   # a rich Layout, or a Text when nothing fits
    render_dish(culture, 2)     # the agar at half resolution: 18 lines of 48 glyphs

`fit` is a function of four integers and the vitals panel's height, which
defaults to the 13 rows it has with a dormant mind and nothing wrapped; `plan`
measures the real one, `spent` row, error line and wrapping included. `build` is a function of the culture's state and the size, taken under
the culture's lock. Nothing in the eyepiece writes to the dish or to
`vessel/`, apart from that one `eyepiece` log line.
