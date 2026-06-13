"""Parse + validate the LLM's JSON action against the legal-move context (PRD §11).

Any malformed or illegal pick falls back to a safe default (free hands -> guard, no footwork/defense),
so the engine can never receive an impossible action.
"""
import json

_PLACEMENTS = ("head_center", "head_left", "head_right", "body_left", "body_center")
_PUNCH_TYPES = ("jab", "cross", "hook", "uppercut")
_DEFENSES = ("slip_left", "slip_right", "duck")


def safe_default(ctx: dict, reasoning: str = "fallback: cover up") -> dict:
    act = {"footwork": None, "defense": None, "reasoning": reasoning}
    for hk in ("left_hand", "right_hand"):
        act[hk] = None if ctx["legal"][hk] == "LOCKED" else {"action": "guard"}
    return act


def _clamp(v, lo=0, hi=10):
    try:
        return max(lo, min(hi, int(round(float(v)))))
    except (TypeError, ValueError):
        return lo


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1] if raw.count("```") >= 2 else raw.strip("`")
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]
    i, j = raw.find("{"), raw.rfind("}")
    return raw[i:j + 1] if i != -1 and j != -1 else raw


def _validate_hand(hand, legal_opts, ctx):
    """Return a clean hand action or None (which the runner treats as 'leave as-is/guard')."""
    if legal_opts == "LOCKED" or not isinstance(hand, dict):
        return None
    action = hand.get("action")
    if action not in legal_opts:
        return {"action": "guard"} if "guard" in legal_opts else None
    if action in ("guard", "free"):
        return {"action": action}
    # punch
    pt = hand.get("punch_type")
    pl = hand.get("placement")
    if pt not in ctx["legal"]["types_in_range"] or pl not in _PLACEMENTS:
        return {"action": "guard"}
    strength = _clamp(hand.get("strength", 5))
    if strength > ctx["legal"]["max_strength"]:
        strength = ctx["legal"]["max_strength"]
    return {"action": "punch", "punch_type": pt, "placement": pl,
            "strength": strength, "speed": _clamp(hand.get("speed", 5))}


def parse_action(raw: str, ctx: dict) -> dict:
    try:
        data = json.loads(_strip_fences(raw))
    except (json.JSONDecodeError, TypeError):
        return safe_default(ctx, "parse_error")
    if not isinstance(data, dict):
        return safe_default(ctx, "parse_error")

    defense = data.get("defense")
    defense = defense if defense in _DEFENSES and defense in ctx["legal"]["defense"] else None

    left = _validate_hand(data.get("left_hand"), ctx["legal"]["left_hand"], ctx)
    right = _validate_hand(data.get("right_hand"), ctx["legal"]["right_hand"], ctx)

    footwork = data.get("footwork")
    footwork = footwork if footwork in ctx["legal"]["footwork"] else None

    # Legality: slip/duck is a STANDALONE move — it cannot combine with a punch or a step (PRD §8).
    # If the model specified both, honor the DEFENSE (it is trying to avoid an incoming shot) and drop
    # the punch/step; the counter comes on a later step. The engine ignores the hands while defending.
    if defense is not None:
        footwork = None
        left = right = None

    return {
        "left_hand": left,
        "right_hand": right,
        "footwork": footwork,
        "defense": defense,
        "reasoning": str(data.get("reasoning", ""))[:400],
    }
