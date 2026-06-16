"""Energy: punch cost, ratchet-capped regen, and low-energy degradation (PRD §5).

Pure functions over plain numbers — BoxerState (engine/boxer.py) holds the state and calls these.
"""
from .config import CONFIG

_E = CONFIG["energy"]
_START = _E["start"]


def punch_energy(strength: float, speed: float) -> float:
    """Energy a punch costs. Depends on strength & speed ONLY — not punch type (PRD §5).
    Fits the anchors 10/10->3.0, 10/1->1.0, 1/10->0.5."""
    s, v = strength / 10.0, speed / 10.0
    return _E["cost_a"] * s + _E["cost_b"] * v + _E["cost_c"] * s * v


def lower_ceiling(energy: float, ceiling: float) -> float:
    """The ratchet: once energy drops below a cap (75/50/25), the ceiling can never rise above it
    again this round. Only ever lowers. Pass the boxer's current ceiling, get the new one."""
    for cap in _E["ratchet_caps"]:
        if energy < cap:
            ceiling = min(ceiling, float(cap))
    return ceiling


def stamina_regen_mult(stamina: float) -> float:
    """A deeper gas tank recovers faster between exchanges (no-op at the 75 baseline)."""
    return 1.0 + (stamina - 75.0) / 75.0 * _E["stamina_regen_scale"]


def regen(energy: float, ceiling: float, dt: float, rate_mult: float = 1.0) -> float:
    """Slow recovery while not throwing, clamped to the (ratcheted) ceiling. rate_mult scales by stamina."""
    return min(ceiling, energy + _E["regen_per_sec"] * rate_mult * dt)


def output_factor(energy: float) -> float:
    """Multiplier on effective punch power & speed as the boxer gasses: 1.0 at full -> ~0.6 at empty."""
    d = _E["degradation"]
    frac = max(0.0, min(1.0, energy / _START))
    return d["empty_factor"] + (d["full_factor"] - d["empty_factor"]) * frac


def reaction_penalty(energy: float) -> float:
    """Seconds added to reaction delay as the boxer tires: 0 at full -> reaction_penalty_at_empty at 0."""
    frac = max(0.0, min(1.0, energy / _START))
    return _E["degradation"]["reaction_penalty_at_empty"] * (1.0 - frac)
