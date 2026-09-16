---
id: 9
title: Survive small and resized terminals
type: feature
status: done
milestone: dish
assignee: Oddur Sigurdsson
created: 2026-09-08
updated: 2026-09-16
priority: p2
effort: s
area: bio/tui.py
---

## Problem

The dish is sized to the terminal at seed time. Watch it later from a smaller
window and the layout clips silently; resize mid-run and the frame tears.

## Proposal

- On each frame, compare `console.size` to what the layout needs. If the dish
  does not fit, render it at half resolution: 2×2 tiles → one glyph, coloured by
  the dominant strain in the block, `▪` when only one cell, `●` when ≥2. Show a
  `½` badge in the agar panel title.
- Below ~80 columns, drop the side panel and put a one-line vitals strip above
  the log instead.
- Handle `SIGWINCH` by letting `rich.Live` re-measure (it does) and by
  recomputing the layout in `build()` every frame — already the case; verify.

## Acceptance criteria

- [x] A dish seeded at 150×50 is watchable at 100×30 with the ½ badge
- [x] Resizing during `biotic live` never raises and settles within one frame

## 2026-09-09

From the 0003 review: the events deque is appended by the main and mutagen threads and iterated by the renderer with no lock; the renderer swallows the RuntimeError, so a frame is dropped now and then. Pre-existing; the eyepiece work here is the place to own it.

## 2026-09-16

Branch fix/tui-resize-fit: the requested name fix/tui-resize was already a branch with a worktree. Two earlier, unpushed attempts at this item exist and are superseded by this branch; both can be deleted after it merges: fix/tui-resize (worktree /Users/oddurs/Code/.worktrees/biotic/fix/tui-resize, commit 20260d9, 8 merges behind main, uncommitted edits) and feat/tui-fit-terminal (worktree /Users/oddurs/Code/.worktrees/biotic/feat/tui-fit-terminal, commit 873b179, 4 merges behind main, an uncommitted census-rows expansion). This branch is feat/tui-fit-terminal's committed design rebuilt on today's main (main changed nothing in bio/tui.py since its base), plus the events-deque copy from its uncommitted follow-up; the census-rows / measured-vitals-height expansion in that follow-up was left out as out of scope (a compact vitals panel is its own item).

## 2026-09-16

Regression check before changing anything, against main's build() (no size argument), painted through Screen: a 96x35 dish at 100x30 shows 19 of the agar panel's 37 rows and no census; at 80x24, 13 rows, the right border in the wrong column and no census; a 40x18 dish at 80x24 shows 13 of 20 rows and no census, and at 60x40 no census. 150x50 and 94x33, the terminals that pour those dishes, pass. The same check is tests/test_tui.py::assert_unclipped, run by the frame tests at nine sizes; it now passes everywhere fit() returns a Fit.

## 2026-09-16

No SIGWINCH handler: a handler can only be installed on the main thread, which runs the dish and already owns SIGALRM through membrane.Budget (membrane.py:171-192). None is needed. rich 15.0.0: Console.size re-reads os.get_terminal_size() on every access (console.py:1005-1028; COLUMNS/LINES win when exported, documented in docs/eyepiece.md, not handled); Live(screen=True) wraps each paint in Screen, which set_shapes to the current width x height (live.py:228, screen.py:49); the render hook prepends Control.home() (live.py:287). frame() reads console.size outside c.lock and builds under it, so the lock is held for build() only and painting happens after release.

## 2026-09-16

auto_refresh=False: rich's _RefreshThread (live.py:22-38) repaints the LAST renderable at its own 6 Hz, so after a resize it reflowed the old Layout into the new Screen until our thread replaced it: the tearing in the problem statement, and settling could take two periods. Now redraw() is the only painter, via live.update(frame, refresh=True). Live.__enter__ still paints the initial renderable (start(refresh=True), live.py:111-141) and stop() in alt-screen mode does not repaint (live.py:161-167). tests/test_tui.py::test_observe_is_the_only_painter pins auto_refresh=False and screen=True on the console given.

## 2026-09-16

Priority when the window is small: the agar first, at the smallest scale 1..4 whose panel fits between header and footer; then the side panel, kept when SIDE_MIN=36 columns remain beside the agar, else a one-row vitals strip; then the log with the rows left over (LOG_H=9 at most, LOG_MIN=3, dropped below that); then the one-line notice. Decided by the minimum 40x18 dish on the classic 80x24 terminal: with a reserved log it became a 20x9 thumbnail with a 9-row log; under this rule it is full resolution, side panel, no log. A judgment call the owner may reverse, e.g. keeping a log line over a step of agar resolution at 80x24 for the default 72x34 dish (today: half resolution, side panel, 3-row log); it is one loop in fit(). Known weakness: at exactly SIDE_MIN main's vitals rows wrap to about 17 lines and the census sits low in the body; every vitals row 0002/0040 add makes that worse, and a compact vitals panel should be its own item if it bites.

