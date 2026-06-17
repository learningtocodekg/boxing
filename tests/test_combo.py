"""Verifies the COMBO mechanic: a lead punch + follow-ups schedules a flurry that fires alternating hands
faster than a normal single-punch reset, costs energy per shot, and commits the fighter (no re-decision)."""
from engine.boxer import make_boxer, WINDUP, RECOVERY, GUARD
from engine.config import CONFIG
from sim.runner import _apply, _advance, _fire_combo, _needs_decision, Fight
from replay.recorder import Recorder

_BASE = {"reach": 75, "height": 75, "power": 75, "agility": 75, "chin": 75, "stamina": 75}
_INTERVAL = CONFIG["timing"]["combo_interval"]
_DT = CONFIG["time"]["dt"]


def _setup():
    red = make_boxer("Red", [8.0, 7.1], dict(_BASE))    # 1.8 ft apart -> all punch types in range
    blue = make_boxer("Blue", [8.0, 8.9], dict(_BASE))
    return red, blue, Recorder({"scenario": "t", "seed": 1, "round_seconds": 60, "dt": 0.05, "config": {}})


def _advance_until_landed(b, hand):
    """Tick the loop forward until `hand` finishes its windup and is RECOVERING, like run_fight does each
    tick — a combo follow-up only fires once the previous shot has LANDED (no hand still winding up)."""
    t = 0.0
    while hand.state == WINDUP:
        t += _DT
        _advance(b, t, _DT)
    return t


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
    # while the lead (left) is still winding up, the follow-up does NOT fire — never two windups at once
    _fire_combo(red, _INTERVAL)
    assert len(red.combo_queue) == 1 and red.right.state != WINDUP
    # advance the lead past impact so it's RECOVERING (the real loop does this each tick)
    t = _advance_until_landed(red, red.left)
    assert red.left.state == RECOVERY
    # now the follow-up fires on the RIGHT hand, overriding the left's recovery
    _fire_combo(red, max(t, _INTERVAL))
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
    t = _advance_until_landed(red, red.left)             # lead lands, then the follow-up comes due
    _fire_combo(red, max(t, _INTERVAL))
    assert red.combo_queue == []                         # flurry dies — couldn't afford the shot
    assert red.right.state != WINDUP


def test_combo_never_two_windups_at_once():
    """The reported bug: a flurry must never have BOTH gloves winding up at the same instant (it read as
    'punching with both hands'). A power-shot combo's follow-up fires faster than a single reset but only
    once the previous punch has LANDED — so at every tick at most one hand is in WINDUP."""
    red, blue, rec = _setup()
    action = {"left_hand": {"action": "punch", "punch_type": "cross", "placement": "head_center",
                            "strength": 8, "speed": 6},                     # slow windup -> easy to overlap
              "right_hand": {"action": "guard"}, "footwork": None, "defense": None,
              "combo": [{"punch_type": "hook", "placement": "head_left", "strength": 8, "speed": 6},
                        {"punch_type": "cross", "placement": "head_center", "strength": 8, "speed": 6}],
              "reasoning": "3-punch flurry"}
    _apply(red, blue, action, 0.0, Fight(), rec)
    t = 0.0
    while t < 4.0 and (red.combo_queue or red.throwing()):  # run the flurry to completion
        t += _DT
        _advance(red, t, _DT)
        _fire_combo(red, t)
        assert not (red.left.state == WINDUP and red.right.state == WINDUP), \
            f"both hands winding up at t={t:.2f}"
    assert red.combo_queue == []                            # the whole flurry did fire


if __name__ == "__main__":
    test_combo_schedules_alternating_hands()
    test_combo_fires_and_costs_energy_and_overrides_recovery()
    test_combo_dies_when_gassed()
    test_combo_never_two_windups_at_once()
    print("--- PASS --- combo: scheduling, alternating hands, energy cost, recovery-override, "
          "gas-out, no-double-windup verified")
