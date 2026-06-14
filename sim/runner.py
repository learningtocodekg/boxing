"""run_fight() — the main loop (PRD §4). Continuous tick at dt; OPENING polls both boxers until the
first punch, then LIVE event-driven decision steps with the reaction-delay model. Deterministic given
the seed (the only RNG is the contest roll).
"""
from pathlib import Path
import yaml

from engine.config import CONFIG
from engine import ring, damage
from engine import boxer as B
from engine.boxer import make_boxer, Hand, WINDUP, RECOVERY, FREE, GUARD
from engine.energy import punch_energy, regen, lower_ceiling, reaction_penalty as energy_react_pen
from engine import timing
from engine.state_machine import FightPhase
from agents.observation import build_context
from agents.boxer_agent import BoxerAgent
from agents.scripted import ScriptedBoxer
from replay.recorder import Recorder
from sim.seeds import make_rng

EPS = 1e-9
_T = CONFIG["time"]
_E = CONFIG["energy"]
_H = CONFIG["health"]
_OBS = CONFIG["observation"]
_JAB_FIX = _H["jab_fixed_strength"]


class Fight:
    def __init__(self):
        self.over = False
        self.result = ""
        self.ko_t = None
        self.first_punch = False


# ---------- helpers ----------

def _eff_strength(hand: Hand) -> float:
    return _JAB_FIX if hand.punch_type == "jab" else hand.strength


def _avoids(defense: str, punch_type: str, placement: str) -> bool:
    if placement.startswith("body"):
        return False
    if defense == "duck":
        return punch_type != "uppercut"
    if defense == "slip_left":
        return placement in ("head_center", "head_right")
    if defense == "slip_right":
        return placement in ("head_center", "head_left")
    return False


def _incoming(self_b: B.BoxerState, opp: B.BoxerState, t: float) -> dict | None:
    for hand in opp.hands:
        if hand.impact_pending and hand.impact_t > t and hand.state == WINDUP:
            ttl = hand.impact_t - t
            react = timing.reaction_delay(self_b.attrs.get("reaction", 75),
                                          energy_react_pen(self_b.energy))
            can = ("It is coming — you have time to slip or block it, but not to land a counter first."
                   if ttl >= react else
                   "It is coming fast — barely time to react; cover up, you likely can't slip clean.")
            return {"punch_type": hand.punch_type, "placement": hand.placement, "can_react": can}
    return None


# ---------- per-tick stages ----------

def _resolve_impacts(red: B.BoxerState, blue: B.BoxerState, t: float, rng, fight: Fight, rec: Recorder):
    for atk, dfn in ((red, blue), (blue, red)):
        for hand in atk.hands:
            if hand.impact_pending and t >= hand.impact_t - EPS:
                hand.impact_pending = False
                _impact(atk, dfn, hand, t, rng, fight, rec)
                if fight.over:
                    return


def _impact(atk, dfn, hand, t, rng, fight, rec):
    dist = ring.distance(atk.pos, dfn.pos)
    pt, pl = hand.punch_type, hand.placement
    lq = ring.land_quality(dist, pt, atk.attrs.get("reach", 75))
    if lq == 0.0:
        rec.event(t, "whiff", {"by": atk.name, "punch": pt, "reason": "out_of_range"})
        atk.last_action_desc = f"missed a {pt} (out of range)"
        return
    if (dfn.defense and dfn.defense_effective_t <= t <= dfn.defense_active_until
            and _avoids(dfn.defense, pt, pl)):
        rec.event(t, "avoid", {"by": dfn.name, "via": dfn.defense, "punch": pt})
        dfn.last_action_desc = f"{dfn.defense.replace('_', ' ')}d a {pt}"
        atk.last_action_desc = f"missed a {pt} (slipped)"
        return

    blocked = dfn.guarding()
    roll = rng.uniform(*_H["contest_roll"])
    raw = damage.raw_damage(pt, pl, _eff_strength(hand), atk.energy, lq, blocked, roll, dfn.energy)
    hd, ed = damage.split(raw, pl, dfn.attrs.get("chin", 75))

    gassed_ko = dfn.energy < _E["ko_energy_threshold"] and _E["zero_energy_next_hit_is_ko"] and not blocked
    dfn.health -= hd
    dfn.energy = max(0.0, dfn.energy - ed)
    dfn.energy_ceiling = lower_ceiling(dfn.energy, dfn.energy_ceiling)
    # A head shot that leaks past a SAGGING (gassed) guard landed for real — the tired guard didn't
    # stop it, so it reads "clean", not "blocked" (matches the observation's "sagging" read).
    sagging_leak = blocked and not pl.startswith("body") and dfn.energy < _OBS["guard_sags_below_energy"]
    tag = ("glancing" if lq < 1.0 else "clean") if (not blocked or sagging_leak) else "blocked"
    rec.event(t, "land", {"by": atk.name, "punch": pt, "placement": pl, "quality": tag,
                          "health_dmg": round(hd, 2), "energy_dmg": round(ed, 2)})
    atk.last_action_desc = f"landed a {pt} to your {pl.replace('_', ' ')}"

    if gassed_ko or dfn.health <= 0.0:
        fight.over = True
        fight.ko_t = t
        why = "gassed-out KO" if gassed_ko and dfn.health > 0 else "KO"
        fight.result = f"{atk.name} wins by {why}"


