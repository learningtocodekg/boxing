"""Verifies a DUCK is a standalone quick dodge: while it's still resolving you CANNOT punch (offense
offline — you bob and you're right back up, not crouched and trading), but you can still cover/move.
Once the duck window clears, punching is offered again. Mirrors the ROCKED enforcement (see test_rock.py)."""
from engine.boxer import make_boxer, GUARD, WINDUP
from engine.config import CONFIG
from sim.runner import _apply, Fight
from agents.observation import build_context
from replay.recorder import Recorder

_BASE = {"reach": 75, "height": 75, "power": 75, "agility": 75, "chin": 75, "stamina": 75}


def _rec():
    return Recorder({"scenario": "t", "seed": 1, "round_seconds": 60, "dt": 0.05, "config": {}})


def _pair():
    red = make_boxer("Red", [8.0, 7.1], dict(_BASE))     # 1.8 ft apart -> all punch types in range
    blue = make_boxer("Blue", [8.0, 8.9], dict(_BASE))
    return red, blue


def _punch_action():
    return {"left_hand": {"action": "punch", "punch_type": "hook", "placement": "head_center",
                          "strength": 8, "speed": 6},
            "right_hand": {"action": "guard"}, "footwork": None, "defense": None, "combo": [],
            "reasoning": "x"}


def test_ducking_fighter_cannot_punch():
    red, blue = _pair()
    red.defense = "duck"                       # mid-duck (window still resolving)
    threw = _apply(red, blue, _punch_action(), 1.0, Fight(), _rec())
    assert not threw and red.left.state != WINDUP, "no punching while still ducking"


def test_menu_drops_punch_while_ducking():
    red, blue = _pair()
    red.left.state = red.right.state = GUARD
    red.defense = "duck"
    ctx = build_context(red, blue, 1.0, 60.0, None)
    assert "punch" not in ctx["legal"]["left_hand"]
    assert "punch" not in ctx["legal"]["right_hand"]
    # once he's back up (duck cleared), punching is offered again
    red.defense = None
    ctx2 = build_context(red, blue, 1.0, 60.0, None)
    assert "punch" in ctx2["legal"]["left_hand"]


if __name__ == "__main__":
    for fn in list(globals().values()):
        if callable(fn) and getattr(fn, "__name__", "").startswith("test_"):
            fn()
    print("--- PASS --- duck: standalone quick dodge — can't punch while ducking (_apply guard + menu "
          "drops punch), punch offered again once back up")
