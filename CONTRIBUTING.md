# Contributing

Short rules so four people can share one repo without stepping on toes.

## Branches

- Branch from `main` per feature. Never merge your own branch, the repo owner merges by hand.
- One task, one branch. Small commits with honest messages.
- Never use the word phase in branch or commit names.
- Rebase onto `main` before opening a pull request. No fork-sync merge noise.

## Code

- Latest pinned deps. Tests for core logic, all offline, no network or downloads.
- No em dashes anywhere in code or docs. No emojis in code.
- No sensitive names in pushed files.
- Shared validators and helpers live in `edge/models.py`. Do not copy them.

## Docs and log

- Docs go in `docs/` in simple words.
- Every change adds a row on top of `CHANGELOG.md` with date, author, files, and why.
- The `memory/` folder stays local and never pushes.

## Checks

Push runs the checks workflow: backend tests, em dash scan, dashboard build. Green before review.