def _advance(b: B.BoxerState, t: float, dt: float):
    for hand in b.hands:
        if hand.state == WINDUP and t >= hand.windup_end - EPS:
            hand.state = RECOVERY
        if hand.state == RECOVERY and t >= hand.recovery_end - EPS:
            hand.state = FREE
            hand.punch_type = ""
    if b.defense and t >= b.defense_locked_until - EPS:
        b.defense = None
    if not b.throwing():
        b.energy = regen(b.energy, b.energy_ceiling, dt)
    if b.guarding():
        b.energy = max(0.0, b.energy - _E["guard_energy_per_sec"] * dt)
    b.energy_ceiling = lower_ceiling(b.energy, b.energy_ceiling)


def _needs_decision(b: B.BoxerState, opp: B.BoxerState, t: float, first_punch: bool) -> bool:
    if not first_punch:
        return (t - b.last_call_t) >= _T["opening_poll_interval"] - EPS
    busy = b.throwing() or b.in_defense()
    reactive = (opp.last_commit_t > b.last_call_t) and opp.has_pending_punch(t) and not b.fully_locked()
    idle = (not busy) and (t - b.last_call_t) >= _T["live_poll_interval"] - EPS
    return reactive or idle


def _apply(b: B.BoxerState, opp: B.BoxerState, action: dict, t: float, fight: Fight, rec: Recorder):
    threw = False
    if action.get("defense"):
        for hand in b.hands:                      # cancel any in-flight punch
            if hand.state == WINDUP:
                hand.state = FREE
                hand.impact_pending = False
                hand.punch_type = ""
        b.defense = action["defense"]
        eff = t + timing.reaction_delay(b.attrs.get("reaction", 75), energy_react_pen(b.energy))
        b.defense_effective_t = eff
        # Avoidance window runs from when the slip/duck becomes EFFECTIVE (after the reaction delay),
        # so the head stays offline for the full slip duration rather than having the delay eat into it.
        active, locked = (timing.duck_window(eff) if b.defense == "duck" else timing.slip_window(eff))
        b.defense_active_until, b.defense_locked_until = active, locked
        b.energy = max(0.0, b.energy - (_E["duck_energy"] if b.defense == "duck" else _E["slip_energy"]))
    else:
        for name, hand in (("left_hand", b.left), ("right_hand", b.right)):
            ha = action.get(name)
            if ha is None or hand.locked():
                continue
            kind = ha["action"]
            if kind == "guard":
                hand.state = GUARD
            elif kind == "free":
                hand.state = FREE
            elif kind == "punch":
                eff_s = _JAB_FIX if ha["punch_type"] == "jab" else ha["strength"]
                cost = punch_energy(eff_s, ha["speed"])
                if cost > b.energy:
                    hand.state = GUARD
                    continue
                hand.punch_type, hand.placement = ha["punch_type"], ha["placement"]
                hand.strength, hand.speed = ha["strength"], ha["speed"]
                wt = timing.windup_time(ha["punch_type"], ha["speed"], b.attrs.get("hand_speed", 75))
                hand.windup_end = t + wt
                hand.impact_t = hand.windup_end
                hand.recovery_end = hand.impact_t + timing.recovery_time(ha["punch_type"], eff_s)
                hand.state = WINDUP
                hand.impact_pending = True
                b.energy = max(0.0, b.energy - cost)
                b.last_commit_t = t
                threw = True
        fw = action.get("footwork")
        if fw and fw != "none":
            b.pos = ring.step_target(b.pos, opp.pos, fw, CONFIG["footwork"]["step_distance_ft"])
            b.energy = max(0.0, b.energy - _E["step_energy"])
    b.energy_ceiling = lower_ceiling(b.energy, b.energy_ceiling)
    b.last_action_desc = action.get("reasoning") or "resets"
    if threw:
        fight.first_punch = True
    return threw


