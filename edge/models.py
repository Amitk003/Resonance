"""Shared Pydantic 2 models — the one data contract for all branches.

Matches docs/data-model.md Place record, plus explicit agent_id
so per-agent isolation can be validated (Task 1 extension).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

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
        if not isinstance(v, list):
            raise ValueError("vector must be a list of floats")
        if len(v) != DIM:
            raise ValueError(f"vector must have exactly {DIM} values, got {len(v)}")
        for item in v:
            if not isinstance(item, (int, float)):
                raise ValueError("vector values must be numeric")
        return [float(x) for x in v]

    @model_validator(mode="after")
    def _validate_id_convention(self) -> "Place":
        # Project convention: <agent_id>-<local_counter>, e.g. robot-a-42.
        # Enforce prefix so data from another agent can't leak into this store.
        if not self.id.startswith(self.agent_id + "-"):
            raise ValueError(f"id '{self.id}' must start with agent_id '{self.agent_id}-'")
        return self
