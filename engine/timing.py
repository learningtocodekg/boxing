"""Action phase durations + the reaction-delay model (PRD §4.3-§4.4). All in seconds.

Faster `speed` shortens a punch's windup (less telegraph, harder to react to); higher `strength`
lengthens its recovery (longer exposed). Attributes nudge both. Numbers come from config.timing.
"""
from .config import CONFIG

_T = CONFIG["timing"]
_BASE_REACT = CONFIG["time"]["reaction_delay_base"]
_ATTR_BASELINE = 75.0


def _lerp(a: float, b: float, f: float) -> float:
    return a + (b - a) * f


def windup_time(punch_type: str, speed: float, hand_speed: float = _ATTR_BASELINE) -> float:
    """Telegraph length. speed 0 -> full base; speed 10 -> base * speed_windup_scale. Faster hands shorten it."""
    base = _T["windup"][punch_type]
    scaled = base * _lerp(1.0, _T["speed_windup_scale"], speed / 10.0)
    return scaled * (_ATTR_BASELINE / max(1.0, hand_speed))


def recovery_time(punch_type: str, strength: float) -> float:
    """How long the hand is locked (no guard) after impact. Grows with strength."""
    base = _T["recovery"][punch_type]
    return base * _lerp(1.0, _T["strength_recovery_scale"], strength / 10.0)


def reaction_delay(reaction_attr: float = _ATTR_BASELINE, energy_penalty: float = 0.0) -> float:
    """Seconds before a freshly-chosen defense becomes effective. Tired boxers (energy_penalty>0) react slower."""
    return _BASE_REACT * (_ATTR_BASELINE / max(1.0, reaction_attr)) + energy_penalty


def slip_window(t: float) -> tuple[float, float]:
    """(active_until, locked_until) for a slip started at time t."""
    return t + _T["slip_duration"], t + _T["slip_duration"] + _T["slip_recovery"]


def duck_window(t: float) -> tuple[float, float]:
    return t + _T["duck_duration"], t + _T["duck_duration"] + _T["duck_recovery"]
