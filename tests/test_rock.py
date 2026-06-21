"""Verifies the ROCKED (stun) mechanic: a CLEAN POWER shot that lands hard stuns the defender for a beat
— offense goes offline (can't punch/combo, his own windup+combo are aborted) while defense stays intact —
and the land event carries a light/medium/hard tier for the animation. A jab or a blocked shot never rocks,
and a fresh (small-damage) shot is shrugged off."""
from engine.boxer import make_boxer, Hand, WINDUP, GUARD, FREE
from engine.config import CONFIG
from engine import damage
from sim.runner import _impact, _apply, Fight
from sim.seeds import make_rng
from agents.observation import build_context
from replay.recorder import Recorder

_BASE = {"reach": 75, "height": 75, "power": 75, "agility": 75, "chin": 75, "stamina": 75}
_R = CONFIG["rock"]


def _rec():
    return Recorder({"scenario": "t", "seed": 1, "round_seconds": 60, "dt": 0.05, "config": {}})


def _pair():
    red = make_boxer("Red", [8.0, 7.1], dict(_BASE))     # 1.8 ft apart -> all punch types in range
    blue = make_boxer("Blue", [8.0, 8.9], dict(_BASE))
    return red, blue


# ---- pure classification ----

def test_jab_never_rocks():
    assert damage.rock_severity("jab", "head_center", 99.0, 0.0, blocked=False) == "none"


def test_blocked_power_shot_never_rocks():
    assert damage.rock_severity("hook", "head_center", 99.0, 0.0, blocked=True) == "none"


def test_head_tiers_scale_by_health_damage():
    f = lambda hd: damage.rock_severity("hook", "head_center", hd, 0.1, blocked=False)
    assert f(_R["head_dmg"]["light"] - 0.1) == "none"
    assert f(_R["head_dmg"]["light"]) == "light"
    assert f(_R["head_dmg"]["medium"]) == "medium"
    assert f(_R["head_dmg"]["hard"]) == "hard"


def test_body_tiers_scale_by_energy_damage():
    f = lambda ed: damage.rock_severity("hook", "body_left", 0.1, ed, blocked=False)
    assert f(_R["body_dmg"]["light"] - 0.1) == "none"
    assert f(_R["body_dmg"]["light"]) == "light"
    assert f(_R["body_dmg"]["hard"]) == "hard"


def test_duration_scales_with_tier_and_body_is_shorter():
    assert damage.rock_duration("light", "head_center") < damage.rock_duration("hard", "head_center")
    # same tier: a body rock lasts less than a head rock
    assert damage.rock_duration("hard", "body_left") < damage.rock_duration("hard", "head_center")
    assert damage.rock_duration("none", "head_center") == 0.0


# ---- integration through _impact ----

def _landed_hand(pt, pl, strength):
    h = Hand(state=WINDUP, punch_type=pt, placement=pl, strength=strength, speed=6)
    h.impact_pending = True
    return h


def test_clean_power_head_shot_rocks_and_aborts_own_offense():
    red, blue = _pair()
    blue.left.state = blue.right.state = FREE          # not guarding -> the shot lands clean
    blue.rocked_until = 0.0
    blue.combo_queue = [(0.3, {"punch_type": "cross"}, "left")]   # his pending offense...
    blue.right.state = WINDUP                                      # ...and a glove he's winding up
    rec = _rec()
    _impact(red, blue, _landed_hand("hook", "head_center", 9), 1.0, make_rng(1), Fight(), rec)
    assert blue.rocked(1.0), "a clean hard hook upstairs should rock him"
    assert blue.combo_queue == [], "getting rocked aborts his pending combo"
    assert blue.right.state != WINDUP, "getting rocked aborts his own windup"
    land = [e for e in rec._events if e["kind"] == "land"][-1]
    assert land["rock"] in ("light", "medium", "hard")


def test_fresh_jab_does_not_rock():
    red, blue = _pair()
    blue.left.state = blue.right.state = FREE
    rec = _rec()
    _impact(red, blue, _landed_hand("jab", "head_center", 3), 1.0, make_rng(1), Fight(), rec)
    assert not blue.rocked(1.0)
    land = [e for e in rec._events if e["kind"] == "land"][-1]
    assert land["rock"] == "none"


# ---- enforcement: rocked = can't punch, but can still defend ----

def _punch_action():
    return {"left_hand": {"action": "punch", "punch_type": "hook", "placement": "head_center",
                          "strength": 8, "speed": 6},
            "right_hand": {"action": "guard"}, "footwork": None, "defense": None, "reasoning": "x"}


def test_rocked_fighter_cannot_punch_but_can_defend():
    red, blue = _pair()
    red.rocked_until = 5.0
    # tries to punch while rocked -> the hand just holds guard, no windup
    threw = _apply(red, blue, _punch_action(), 1.0, Fight(), _rec())
    assert not threw and red.left.state != WINDUP
    # but a slip still works while rocked
    _apply(red, blue, {"left_hand": None, "right_hand": None, "footwork": None,
                       "defense": "slip_left", "reasoning": "cover"}, 1.0, Fight(), _rec())
    assert red.defense == "slip_left"


def test_menu_drops_punch_while_rocked():
    red, blue = _pair()
    red.left.state = red.right.state = GUARD
    red.rocked_until = 5.0
    ctx = build_context(red, blue, 1.0, 60.0, None)
    assert "punch" not in ctx["legal"]["left_hand"]
    assert "punch" not in ctx["legal"]["right_hand"]
    assert ctx["self"]["rocked"] is True
    # once the stun clears, punching is offered again
    ctx2 = build_context(red, blue, 6.0, 60.0, None)
    assert "punch" in ctx2["legal"]["left_hand"]


if __name__ == "__main__":
    for fn in list(globals().values()):
        if callable(fn) and getattr(fn, "__name__", "").startswith("test_"):
            fn()
    print("--- PASS --- rock: classification (jab/blocked/tiers/duration), _impact stun + offense-abort + "
          "JSON tier, and enforcement (can't punch / can defend / menu drops punch) verified")
