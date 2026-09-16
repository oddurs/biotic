---
id: 5
title: 'The freezer: `biotic freeze` and `biotic revive`'
type: feature
status: done
milestone: dish
assignee: Oddur Sigurdsson
created: 2026-09-08
updated: 2026-09-16
priority: p0
effort: m
area: bio/culture.py, bio/__main__.py
---

## Problem

Lenski's experiment is possible because every 500 generations a sample goes in
the freezer, and any question about contingency — would this have happened
again? — is answered by thawing an ancestor and replaying. We serialise the
dish every 150 ticks but overwrite it, so the past is gone. Without a freezer
there is no replay, and without replay there is no experiment.

## Proposal

- `vessel/freezer/<tick>.json.gz` — a full dish snapshot (cells, agar, pheromone,
  RNG state, genomes) plus the strains registry at that moment. Automatic every
  `BIOTIC_FREEZE_EVERY` ticks (default 2000); manual with `biotic freeze [--label]`.
- `biotic freeze --strain <id>` — a *strain* sample: the genome plus one cell's
  memory, as `vessel/freezer/strain-<id>.json`.
- `biotic revive <tick>` — replace the current dish with the snapshot (after
  confirming; the current dish is itself frozen first as `pre-revive`). The
  events log gets a `revived from tick N` entry and the curve gets a marker.
- `biotic revive --strain <id> [--into fresh|current] [--n 5]` — inoculate a
  strain sample into a fresh dish (same seed, so same agar) or drop it into the
  running one as an invader.
- `biotic freezer` lists what is frozen with tick, label, population, strains.
- Snapshots are gzipped; a 72×34 dish is ~100KB compressed.

## Acceptance criteria

- [x] Automatic snapshots appear at the configured cadence; the freezer listing shows them
- [x] `revive <tick>` restores a dish whose next 100 ticks match a run that never left that state (same RNG state → identical trajectory)
- [x] `revive --strain` into a fresh dish grows (or does not) and the log says which
- [x] Reviving records the event and a curve marker

## 2026-09-16

Persistence was lossy by one line: Dish.to_dict rounded cell energy to four decimals, so a to_dict/from_dict twin left the trajectory within a few ticks. Energies are now stored exactly (JSON floats round-trip through repr) and an exact twin is bit-identical for hundreds of ticks; tests/test_dish.py has the lossless test and a rounded-energy control. dish.json grows a few percent. Criterion 2 is impossible without this, and a dish running across the upgrade is not bit-reproducible over the boundary (changelog).

## 2026-09-16

Memory: Dish.place deep-copies the memory a new cell is given (copy.deepcopy, falling back to a shallow copy if deepcopy raises), so mother and daughter never share a nested list or dict that a save would then separate; and Dish._jsonable keeps any value whose JSON is 200 characters or less (normalised through dumps/loads, so tuples come back as lists) instead of stringifying every non-scalar; the 64-key cap stays. Both are dish-behaviour changes for every culture and are in the changelog under Changed. The owner may want to make the deep-copy call consciously: if it is rejected, WANDERER in tests/conftest.py must stop mutating its list in place and docs/freezer.md must say such genomes diverge after any resume. The 200/64 limits are arbitrary; a genome past them gets strings back after a resume with no warning (a one-time log line would make it visible; small follow-up).

## 2026-09-16

Culture-level state (the mutation-roll RNG, the phase debounce, the mutagen boost, the revivals chain, the watch list) rides in dish.json under a culture key and in every dish sample, so a resume and a revive are one mechanism. Culture.state_dict/restore_state is the seam; restore_state tolerates every key missing. 0002 (budget, spent) and 0040 (clock) should add their keys there and they ride into samples for free.

## 2026-09-16

