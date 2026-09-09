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
`check`, `version`. Do not call `uv`, `ruff`, or `pytest` directly in hooks, CI, or docs,
and do not add tooling that bypasses it. A branch is green when `scripts/task check` passes.
If you add a rule, config, or dependency, make the check pass in the same change.

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
