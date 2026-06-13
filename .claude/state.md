# Build State
Current phase: **B3 — dynamics + balance pass UNDERWAY (B1/B2 built & verified).** Full engine + agents
+ runner; BOTH viewers (2D pygame side-view `renderer_2d` = readable; 3D ursina = alt). Mock e2e passes;
LLM-vs-mock on Ollama (qwen3:8b) validated with the new strategy prompt + slip/balance fixes (0 parse
errors, strategic reasoning, slips now land and decide fights).

## DONE this session (the SESSION 3 gaps — see left_off.md for detail)
- **Slips now work** — fixed avoidance-window bug (anchor to EFFECTIVE time, not decision time) +
  flipped schema to DEFENSE-FIRST (was silently dropping a slip in favor of a co-specified punch).
- **Movement** — start_range 2.4 → 4.0 (start out of range, must close); mock alternates head/body +
  resets range/circles so the verifier actually exercises slips/head/footwork.
- **Blocking** — now line-specific: head 0.20x, body LEAKS 0.55x (`body_block_factor`); reaction_delay
  0.18 → 0.10 so power shots are slippable but jab/cross aren't.
- **Strategy** — prompt rewritten with a "HOW TO WIN" doctrine (energy economy, outlast, slip>block,
  pick power shots, body work) in band-language only; reasoning now carries real intent on every decision.

## DONE next session (dynamic openings + movement) — see left_off.md
- **`_openings` rebuilt**: per-line read from the opponent's ACTUAL hand states + fatigue (was a binary
  guard flag). RECOVERY/winding-up/down hand → that side `OPEN`; gassed → head lines `sagging`; body
  still `partial`; `head_center` opens only if both hands off it. Config `observation.guard_sags_below_energy: 45`.
- **Range reframed as defense+rest**; prompt promotes jab-to-tire → guard-sag/recovery-window power shot.
- 15s before/after (Ollama qwen3:8b, seed 42): head shots 4→17, movement 2→7 cells, slips 3→16, parse
  errors 8→0. Confirmed the diagnosis (the head never opened because the OBSERVATION never let it).

