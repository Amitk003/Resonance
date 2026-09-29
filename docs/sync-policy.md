# Sync policy

What stays on the robot and what goes to the cloud.

## Value score

Each point gets 0 to 1, best first:

- Hazard note: plus 0.4
- Merge anchor: plus 0.3
- Confidence: plus 0.2 times confidence
- Rare zone: plus 0.1 times rarity (1 minus zone share)

Ties break toward newer places. The exact math lives in
`edge/sync.py` so code and docs cannot drift apart.

## Upload order

1. Hazards and key findings
2. Good merge anchors
3. Rare places
4. Normal points if space allows

A place counts as a hazard when its note contains the word hazard.
The swap ranking in code uses the same rule, see HAZARD_KEYWORD.

## Conflicts

Same place sent twice with different data:

- Higher confidence wins
- Tie goes to more agents agreeing
- Keep old versions in history
- Show all conflicts in the dashboard log

## Offline rule

Sync never blocks local work. Queue waits with no network. Sends in order when back online.