## 2026-09-16

Block colour rule at scale k (_render_blocks): only masked tiles count; a block with no masked tile is blank. Dominant strain = most cells in the block, ties to the smaller strain id so the frame is a function of the state. Glyph: a single square for exactly one cell, the round cell glyph for two or more. Colour: reg.color(top, mean energy of the top strain's cells in the block), so a hungry region stays dim. An empty block shows _agar_glyph(mean nutrient, mean pheromone) over its masked tiles. Minority strains in a block are not drawn (documented, with the advice to watch from a fitting window when the moment matters). No randomness anywhere in the renderer: twins with the same seed and tick count render identical plain and spans at scale 2 and 3 (test and a scratch check on 96x35).

## 2026-09-16

The vitals strip shows the mutagen's state as a word without its glyph (thinking / idle / dormant / error): between the strip's dot separators the dormant glyph read as a run of three dots, and a dish without a key, which is the quickstart, is dormant. The vitals panel keeps the glyphs. Otherwise the strip is main's vitals in order of importance, most important first because a narrow window cuts the tail: pop, share of agar, phase, agar, mutagen state (and x6 when boosted), ready, living, arisen, H, top strain with its count. The mind's error text is not in the strip; the log carries it. Order and the ellipsis are tested.

## 2026-09-16

The events deque (note of 2026-09-09 from the 0003 review): events() now copies it with list(c.events) before filtering. Culture.log() appends from the main thread (step) and from the mutagen thread without c.lock, and a Python-level iteration that one of them interrupts raises RuntimeError: deque mutated during iteration; list() of a deque runs in C without a thread switch under the GIL. Measured with sys.setswitchinterval(1e-6) and a thread appending in a loop: main's events() raised on 1156-1264 of 1500 calls in three runs; the new one never does (tests/test_tui.py::test_log_panel_survives_appends_from_other_threads, 1500 calls under the same stress, about 0.1 s). Not a guarantee on a free-threaded build, which this project does not target.

## 2026-09-16

A frame that raises is still dropped and the dish runs on, but the first failure in a sitting is written to the incubator log as an eyepiece event (icon !) with the exception and the function, file and line it was raised in (redraw -> _report, best effort). Later failures are not repeated. So a frozen heartbeat with an eyepiece line in biotic log is an eyepiece bug; one without is a stopped dish. test_a_failed_frame_is_logged_once_and_the_loop_lives_on also checks that c.lock is released after a failure inside build().

## 2026-09-16

Baselines on this machine (Python 3.13.15, rich 15.0.0, n=200 per figure, means): 96x35 dish at population 105 (60 ticks): render_dish k=1 2.20 ms, k=2 1.13, k=3 0.68, k=4 0.52; build 150x50 2.67 ms, 100x30 1.55, 80x24 1.48, 60x20 1.02; a full frame through Screen 12.6 ms at 150x50, 5.35 at 100x30. Population 866 (400 ticks): render k=1 2.66, k=2 1.34, k=3 0.77, k=4 0.55; build 150x50 3.20, 100x30 1.80; full frame 13.6 / 6.1 ms. c.lock is held for build() only, so lock hold time falls at reduced scale and never rises.

## 2026-09-16

No change at the terminal that poured the dish: frames painted through Screen with main's build() and this branch's build(c, size) are byte-identical, ANSI included, at 150x50 for a 96x35 dish, 94x33 for 40x18 and 126x49 for 72x34, at 60 and 400 ticks. The one adjustment this needed: the agar title is Text.assemble((agar, dim)), a span like the [dim]agar[/] markup produced; a Text with a base style would also dim the title's padding and change the bytes.

## 2026-09-16

What pytest cannot do here: open a tty or construct rich.Live. What it pins instead: fit() worked values and a 3x16x12 sweep with a minimal-scale proof; frames through Screen at nine sizes with the unclipped check and the badge; frame(c, console) refitting when console.size changes; redraw() under a fake Live that resizes the console between frames, so every frame after a size change is already the new layout (criterion 2 by construction, and a refactor that moved the size read or turned auto_refresh back on fails it); the strip's order and ellipsis; the log panel under concurrent appends; a failing build() logged once with the loop alive. Tests set CELL_TIME_BUDGET=60 for the module (dish.py reads it at call time) so a scheduler stall cannot lyse a cell in one seeded twin and not the other; conftest.py is untouched. The file runs in about 2.4 s.

## 2026-09-16

Manual verification in a pty (pty.fork, TIOCSWINSZ + SIGWINCH, observe() on a fresh 96x35 culture in a scratch vessel with no key; script kept outside the repo). Plan 150x50 -> 100x30 -> 80x24 -> 60x20 -> 20x8 -> 150x50, 1.5 s each, frames timed by arrival of the home sequence. Tick 0.05 s: the first frame with the new layout came 42, 160, 91, 175 and 82 ms after the resize, within one 167 ms period plus a few ms; no complete frame of the old layout at any size except one at 20x8 that was built in the instant of the resize; every frame at a size had exactly rows lines (30, 24, 20, 8, 50); the heartbeat flipped at every size that has a header; ticks advanced; mean frame interval 173-193 ms. Tick 0.5 s: 156, 94, 31, 132 and 52 ms, no stale frames. Both runs: exit status 0 on ctrl-c with the incubating line, no traceback. The 80x24 frame reads as designed: agar at half with the badge, the strip cut with an ellipsis at column 80, the footer, no log.

## 2026-09-16

Consolidation of the three attempts, after the review: fix/tui-resize-fit stays the branch (the review ran against it and it is the merge target). The only work not already here was feat/tui-fit-terminal's uncommitted census-rows / measured-vitals follow-up; it is carried over in a simplified form (next note) and that worktree and branch are removed. fix/tui-resize's uncommitted edits were older than everything here (no metrics rows, no deque copy, no _report) and its worktree is removed; the branch name is kept pointing at this branch's tip until one of the two merges, because the task named both as the merge target. Not carried over from the follow-up: a per-(exception, file, line) dedupe of the eyepiece log line. The doc and the test say the first failure in a sitting is logged; one rule is simpler and a second kind of failure in one sitting is rare.

## 2026-09-16

Review finding: fit() ignored the side panel's height, so from 6 living strains at 100x30 the census panel ran off the bottom without a border and its `… n more` line was never visible; at 80x24 for the minimum dish the wrapped vitals pushed it further. Now build() measures the vitals panel as it will be drawn (tui.height: an off-screen Console.render_lines at the side column's width; about 0.9 ms per frame, only when a side column is a candidate, 3.5 ms per build at 150x50 against 2.7 before), fit() takes that height and gives the census the rows the vitals leave beside the agar (Fit.census_rows), census_table(avail) lists what fits and ends with `… n more`, and when not even one census row is left the side panel folds into the strip at the same scale. The log is unchanged: it takes the spare rows under the taller of the agar and the side panel, so the documented table holds and the layout does not shift when a strain arises or dies. Measured: 100x30 with 13 living, 4 strains and `… 9 more` with the log at 8 rows; 80x24 for 40x18, the vitals wrap to 19 rows and the census is one row, `… n more` from two living on; a mind error there folds the side panel into the strip. The census panel keeps its natural height (a Panel inside a Group does not stretch to the region), as on main. Frames at 150x50, 94x33 and 126x49 are byte-identical to before this change except the 94x33 footer, which used to be cropped mid-word.

