"""ScriptedBoxer — the deterministic mock opponent for B1 (PRD §2). Reads the decision context dict
directly (no LLM). Aggressive when in range with energy; blocks/slips threats; closes when out of range;
circles to breathe when gassed. Exercises every move type so the engine and viewer can be verified.
"""
from engine.config import CONFIG

_GASSED = 22.0  # raw energy below which the mock backs off to recover


class ScriptedBoxer:
    def __init__(self, name: str):
        self.name = name
        self.call_count = 0
        self.parse_errors = 0

    def decide(self, ctx: dict) -> dict:
        self.call_count += 1
        lg = ctx["legal"]
        me = ctx["self"]
        inc = ctx["incoming"]
        band = ctx["range"]["band"]
        free = [h for h in ("right_hand", "left_hand") if lg[h] != "LOCKED"]

        act = {"left_hand": None, "right_hand": None, "footwork": None, "defense": None, "reasoning": ""}
        for h in free:
            act[h] = {"action": "guard"}  # default: free hands hold guard

        # Gassed -> circle and breathe (unless under fire).
        if me["energy"] < _GASSED and not inc:
            act["footwork"] = "circle_left" if "circle_left" in lg["footwork"] else "none"
            act["reasoning"] = "gassed — circle out and breathe"
            return act

        # Under fire -> slip a head shot, else block.
        if inc and free:
            if inc["placement"].startswith("head") and lg["defense"]:
                slip = "slip_left" if inc["placement"] in ("head_right", "head_center") else "slip_right"
                if slip in lg["defense"]:
                    act["defense"] = slip
                    act["reasoning"] = f"slip his {inc['punch_type']}"
                    return act
            act["reasoning"] = "block up"
            return act

        # Out of range -> close the distance.
        if band != "pocket" and not lg["types_in_range"] and "forward" in lg["footwork"]:
            act["footwork"] = "forward"
            act["reasoning"] = "close the distance"
            return act

        # In range -> rip a punch with a free hand at an open line.
        puncher = free[0] if free else None
        if puncher and "punch" in lg[puncher] and lg["max_strength"] >= 1:
            opens = [p for p, st in lg["placements"].items() if st == "OPEN"]
            target = opens[0] if opens else "body_left"
            tir = lg["types_in_range"]
            if target.startswith("body") and "hook" in tir:
                ptype = "hook"
            elif "cross" in tir:
                ptype = "cross"
            else:
                ptype = tir[0]
            act[puncher] = {"action": "punch", "punch_type": ptype, "placement": target,
                            "strength": min(lg["max_strength"], 7), "speed": 6}
            if "forward" in lg["footwork"] and band != "pocket":
                act["footwork"] = "forward"
            act["reasoning"] = f"{ptype} to {target}"
            return act

        act["reasoning"] = "reset"
        return act
