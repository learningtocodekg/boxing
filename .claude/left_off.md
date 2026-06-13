# Left Off
Date: 2026-06-13

## This session — dynamic-openings model + movement (B3 continued)
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
