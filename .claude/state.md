# Build State
Current phase: **B3 — dynamics + balance pass UNDERWAY (B1/B2 built & verified).** Full engine + agents
+ runner; THREE viewers: 2D pygame side-view `renderer_2d` (readable); **3D browser `render/viewer_3d.html`
(Three.js, drag-and-drop, NEW — primary 3D viewer)**; legacy 3D ursina (superseded). Mock e2e passes;
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

## DONE latest: `sagging`-vs-block disagreement FIXED — tired-guard head shots now land clean
- **`damage.block_multiplier(placement, defender_energy)`**: head block lerps `block_factor` 0.20 →
  `block_factor_sagging` 0.75 as the blocker's energy falls from `guard_sags_below_energy` (45) to 0
  (same threshold the observation reads "sagging"). `raw_damage` takes `defender_energy`. `runner._impact`
  passes `dfn.energy` and reclassifies a head shot leaking a sagging guard as `clean`. Body block unchanged.
- Verified: new `test_sagging_guard_leaks_head_shots` + all unit tests PASS. 15s GPT-5-nano fight
  (`replays/b2_15s_sagfix.json`): HEAD 35 clean / 0 glancing / 25 blocked (was 0 clean); 14 clean head
  shots vs a SAGGING guard, real health damage; 0 parse errors.

## DONE latest: FIRST KO — round lengthened + gassed-KO threshold fixed (open problem #2 RESOLVED)
- Prev (crashed) agent slowed punch `timing` for watchability; that made the 15s fight less decisive.
  Per user: kept the slow pace, lengthened the round (`sim/scenarios/b2_llm_45s.yaml`, 45s).
- 45s run gassed both fighters to ~0.2 energy but no KO: `gassed_ko` needed `energy <= 0.0` exactly,
  unreachable because `regen` bounces a spent fighter off 0 between hits. Fixed with config
  `energy.ko_energy_threshold: 1.0` (floor of the "completely spent" band the observation promises);
  `runner._impact` now uses `dfn.energy < ko_energy_threshold`.
- Verified: all unit tests PASS; `replays/b2_45s_ko.json` (seed 42, GPT-5-nano) =
  **Red wins by gassed-out KO at 35.75s** (first KO). Viewer shows the gold KO banner.

## DONE latest: ENERGY RE-CENTERED as capacity, NOT a win condition (supersedes the gassed-KO above)
- User feedback: LLMs treat "drain energy" as the GOAL (prompt-induced — the prompt literally said
  "ENERGY IS WHAT WINS FIGHTS"). Correct model: HEALTH→0 is the only win; energy is CAPACITY (gates punch
  power/speed + defense reaction). Low energy ≠ KO; it means you can't defend → eat clean head shots →
  lose HEALTH. Decision (locked): keep body→energy as a MEANS, not a win path.
