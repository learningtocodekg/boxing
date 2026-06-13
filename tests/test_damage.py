"""Verifies the damage formula, the head-vs-body split, and block reduction (PRD §9)."""
from engine import damage as D


def approx(a, b, tol=0.02):
    return abs(a - b) <= tol


def test_clean_max_hook_to_chin():
    # s=10 hook, head_center, full energy, unblocked, neutral roll -> 5*1.6*1.20 = 9.6
    raw = D.raw_damage("hook", "head_center", 10, attacker_energy=100.0,
                       land_quality=1.0, blocked=False, contest_roll=1.0)
    assert approx(raw, 9.6), raw
    health, energy = D.split(raw, "head_center")
    assert approx(health, 9.6) and approx(energy, 0.96), (health, energy)


def test_body_shot_drains_energy_more_than_health():
    raw = D.raw_damage("hook", "body_left", 10, attacker_energy=100.0,
                       land_quality=1.0, blocked=False, contest_roll=1.0)  # 5*1.6*0.90 = 7.2
    assert approx(raw, 7.2), raw
    health, energy = D.split(raw, "body_left")          # 0.55 / 0.70
    assert approx(health, 3.96) and approx(energy, 5.04), (health, energy)
    assert energy > health  # body work gasses the opponent


def test_jab_uses_fixed_strength():
    # jab ignores the 10 effort -> uses fixed strength 3: 3*0.5*1.0*1.0(head_left) = 1.5
    raw = D.raw_damage("jab", "head_left", 10, attacker_energy=100.0,
                       land_quality=1.0, blocked=False, contest_roll=1.0)
    assert approx(raw, 1.5), raw


def test_block_heavily_reduces():
    clean = D.raw_damage("cross", "head_center", 8, 100.0, 1.0, False, 1.0)
    blocked = D.raw_damage("cross", "head_center", 8, 100.0, 1.0, True, 1.0)
    assert approx(blocked, clean * 0.20), (clean, blocked)


def test_body_leaks_past_guard():
    # A high guard stops the head (0.20x) but the body LEAKS more (0.55x) — dig the body vs a turtle.
    clean = D.raw_damage("hook", "body_left", 10, 100.0, 1.0, False, 1.0)
    blocked_body = D.raw_damage("hook", "body_left", 10, 100.0, 1.0, True, 1.0)
    blocked_head = D.raw_damage("hook", "head_center", 10, 100.0, 1.0, True, 1.0)
    assert approx(blocked_body, clean * 0.55), (clean, blocked_body)
    # body gets through a guard far better than the head does
    assert (blocked_body / clean) > (blocked_head /
            D.raw_damage("hook", "head_center", 10, 100.0, 1.0, False, 1.0))


def test_degraded_attacker_hits_softer():
    full = D.raw_damage("hook", "head_center", 10, 100.0, 1.0, False, 1.0)
    gassed = D.raw_damage("hook", "head_center", 10, 0.0, 1.0, False, 1.0)
    assert approx(gassed, full * 0.6), (full, gassed)


if __name__ == "__main__":
    for fn in [test_clean_max_hook_to_chin, test_body_shot_drains_energy_more_than_health,
               test_jab_uses_fixed_strength, test_block_heavily_reduces, test_body_leaks_past_guard,
               test_degraded_attacker_hits_softer]:
        fn()
    print("--- PASS --- damage: formula, head/body split, jab-fixed, block, degradation verified")