No marker column. 0003 landed bio/curve.py with the rule that markers stay in events.jsonl (0004, 0005, 0010, 0012 add no columns), so the item's curve marker is the revived event, logged after the swap so its tick is the revived tick, plus the discontinuity it leaves: the curve's tick column steps back to the sample's tick and no row is written for the revive itself. Culture._curve and bio/curve.py are untouched. A tick is no longer unique across the file, so a join on tick alone picks up the other timeline: 0004 should split segments where tick decreases (the k-th decrease is the k-th revived dish event) and join within a segment. 0010's proposal still says it writes a marker row; it should log its gap as an event instead. docs/curve.md has the paragraph.

## 2026-09-16

Sample names are <tick:08d>-<label>.json.gz (gzip level 6, tmp + os.replace, format: 1) and are never overwritten: a second sample at the same tick and label gets -2, -3. After revive 4000 the timeline reaches 6000 again and the original 00006000-auto is exactly what a contingency comparison needs. Each culture carries a revivals chain (from, was, at, sample); the listing shows the last hop as the branch column and 0036/0037 get branch history from it. revive TICK --label narrows by the label the sample stores, not by parsing the name, since a label may itself end in -digits (run-2).

## 2026-09-16

A running incubator owns the dish: a second process reading dish.json sees a state up to 150 ticks stale and its writes are clobbered by the next autosave. freeze and revive are Culture methods; the CLI runs them in-process when nothing holds the vessel and queues them through the inbox when something does. Running means an advisory flock on vessel/incubator.lock taken in Culture.run() and released by the kernel however the process ends: no stale pid to clean up (the pid inside is for the message only), Unix-only like SIGALRM already, and not reliable on a network filesystem (docs say so). The file itself stays behind after a run. incubating() probes with LOCK_SH so probes do not refuse each other, and the incubator retries eight times over a quarter second so a biotic status probe at the wrong instant is not mistaken for another incubator (tested). Consequences: two incubators on one vessel now refuse instead of interleaving writes, and biotic seed and biotic sterilize refuse while the incubator runs, since both would pull the files out from under it. 0006 gets the guard for free and must move FREEZER and LOCK_FILE with the vessel.

## 2026-09-16

The inbox: freeze, freeze_strain, revive and revive_strain requests join whisper and drop. _inbox() returns True when a dish revive replaced self.dish, and step() returns at once, since its local dish and census now describe the old dish (the revive has logged and saved; no curve row for that tick). A queued freezer request is stamped with the pid of the incubator it was meant for; a later incubator drops it and logs why, rather than freezing or reviving days later unannounced. Whispers and drops are not stamped.

## 2026-09-16

revive --strain --into fresh is Culture.germinate(seed, mind, fresh=True, thaw=path, n=N): a germination with a given founder. Order: read and admit the sample, refuse a seed mismatch, freeze the dish on disk as pre-revive, autoclave (the freezer is kept), pour a dish of the sample's seed and size (same seed and dimensions = same agar), adopt the strain, inoculate --n cells with the sampled memory, log revived, save, freeze genesis, start a watch. Every RNG starts from the seed, so the same sample into the same seed gives the same trajectory (tested). It needs a stopped incubator: an in-place reset of a running culture (seed, RNGs, registry, dish dimensions under the renderer) is not worth its risk, so the CLI says so instead of queueing it. revive TICK and --into current work in-process or through the inbox. --at goes with --into current only. Cut: freeze --strain ID --at TICK (sample an ancestor out of a frozen dish without reviving it); about 15 lines when someone needs it.

## 2026-09-16

revive --strain --into current also freezes the dish as pre-revive: the pre-invasion dish is what one compares against. The strain is registered with the dish before it is inoculated (a genome the dish does not know raises KeyError in Dish._fn on the first tick and every cell lyses, a spurious did-not-take; tested), the registry is adopted under the culture lock because the eyepiece iterates it under that lock, placement takes the n nearest free tiles by the dish's 2:1 metric and draws no RNG, and no confirmation is asked since nothing is replaced.

## 2026-09-16

