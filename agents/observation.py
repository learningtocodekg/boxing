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


def _hand_legal(hand: B.Hand, other: B.Hand, types_in_range: list[str], max_strength: int):
    if hand.locked():
        return "LOCKED"
    opts = ["guard", "free"]
    # Only one hand throws at a time — no punch offered while the other hand is mid-punch/recovering.
    if types_in_range and max_strength >= 1 and not other.busy():
        opts.append("punch")
    return opts


# Which hand covers each line (orthodox, identical boxers). A hand only covers its side while it's
# held in GUARD; mid-punch / recovering / down, that side is exposed. head_center sits behind the high
# guard — it stays covered while EITHER hand is up, so it only opens when both hands are off it.
_COVER = {
    "head_left":   ("left",),
    "body_left":   ("left",),
    "head_right":  ("right",),
    "body_center": ("right",),
    "head_center": ("left", "right"),
}


def _openings(opp: B.BoxerState) -> dict:
    """Per-line read of what's open on the opponent, from his actual hand states + fatigue.

    A line is OPEN when no covering hand is guarding it — a hand that is winding up, recovering
    (stuck out), or down is not protecting its side, so that side is there for the taking (this is
    the counter window right after he throws). A guarded BODY line still LEAKS (partial); a guarded
    HEAD line SAGS open once he's gassed and can't keep the high guard up.
    """
    tired = opp.energy < _OBS["guard_sags_below_energy"]
    out = {}
    for p, hands in _COVER.items():
        covering = [getattr(opp, hn) for hn in hands]
        guarded = (any if p == "head_center" else all)(h.guarding() for h in covering)
        if not guarded:
            out[p] = "OPEN"
        elif p.startswith("body"):
            out[p] = "partial"
        elif tired:
            out[p] = "sagging"
        else:
            out[p] = "GUARDED"
    return out


# Per-stat matchup read: (advantage phrase, disadvantage phrase). Only shown when the gap is notable,
# so each boxer is told its real edges and holes and can fight to type.
_MATCHUP_MIN_GAP = 8
_MATCHUP = {
    "reach": ("REACH: you're longer — at the end of your jab/cross you hit him and he CANNOT reach back. Plant at that range; the moment he closes, pivot or step out and reset it. Brawling in tight throws this edge away.",
              "REACH: he's longer — out at distance he hits you for free and you land nothing. Don't sit there eating shots: close the gap behind a punch and get into the pocket where you're dangerous."),
    "height": ("HEIGHT: you're taller — his head is low and easy to reach; punch down and keep him at the end of your range. Mind your body, he'll dig underneath.",
               "HEIGHT: he's taller — his head is hard to reach from outside, but his BODY is right in front of you. Get inside, rip the body to drag his guard down, THEN go up top."),
    "power": ("POWER: your hands are heavier — every clean shot costs him more than his cost you. Don't paw; string real combinations and make him pay when he opens up.",
              "POWER: he punches harder — you lose a bomb-for-bomb trade. But lighter does NOT mean pawing jabs all night: throw real shots — cross, hook, uppercut — to actually take his health. Just put them in combinations and slide off, don't plant and swap power in the pocket."),
    "agility": ("SPEED: you're quicker — beat him to the punch, hit and slide off, and you can slip him clean. Make it a speed fight.",
                "SPEED: he's quicker — you'll lose a slip-and-dart race. Cut the ring off, make it physical, and time one big shot instead of racing his hands."),
    "chin": ("CHIN: you take a shot — you can afford to walk through one to land yours. Use it.",
             "CHIN: your chin is suspect — one clean power shot can flip this. Do NOT get caught clean upstairs; defend the head first."),
    "stamina": ("GAS: you last longer — push the pace late, he fades first.",
                "GAS: you tire sooner — pick your spots, don't empty the tank in early firefights you'll fade in."),
}


def _matchup(self_b: B.BoxerState, opp: B.BoxerState) -> list[str]:
    out = []
    for stat, (adv, dis) in _MATCHUP.items():
        diff = self_b.attrs.get(stat, 75) - opp.attrs.get(stat, 75)
        if diff >= _MATCHUP_MIN_GAP:
            out.append(adv)
        elif diff <= -_MATCHUP_MIN_GAP:
            out.append(dis)
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
    legal_steps = ring.legal_steps(self_b.pos, opp.pos, ring.step_distance(self_b.attrs.get("agility", 75)))
    can_defend = not self_b.in_defense()

    return {
        "t": t,
        "round_time_left": max(0.0, round_seconds - t),
        "matchup": _matchup(self_b, opp),
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
            "health": opp.health, "energy": opp.energy,               # raw - shown when vitals_display=exact
            "health_band": health_band(opp.health),
            "energy_band": energy_band(opp.energy),
            "openings": _openings(opp),
            "last_action": opp.last_action_desc,
        },
        "range": {"dist": dist, "band": ring.range_band(dist)},
        "incoming": incoming,   # {punch_type, placement, can_react: "slip/block only" | "slip or counter"} or None
        "legal": {
            "left_hand": _hand_legal(self_b.left, self_b.right, tir, max_s),
            "right_hand": _hand_legal(self_b.right, self_b.left, tir, max_s),
            "footwork": legal_steps,
            "defense": ["slip_left", "slip_right", "duck"] if can_defend else [],
            "types_in_range": tir,
            "max_strength": max_s,
            "placements": _openings(opp),
        },
    }


_RANGE_LINE = {
    "pocket": "IN THE POCKET - every punch reaches, his too; stand square and you trade. Cut an angle to land clean.",
    "jab": "AT JAB RANGE - your jab (and barely the cross) reaches, but his hooks/uppercuts CAN'T reach you here. A safe place to measure him and bank energy; step in to land power.",
    "out": "OUT OF RANGE - nothing reaches either way. You're safe: step in to work, or stay out and get your wind back.",
}


def _vitals(d: dict) -> str:
    """Health/energy line. Raw numbers (out of 100) when vitals_display=exact, else the band phrase."""
    if CONFIG["observation"]["vitals_display"] == "exact":
        return f"health {d['health']:.0f}/100, energy {d['energy']:.0f}/100"
    return f"{d['health_band']}; {d['energy_band']}"


def render_observation(ctx: dict) -> str:
    s, o, lg = ctx["self"], ctx["opponent"], ctx["legal"]
    L = []
    L.append(f"=== {ctx['round_time_left']:.1f}s left in the round ===\n")

    L.append(f"YOU ({s['name']}):")
    ratchet = " You've spent past your reserves - you won't fully get this energy back this round." if s["ratcheted"] else ""
    L.append(f"  Condition: {_vitals(s)}.{ratchet}")
    L.append(f"  Left hand:  {s['left_status']}.")
    L.append(f"  Right hand: {s['right_status']}.")
    if s["cornered"]:
        L.append("  Position:   CORNERED against the ropes.")
    L.append("")

    L.append(f"OPPONENT ({o['name']}):")
    L.append(f"  Condition: {_vitals(o)}.")
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

    if ctx.get("matchup"):
        L.append("YOUR EDGE IN THIS MATCHUP (fight to your strengths, hide your weaknesses):")
        for line in ctx["matchup"]:
            L.append(f"  - {line}")
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
