"""Fuse gate (Task 13, decision only).

decide_fuse turns a merge score and a live threshold into a fuse vs
log verdict. shift_preview moves B places into A frame for display.
No endpoints here (Task 14), no UI here (Task 16), no storage here:
preview objects must never be written back, they share ids with the
originals. Fully offline.
"""

from __future__ import annotations

import math

from edge.align import normalize_angle as _normalize_angle
from edge.models import FuseDecision, Place, Pose, Transform

# Starting threshold. Operators move it live; Task 16 owns the control.
DEFAULT_FUSE_THRESHOLD: float = 0.8


def decide_fuse(
    score: float, threshold: float = DEFAULT_FUSE_THRESHOLD
) -> FuseDecision:
    """Fuse when score meets the threshold. Boundary counts as fuse.

    Raises ValueError when either number leaves [0, 1].
    """
    for name, value in (("score", score), ("threshold", threshold)):
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not 0.0 <= value <= 1.0
        ):
            raise ValueError(f"{name} must be a number in [0, 1]")
    fuse = score >= threshold
    margin = round(score - threshold, 4)
    reason = "at-or-above-threshold" if fuse else "below-threshold"
    return FuseDecision(
        fuse=fuse,
        score=float(score),
        threshold=float(threshold),
        margin=margin,
        reason=reason,
    )


def shift_preview(places: list[Place], transform: Transform) -> list[Place]:
    """Copy B places into A frame for preview. Never store the result.

    Applies the full rigid move x' = R*x + t, so rotated maps preview
    correctly. Everything but the pose stays equal.
    """
    c, s = math.cos(transform.dtheta), math.sin(transform.dtheta)
    moved = []
    for place in places:
        moved.append(
            Place(
                id=place.id,
                agent_id=place.agent_id,
                vector=list(place.vector),
                pose=Pose(
                    x=c * place.pose.x - s * place.pose.y + transform.dx,
                    y=s * place.pose.x + c * place.pose.y + transform.dy,
                    theta=_normalize_angle(
                        place.pose.theta + transform.dtheta
                    ),
                ),
                timestamp=place.timestamp,
                confidence=place.confidence,
                payload=place.payload,
            )
        )
    return moved


def normalize_angle_display(value: float) -> float:
    """Wrap radians into [-pi, pi] for display. Single source is align."""
    return _normalize_angle(value)


# Kept for older imports; single source stays in edge.align.
normalize_angle = _normalize_angle
