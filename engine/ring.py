"""Ring geometry: range between boxers, reach gating, footwork, and cornering (PRD §3, §6).

Positions are [x, z] in feet on the 16x16 floor. Boxers auto-face each other; footwork is expressed
relative to that facing (forward = close range, back = open range, left/right/circle = lateral).
"""
import math
from .config import CONFIG

_RING = CONFIG["ring"]
_REACH = CONFIG["reach"]
_GLANCING = CONFIG["health"]["glancing_mult"]
SIZE = _RING["size_ft"]
MARGIN = _RING["corner_margin_ft"]
MIN_DISTANCE = _RING["min_distance_ft"]
BOXER_RADIUS = 0.7
_ATTR_BASELINE = 75.0
_CLEAN_BAND = 0.5  # within (reach - this) of the opponent = clean; beyond = glancing

_DIRS = ("forward", "back", "left", "right", "circle_left", "circle_right")


def distance(a: list[float], b: list[float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _reach_ft(punch_type: str, reach_attr: float) -> float:
    return _REACH[punch_type] + (reach_attr - _ATTR_BASELINE) / _ATTR_BASELINE * _REACH["attr_scale_ft"]


def _height_reach_adjust(placement: str, height_attr: float, opp_height: float) -> float:
    """How height shifts the reach NEEDED for a target. A taller boxer reaches a shorter man's (lower)
    head from farther; the shorter boxer reaches the taller man's body more easily. No-op when heights
    match. (PRD §3 — head/body sit at different heights, so the reach to each differs.)"""
    if placement.startswith("head"):
        return (height_attr - opp_height) / _ATTR_BASELINE * _REACH["height_head_ft"]
    return (opp_height - height_attr) / _ATTR_BASELINE * _REACH["height_body_ft"]


def in_reach(dist: float, punch_type: str, reach_attr: float = _ATTR_BASELINE) -> bool:
    return dist <= _reach_ft(punch_type, reach_attr)


def land_quality(dist: float, punch_type: str, placement: str = "head_center",
                 reach_attr: float = _ATTR_BASELINE, height_attr: float = _ATTR_BASELINE,
                 opp_height: float = _ATTR_BASELINE) -> float:
    """1.0 clean / glancing at the edge of reach / 0.0 out of range. Effective reach combines the
    attacker's reach attr with the head/body height geometry between the two boxers."""
    r = _reach_ft(punch_type, reach_attr) + _height_reach_adjust(placement, height_attr, opp_height)
    if dist > r:
        return 0.0
    return 1.0 if dist <= r - _CLEAN_BAND else _GLANCING


def step_distance(agility_attr: float = _ATTR_BASELINE) -> float:
    """Feet covered per footwork step. Quicker feet (higher agility) cover more ground."""
    fw = CONFIG["footwork"]
    return fw["step_distance_ft"] * (1.0 + (agility_attr - _ATTR_BASELINE) / _ATTR_BASELINE * fw["agility_scale"])


def range_band(dist: float) -> str:
    if dist <= _REACH["pocket_ft"]:
        return "pocket"
    if dist <= _REACH["jab"]:
        return "jab"
    return "out"


def types_in_range(dist: float, reach_attr: float = _ATTR_BASELINE) -> list[str]:
    return [pt for pt in ("jab", "cross", "hook", "uppercut") if in_reach(dist, pt, reach_attr)]


def _unit_to(opp: list[float], pos: list[float]) -> tuple[float, float]:
    dx, dz = opp[0] - pos[0], opp[1] - pos[1]
    d = math.hypot(dx, dz) or 1.0
    return dx / d, dz / d


def step_target(pos: list[float], opp: list[float], direction: str, dist: float) -> list[float]:
    ux, uz = _unit_to(opp, pos)
    px, pz = -uz, ux  # left-perpendicular
    vec = {
        "forward": (ux, uz), "back": (-ux, -uz),
        "left": (px, pz), "circle_left": (px, pz),
        "right": (-px, -pz), "circle_right": (-px, -pz),
        "none": (0.0, 0.0),
    }[direction]
    return [pos[0] + vec[0] * dist, pos[1] + vec[1] * dist]


def clamp_min_distance(pos: list[float], opp: list[float]) -> list[float]:
    """Keep the two boxers from stepping inside each other: if a move puts pos closer than MIN_DISTANCE
    to the opponent, push it back out onto that circle (along the line away from him)."""
    dx, dz = pos[0] - opp[0], pos[1] - opp[1]
    d = math.hypot(dx, dz)
    if d >= MIN_DISTANCE:
        return pos
    if d < 1e-9:                      # exactly overlapping — pick an arbitrary push direction
        dx, dz, d = 1.0, 0.0, 1.0
    return [opp[0] + dx / d * MIN_DISTANCE, opp[1] + dz / d * MIN_DISTANCE]


def _inside(p: list[float]) -> bool:
    return BOXER_RADIUS <= p[0] <= SIZE - BOXER_RADIUS and BOXER_RADIUS <= p[1] <= SIZE - BOXER_RADIUS


def legal_steps(pos: list[float], opp: list[float], dist: float) -> list[str]:
    """Directions that keep the boxer inside the ring (cornering removes the rest). Always includes 'none'."""
    ok = [d for d in _DIRS if _inside(step_target(pos, opp, d, dist))]
    return ok + ["none"]


def cornered(pos: list[float]) -> bool:
    return (pos[0] <= MARGIN or pos[0] >= SIZE - MARGIN or
            pos[1] <= MARGIN or pos[1] >= SIZE - MARGIN)
