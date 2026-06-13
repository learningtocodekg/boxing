"""Verifies the energy module against the design anchors and the ratchet (PRD §5).
Run: .venv\\Scripts\\python.exe -m tests.test_energy   (from the boxing/ root)
"""
from engine import energy as E


def approx(a, b, tol=0.02):
    return abs(a - b) <= tol


def test_punch_energy_anchors():
    assert approx(E.punch_energy(10, 10), 3.0), E.punch_energy(10, 10)
    assert approx(E.punch_energy(10, 1), 1.0), E.punch_energy(10, 1)
    assert approx(E.punch_energy(1, 10), 0.5), E.punch_energy(1, 10)
    assert approx(E.punch_energy(0, 0), 0.0)
    # type-independence is structural: punch_energy takes no punch_type argument.


def test_ratchet_only_lowers_and_caps_regen():
    ceiling = 100.0
    # drop to 56 -> ceiling should ratchet to 75
    ceiling = E.lower_ceiling(56.0, ceiling)
    assert ceiling == 75.0, ceiling
    # regen from 56 can approach but never exceed 75
    e = 56.0
    for _ in range(1000):
        e = E.regen(e, ceiling, 0.05)
    assert approx(e, 75.0, 0.001) and e <= 75.0, e
    # dip below 50 -> ceiling ratchets to 50 and never returns to 75
    ceiling = E.lower_ceiling(40.0, ceiling)
    assert ceiling == 50.0, ceiling
    ceiling = E.lower_ceiling(50.0, ceiling)  # back up to 50 exactly must NOT lift the cap
    assert ceiling == 50.0, ceiling
    # below 25 -> 25
    ceiling = E.lower_ceiling(10.0, ceiling)
    assert ceiling == 25.0, ceiling


def test_degradation_curve():
    assert approx(E.output_factor(100.0), 1.0)
    assert approx(E.output_factor(0.0), 0.6)
    assert approx(E.output_factor(50.0), 0.8)
    assert approx(E.reaction_penalty(100.0), 0.0)
    assert approx(E.reaction_penalty(0.0), 0.12)


if __name__ == "__main__":
    test_punch_energy_anchors()
    test_ratchet_only_lowers_and_caps_regen()
    test_degradation_curve()
    print("--- PASS --- energy: anchors, ratchet, degradation all verified")
