"""Verifies distinct boxer attributes produce real mechanical differences (PRD §13 asymmetry).
Every effect must be a NO-OP at the 75 baseline (covered by the other suites staying green).
Run: .venv\\Scripts\\python.exe -m tests.test_roster   (from the boxing/ root)
"""
from engine import ring, damage, timing
from engine.energy import stamina_regen_mult
from engine.config import CONFIG

OUT = CONFIG["rosters"]["out_boxer"]   # tall, rangy, quick, fragile
PRE = CONFIG["rosters"]["pressure"]    # short, heavy-handed, granite


def test_baseline_is_noop():
    assert ring._reach_ft("jab", 75) == CONFIG["reach"]["jab"]
    assert ring._height_reach_adjust("head_center", 75, 75) == 0.0
    assert abs(damage.power_mult(75) - 1.0) < 1e-9
    assert abs(stamina_regen_mult(75) - 1.0) < 1e-9
    assert abs(ring.step_distance(75) - CONFIG["footwork"]["step_distance_ft"]) < 1e-9


def test_reach_and_height_geometry():
    # longer-armed boxer reaches farther
    assert ring._reach_ft("jab", OUT["reach"]) > ring._reach_ft("jab", PRE["reach"])

    def head(att, dfn):
        return ring._reach_ft("jab", att["reach"]) + ring._height_reach_adjust("head_center", att["height"], dfn["height"])

    def body(att, dfn):
        return ring._reach_ft("jab", att["reach"]) + ring._height_reach_adjust("body_center", att["height"], dfn["height"])

    # at a mid distance the tall rangy boxer tags the short man's head; the short man can't reach back upstairs
    d = 3.0
    assert head(OUT, PRE) >= d > head(PRE, OUT)
    # but the short pressure fighter reaches the tall man's BODY more easily than his head
    assert body(PRE, OUT) > head(PRE, OUT)


def test_power_and_agility_and_stamina():
    # same str-8 cross: the heavier-handed boxer does more damage
    args = ("cross", "head_center", 8, 100, 1.0, False, 1.0, 100)
    assert damage.raw_damage(*args, PRE["power"]) > damage.raw_damage(*args, OUT["power"])
    # the quicker boxer has a shorter windup and reacts sooner, and steps farther
    assert timing.windup_time("jab", 8, OUT["agility"]) < timing.windup_time("jab", 8, PRE["agility"])
    assert timing.reaction_delay(OUT["agility"]) < timing.reaction_delay(PRE["agility"])
    assert ring.step_distance(OUT["agility"]) > ring.step_distance(PRE["agility"])
    # the deeper gas tank recovers faster
    assert stamina_regen_mult(OUT["stamina"]) > stamina_regen_mult(PRE["stamina"])


if __name__ == "__main__":
    test_baseline_is_noop()
    test_reach_and_height_geometry()
    test_power_and_agility_and_stamina()
    print("--- PASS --- roster: reach/height/power/agility/stamina asymmetry verified, baseline no-op")
