"""Shared Pydantic 2 models - the one data contract for all branches.

Matches docs/data-model.md Place record, plus explicit agent_id
so per-agent isolation can be validated.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from edge.config import DIM


class Pose(BaseModel):
    """Robot pose: x, y in meters, theta in radians."""

    x: float
    y: float
    theta: float


class Payload(BaseModel):
    """Small metadata attached to every place."""

    zone: str = ""
    sensor: str = ""
    note: str = ""

    @field_validator("zone", "sensor", "note")
    @classmethod
    def _must_be_str(cls, v: Any) -> str:
        if not isinstance(v, str):
            raise ValueError("payload fields must be strings")  # noqa: TRY004 - Pydantic expects ValueError
        return v


def validate_vector(v: Any, dim: int = DIM) -> list[float]:
    """Shared vector check used by models, API, and store.

    Accepts a list of exactly dim numbers, returns them as floats.
    Raises ValueError for anything else.
    """
    if not isinstance(v, list):
        raise ValueError("vector must be a list of floats")  # noqa: TRY004 - API maps ValueError to 400/422
    if len(v) != dim:
        raise ValueError(f"vector must have exactly {dim} values, got {len(v)}")
    for item in v:
        if not isinstance(item, (int, float)):
            raise ValueError("vector values must be numeric")  # noqa: TRY004 - API maps ValueError to 400/422
    return [float(x) for x in v]


def validate_str_list(v: Any, name: str) -> list[str] | None:
    """Shared match-any filter check used by the API and the store.

    None stays None (no filter). Otherwise returns the cleaned list.
    Raises ValueError for anything else.
    """
    if v is None:
        return None
    if not isinstance(v, list):
        raise ValueError(f"{name} must be a list of strings or omitted")  # noqa: TRY004 - API maps ValueError to 400/422
    for item in v:
        if not isinstance(item, str) or not item:
            raise ValueError(f"{name} must hold non-empty strings")
    return list(v)


# Keyword marking a hazard in a place note. The swap and the cloud sync
# both rank hazard places first. Keep the match simple on purpose:
# any note containing this word counts.
HAZARD_KEYWORD: str = "hazard"


class Place(BaseModel):
    """One remembered place.

    Example:
        {"id": "robot-a-42", "agent_id": "robot-a", "vector": [...512...],
         "pose": {"x": 1.5, "y": 2.0, "theta": 0.4},
         "timestamp": 1727000000, "confidence": 0.9,
         "payload": {"zone": "hall", "sensor": "cam", "note": ""}}
    """

    id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    vector: list[float]
    pose: Pose
    timestamp: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    payload: Payload = Field(default_factory=Payload)

    @field_validator("vector")
    @classmethod
    def _validate_vector(cls, v: Any) -> list[float]:
        return validate_vector(v)


class SwapCandidate(BaseModel):
    """Slim swap unit for the Task 6 meeting exchange.

    Carries only what a rendezvous needs: identity, vector, pose,
    confidence, and time. No zone, sensor, or note text, so radio
    messages stay small.
    """

    id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    vector: list[float]
    pose: Pose
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: int = Field(ge=0)

    @field_validator("vector")
    @classmethod
    def _validate_vector(cls, v: Any) -> list[float]:
        return validate_vector(v)


def place_to_swap_candidate(place: Place) -> SwapCandidate:
    """Strip a Place down to the fields a meeting swap needs."""
    return SwapCandidate(
        id=place.id,
        agent_id=place.agent_id,
        vector=place.vector,
        pose=place.pose,
        confidence=place.confidence,
        timestamp=place.timestamp,
    )


class Transform(BaseModel):
    """Rigid move of map B into map A: shift plus heading change."""

    dx: float
    dy: float
    dtheta: float


class MergeRecord(BaseModel):
    """One finished meeting between two agents (Task 12).

    score blends the mean vector match with the shape fit, so 1.0
    means same places and same shape. No fuse gate here; Task 13
    decides fuse vs log from this score.
    """

    id: str = Field(min_length=1)
    timestamp: int = Field(ge=0)
    agent_a: str = Field(min_length=1)
    agent_b: str = Field(min_length=1)
    pairs_total: int = Field(ge=0)
    inliers: int = Field(ge=0)
    mean_score: float
    score: float = Field(ge=0.0, le=1.0)
    transform: Transform
    anchor_ids: list[str] = Field(default_factory=list)


class FuseDecision(BaseModel):
    """Fuse vs log verdict for one merge score (Task 13)."""

    fuse: bool
    score: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(ge=0.0, le=1.0)
    margin: float
    reason: str


def make_pair_id(query_id: str, match_id: str) -> str:
    """Stable key for one matched pair. Later tasks reuse it."""
    return f"{query_id}~{match_id}"


class PlaceMatch(BaseModel):
    """One nearest neighbor pair between two agents (Task 9).

    Matches docs/data-model.md Match result. query_id is the swapped
    candidate from the other robot, match_id is the own place with
    the closest vector, score is cosine similarity in [-1, 1].
    inliers stays 0 here; Task 10 fills it during the shape check.
    """

    pair_id: str = Field(min_length=1)
    query_id: str = Field(min_length=1)
    match_id: str = Field(min_length=1)
    score: float = Field(ge=-1.0, le=1.0)
    inliers: int = Field(default=0, ge=0)