Samples are files anyone can edit, so a revived genome passes the membrane again: inspect() (static) for every genome in a dish sample, admit() (static plus smoke test) for a strain sample, and check_record refuses a strain record missing a field a Strain has no default for. Every refusal comes before the pre-revive freeze and before the autoclave of a fresh dish, so a refused revive changes nothing (tested from the library and the CLI). All call sites are on the main thread (the CLI process, or _inbox() inside step()), so Budget's SIGALRM is legal; never call freeze or revive from the mutagen or renderer threads.

## 2026-09-16

The seed rule: the agar is a function of (seed, w, h). A vessel that holds a dish keeps its seed and a dish sample from another seed is refused with sterilize first; an empty vessel takes the seed of what is revived into it and seed.txt is written. A strain into a fresh dish autoclaves anyway and founds a dish of the sample's own seed and size; into the current dish a strain's origin seed does not matter, it is only a genome. Cross-vessel revives belong to 0006.

## 2026-09-16

Criterion 2 (identical trajectory for 100 ticks) holds with a dormant or deterministic mind: physics, both RNGs, memories within the JSON limits, the registry's counter and hue stream, and the phase debounce all replay exactly. The test uses a fake mutagen (Mutagen.take always returns a variant) so the culture RNG and the registry are load-bearing. A live model's replies are not reproduced; that is the experiment, and 0037's manifest is where mutation replay would live. docs/freezer.md says what is and is not reproduced.

## 2026-09-16

The watch: REVIVE_WATCH = 300 ticks (100 in tests) is bookkeeping, not physics. A revived strain extinct before the watch ends logs revived ... did not take, one alive at the end logs took, both as revived events with took, cells and ticks in their data, and nothing about the dish differs for being watched. The list is persisted with the culture state so it survives ctrl-c then biotic live, the usual way a revived strain is watched. A dish revive restores the sample's watch list with the rest of its state: a watch belongs to the state it was started in and concludes in the revived timeline (tested: two took events at the same tick, one per timeline).

## 2026-09-16

sterilize() used to rmtree vessel/, which would have destroyed the freezer. It now removes every child of the vessel except freezer/; biotic sterilize --freezer empties that too and the prompt says which. Consequence: biotic seed --fresh with a new seed keeps the old seed's samples in the listing (marked with their seed, refused by the seed rule) and the new genesis sample is 00000000-genesis-2. Cosmetic until 0006 decides whether the freezer belongs to the vessel or to the seed; 0006's flasks new must expect sterilize() to keep it.

## 2026-09-16

The culture's own freezes (genesis and the cadence) must not stop the dish when the freezer cannot be written: an OSError is logged once as a freezer event, the sample is tried again at the next cadence, and the log says when the freezer is writable again, the way curve.csv is handled. A freeze a person asked for raises instead, so the CLI and the inbox can say so. A failed write leaves no .tmp behind.

## 2026-09-16

