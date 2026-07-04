"""Tests for the spoiler gate — the core correctness guarantee of the project."""

from companion_cube.filtering import decide
from companion_cube.models import Chunk, PlayerState, SpoilerLevel, SpoilerTolerance


def _chunk(level: SpoilerLevel, reveals: list[str]) -> Chunk:
    return Chunk(
        id="t",
        text="test",
        region="X",
        reveals_beats=frozenset(reveals),
        spoiler_level=level,
        entities=frozenset(),
        source="test",
    )


def test_mechanics_always_allowed():
    early = PlayerState()
    d = decide(_chunk(SpoilerLevel.MECHANICS, []), early, SpoilerTolerance.NONE)
    assert d.allowed


def test_major_plot_blocked_for_early_player():
    early = PlayerState(completed_beats=set())
    d = decide(_chunk(SpoilerLevel.MAJOR_PLOT, ["radiance_true_ending"]), early, SpoilerTolerance.NONE)
    assert not d.allowed
    assert "radiance_true_ending" in d.reason


def test_major_plot_allowed_once_beat_completed():
    late = PlayerState(completed_beats={"radiance_true_ending"})
    d = decide(_chunk(SpoilerLevel.MAJOR_PLOT, ["radiance_true_ending"]), late, SpoilerTolerance.NONE)
    assert d.allowed


def test_light_blocked_under_strict_tolerance():
    early = PlayerState()
    d = decide(_chunk(SpoilerLevel.LIGHT, ["broken_vessel"]), early, SpoilerTolerance.NONE)
    assert not d.allowed


def test_light_permitted_under_light_tolerance():
    early = PlayerState()
    d = decide(_chunk(SpoilerLevel.LIGHT, ["broken_vessel"]), early, SpoilerTolerance.LIGHT)
    assert d.allowed


def test_light_tolerance_does_not_leak_major_plot():
    early = PlayerState()
    d = decide(_chunk(SpoilerLevel.MAJOR_PLOT, ["void_heart_ending"]), early, SpoilerTolerance.LIGHT)
    assert not d.allowed
