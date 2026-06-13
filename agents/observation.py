"""Builds the decision context (facts + legal moves) and renders it to the band-based text the LLM
sees (PRD §10, step_example.md).

`build_context` is the engine-side feature engineering: range gating, openings, affordability, locks,
cornering. The scripted mock reads the dict directly; the LLM agent renders it with `render_observation`.
Raw health/energy numbers live in the context for the engine/mock but are NEVER rendered - only the
deterministic band phrases are (PRD §10.1).
"""
from engine.config import CONFIG
from engine import ring
from engine import boxer as B
from engine.energy import punch_energy

_PLACEMENTS = ("head_center", "head_left", "head_right", "body_left", "body_center")
_PUNCH_TYPES = ("jab", "cross", "hook", "uppercut")
_OBS = CONFIG["observation"]


def _band(value: float, table: list) -> str:
    for floor, phrase in table:  # tables are ordered high->low in config
        if value >= floor:
            return phrase
    return table[-1][1]


def energy_band(e: float) -> str:
    return _band(e, _OBS["energy_bands"])


def health_band(h: float) -> str:
    return _band(h, _OBS["health_bands"])


def _max_affordable_strength(energy: float) -> int:
    """Largest 0-10 strength affordable even at full speed (worst case), so any speed pick is valid."""
    for s in range(10, -1, -1):
        if punch_energy(s, 10) <= energy:
            return s
    return 0


def _hand_legal(hand: B.Hand, types_in_range: list[str], max_strength: int):
    if hand.locked():
        return "LOCKED"
    opts = ["guard", "free"]
    if types_in_range and max_strength >= 1:
        opts.append("punch")
    return opts


def _openings(opp: B.BoxerState) -> dict:
    """Loose read of which lines are open on the opponent given their guard (PRD §10, B1 simplification)."""
    guarding = opp.guarding()
    out = {}
    for p in _PLACEMENTS:
        if not guarding:
            out[p] = "OPEN"
        elif p.startswith("body"):
            out[p] = "partial"
        else:
            out[p] = "GUARDED"
    return out


def _hand_status(hand: B.Hand, t: float) -> str:
    if hand.state == B.WINDUP:
        return f"winding up a {hand.punch_type}"
    if hand.state == B.RECOVERY:
        return f"LOCKED - recovering, frees in +{max(0.0, hand.recovery_end - t):.2f}s"
    if hand.state == B.GUARD:
        return "up in guard"
    return "free"


def build_context(self_b: B.BoxerState, opp: B.BoxerState, t: float, round_seconds: float,
                  incoming: dict | None) -> dict:
    dist = ring.distance(self_b.pos, opp.pos)
    tir = ring.types_in_range(dist, self_b.attrs.get("reach", 75))
    max_s = _max_affordable_strength(self_b.energy)
    legal_steps = ring.legal_steps(self_b.pos, opp.pos, CONFIG["footwork"]["step_distance_ft"])
    can_defend = not self_b.in_defense()

    return {
        "t": t,
        "round_time_left": max(0.0, round_seconds - t),
        "self": {
            "name": self_b.name,
            "health": self_b.health, "energy": self_b.energy,         # raw - engine/mock only
            "health_band": health_band(self_b.health),
            "energy_band": energy_band(self_b.energy),
            "ratcheted": self_b.energy_ceiling < CONFIG["energy"]["start"],
            "left_status": _hand_status(self_b.left, t),
            "right_status": _hand_status(self_b.right, t),
            "cornered": ring.cornered(self_b.pos),
        },
        "opponent": {
            "name": opp.name,
            "health_band": health_band(opp.health),
            "energy_band": energy_band(opp.energy),
            "openings": _openings(opp),
            "last_action": opp.last_action_desc,
        },
        "range": {"dist": dist, "band": ring.range_band(dist)},
        "incoming": incoming,   # {punch_type, placement, can_react: "slip/block only" | "slip or counter"} or None
        "legal": {
            "left_hand": _hand_legal(self_b.left, tir, max_s),
            "right_hand": _hand_legal(self_b.right, tir, max_s),
            "footwork": legal_steps,
            "defense": ["slip_left", "slip_right", "duck"] if can_defend else [],
            "types_in_range": tir,
            "max_strength": max_s,
            "placements": _openings(opp),
        },
    }


_RANGE_LINE = {
    "pocket": "IN THE POCKET - every punch reaches.",
    "jab": "AT JAB RANGE - only the jab (and barely the cross) reaches; step in to land hooks/uppercuts.",
    "out": "OUT OF RANGE - nothing reaches; close the distance.",
}


def render_observation(ctx: dict) -> str:
    s, o, lg = ctx["self"], ctx["opponent"], ctx["legal"]
    L = []
    L.append(f"=== {ctx['round_time_left']:.1f}s left in the round ===\n")

    L.append(f"YOU ({s['name']}):")
    ratchet = " You've spent past your reserves - you won't fully get this energy back this round." if s["ratcheted"] else ""
    L.append(f"  Condition: {s['health_band']}; {s['energy_band']}.{ratchet}")
    L.append(f"  Left hand:  {s['left_status']}.")
    L.append(f"  Right hand: {s['right_status']}.")
    if s["cornered"]:
        L.append("  Position:   CORNERED against the ropes.")
    L.append("")

    L.append(f"OPPONENT ({o['name']}):")
    L.append(f"  Condition: {o['health_band']}; {o['energy_band']}.")
    if ctx["incoming"]:
        inc = ctx["incoming"]
        L.append(f"  JUST DID: threw a {inc['punch_type']} at your {inc['placement']}. {inc['can_react']}")
    else:
        L.append(f"  {o['last_action']}.")
    opens = ", ".join(f"{p}: {st}" for p, st in o["openings"].items())
    L.append(f"  Guard read: {opens}")
    L.append("")

    L.append(f"RANGE: {_RANGE_LINE[ctx['range']['band']]}")
    L.append("")

    L.append("YOUR LEGAL MOVES THIS STEP:")
    for hand_key, label in (("left_hand", "LEFT HAND"), ("right_hand", "RIGHT HAND")):
        h = lg[hand_key]
        if h == "LOCKED":
            L.append(f"  {label}: LOCKED - you do not set it this step.")
            continue
        line = f"  {label}: " + " | ".join(h)
        if "punch" in h:
            line += (f"   (punch types in range: {', '.join(lg['types_in_range'])}; "
                     f"max strength you can afford: {lg['max_strength']} - same for every type)")
        L.append(line)
    if lg["footwork"]:
        L.append("  FOOTWORK: " + " | ".join(lg["footwork"]) + "  (cannot combine with slip/duck)")
    if lg["defense"]:
        L.append("  DEFENSE (cannot also punch this step): " + " | ".join(lg["defense"]))
    L.append("")
    L.append("Return one JSON action: {left_hand, right_hand, footwork, defense, reasoning}. Omit a LOCKED hand.")
    return "\n".join(L)
