"""Verifies the strength/speed -> timing model and the one-hand-at-a-time rule (PRD §4.3).
Run: .venv\\Scripts\\python.exe -m tests.test_timing   (from the boxing/ root)
"""
from engine import timing
from engine.boxer import make_boxer, WINDUP, GUARD
from sim.runner import _apply, Fight
from replay.recorder import Recorder


def _punch(pt, pl, s, v):
    return {"action": "punch", "punch_type": pt, "placement": pl, "strength": s, "speed": v}


def test_recovery_strength_dominates_speed_trims():
    # A committed power shot stays exposed far longer than a snappy jab; speed only trims recovery.
    jab = timing.recovery_time("jab", 3, 9)        # light + fast -> snaps back
    cross = timing.recovery_time("cross", 9, 9)    # heavy -> slow reset
    assert cross > 1.7 * jab, (jab, cross)
    # for a fixed punch, a faster (snappier) hand resets quicker, but not by much (strength dominant)
    slow = timing.recovery_time("cross", 9, 0)
    fast = timing.recovery_time("cross", 9, 10)
    assert fast < slow, (fast, slow)
    assert fast > 0.8 * slow, (fast, slow)


def test_strong_shot_forced_fast():
    # A strong shot can't be thrown slowly (momentum) -> stored speed is floored at strength.
    red, blue = make_boxer("R", [8, 7], {"reach": 75, "hand_speed": 75}), make_boxer("B", [8, 8.5], {})
    _apply(red, blue, {"left_hand": _punch("cross", "head_center", 9, 1),
                       "right_hand": {"action": "guard"}, "footwork": None, "defense": None}, 0.0,
           Fight(), Recorder({}))
    assert red.left.speed == 9, red.left.speed   # max(speed 1, strength 9)


def test_one_hand_punches_at_a_time():
    red, blue = make_boxer("R", [8, 7], {"reach": 75, "hand_speed": 75}), make_boxer("B", [8, 8.5], {})
    rec, f = Recorder({}), Fight()
    # both hands asked to punch in one decision -> exactly one throws, the other holds guard
    _apply(red, blue, {"left_hand": _punch("jab", "head_center", 3, 8),
                       "right_hand": _punch("cross", "head_center", 8, 8),
                       "footwork": None, "defense": None}, 0.0, f, rec)
    assert (red.left.state == WINDUP) ^ (red.right.state == WINDUP), (red.left.state, red.right.state)
    assert red.right.state == GUARD, red.right.state
    # the free hand can't start a punch while the other is mid-punch
    _apply(red, blue, {"left_hand": None, "right_hand": _punch("jab", "head_center", 3, 8),
                       "footwork": None, "defense": None}, 0.1, f, rec)
    assert red.right.state == GUARD, red.right.state


if __name__ == "__main__":
    test_recovery_strength_dominates_speed_trims()
    test_strong_shot_forced_fast()
    test_one_hand_punches_at_a_time()
    print("--- PASS --- timing: recovery model + strong-forced-fast + one-hand-at-a-time verified")
