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


def block_multiplier(placement: str, defender_energy: float) -> float:
    """Fraction of a punch a block lets through. Body leaks at a flat factor. The HEAD guard tightens
    to block_factor while fresh, but SAGS as the blocker tires: below guard_sags_below_energy it lerps
    block_factor -> block_factor_sagging (reached at empty), so a gassed guard leaks the head shot the
    observation already reads as "sagging" (PRD §9.2)."""
    if placement.startswith("body"):
        return _H["body_block_factor"]
    base = _H["block_factor"]
    if defender_energy >= _SAG_AT:
        return base
    frac = (_SAG_AT - defender_energy) / _SAG_AT      # 0 at the threshold -> 1 at empty
    return base + (_H["block_factor_sagging"] - base) * frac


def raw_damage(punch_type: str, placement: str, strength: float,
               attacker_energy: float, land_quality: float,
               blocked: bool, contest_roll: float, defender_energy: float = 100.0) -> float:
    """The undivided punch potency before the health/energy split (PRD §9.2).
    land_quality: 1.0 clean, config glancing_mult at the edge of reach. contest_roll: seeded ~[0.9,1.1].
    defender_energy gates how much a HEAD guard sags (tired guards block worse)."""
    base = strength_value(punch_type, strength) * _H["damage_per_strength"]
    block_mult = block_multiplier(placement, defender_energy) if blocked else 1.0
    return (base
            * _H["punch_type_power_mult"][punch_type]
            * _H["placement_mult"][placement]
            * land_quality
            * output_factor(attacker_energy)
            * block_mult
            * contest_roll)


def split(raw: float, placement: str, defender_chin: float = _CHIN_BASELINE) -> tuple[float, float]:
    """Split raw potency into (health_damage, energy_damage). Head shots -> health, body shots -> energy.
    Defender chin divides health damage only (neutral at baseline)."""
    resistance = defender_chin / _CHIN_BASELINE
    health = raw * _H["placement_health_share"][placement] / resistance
    energy = raw * _H["placement_energy_share"][placement]
    return health, energy


def glancing_mult() -> float:
    return _H["glancing_mult"]
