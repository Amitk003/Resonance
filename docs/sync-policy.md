# Sync policy

What stays on the robot and what goes to the cloud.

## Value score

Each point gets 0 to 1 from:

- New or rare place: higher is better
- Model confidence: higher is better
- Helped a merge: keep it
- Hazard or key finding: upload first
- Old and low value: drop first

## Upload order

1. Hazards and key findings
2. Good merge anchors
3. Rare places
4. Normal points if space allows

## Conflicts

Same place sent twice with different data:

- Higher confidence wins
- Tie goes to more agents agreeing
- Keep old versions in history
- Show all conflicts in the dashboard log

## Offline rule

Sync never blocks local work. Queue waits with no network. Sends in order when back online.
