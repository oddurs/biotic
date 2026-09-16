---
id: 48
title: 'Site membrane page: the me.memory rule'
type: docs
status: backlog
milestone: dish
created: 2026-09-16
updated: 2026-09-16
priority: p3
area: web/
effort: s
part_of:
- 39
---

## Problem

0046 brought web/apps/site/src/content/docs/instrument/membrane.mdx in line with docs/membrane.md, and 0043 then added a rule the page does not state: what a cell may keep in me.memory. After every live() the dish holds the memory to membrane.memory_fault and a cell that breaks it bursts; the smoke test refuses a genome that does so within its forty rounds. A reader who writes a founder from the page will be surprised by memory holds one list or dict in two places, or inside itself; keep a copy in each.

## Proposal

Add the rule to the page, or link to the section in docs/membrane.md (What a cell may keep: me.memory): values None, bools, ints, floats, strings, and lists, tuples and dicts of those; keys strings, numbers, bools or None; nested at most MEMORY_MAX_DEPTH (16) deep; no list or dict in two places; at most MEMORY_MAX_CHARS (2048) characters as JSON. The reason strings: memory over 2048 chars as JSON; memory holds a range; only None, bools, numbers, strings, lists, tuples and dicts may stay in it; memory has a tuple as a key; keys must be strings, numbers, bools or None; memory nested deeper than 16; memory holds one list or dict in two places, or inside itself; keep a copy in each. In the smoke test each ends with (tick N). Also the file format (~t and ~d tags in dish.json and strain samples), one sentence. Any change under web/ pulls pnpm into scripts/task check, which is why 0043 did not touch it.

## Acceptance criteria

- [ ] The page states the me.memory rule and its reason strings, or links to the section in docs/membrane.md
- [ ] TASK_SCOPE=all scripts/task check is green