## 2026-09-16

Header and footer are one row each (Text no_wrap, overflow ellipsis), so the 1-row regions never crop a wrapped second line. The header drops, in this order, the seed (cut with an ellipsis to the cells left, dropped below four), the uptime, the tick; the heartbeat is never dropped, because it is what tells a stopped dish from a frozen eyepiece. The footer drops commands from the left; `ctrl-c to incubate (state is saved)` is the last to go. Display order and styling are unchanged, so both rows at the pouring terminal are byte-identical to before. Tests sweep 14 to 159 columns for both (14 is the narrowest agar panel fit() ever draws).

## 2026-09-16

Tests after the review. assert_unclipped checks the heartbeat on row 0, ctrl-c on the last row, the log panel's bottom border, the frame's row count, and in side mode that the vitals and census panels close at the side column (x = panel_w), the census with at most Fit.census_rows rows and exactly its strains' rows when the test knows how many live. A strains() helper places extra strains by hand with the longest names a strain can have. The Lens harness has a bounded stop event (Bounded sets itself after 200 waits) and asserts nothing inside update(), since redraw() swallows every exception a frame raises, AssertionError included; test_a_frame_that_always_fails_is_logged_once_and_the_harness_does_not_hang pins both. test_console_size_follows_the_tty_when_no_size_is_given patches os.get_terminal_size and builds Console() with no width or height, as observe() does, so a rich release that cached Console.size, or a Console(width=...) in observe(), would fail the suite rather than break resizing silently. The file runs in about 3.5 s.

## 2026-09-16

Left as documented, not fixed: at a 36 to 40 column side panel the vitals rows wrap and the sparkline loses its right end, the newest samples. docs/eyepiece.md says so under the 80x24 paragraph and points at biotic status and biotic strains. The compact-vitals item, when it comes, should let the sparkline and the agar bar take the column's width and keep every row on one line; with that, fit() could go back to a constant vitals height.
