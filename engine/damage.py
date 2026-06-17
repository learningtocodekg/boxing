"""Damage resolution at a punch's IMPACT tick (PRD §9). Pure/deterministic: the seeded contest
roll is passed in by the caller (sim/runner), so this module is fully unit-testable."""
from .config import CONFIG
from .energy import output_factor

_H = CONFIG["health"]
_SAG_AT = CONFIG["observation"]["guard_sags_below_energy"]  # same threshold the observation reads "sagging"
_CHIN_BASELINE = 75.0  # roster baseline; chin == baseline -> no resistance effect (identical boxers, v1)


def strength_value(punch_type: str, strength: float) -> float:
    """Jab uses a fixed strength; other punches use the LLM's 0-10 effort."""
    return _H["jab_fixed_strength"] if punch_type == "jab" else strength


def block_multiplier(placement: str, defender_energy: float, punch_type: str = "jab") -> float:
    """Fraction of a punch a block lets through. Body leaks at a flat factor. The HEAD guard tightens
    to block_factor while fresh, but SAGS as the blocker tires: below guard_sags_below_energy it lerps
    block_factor -> block_factor_sagging (reached at empty), so a gassed guard leaks the head shot the
    observation already reads as "sagging" (PRD §9.2).

    The sag-leak scales with PUNCH POWER: a tired arm can't absorb a heavy shot's momentum, so a sagging
    guard barely slows a hook/uppercut but still partly parries a light jab. The extra leak past a fresh
    guard is multiplied by the punch's power_mult (jab 1.0 -> unchanged; hook 1.6 -> blasts through),
    capped at letting the whole punch land. This is what makes loading up the power shot pay off once his
    guard sags, instead of cracking a tired guard cheaply with the jab."""
    if placement.startswith("body"):
        return _H["body_block_factor"]
    base = _H["block_factor"]
    if defender_energy >= _SAG_AT:
        return base
    frac = (_SAG_AT - defender_energy) / _SAG_AT      # 0 at the threshold -> 1 at empty
    power = _H["punch_type_power_mult"][punch_type]   # jab 1.0; heavier punches leak a sagging guard more
    return min(1.0, base + (_H["block_factor_sagging"] - base) * frac * power)


def power_mult(attacker_power: float) -> float:
    """A stronger boxer's same 0-10 punch lands a bit harder (no-op at the 75 baseline)."""
    return 1.0 + (attacker_power - _CHIN_BASELINE) / _CHIN_BASELINE * _H["power_scale"]


def vulnerability_mult(defender_energy: float) -> float:
    """How much MORE health damage a tired defender takes. A gassed fighter can't roll with a shot, his
    guard is down and his legs are gone, so the same clean punch hurts him more — health damage scales up
    as his energy falls (1.0 at full -> 1 + hurt_vulnerability_scale at empty). This is what makes HEALTH
    accelerate to 0 (the KO) before energy flatlines: you get rocked harder the more spent you are. It
    touches HEALTH damage only — body shots still drain energy at the flat rate."""
    frac = max(0.0, min(1.0, defender_energy / _H["start"]))
    return 1.0 + (1.0 - frac) * _H["hurt_vulnerability_scale"]


def raw_damage(punch_type: str, placement: str, strength: float,
               attacker_energy: float, land_quality: float,
               blocked: bool, contest_roll: float, defender_energy: float = 100.0,
               attacker_power: float = _CHIN_BASELINE) -> float:
    """The undivided punch potency before the health/energy split (PRD §9.2).
    land_quality: 1.0 clean, config glancing_mult at the edge of reach. contest_roll: seeded ~[0.9,1.1].
    defender_energy gates how much a HEAD guard sags (tired guards block worse). attacker_power scales
    the punch's potency by the attacker's strength attribute."""
    base = strength_value(punch_type, strength) * _H["damage_per_strength"]
    block_mult = block_multiplier(placement, defender_energy, punch_type) if blocked else 1.0
    return (base
            * _H["punch_type_power_mult"][punch_type]
            * _H["placement_mult"][placement]
            * land_quality
            * output_factor(attacker_energy)
            * block_mult
            * power_mult(attacker_power)
            * contest_roll)


def split(raw: float, placement: str, defender_chin: float = _CHIN_BASELINE,
          defender_energy: float = 100.0) -> tuple[float, float]:
    """Split raw potency into (health_damage, energy_damage). Head shots -> health, body shots -> energy.
    Defender chin divides health damage only (neutral at baseline). A tired defender takes MORE health
    damage (vulnerability_mult) — that's what lets health reach 0 before energy does."""
    resistance = defender_chin / _CHIN_BASELINE
    health = raw * _H["placement_health_share"][placement] / resistance * vulnerability_mult(defender_energy)
    energy = raw * _H["placement_energy_share"][placement]
    return health, energy


def glancing_mult() -> float:
    return _H["glancing_mult"]
