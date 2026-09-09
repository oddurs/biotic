---
id: 24
key: secretions
title: The dish is the program
type: milestone
status: planned
depends_on:
- 17
created: 2026-09-08
updated: 2026-09-08
priority: p2
due: 2026-11-30
---

Bacteria secrete enzymes. An extracellular enzyme breaks a complex substrate
into pieces the secretor *and its neighbours* can eat — a public good, which
invites cheaters, which invites policing. Here a cell can leave an
intermediate on its tile: the output of one step toward digesting the
substrate. Others can eat the intermediate. Nobody has to solve the whole task.

This is compositional software emerging from ecology: a pipeline of strains,
each doing a stage, none designed to fit. The dish as a whole computes what no
cell can, and the map of who-eats-whose-secretions is the architecture — grown,
not drawn. `biotic compile` reads that map back out as one program. This is
where "an app that slowly builds itself" becomes literally true.

Done when: a multi-step substrate has been digested end-to-end by a chain of
≥ 2 strains with no single strain able to do it alone, and `biotic compile`
has emitted a runnable program from that chain.
