# Build State
Current phase: **B1 — BUILT & VERIFIED + 2D viewer.** Full engine + agents + runner; BOTH viewers
(2D pygame side-view `renderer_2d` = the readable one; 3D ursina `renderer_ursina` = alt). Mock-vs-mock
e2e passes; LLM-vs-mock AND LLM-vs-LLM on Ollama (qwen3:8b) ran clean (0 parse errors, coherent reasoning).

## NEXT: make fights dynamic + B3 balance (gaps user saw watching replays)
- **No movement** — agents barely use footwork (start in jab range; punching prioritized). Start them
  further apart; prompt footwork/angles; make footwork matter.
- **No slips/ducks** — defense is almost always `guard`. Verify reactive trigger + `incoming` reach the
  agent; make blocking cost/leak so slipping pays.
- **Reasoning sparse / none on blocks** — every decision (incl. guard/defense) must carry real reasoning;
  viewer shows only latest persisted reasoning.
- **Blocking too strong** — block_factor 0.20 on everything -> shots chip; make it line-specific.

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
  energy damage (head = health, body = drains energy). Block = 0.2 mult (heavy reduction). 0 health = KO.
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
- **Blocking too strong:** mock holds guard often -> most punches chip (block_factor 0.20 on everything).
  Tune in B3 (e.g. guard only covers some lines; body shots leak more past a high guard).
- **Openings model is coarse:** when opponent guards, only body lines read as "partial" -> LLM spams body_left.
  Refine `_openings` so different guard postures open different specific lines.
- Roster folded into config.roster_default (no separate sim/rosters/default.yaml yet); both boxers identical.
- Footwork is instant displacement (no leg-lock duration) — fine for B1, revisit if it looks jumpy in 3D.
- See left_off.md for the single NEXT STEP.
