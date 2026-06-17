"""Verifies the COMBO mechanic: a lead punch + follow-ups schedules a flurry that fires alternating hands
faster than a normal single-punch reset, costs energy per shot, and commits the fighter (no re-decision)."""
from engine.boxer import make_boxer, WINDUP, RECOVERY, GUARD
from engine.config import CONFIG
from sim.runner import _apply, _fire_combo, _needs_decision, Fight
from replay.recorder import Recorder

_BASE = {"reach": 75, "height": 75, "power": 75, "agility": 75, "chin": 75, "stamina": 75}
_INTERVAL = CONFIG["timing"]["combo_interval"]


def _setup():
    red = make_boxer("Red", [8.0, 7.1], dict(_BASE))    # 1.8 ft apart -> all punch types in range
    blue = make_boxer("Blue", [8.0, 8.9], dict(_BASE))
    return red, blue, Recorder({"scenario": "t", "seed": 1, "round_seconds": 60, "dt": 0.05, "config": {}})


def test_combo_schedules_alternating_hands():
    red, blue, rec = _setup()
    action = {"left_hand": {"action": "punch", "punch_type": "jab", "placement": "head_center",
                            "strength": 3, "speed": 6},
              "right_hand": {"action": "guard"}, "footwork": None, "defense": None,
              "combo": [{"punch_type": "cross", "placement": "head_center", "strength": 7, "speed": 6},
                        {"punch_type": "hook", "placement": "head_left", "strength": 7, "speed": 6}],
              "reasoning": "flurry"}
    threw = _apply(red, blue, action, 0.0, Fight(), rec)
    assert threw and red.left.state == WINDUP, red.left.state
    # two follow-ups, alternating from the hand OPPOSITE the lead (lead=left -> right, then left)
    assert len(red.combo_queue) == 2, red.combo_queue
    assert [h for _, _, h in red.combo_queue] == ["right", "left"]
    assert abs(red.combo_queue[0][0] - _INTERVAL) < 1e-9
    assert abs(red.combo_queue[1][0] - 2 * _INTERVAL) < 1e-9
    # mid-combo the fighter is committed: not asked to decide again
    assert not _needs_decision(red, blue, _INTERVAL, first_punch=True)


def test_combo_fires_and_costs_energy_and_overrides_recovery():
    red, blue, rec = _setup()
    action = {"left_hand": {"action": "punch", "punch_type": "jab", "placement": "head_center",
                            "strength": 3, "speed": 6},
              "right_hand": {"action": "guard"}, "footwork": None, "defense": None,
              "combo": [{"punch_type": "cross", "placement": "head_center", "strength": 7, "speed": 6}],
              "reasoning": "1-2"}
    _apply(red, blue, action, 0.0, Fight(), rec)
    e_after_lead = red.energy
    assert e_after_lead < CONFIG["energy"]["start"]      # lead punch cost energy
    # not yet due
    _fire_combo(red, _INTERVAL - 0.01)
    assert len(red.combo_queue) == 1
    # the lead (left) hand is past impact and RECOVERING by now; the follow-up is on the RIGHT hand
    _fire_combo(red, _INTERVAL)
    assert red.combo_queue == []
    assert red.right.state == WINDUP and red.right.punch_type == "cross"
    assert red.energy < e_after_lead                     # the follow-up cost more energy


def test_combo_dies_when_gassed():
    red, blue, rec = _setup()
    red.energy = 1.0                                     # not enough for the follow-up power shot
    action = {"left_hand": {"action": "punch", "punch_type": "jab", "placement": "head_center",
                            "strength": 3, "speed": 1},
              "right_hand": {"action": "guard"}, "footwork": None, "defense": None,
              "combo": [{"punch_type": "hook", "placement": "head_center", "strength": 9, "speed": 8}],
              "reasoning": "overreach"}
    _apply(red, blue, action, 0.0, Fight(), rec)
    _fire_combo(red, _INTERVAL)
    assert red.combo_queue == []                         # flurry dies — couldn't afford the shot
    assert red.right.state != WINDUP


if __name__ == "__main__":
    test_combo_schedules_alternating_hands()
    test_combo_fires_and_costs_energy_and_overrides_recovery()
    test_combo_dies_when_gassed()
    print("--- PASS --- combo: scheduling, alternating hands, energy cost, recovery-override, gas-out verified")
