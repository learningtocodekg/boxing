# LLM WWE

**A boxing simulator where both fighters are LLMs.**

Two `gpt-5-nano` agents fight each other inside a deterministic 20 Hz physics engine. Neither model
ever sees a coordinate or computes a distance. Each one reads the fight as structured English — what
its own hands are doing, where the opponent's guard is open, how much time it has to react to the
punch already travelling toward it — and returns one JSON action. The engine owns everything else:
reach, contact, damage, fatigue, timing.

Every fight serializes to a replay file. Open `render/viewer_3d.html`, drag the replay onto it, and
watch it back in 3D with each fighter's reasoning floating on screen as it throws.

```
sim/scenarios/*.yaml ──► sim/runner.py ──► replays/*.json ──► render/viewer_3d.html
                              │
                       engine/ (physics)  +  agents/ (LLM)
```

---

## The design constraint

A nano-class model cannot do geometry, and it should not have to. The whole architecture follows
from one rule:

> **Physics owns the body. The model only picks intent, from a menu of moves that are already legal.**

So the observation layer does all the feature engineering up front. By the time the model is asked to
decide, range gating, affordability, hand locks and guard reads have already been resolved into
prose. It sees this:

```
Your left hand: LOCKED - recovering, frees in +0.42s
Your right hand: up in guard

He is winding up a hook. It is coming - you have time to slip or block it.
His guard: head_left OPEN | head_center GUARDED | head_right sagging | body_left partial

LEGAL MOVES (right hand): guard, free, punch
  types in range: jab, cross     max strength you can afford: 6
```

...and answers with a single JSON object:

```json
{
  "right_hand": {"action": "punch", "punch_type": "cross", "placement": "head_right",
                 "strength": 6, "speed": 8},
  "combo": [{"punch_type": "jab", "placement": "body_left", "strength": 3, "speed": 9}],
  "defense": null,
  "reasoning": "His left is stuck recovering and that side of his guard is sagging - go now."
}
```

The parser is defensive by design: illegal picks coerce to `guard`, strength clamps to what the
fighter can actually afford, a defense drops any punch specified alongside it, a combo is dropped
without a lead punch. **The engine can never receive an impossible action.** Across the two shipped
60-second fights, ~156 model calls per round produced **zero parse errors**.

---

## What makes the fights interesting

The engine is small, but three mechanics do most of the dramatic work.

**Guard sag — fatigue you can see and exploit.** A fresh head guard blocks 70% of a shot. As the
blocker's energy falls past 45, that lerps toward blocking only 25% — and the extra leak scales with
the punch's power, so a sagging guard still parries a jab but barely slows a hook. Crucially, the
*same* threshold that changes the physics is what the observation renders to the opponent as
`sagging`. The model's read and the simulation agree, so "his guard is dropping, go upstairs" is a
real actionable tell rather than flavor text.

**Hurt vulnerability — why the knockout arrives before the gas tank empties.** Health damage is
multiplied by up to 2× as the defender's energy empties. Energy is deliberately *not* a win condition
(`zero_energy_next_hit_is_ko: false`); it is capacity. It gates punch power and reaction speed, so a
tired fighter hits softer, reacts slower, can't get out of the way — and the head shots he eats now
count double. Fatigue kills by making you hittable, which is the correct causal story.

**ROCKED — a stun that only exists once someone is hurt.** A clean, unblocked power shot (cross,
hook, uppercut — never a jab) that crosses a damage tier stuns the defender: offense goes offline,
his own windup and queued combo abort, but guard, slips and footwork still work. Because the trigger
is damage-gated, a fresh fighter shrugs off the same punch that would rock him in the third minute.
No early stun-lock — the finishing window emerges on its own.

Supporting cast:

- **Windup / impact / recovery is the entire risk model.** Speed shortens the windup (harder to react
  to); strength lengthens the recovery (longer exposed). You cannot throw a heavy shot slowly. The
  exposure window *is* the price of headhunting.
- **Reaction delay instead of freezing the clock.** A chosen slip only becomes *effective* after
  ~0.20s, scaled by agility and penalized by fatigue. The clock never pauses, so a fast jab lands
  before the guard arrives while a telegraphed hook is slippable. Hand speed is a real weapon.
- **Ratchet energy caps (75 / 50 / 25).** Once energy drops past a cap, the ceiling can never rise
  above it again. Stamina only trends down, so late rounds genuinely degrade instead of resetting.
- **Combos** queue up to three follow-ups 0.25s apart, alternating hands, force-firing through
  recovery — but never two gloves winding up at once, and the whole flurry is cancelled if you get
  rocked.