# ---------- agents / setup ----------

def _make_agent(spec: dict, local: bool, model_override: str | None):
    if spec.get("type") == "llm":
        provider = "ollama" if local else spec.get("provider", "openai")
        model = model_override or spec.get("model", "gpt-5-nano")
        re = None if provider == "ollama" else spec.get("reasoning_effort", "low")
        return BoxerAgent(spec["name"], model=model, reasoning_effort=re, provider=provider)
    return ScriptedBoxer(spec["name"])


def run_fight(scenario_path: str | None = None, seed: int | None = None, output: str | None = None,
              local: bool = False, model: str | None = None, verbose: bool = True) -> dict:
    sc = {"name": "default", "round_seconds": _T["round_seconds"], "start_range": 4.0,
          "red": {"type": "scripted", "name": "Red"}, "blue": {"type": "scripted", "name": "Blue"}}
    if scenario_path:
        sc.update(yaml.safe_load(Path(scenario_path).read_text(encoding="utf-8")))
    seed = seed if seed is not None else sc.get("seed", 42)
    round_seconds = sc["round_seconds"]
    dt = _T["dt"]
    rng = make_rng(seed)

    attrs = dict(CONFIG["roster_default"])
    half = sc["start_range"] / 2.0
    red = make_boxer(sc["red"]["name"], [ring.SIZE / 2, ring.SIZE / 2 - half], attrs)
    blue = make_boxer(sc["blue"]["name"], [ring.SIZE / 2, ring.SIZE / 2 + half], attrs)
    agents = {red.name: _make_agent(sc["red"], local, model),
              blue.name: _make_agent(sc["blue"], local, model)}

    rec = Recorder({"scenario": sc["name"], "seed": seed, "round_seconds": round_seconds,
                    "dt": dt, "config": {"ring": CONFIG["ring"], "reach": CONFIG["reach"]}})
    fight = Fight()
    t = 0.0
    while t < round_seconds and not fight.over:
        _resolve_impacts(red, blue, t, rng, fight, rec)
        if fight.over:
            rec.snapshot(t, FightPhase.END, red, blue, {})
            break
        _advance(red, t, dt)
        _advance(blue, t, dt)

        decisions = {}
        phase = FightPhase.OPENING if not fight.first_punch else FightPhase.LIVE
        for b, opp in ((red, blue), (blue, red)):
            if _needs_decision(b, opp, t, fight.first_punch):
                ctx = build_context(b, opp, t, round_seconds, _incoming(b, opp, t))
                action = agents[b.name].decide(ctx)
                _apply(b, opp, action, t, fight, rec)
                b.last_call_t = t
                decisions[b.name] = {"reasoning": action.get("reasoning", ""),
                                     "footwork": action.get("footwork"), "defense": action.get("defense")}
        rec.snapshot(t, phase, red, blue, decisions)
        t += dt

    if not fight.over:
        if abs(red.health - blue.health) < 1.0:
            fight.result = "Draw"
        else:
            w = red if red.health > blue.health else blue
            fight.result = f"{w.name} wins by decision"

    footer = {"result": fight.result, "ko_t": fight.ko_t,
              "red": {"health": round(red.health, 1), "energy": round(red.energy, 1),
                      "calls": agents[red.name].call_count, "parse_errors": agents[red.name].parse_errors},
              "blue": {"health": round(blue.health, 1), "energy": round(blue.energy, 1),
                       "calls": agents[blue.name].call_count, "parse_errors": agents[blue.name].parse_errors}}
    out = output or sc.get("output") or f"replays/{sc['name'].replace(' ', '_')}_{seed}.json"
    rec.save(out, footer)
    if verbose:
        print(f"RESULT: {fight.result}" + (f" at {fight.ko_t:.2f}s" if fight.ko_t else ""))
        print(f"  Red : health {footer['red']['health']:5.1f}  energy {footer['red']['energy']:5.1f}  "
              f"calls {footer['red']['calls']}  parse_err {footer['red']['parse_errors']}")
        print(f"  Blue: health {footer['blue']['health']:5.1f}  energy {footer['blue']['energy']:5.1f}  "
              f"calls {footer['blue']['calls']}  parse_err {footer['blue']['parse_errors']}")
        print(f"  Replay -> {out}  ({len(rec.frames)} frames)")
    return {"result": fight.result, "footer": footer, "replay": out, "frames": len(rec.frames)}
