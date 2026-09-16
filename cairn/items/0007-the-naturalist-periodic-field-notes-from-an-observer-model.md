---
id: 7
title: 'The naturalist: periodic field notes from an observer model'
type: feature
status: done
milestone: dish
assignee: Oddur Sigurdsson
depends_on:
- 3
created: 2026-09-08
updated: 2026-09-16
priority: p1
effort: m
area: bio/prompts.py, bio/culture.py, bio/tui.py
---

## Problem

The incubator log is a list of events; nobody reads 4,000 lines of "arose" and
"extinct". What a human wants is what a microbiologist writes in the lab book:
what changed since the last look, what it might mean, hedged. This is the one
output of a long run a person will actually read, and it is what makes the
dish feel observed rather than logged. (Sakana's ASAL is the precedent for a
foundation model as the observer of an artificial-life system.)

## Proposal

- Every `BIOTIC_NOTES_EVERY` ticks (default 600, ≈ 5 min at 0.5s) the culture
  builds an *observation packet*: tick, phase, population and diversity deltas
  since the last note, census with names and one-line notes, births/deaths by
  cause, the last 20 events, a low-resolution text rendering of the dish, and
  the previous field note (so notes read as a continuing record).
- One call to the mind with a `NATURALIST_SYSTEM` prompt: write 3–8 sentences
  in the voice of a lab notebook. Report what is observable; when interpreting,
  say so ("this resembles…"). Never invent mechanisms. Never give advice.
- Appended to `vessel/fieldnotes.md` under a `## tick N · HH:MM` heading, and
  logged as a `note` event. `biotic notes [-n]` prints them. The TUI shows the
  latest note's first line in the footer area instead of the static help text
  when a note exists.
- Counts against the budget like any call. Off when `BIOTIC_NOTES_EVERY=0`.

## Acceptance criteria

- [x] Notes appear at the cadence; each references the previous by content
- [x] A sweep (one strain going from <10% to >70%) is remarked on in the next note
- [x] `biotic notes` prints the notebook; the TUI shows the latest line
- [x] Prompt text in `bio/prompts.py`; no instructions to the culture leak into it

## 2026-09-16

Thread and one slot: Naturalist is a daemon thread shaped like Mutagen (run/_turn/_cycle, 2 s wake, every fault logged, never fatal). The main thread builds the packet in Culture._packet (copies only: names, ids, generations, counts, shares, the mutagen's per-strain note, NOTE_EVENTS from the deque, a sketch) and hands it to observe(), which replaces any unwritten packet (dropped += 1) and never waits. The thread never reads dish/registry/events and never takes culture.lock; the only nesting is culture.lock -> naturalist.lock from state_dict() and snapshot().

## 2026-09-16

Wall-clock floor: NOTES_MIN_SECONDS = 120 s (bio/config.py, a constant, not an env knob) gates due() on the time of the last look (observe), not the last write. At the default cadence and tick (300 s per note) it never binds; at --tick 0 the cadence alone would be one call per reply and spend the dish budget on notes in hours; the floor caps a headless run at 30 notes/hour. Headless experiments set BIOTIC_NOTES_EVERY=0. If the owner disagrees it is one line.

## 2026-09-16

Baseline on the event: the last note written plus tick/at/text/branch/metrics/census is kept in memory, saved under culture.naturalist in dish.json (so in dish samples too) and put whole on every note event. load() reconciles from the last note event in the 64 KiB log tail when its observation time is later than the saved one — same mechanism as the ledger. Tail only: a note the save missed is within 150 ticks of the end, and a dish with no notes must not read a week's log. The event's tick and at are the observation's (the dish is further on when the reply comes back at --tick 0); at is a distinct key because log() lets data override t.

## 2026-09-16

Seam: revive() keeps the vessel's baseline (state['naturalist'] = baseline(), like state['branch']) and _swap calls naturalist.reset(): the pending packet is dropped and seam=True is set and saved. The next entry is composed with no deltas and no share comparison and its prompt says the dish was replaced with a frozen sample since the last entry; the previous entry is still shown so the record continues; writing that entry clears the seam. A dish sample carries the baseline it had at the freeze and a revive ignores it (one sentence in docs/freezer.md).

## 2026-09-16

Sweep is computed, not left to the model: remarks() flags a strain whose share at the last entry was < 10 % (absent counts as 0) and is > 70 % now, and the prompt lists it under 'Changes worth noting'. A sweep spread over more than one interval is not flagged; the census block still shows share now -> share then for every strain. 0034's detectors extend remarks(); compose() is where their output enters the prompt.

## 2026-09-16

Per-tick cost, measured in the worktree (72x34, 1200 ticks, --tick 0, three runs each, median): dormant mind 2.81 ms/tick; awake FakeMind with NOTES_EVERY=0 2.67; NOTES_EVERY=600 (2 looks) 2.67; NOTES_EVERY=10 (120 looks, the call stubbed) 2.71. One packet costs 0.52 ms at 239 cells. The difference between 0 and 600 is inside run-to-run noise (min/max spread 3.19-3.21 s per 1200 ticks).

## 2026-09-16

Criterion 1's 'references the previous by content' is verified structurally: every prompt after the first carries the previous entry's text and tick and the deltas since it (test_each_note_is_composed_against_the_one_before_it), not against a live model, since the item grants no spend. The prose (hedging, continuity, no advice) rests on NATURALIST_SYSTEM alone; the owner should read the first day's notebook and adjust the prompt, which needs no code.

## 2026-09-16

Beyond the plan: due() does not test mind.exhausted, so a spent budget is met at the call and said once as 'field notes end at tick N — budget spent', whatever spent it; the prompt is told the incubator's pace (Culture.tick_seconds, set by run()) so 'ticks vs wall-clock' is computable; a notebook that cannot be written is one mind event per look and no backoff, baseline unchanged; call events carry role (genesis/mutagen/naturalist/probe). No vitals row for the naturalist: VITALS_H is pinned and a row would shrink the census everywhere; failures are mind events and biotic status counts the notebook.