## NEXT: fix `sagging`-vs-block disagreement so tired-guard head shots land clean; then tune toward KOs
- **Open (this session's finding): `sagging` overpromises** — 17 head shots, 0 CLEAN. The damage resolver
  only checks binary `guarding()` and applies full `block_factor`, so a `sagging` (tired-but-up) guard
  still blocks fully. Make block scale with the blocker's energy, OR downgrade what `sagging` claims.
- **Open: more dynamic but less decisive** — movement+range-as-defense → fighters bank energy (end ~55
  vs ~22) and take less damage; KO got further away. Needs balance tune (drain/leak/round length).
- **Open: slips chosen a lot (16) but rarely LAND (1 avoid)** — slip-vs-impact timing still mostly misses.

## What exists
- `PRD.md` — full design (long). Source of truth for mechanics.
- `config.yaml` — all tunable numbers, injected everywhere (energy/health/timing/reach/roster/bands).
- `step_example.md` — the LLM observation/return contract (reference).
- `CLAUDE.md`, `.claude/` (commands/, settings.json, roadmap.md), `article.md`, `README.md`.

## Locked design decisions (from the Q&A that produced the PRD)
- **Phasing:** B1 = 1 LLM vs mock (verify moves), then B2 = LLM-v-LLM at **15-second** rounds, then build up.
- **Time model:** continuous physics tick `dt=0.05`. **Opening regime**: both boxers polled every 0.1s
  until the first punch. **Live regime**: event-driven decision steps (self-completion OR opponent
  commitment). No time-freeze during LLM calls in live — reaction-delay model governs whether a
  response lands. Attacker-commits-then-defender-reacts ordering.
- **Punch phases:** WINDUP (telegraph, cancel-able into duck/slip) -> IMPACT (1 tick, damage) ->
  RECOVERY (hand locked, no guard). Fast speed = short windup = harder to react to (less reaction
  time), low strength; high strength = longer recovery (exposed).
- **Energy:** start 100. `punch_energy = 0.78*(s/10)+0.22*(v/10)+2.0*(s/10)*(v/10)` (fits user anchors
  10/10->3, 10/1->1, 1/10->0.5). Regen ~1.2/s only while not throwing. **Ratchet caps 75/50/25** —
  once below a cap, never recover above it. **Energy 0 -> next clean hit is instant KO.** Gradual
  degradation scales output 1.0->0.6 and slows reaction as energy falls.
- **Health:** one bar, start 100. `base = strength*0.5`, jab uses fixed strength 3. Power mult
  jab1.0/cross1.3/uppercut1.45/hook1.6 (so to head: hook>uppercut>jab). Placement splits health vs
  energy damage (head = health, body = drains energy). Block is LINE-SPECIFIC: head 0.20x / body 0.55x
  (body leaks past a high guard). 0 health = KO.
- **Action space:** per hand {punch(type,placement,strength,speed) | guard | free}; punches
  {jab,cross,hook,uppercut} x placements {head_center,head_left,head_right,body_left,body_center};
  footwork {fwd,back,left,right,circle_l,circle_r,none}; defense {slip_l,slip_r,duck}. Can't
  duck/slip + punch same step; slip/duck lock legs; cornered removes into-wall steps.
- **Range** gates punches by reach (jab>cross>hook>uppercut); LLM told IN/OUT of range, never computes.
- **Observation:** full plain-English scenario + annotated **legal-move menu**; LLM just picks. No
  coordinates, no geometry. **Single-pass** decision -> JSON. Safe default = both hands guard.
  **Vitals (health + energy) shown via DETERMINISTIC number->phrase bands** for BOTH fighters
  (config `vitals_display: bands|exact`, `energy_bands`/`health_bands` tables). The **system prompt
  NEVER reveals the thresholds or that a phrase maps to a number** — LLM just gets the words and must
  be smart. Raw numbers never appear in the observation. Timing reads are qualitative the same way
  ("time to slip but not counter", not "0.24s"). Incoming punch power read from its windup telegraph.
- **Energy cost = strength & speed ONLY** (punch type does NOT affect energy — dropped the type mult,
  so "max strength you can afford" is one number for all punches). Punch type still drives damage.
- **No illegal moves offered:** out-of-range and out-of-energy punches are filtered OUT of the menu,
  never shown. Combinatorics handled by slot-composition (fill hand/footwork/defense slots + write
  strength/speed integers) — we never enumerate the move product. See `step_example.md`.
- **Determinism:** seeded RNG; only randomness is the contest_roll margin + opening tie-breaks.
- **Boxers identical (v1)**, all stats 75. **3D ursina only** — rectangle torso + circle head + arms;
  floating reasoning overlay. No 2D viewer.
- **Providers:** gpt-5-nano + Ollama, llm_client.py copied from football.

## Built (B1)
- engine/config.py (loads config.yaml -> CONFIG), seeds.py (copied)
- engine/energy.py — punch_energy (anchors verified), lower_ceiling (ratchet), regen, output_factor, reaction_penalty. test_energy PASS.
- engine/damage.py — raw_damage, split (head->health/body->energy, chin neutral), glancing_mult. test_damage PASS.
- engine/timing.py — windup_time (shrinks w/ speed+hand_speed), recovery_time (grows w/ strength), reaction_delay, slip/duck windows.
- engine/ring.py — distance, in_reach, land_quality (clean/glancing/miss), range_band, types_in_range, step_target, legal_steps, cornered. SIZE=16, BOXER_RADIUS=0.7.
- engine/boxer.py — Hand (free/guard/windup/recovery + phase timers), BoxerState (health/energy/ceiling/hands/defense/pos/attrs + predicates).
- engine/state_machine.py — FightPhase OPENING/LIVE/END.
- agents/observation.py — build_context (engine-side feature-eng: range gate, openings, affordability, locks, corner) + render_observation (band text, ASCII separators) + energy_band/health_band.
- agents/schema.py — parse_action (strip fences, validate vs legal, slip/duck exclusivity, safe_default).
- agents/boxer_agent.py — BoxerAgent (LLM: render->call_llm->parse). agents/scripted.py — ScriptedBoxer (mock).
- agents/prompts/boxer_system.txt — timeless rules (never reveals band thresholds).
- sim/runner.py — run_fight: two-regime loop, _resolve_impacts, _impact (gate: range->avoid->block->damage->KO), _advance (phase/regen/ratchet), _needs_decision (opening poll / live reactive+idle), _apply (punch windup/energy, defense cancel+reaction-delay, footwork). Loads scenario yaml; --local routes LLM->ollama.
- replay/recorder.py — per-tick snapshot + events -> JSON.
- render/renderer_2d.py — **2D pygame side-view (primary, readable)**: profile poses (guard/windup/punch-to-target/duck/slip), impact flashes, HP/EN bars, top-down minimap, play-by-play log, reasoning panels. Controls: SPACE/arrows(scrub)/+-/R/Q.
- render/renderer_ursina.py — 3D viewer (alt). Fixed: color.hex (was 0-255 -> white); shadow uses `quad` (no `cylinder` model). Cameras 1/2/3 + [/] zoom.
- main.py, gen_demo.py, sim/scenarios/{b1_mock,b1_llm_ollama,b1_llm_smoke,b2_llm_15s,b2_llm_smoke}.yaml
- tests/test_energy, test_damage, test_e2e — all PASS (e2e = mock fight, no API key).

## Known issues / next
- **Blocking too strong: FIXED** — now line-specific (head 0.20x / body 0.55x leak). Body work drains a
  guarding opponent's energy, which is the new path to wear-down/KO.
- **Openings model is coarse: REWORKED** — `_openings` now reads per-line from the opponent's real hand
  states + fatigue (RECOVERY/down → side OPEN; gassed → head `sagging`). Head shots jumped 4→17 in 15s.
  Residual: `sagging` isn't honored by the block resolver (0 clean head shots) — see NEXT.
- **No clean head shots / no KOs yet:** style is body-drain + tight defense; nobody opens the head. Needs
  either a tiring opponent's guard to drop or a prompt nudge to switch upstairs once the body's done.
- Roster folded into config.roster_default (no separate sim/rosters/default.yaml yet); both boxers identical.
- Footwork is instant displacement (no leg-lock duration) — fine for B1, revisit if it looks jumpy in 3D.
- See left_off.md for the single NEXT STEP.