- Changes: `config.yaml` `zero_energy_next_hit_is_ko: false` (KO is health-only now — un-does the gassed-KO
  on purpose); `reaction_penalty_at_empty` 0.12→0.25 (gassed = can't slip/block in time); bottom energy
  band phrase fixed. `boxer_system.txt` reframed ("YOU WIN ONE WAY: TAKE HIS HEALTH TO ZERO… energy is
  capacity, not a way to win"; body = "SAP HIM SO HE CAN'T DEFEND", the means to open the head).
- Replays pruned to TWO fixed files: `replays/fifteen.json` + `replays/forty-five.json`; each scenario
  ALWAYS overwrites its own via a new `output:` field honored by the runner. README slimmed to those two.
  `test_e2e` now writes its mock replay to tempdir (keeps replays/ to the two curated files).
- Verified: all unit tests PASS; 15s GPT-5-nano (`fifteen.json`) — drain-vs-health reasoning ratio
  1.81:1→1.11:1, slips LAND 0→6, 0 parse errors. Tradeoff: 15s now less damaging (nobody gasses in 15s
  with regen, so the fatigue→open-head chain never fires) — finishes need a long round.

## DONE latest: 3D BROWSER VIEWER (Three.js) — `render/viewer_3d.html`
- Goal: 2D is hard to read; wants simple 3D. Past Python Ursina was "really bad" → Python desktop-3D
  ruled out. Locked: Three.js in-browser + drag-and-drop (no server/build/assets). Pure new renderer over
  the existing replay JSON — zero engine changes.
- Primitive boxers (sphere/capsule/cylinder + dynamic arms). Poses mirror engine hand states
  (guard/windup/recovery + head/body placement); defense duck=crouch, slip=head shift; impact flash
  yellow=clean / gray=blocked; OrbitControls camera; HUD + reasoning panels; frame interpolation; full
  playback controls. Fixed a +X-vs-+Z forward-axis bug (punches would've fired sideways).
- Verified: fields match `replays/fifteen.json`; `node --check` clean; user said "looks great". NOT yet
  eyeballed live in a browser by me. Open: make blocked flash a more distinct color / add BLOCK label?

## DONE latest: MULTI-ROUND CONTINUATION — round 2 carries round 1's end state
- `sim/runner.py`: scenario fields `carry_from` (a replay path) + `rest_energy`. Seeds each boxer from
  that replay's LAST frame: `health`, `energy_ceiling` (ratcheted cap CARRIED, not lifted = accumulated
  fatigue), `energy = min(ceiling, prev_energy + rest_energy)`. `sim/scenarios/b2_llm_15s_r2.yaml` =
  round 2 off `replays/fifteen.json`, +5 rest, → `replays/fifteen_r2.json`.
- Validated the realism model: R1 nobody tires (energy ~58, sag-threshold 45 never crossed → jab-fest,
  17 clean / 26 blocked, no finish). R2 starts worn, BOTH cross sag mid-round → 35 clean / 16 blocked,
  Blue eats 36 hp (vs 21.8 in R1), defense collapses (0 slips land). Cumulative Blue 100→88→52,
  Red 100→78→64; a round 3 would likely KO Blue. All unit tests PASS.
- REALISM ANALYSIS of fifteen.json drove this: the single biggest gap was "nobody gasses in 15s so the
  whole fatigue→sag→clean-shot→KO chain is dead." Multi-round continuation makes it fire.

## DONE latest: POWER SHOTS PAY OFF — jab-fest broken (open #1 RESOLVED, took BOTH levers)
- **Mechanic (`engine/damage.py`)**: `block_multiplier(placement, defender_energy, punch_type)` scales
  the sagging-guard leak by PUNCH POWER — jab stays 0.75 at empty (unchanged), hook ~1.0 (blasts through),
  cross 0.92, uppercut ~1.0. `raw_damage` forwards `punch_type`; runner unchanged. New test
  `test_sagging_guard_leaks_power_more_than_jab`; all unit tests PASS.
- **The mechanic alone did NOTHING** (R2 still 32 jab / 2 cross / 1 hook clean). Power shots were barely
  THROWN (47 jab vs 4 hook / 0 uppercut) — and NOT a range issue (hooks legal 62% of frames, uppercuts
  40%). Reasoning logs: LLMs name the sagging openings then jab them "to conserve energy". So added a
  **prompt nudge** (`boxer_system.txt` item 6): a sagging head = the moment to SPEND, a loaded hook costs
  barely more than a jab, pecking wastes the opening.
- **Both together (R2):** power thrown 7→21, power clean 3→14, total clean 35→54, loser health ~60→~36.
  R1 (fresh) unchanged. 0 parse errors.

## DONE latest: 3-ROUND CONTINUATION run out → Draw, no KO (symmetry is the ceiling)
- Cumulative health R1→R2→R3: 75/79 → 36/40 → 20/20; energy floor 0/0 by R3 end. Damage accelerates into
  R2, DECELERATES in R3: at 0 energy both swing back to max conservation (hook throws 8→1) + output_factor
  caps damage at 0.6 → the round grinds. Deeper cause: identical boxers gas in LOCKSTEP (R3 19.9 vs 20.5
  hp, 0.0 vs 0.0 en) → neither falls behind enough to capitalize. KO needs ASYMMETRY, not more tuning.
- `sim/scenarios/b2_llm_15s_r3.yaml` added (carry_from fifteen_r2.json, +5 rest → fifteen_r3.json).

## DONE latest: 1-MIN ROUNDS + LLM-AWARE REST (+10 en / +5 hp) + GLOBAL HALF-SPEED
- User asks: rounds = 1 minute; LLMs should KNOW the between-round rest gives +10 energy + +5 health;
  slow the whole fight to half speed.
- `round_seconds: 15→60` in all three scenarios. `sim/runner.py` carry block adds `rest_health` applied
  CAPPED at full (`min(_H["start"], health + rest_health)`); energy already capped at the ratcheted
  ceiling. `_r2`/`_r3`: `rest_energy 5→10`, `rest_health: 5`. Prompt energy paragraph now tells boxers a
  corner rest restores a good chunk of wind + a little health, so don't hoard energy at the bell — spend
  on a late finish (band-language, no raw numbers).
- Half-speed: `config.yaml` DOUBLED every timing duration (windup/recovery/slip/duck), `reaction_delay_base`
  .10→.20, poll intervals (opening .1→.2, live .15→.30). Scaled together → slip/block balance preserved.
- Verified: all unit tests PASS; mock dry-run confirms carry math (hp +5 capped at 100, energy +10 capped
  at ceiling). Did NOT run a full 60s LLM fight (token cost).
- OPEN: regen_per_sec (1.2/s) unchanged — over a 60s round at half-pace, within-round fatigue may be too
  light (watch in first real run). Filenames now stale (15s files run 60s).

## DONE latest: first real 60s round + ONE-HAND-AT-A-TIME + STRENGTH/SPEED REWORK
- Ran the first real 60s symmetric round (`replays/sixty.json`, renamed from `fifteen*`; all scenarios →
  `b2_llm_60s*.yaml` / `sixty*.json`). CONFIRMED within-round fatigue works over 60s (energy 99→~24, both
  cross sag(45) at t≈45, damage accelerates back-half) — the regen-vs-longer-round fear is dead.
- **One hand punches at a time:** `_apply` started both hands + the menu offered a 2nd punch while one was
  busy. Fixed in `runner._apply` (punch only if the other hand isn't `busy()` & none thrown this step) +
  `observation._hand_legal` (no "punch" while other busy) + prompt. 0 simultaneous windups in a live fight.
- **Strength/speed:** `eff_speed = max(speed, strength)` (strong can't be slow; jab unaffected) feeds
  windup + energy. `timing.recovery_time(pt, strength, speed)` grows w/ strength (dominant), trims w/ speed
  → jab 0.74s, cross 1.29s, hook 1.67s. config `timing.speed_recovery_scale`. `tests/test_timing.py`.

## DONE latest: FIGHTER ASYMMETRY — every attr now has a mechanic; lockstep-draw BROKEN
- Audited: `power`/`foot_speed`/`stamina` were DEAD, no `height`, `chin` gated off. Wired all, **no-op at
  the 75 baseline** (symmetric fights/tests byte-identical): reach→effective distance; height→head/body
  reach geometry (`ring.land_quality` now takes placement+both heights); power→damage (`damage.power_mult`);
  agility→windup+reaction+step (replaces reaction/hand_speed/foot_speed); chin→head-dmg resist;
  stamina→regen (`energy.stamina_regen_mult`). New config: `reach.attr_scale_ft/height_head_ft/height_body_ft`,
  `footwork.agility_scale`, `health.power_scale`, `energy.stamina_regen_scale`.
- Two archetypes `config.rosters` (out_boxer rangy/quick/fragile vs pressure short/heavy/granite). Scenario
  `red.roster`/`blue.roster`; `runner._roster()` merges default←archetype←inline attrs. `tests/test_roster.py`.
- LLM AWARENESS: `observation._matchup()` → "YOUR EDGE IN THIS MATCHUP" block + shared-prompt paragraph.
- RAN mismatched 60s: Blue(pressure) bt Red(out-boxer) **86.6/63.1**, Red gassed — lockstep broken. But
  fight was in the pocket 1150/1201 frames; Red wasted his reach (48 jabs/1 hook), Blue used power. Gap is
  now TACTICAL (the LLM doesn't fight to type), not mechanical.

## DONE latest: 4 follow-ups (DONE, NOT yet run — next agent analyzes)
1. **Min distance** `ring.min_distance_ft: 1.6` + `ring.clamp_min_distance` (after every step) — no overlap.
2. **Raw vitals** `vitals_display: bands→exact`; `observation._vitals()` shows `health/energy NN/100` for
   both. Deliberately overrides the locked "never show numbers" principle — user experiment, reversible.
3. **Firmer matchup prompts** (`_MATCHUP` + prompt paragraph): how to exploit + WHY, "not an order, the read".
4. **Power-disadvantage reframed**: lighter fighter pawed 48 jabs; now told jab=setup not score, throw real
   combinations (`_MATCHUP` power line + jab doctrine items).

## NEXT: run mismatched 60s + analyze the 4 changes (does the LLM finally fight to type?)
- `python main.py --scenario sim/scenarios/b2_llm_60s.yaml`. Watch: min-distance holding/looks better;
  out-boxer USING range (fewer pocket frames than 1150/1201, steps out when pressured); lighter fighter
  throwing REAL shots (crosses/hooks up from 1, jabs down from 48); raw vitals changing reasoning. THEN the
  no-KO finish-nudge (ahead fighter won't commit to finish a gassed opponent).
- DEFERRED: regenerate `replays/forty-five.json` (pre-asymmetry baseline); eyeball viewer_3d.html live;
  continuation→real round loop (auto-KO-stop, scorecard, ceiling lift) = roadmap B4.

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
  be smart. (UPDATE: `vitals_display` flipped to `exact` this session — health/energy now shown as raw
  NN/100 for both fighters, a user experiment that overrides this "bands only" rule; reversible via config.)
  Timing reads are qualitative the same way
  ("time to slip but not counter", not "0.24s"). Incoming punch power read from its windup telegraph.
- **Energy cost = strength & speed ONLY** (punch type does NOT affect energy — dropped the type mult,
  so "max strength you can afford" is one number for all punches). Punch type still drives damage.
- **No illegal moves offered:** out-of-range and out-of-energy punches are filtered OUT of the menu,
  never shown. Combinatorics handled by slot-composition (fill hand/footwork/defense slots + write
  strength/speed integers) — we never enumerate the move product. See `step_example.md`.
- **Determinism:** seeded RNG; only randomness is the contest_roll margin + opening tie-breaks.
- **Boxers identical (v1) — SUPERSEDED:** now distinct archetypes (`config.rosters`), every attr has a
  no-op-at-75 mechanic (reach/height/power/agility/chin/stamina). All-75 is still the symmetric baseline.
- **3D ursina only** — rectangle torso + circle head + arms;
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
