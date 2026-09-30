"""Person 1 Task 13 tests - fuse gate plus shift preview, offline."""

from __future__ import annotations

import math

import pytest

from edge.fuse import (
    DEFAULT_FUSE_THRESHOLD,
    decide_fuse,
    normalize_angle,
    shift_preview,
)
from edge.models import Transform
from tests.conftest import make_place


def test_default_threshold():
    assert DEFAULT_FUSE_THRESHOLD == pytest.approx(0.8)


def test_fuse_above_and_on_boundary():
    assert decide_fuse(0.9).fuse is True
    assert decide_fuse(0.8, 0.8).fuse is True
    assert decide_fuse(0.8, 0.8).reason == "at-or-above-threshold"


def test_log_below_threshold():
    decision = decide_fuse(0.5, 0.8)
    assert decision.fuse is False
    assert decision.reason == "below-threshold"
    assert decision.margin == pytest.approx(-0.3)


def test_bad_numbers_rejected():
    for bad in (-0.1, 1.1, "high", True, None):
        with pytest.raises(ValueError):
            decide_fuse(bad, 0.8)
        with pytest.raises(ValueError):
            decide_fuse(0.9, bad)


def test_shift_preview_moves_poses_only():
    import math as _math

    place = make_place()
    moved = shift_preview([place], Transform(dx=1.0, dy=-2.0, dtheta=0.5))
    assert len(moved) == 1
    c, s = _math.cos(0.5), _math.sin(0.5)
    assert moved[0].pose.x == pytest.approx(c * place.pose.x - s * place.pose.y + 1.0)
    assert moved[0].pose.y == pytest.approx(s * place.pose.x + c * place.pose.y - 2.0)
    assert moved[0].pose.theta == pytest.approx(place.pose.theta + 0.5)
    assert moved[0].id == place.id
    assert moved[0].vector == pytest.approx(place.vector)
    assert moved[0].confidence == pytest.approx(place.confidence)


def test_shift_preview_zero_rotation_is_shift():
    place = make_place()
    moved = shift_preview([place], Transform(dx=1.0, dy=-2.0, dtheta=0.0))
    assert moved[0].pose.x == pytest.approx(place.pose.x + 1.0)
    assert moved[0].pose.y == pytest.approx(place.pose.y - 2.0)


def test_normalize_angle():
    assert normalize_angle(0.0) == pytest.approx(0.0)
    assert abs(normalize_angle(math.pi)) == pytest.approx(math.pi)
    assert abs(normalize_angle(3.0 * math.pi)) == pytest.approx(math.pi)
    assert abs(normalize_angle(-3.0 * math.pi)) == pytest.approx(math.pi)