- **Body versus head.** Head shots drain health; body shots drain energy. Working the body is how you
  manufacture the sagging guard that opens the head.
- **Height and reach are geometry, not stat bonuses.** A taller fighter reaches your head from
  farther out; a shorter one gets to your body more easily. Every attribute is a no-op at the 75
  baseline, so two default fighters are genuinely identical and any difference in a fight comes from
  the two models, not the sheet.

Two archetypes ship — `out_boxer` (reach, agility) versus `pressure` (power, chin) — and breaking
that symmetry is what finally ended a long run of draws between identical fighters.

---

## Determinism

`dt = 0.05s`. One seeded RNG, used for exactly one thing: a ±10% contest roll on each landed punch.
Same seed, same scenario, same model output → the same fight, frame for frame.

The sim and the viewer never run in the same process; the replay JSON is the only interface between
them. Replays carry the punch *timeline* (`impact_t`, `recovery_end`, `strength`, `speed`) rather
than just discrete hand states, so a viewer schedules animations directly instead of inferring
contact from state flips.

---

## Running it

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
```

Five dependencies. Set `OPENAI_API_KEY` in `.env` or the environment for the default path.

**Fight, no API key needed:**

```bash
python main.py --scenario sim/scenarios/b1_mock.yaml --seed 42    # scripted vs scripted
python gen_demo.py 42                                             # -> replays/demo_42.json
```

**Fight, LLM vs LLM:**

```bash
python main.py --scenario sim/scenarios/b2_llm_60s.yaml           # -> replays/sixty.json
python main.py --scenario sim/scenarios/b2_llm_60s_r2.yaml        # round 2, carries round 1 fatigue
```

Run it locally on Ollama instead with `--local` (`ollama pull qwen3:8b && ollama serve`); override
the model with `--model`. The terminal prints the result, both fighters' final health and energy,
call counts and parse errors.

> **Pace:** the model is called roughly once per 0.2–0.3s of *fight* time, so a 60-second round takes
> several minutes of wall clock. Use `b1_mock.yaml` for engine work — it's instant and free.

**Watch a replay:**

Open `render/viewer_3d.html` in a browser and drag a replay JSON onto it. No build step, no server.
(Three.js loads via importmap, so it does need internet.) Gloves thrust along the punch's real
timeline, head shots snap the head back scaled by impact, and a ROCKED fighter visibly wobbles.

There is also a pygame side-view that is often more readable for debugging:

```bash
python -m render.renderer_2d replays/sixty.json
```

`SPACE` play/pause · `←`/`→` scrub · `+`/`-` speed · `R` toggle reasoning · `Q` quit.

Two replays ship, and they pair up nicely: **`sixty.json`** goes the distance to a decision
(61.6 – 51.0), and **`sixty_r2.json`** carries that fatigue into round two and ends in a **knockout at
28.4 seconds**, the winner left standing on 2.5 HP.

**Tests:**

```bash
python -m pytest -q      # 38 tests, no API key, no Ollama
```

Covering the energy cost curve and ratchet, the damage formula and every block path, sagging-guard
leak, the timing tradeoffs, combo scheduling, all twelve ROCKED cases, roster geometry, and a full
mock-vs-mock fight end to end.

---

## Layout

| Path | What's in it |
|---|---|
| `engine/` | Pure functions and dataclasses — energy, damage, timing, ring geometry, boxer state. No I/O, no RNG. |
| `agents/` | LLM client (OpenAI + Ollama), observation builder, JSON schema and parser, system prompt, scripted mock. |
| `sim/runner.py` | The one place state mutates. Tick loop, impact resolution, decision scheduling. |
| `replay/` | Replay writer. |
| `render/` | `viewer_3d.html` (Three.js), `renderer_2d.py` (pygame), `renderer_ursina.py` (superseded). |
| `config.yaml` | Single source of truth. Every tunable, commented with *why* it was retuned. |
| `PRD.md` | Full design spec. |
| `article.md` | Running log of every scaffolding decision and why — including what backfired. |
| `step_example.md` | The exact observation-in / JSON-out contract for one decision step. |

Roughly 2,700 lines of Python plus a self-contained 500-line viewer.

---

## Status

| Phase | | |
|---|---|---|
| **B1** | One LLM against a scripted opponent — every move fires and renders | ✅ |
| **B2** | LLM vs LLM, full rounds | ✅ |
| **B3** | Tune energy / damage / timing; combos, ROCKED, guard sag, asymmetric fighters | ✅ |
| B4 | Knockdowns and a 10-count, full multi-round matches | Next |

Deferred: separate head and body health bars, two-pass decisions.
