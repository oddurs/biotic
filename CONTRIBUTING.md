# Contributing

## Once

    scripts/setup

This points git at the tracked hooks in `.githooks/` and runs the full check. You need
`git`, `gh` (authenticated), and `uv`.

## Every change

1. `scripts/agent start <type>/<slug>` where type is one of `feat fix chore docs perf refactor test`.
   It branches from `origin/main` into `../.worktrees/biotic/<branch>/` and prints the path. `cd` there.
   One unit of work per worktree; never share a checkout between two pieces of work or two agents.
2. Make the change. `scripts/task check` runs formatting, lint, tests, and the build; it is exactly what CI runs.
3. `scripts/agent commit "<type>(<scope>): <subject>"`. Messages are Conventional Commits: subject at most
   72 characters, imperative, no trailing period. The hook rejects anything else.
4. `scripts/agent pr` runs the check, pushes, and opens the pull request from the template. Fill in the
   template; say what a reviewer should doubt.
5. Wait for CI. Squash-merge when green. `scripts/agent done` removes the worktree and branches.

`scripts/agent sync` rebases your branch onto the latest `main`. `scripts/agent list` shows what is open.

## Rules the tooling enforces

- `main` moves only through a squash-merged pull request. The pre-push hook and branch protection both block direct pushes.
- A pull request needs the `required` status check and an up-to-date branch. This is a solo project, so
  required approvals are set to 0: the owner merges their own pull requests once CI is green. That number
  goes to 1 when a second maintainer joins.
- Commits and pull requests carry no attribution to AI tools. The commit-msg hook rejects it; the work is
  published under the owner's name.
- `soma/` is written by the culture. Do not edit it by hand.

## Releases

`scripts/release <x.y.z>` opens the release pull request; merging it tags, builds, attests, and publishes.
Put user-visible changes under `## [Unreleased]` in `CHANGELOG.md` as you go so there is something to release.