Mutagen.reset(genomes) on a dish revive replaces the known genomes and clears the pool and the requests under the mutagen lock. A call to the mind already in flight may still append one orphan pool entry afterwards; it is inert because _pick ignores strains not in genomes, so nothing may assume pool keys are a subset of genomes (0040's mutate_now included). soma/ keeps the fossils of strains from a timeline a dish revive abandoned, so soma/ and strains.json no longer describe the same set; the registry is authoritative and ids are hash-derived, so nothing collides.

## 2026-09-16

Neighbours: 0008's persistence tests are test_dish_dict_is_lossless, its rounded-energy control and the culture resume test. 0014/0015: Registry.adopt and strain samples carry asdict(Strain) and from_dict ignores fields this version does not know, so new fields with defaults flow through; a sample with a later format number is refused by freezer.read. 0006: every freezer path is a config constant and strain samples carry seed, w and h.

## 2026-09-16

Reconciled onto main after #17 (snapshot reads the agar once; auto-merged), #18 (the CLI reference under web/apps/site/src/content/docs/reference/cli.mdx is generated from the argparse tree; regenerated with scripts/task docs, and scripts/task lint fails when it is stale) and #22 (cairn format 3). The item's earlier notes were re-recorded here after the rebase.

## 2026-09-16

Tests: 71 in about 2 s, all on 24x12 dishes with the mind asleep and both urlopen and Mind.think patched to fail. tests/conftest.py carries WANDERER, a genome that draws from the dish RNG, keeps a counter and a list in memory, mutates the list in place and reads it: the aliasing case that makes lossless persistence and deep-copied inheritance load-bearing. CELL_TIME_BUDGET is raised to 0.05 s in tests so a slow machine cannot lyse a cell and break a determinism test. The vessel fixture asserts at teardown that the repository's vessel/freezer listing did not change.

## 2026-09-16

Measured after the rebase, 72x34 dish, tick 600, 229 cells: to_dict plus json.dumps 0.8 ms, gzip level 6 1.9 ms, 76 KB of JSON, 27 KB compressed; a tick of that dish is about 1.9 ms. Neither to_dict nor inoculate is on the tick path; per tick the freezer adds two integer ops and one truthiness test. On a 24x12 dish a twin with energies rounded to four decimals parts from the original at the very first tick (WANDERER and the built-in founder alike); the exact twin is identical for 300.

## 2026-09-16

Review of the branch: the curve marker is a column after all, but a coordinate, not a marker. The earlier note's rule (split curve.csv where tick decreases; the k-th decrease is the k-th revived dish event) is withdrawn: a revive to a sample later than the dish was at leaves tick monotone (140, 50, 60, 150, 160 after reviving 40 from 140 and then the tick-140 sample from 60), so nothing in the file marked that seam and a reader merged two timelines. curve.csv now ends in a branch column: Culture.branch, 0 at genesis, +1 on every dish revive, persisted with the culture state and written into every row; the revived event carries the branch it opens. It is the vessel's count, not the length of the revivals chain: the chain is the dish's lineage and reviving a branch-0 sample after a revive gives length 1 again, which would have hidden the same seam. (branch, tick) is unique in the file; join events on it, and an event's branch is the number of revived dish events before it in the log. tests/test_metrics.py NEW_HEADER is extended; docs/curve.md, docs/freezer.md and README say the new rule. The freezer listing's hop column is renamed from branch to from so the word means one thing.

## 2026-09-16

Review of the branch, the rest: check_record validates shape as well as presence (id four hex, parent an id or null, name a-z0-9_ up to 64, note and source text, born/peak/generation/extinct_at non-negative ints, hue a number in [0,1)), because adopt() took id and name verbatim into a fossil path under soma/ and the culture sums generations at the next curve row; a string generation bricked the vessel and an id of ../.. wrote a .py two directories up. freezer.read checks tick, seed, label, frozen_at and a strain sample's w, h and memory the same way, so one edited sample no longer tracebacks the whole listing. Mutagen._mutate looks the strain up again after the interval and returns if reset() or forget() removed it meanwhile; before, a dish revive through the inbox in that window raised KeyError on the mutagen thread and ended it for the run. revive_strain refuses an --at outside the dish before the pre-revive freeze (inoculate(at=) would have placed the cells on the rim and logged the point). revive TICK --label is cleaned like freeze --label, so Bench finds bench. OSError from a person-requested freeze, or from the pre-revive freeze inside revive, is a one-line exit from the CLI instead of a traceback.

## 2026-09-16

Rebased onto main after #26/#27: kept main's memory hardening (MEMORY_INT bound, _text placeholders) and added the freezer's JSON round trip for containers under 200 chars; conftest keeps main's FakeMind (no Mind.think patch), test_dish.py keeps only the memory/inoculate tests main did not move; the genesis freeze now follows the founding exhaustion event, test_budget adjusted
