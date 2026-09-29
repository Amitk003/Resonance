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
            raise ValueError("payload fields must be strings")
        return v


def validate_vector(v: Any, dim: int = DIM) -> list[float]:
    """Shared vector check used by models, API, and store.

    Accepts a list of exactly dim numbers, returns them as floats.
    Raises ValueError for anything else.
    """
    if not isinstance(v, list):
        raise ValueError("vector must be a list of floats")
    if len(v) != dim:
        raise ValueError(f"vector must have exactly {dim} values, got {len(v)}")
    for item in v:
        if not isinstance(item, (int, float)):
            raise ValueError("vector values must be numeric")
    return [float(x) for x in v]


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
