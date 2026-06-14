# Left Off
Date: 2026-06-14

## Latest session — FIRST KO (open problem #2, RESOLVED)
Resumed mid-stream: the *previous* (crashed) agent had slowed punches down for watchability — lengthened
`timing.windup`/`recovery` (jab recovery .15→.38, up to uppercut .78) + reworked `renderer_2d` (minimap
movement trails, lead/rear-hand poses). That work RAN fine (`replays/b2_15s_watchable.json`, 0 parse
errors) but made the 15s fight LESS decisive (end health 80/83, energy 58/52 — fewer exchanges at the
slower pace). Per user: KEEP the slow watchable pace, get KOs by LENGTHENING the round.

### What got done
1. **`sim/scenarios/b2_llm_45s.yaml`** — 45s round, seed 42, GPT-5-nano (kept the slow timing).
2. First 45s run (`replays/b2_45s_lengthened.json`): both fighters fully gassed (end energy ~0.2) but
   STILL no KO. Root cause found: `gassed_ko` required `dfn.energy <= 0.0` EXACTLY, but `regen` (1.2/s)
   bounces a spent fighter a hair above 0 between hits — so at the moment any clean shot lands the
   defender is at 0.05/0.17/0.43…, never exactly 0. The energy-0 KO rule was effectively unreachable.
   This is the SAME observation-vs-mechanics disagreement as the sagfix: the bottom energy band already
   tells both fighters "completely spent — the next clean shot ends it" (floor = energy 1.0), but the
   mechanic never honored it.
3. **Fix:** `config.yaml` `energy.ko_energy_threshold: 1.0` (floor of that "completely spent" band);
   `sim/runner.py` `_impact` now uses `dfn.energy < ko_energy_threshold` instead of `<= 0.0`.

### Verified
- `test_damage`, `test_energy`, `test_e2e` all PASS.
- Re-run (`replays/b2_45s_ko.json`, seed 42, GPT-5-nano): **Red wins by gassed-out KO at 35.75s** — the
  FIRST KO in the project. Finishing reads true: at t=35.55 Blue (2.37 en) throws a punch, emptying to
  0.23; at t=35.75 Red lands a CLEAN jab to head_center while Blue is spent (0.12 < 1.0) → KO. 0 parse
  errors. 2D viewer surfaces the result (gold KO banner + finishing jab in the play-by-play).

## NEXT STEP (next session)
- **Watch `replays/b2_45s_ko.json` in the 2D viewer** to confirm the slowed pace + KO read well on
  screen: `.venv\Scripts\python.exe -m render.renderer_2d replays/b2_45s_ko.json`.
- **Commit** this resumed state if it looks good (sagfix + slowdown + KO threshold are all uncommitted).
- Optional hardening: add a deterministic runner-level test for the gassed-KO threshold (currently only
  covered end-to-end). Still open: slips chosen a lot but rarely LAND (#3).

---

## Previous session — sagging-guard fix (open problem #1, RESOLVED)
Date: 2026-06-13
The observation read a tired guard as `sagging` but `damage.raw_damage` applied the flat `block_factor`
(0.20) regardless of the blocker's energy, so head shots at a gassed opponent were fully blocked
(17 head shots / 0 clean last session). Fixed the disagreement so mechanics honor the observation.

### What got done
1. **`engine/damage.py`** — new `block_multiplier(placement, defender_energy)`. Body block stays flat
   (0.55). The HEAD block lerps `block_factor` (0.20) → `block_factor_sagging` (0.75) as the blocker's
   energy falls from `observation.guard_sags_below_energy` (45) to 0 — the SAME threshold the
   observation reads "sagging", imported from CONFIG so there's one source of truth. `raw_damage` now
   takes `defender_energy` (default 100, so fresh-guard behavior + old tests are unchanged).
2. **`config.yaml`** — added `health.block_factor_sagging: 0.75`.
3. **`sim/runner.py` `_impact`** — passes `dfn.energy` to `raw_damage`; a head shot that leaks a
   SAGGING guard (defender energy < 45) is reclassified `clean`, not `blocked`, so it reads true.

### Verified
- `test_damage` (+ new `test_sagging_guard_leaks_head_shots`: fresh 0.20x, gassed 0.75x, at-threshold
  still tight, body unaffected), `test_energy`, `test_e2e` all PASS.
- **15s LLM-vs-LLM on GPT-5-nano, seed 42** (`replays/b2_15s_sagfix.json`): HEAD shots
  **35 clean / 0 glancing / 25 blocked** (was 0 clean last session); **14 clean head shots landed
  while the defender's guard was SAGGING (energy < 45)**, each doing real health damage (3.87, 1.46,
  1.27 …) at t≥10.95s once fighters dropped below the sag threshold. 0 parse errors. End health 59.6/65.7
  (more damage than the prior 86/90 "after" baseline — trending more decisive). Result: Blue decision.
  NOTE: baselines were on Ollama qwen3:8b; this run is GPT-5-nano (per model-preference memory) so it's
  not a same-model diff — but the unit test isolates the mechanical before/after, and the absolute
  result (35 clean head shots vs the prior 0) confirms the fix end-to-end.

