# Working in this repository

You are an agent contributing to `biotic`. These are instructions, not suggestions.

## Where to work

- Never edit in the primary checkout. Start every unit of work with
  `scripts/agent start <type>/<slug>` (type in `feat fix chore docs perf refactor test`,
  slug lowercase) and work in the worktree path it prints. One task, one worktree, one
  branch, one pull request. Never share a worktree with another agent.
- Never commit to, push to, or rebase onto anything but `origin/main` via `scripts/agent sync`.
  `main` only changes through a merged pull request; hooks and branch protection enforce it.
- Do not edit `soma/`. The culture writes it. Do not commit `vessel/` or `.env`.

## The seam

All checks run through `scripts/task`: `fmt`, `fmt:check`, `lint`, `test`, `build`,
`check`, `version`. Do not call `uv`, `ruff`, `pytest`, `pnpm`, `eslint`, or `astro`
directly in hooks, CI, or docs, and do not add tooling that bypasses it. A branch is green
when `scripts/task check` passes. If you add a rule, config, or dependency, make the check
pass in the same change.

## The site (`web/`)

A pnpm workspace: `web/packages/design` is the design system (StyleX tokens, themes,
primitives, browser tests) and `web/apps/site` is the Astro site. Rules:

- Style only with StyleX and only with tokens. No raw colours, sizes, or fonts in
  components; add a token first if one is missing. Never write plain CSS beyond
  `packages/design/src/global.css`, which is a structural reset.
- Import tokens from their own module: `@biotic/design/tokens/color.stylex`. StyleX cannot
  see variables through a barrel, and the build fails if you try.
- Components are React; `.astro` files are routes and content shells only. Anything that
  needs JavaScript in the browser is an island with an explicit `client:` directive.
- The palette and fluid scales are generated: edit `packages/design/scripts/generate.ts`,
  run `pnpm --dir web generate`, and commit the output. A test fails on drift.
- Every primitive has a browser test that includes an axe audit. Keep it that way.
- The project name and links live in `web/apps/site/site.config.ts`; nothing else hardcodes them.

## Commits and pull requests

- `scripts/agent commit "<type>(<scope>): <subject>"`. Conventional Commits, imperative,
  at most 72 characters, no trailing period. Never `--no-verify`, `|| true`, or
  `continue-on-error`.
- `scripts/agent pr` after the check is green. Fill the template honestly: the "look at
  this sceptically" section is for the part you are least sure of.
- After the merge, `scripts/agent done`.
- Put user-visible changes under `## [Unreleased]` in `CHANGELOG.md`.

## Attribution

No attribution to AI tools anywhere: not in commit messages, trailers, co-author lines,
pull request text, code comments, docs, changelog, or release notes. No "generated with",
no model names, no robot emoji. If a tool inserts any of that, remove it before it
reaches git or GitHub. The commit-msg hook and `scripts/noattrib` reject what they can
see; you are responsible for the rest.

## What the code is

`bio/` is the apparatus and is the only thing that gets linted and tested. Read
`README.md` for the model of the dish, the membrane, and the mutagen before changing
physics constants in `bio/config.py` or rules in `bio/membrane.py`; a change to either
alters every culture that runs afterwards and belongs in the changelog.

<!-- cairn:begin -->
## Roadmap and issues

This project tracks its roadmap and issues with `cairn`. Every item is a Markdown file under `cairn/items`, described by the schema in `cairn.toml`.

**Do not create ad-hoc TODO, PLAN or NOTES files.** Create a cairn item instead, so the work appears on the board and in the generated roadmap.

### The loop

1. `cairn next` — what is ready to start. It excludes anything blocked by unfinished dependencies and puts work already in progress first.
2. `cairn claim <ID>` — take it before you start, so no one duplicates the work. `cairn claim --next` picks and claims the top-ranked unclaimed item in one step, and prints its body so you can begin immediately.
3. Do the work. Record what you learn: `cairn set <ID> <field>=<value>` for fields, `cairn note <ID> "<TEXT>"` for anything that needs a sentence — why you chose something, what you tried, what to watch for.
4. `cairn close <ID>` when it is done, or `cairn release <ID>` to hand it back.
5. `cairn check` before you report finished. It must pass.

### Commands

```sh
cairn next --json                 # ready work, ranked
cairn claim --next                # take the next ready item
cairn search <TEXT> --json        # titles, bodies and labels
cairn list --json                 # all open items
cairn list --filter 'blocked=false,priority=p0'
cairn show <ID> --json            # one item, including its body
cairn new "<TITLE>" --type <TYPE> --milestone <MILESTONE>
cairn set <ID> status=<STATUS>    # also labels+=x, or any field below
cairn note <ID> "<TEXT>"          # append reasoning; never replaces
cairn close <ID>
cairn check                       # validate; run before finishing
cairn render                      # regenerate ROADMAP.md
```

### Schema

- **Types**: `feature`, `bug`, `chore`, `docs`, `milestone`
- **Statuses**: `backlog` (open), `planned` (open), `doing` (active), `blocked` (active), `done` (done), `dropped` (dropped)
- **`milestone`**: names a `milestone` item, by key — what this ships in
- **`due`**: date, YYYY-MM-DD — when a milestone is meant to land
- **`part_of`**: names any items, by id, several allowed — a larger piece of work this belongs to
- **`priority`**: one of p0, p1, p2, p3 — p0 is a release blocker
- **`effort`**: one of s, m, l, xl — Rough size, not an estimate
- **`area`**: free text — Subsystem this touches
- **Milestones**: `dish` (due 2026-09-21), `biotic-env` (due 2026-10-05), `substrates` (due 2026-10-31), `secretions` (due 2026-11-30), `transitions` (due 2027-01-31), `instrument` (due 2027-03-31)
- **Saved views** (`cairn list --view NAME`): `now`, `next`, `triage`

### Rules

1. Before starting work, find or create the item and set it to an active status.
2. Use the fields above rather than inventing new ones; add new fields to `cairn.toml` first.
3. Never hand-edit the generated roadmap file — change items and run `cairn render`.
4. `cairn check` must pass before the work is considered done.

<!-- cairn:end -->