## NEXT STEP (next session)
Open problem #2 — **more dynamic but no KO yet.** This run still went to decision (end energy ~27-30,
health ~60); the sag mechanic IS being reached (energy fell below 45 and head shots leaked), so the
fight is more damaging than before, but nobody gets finished. Tune toward KOs: faster energy drain,
more block-leak, longer rounds, or a prompt nudge to switch upstairs once the opponent sags. Also still
open: slips chosen a lot but rarely LAND (#3). Watch `replays/b2_15s_sagfix.json` in the 2D viewer to
confirm the head-hunting reads well on screen.

## Earlier session — dynamic-openings model + movement (B3 continued)
Diagnosed and attacked the static `body_left` stalemate from the last B2 fight. Root cause was NOT the
prompt (it already told the model to go upstairs / use range) — it was the **observation**: `_openings`
read the head as permanently GUARDED, so a head shot was always a bad bet and both fighters rationally
spammed the one line that read as available. Did web research on real boxing (jab to break/measure,
distance control as defense, guard-sag from fatigue, recovery-window counters) and translated it into
the model's "mental state" (observation + prompt), NOT new mechanics.

### What got done
1. **`_openings` rebuilt** (`agents/observation.py`) — per-line read from the opponent's ACTUAL hand
   states + fatigue, not a binary guard flag. A hand covers its side only while held in GUARD; mid-punch
   / RECOVERY (stuck out) / down → that side reads `OPEN` (the counter window right after he throws).
   `head_center` only opens if BOTH hands are off it. A guarded BODY line still `partial` (leaks); a
   guarded HEAD line reads `sagging` once the opponent is gassed (energy < `guard_sags_below_energy`).
   Added config knob `observation.guard_sags_below_energy: 45`. Removed orphaned `_PLACEMENTS`.
2. **Range reframed as defense + rest** (`_RANGE_LINE`) — "out of range" / "jab range" now tell the LLM
   his hooks/uppercuts can't reach there and he banks energy, so retreating/circling is a legible option.
3. **Prompt promotes the real tactic** (`boxer_system.txt`) — plan item 1: distance is free defense + a
   chance to recover; item 4: pepper with the cheap jab to measure + make him spend energy covering up,
   and load the power shot when the guard SAGS or right after he throws (recovery window). Band-language
   only, no numbers leaked.

### Verified
- `test_energy`, `test_damage`, `test_e2e` all PASS (run with `PYTHONPATH=. .venv\Scripts\python.exe tests/<f>.py`).
- Unit sanity check of `_openings`: threw-left→left side OPEN; winding-up-right→right side OPEN;
  gassed→all heads `sagging`; fresh both-up→heads GUARDED/body partial (no regression). All correct.
- **15s LLM-vs-LLM before/after on Ollama qwen3:8b, same seed 42** (`replays/b2_15s_baseline.json` =
  OLD build, `replays/b2_15s_after.json` = NEW build):

  | metric            | BEFORE | AFTER |
  |-------------------|--------|-------|
  | head shots landed | 4      | 17    |
  | head/body split   | 4/46   | 17/25 |
  | lines used        | 3      | 5 (incl head_left/right) |
  | movement (non-none footwork) | 10/87 | 41/115 |
  | distinct cells r/b| 2/3    | 7/7   |
  | slips chosen      | 3      | 16    |
  | parse errors r/b  | 2/8    | 0/0   |
  | whiffs            | 2      | 15    |
  | CLEAN shots       | 4      | 0     |
  | end health r/b    | 65.7/73.5 | 86.5/90.9 |
  | end energy r/b    | 22/21  | 55/55 |
  | result            | Blue decision | Blue decision |

  Core diagnosis confirmed: head-hunting, movement, and slips all jumped; parse errors went to zero.

## Broken / Open (NOTED, NOT FIXED this session — per instruction)
1. **`sagging` overpromises — the block engine doesn't honor a fatigue opening.** 17 head shots landed
   but **0 were clean** (all blocked/glancing). `sagging` is an advisory read (the guard is still UP,
   just tired) while the damage resolver only checks the binary `guarding()` and applies the full
   `block_factor`. So the observation invites a head shot the mechanics then fully block. Fix direction:
   either make fatigue actually reduce block effectiveness (a tired guard blocks worse), or downgrade
   what `sagging` claims. Openings-read and damage-resolution must agree.
2. **More dynamic but LESS decisive — the KO got further away.** Movement + range-as-defense let
   fighters bank energy (end ~55 vs ~22 before) and take less damage (health 86/90 vs 65/73), and
   whiffs jumped 2→15. Prettier fight, but nobody gasses now, so the energy-0 KO is further off. Likely
   needs balance tuning (faster drain, more block-leak, or longer rounds) so rewarding movement doesn't
   neuter the fight into a no-damage stalemate of a different kind.
3. **Slips still rarely LAND** — 16 chosen, only 1 registered as an `avoid` event. Timing of slip vs
   incoming impact still mostly misses (pre-existing; the recovery-delay/impact-tick interaction).
4. **NOT visually watched in the 2D viewer this session** — only analyzed via replay JSON. Watch
   `replays/b2_15s_after.json` to confirm the movement/head-hunting reads well on screen:
   `.venv\Scripts\python.exe -m render.renderer_2d replays/b2_15s_after.json`.

## NEXT STEP
**Decide and apply the `sagging`/block fix (open problem #1)** so head shots at a tired opponent actually
land clean — most likely: make `block_factor` scale up (block weaker) as the blocker's energy falls, so a
`sagging` guard mechanically leaks the way the observation promises. Then re-run the 15s before/after to
confirm clean head shots appear and the fight trends toward a KO (problem #2). Run LLM fights in the
background on Ollama qwen3:8b (`--local --model qwen3:8b`; slow, ~20min for a 15s sim).
