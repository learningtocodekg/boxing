# Left Off
Date: 2026-06-17

## Latest session — FIRST REAL HEALTH-KO + both-hands-punching bug fixed. Health now reaches 0 before energy.
Resumed at "eyeball viewer + no-KO finish-nudge". User had eyeballed the viewer (looked like a real fight)
and gave 3 things: (1) still sees both hands punching at once — bug or viewer?; (2) eyeball good; (3) make
the finish a small prompt nudge when opp is very low (~5-10 hp). Then, after seeing a round-2 still not KO,
we reframed the whole no-KO problem and landed the project's FIRST health-KO.

### 1. "Both hands punching" — was a CODE bug in the combo path (not the viewer). FIXED + verified.
Data proved it: old `sixty.json` had frames with BOTH hands in WINDUP (Red 42 / Blue 103). Cause: the combo
scheduler force-fires the next follow-up `combo_interval` (0.25s) after the lead, but a power punch's windup
is longer (cross 0.52s, hook 0.64s) — so the follow-up began winding up BEFORE the lead landed = two gloves
cocked at once. The "one hand at a time" guard lived only in the per-decision path; the combo bypassed it.
FIX (`runner._fire_combo`): a follow-up waits until NO hand is still winding up (prev punch has landed),
then force-fires over RECOVERY (still a fast flurry). New deterministic test `test_combo_never_two_windups_at_once`.
VERIFIED LIVE: both-WINDUP now 0/0 in every new run, and flurries SURVIVED the fix (still 16/14 three-punch
bursts — same as before). The 427/463 "both gloves extended" frames are the CORRECT combo visual (one
winding the next as the other retracts), not the bug.

### 2. The no-KO finish — user REFRAMED it; the real fix was a vulnerability mechanic, not just a nudge.
First added the finish nudge to the prompt (item 6: opp in single digits / "out on his feet" -> rip a
committed power combo upstairs and END it, don't pace for a decision). Parses clean (0 errors). BUT a
single 60s round caps the loser at ~45-47 hp, so the nudge can't fire. Ran a real round-2 carry
(`sixty_2.json`, carry from R1) -> Red dec 31.3 / Blue 16.0, STILL no KO. The data showed WHY: by the time
Blue was hurt (16-25 hp), Red (ahead) was pinned at ~0.1 energy for the whole second half — at 0 energy you
CAN'T throw the finishing combo (can't afford it) and punches cap at 0.6 power. The nudge was physically
impossible to obey. **Exhaustion lockstep: both bottom out at 0 energy together, so nobody can capitalize.**

USER'S REFRAME (the key insight): *energy must NEVER hit 0 before health.* In real boxing 0 energy = passed
out; you reach it BECAUSE you've been getting rocked — the hits end it, not the gas. So: as energy dwindles
you should take MORE damage, such that HEALTH reaches 0 first. Then run a FRESH round simulating a round-2
state: Blue 40hp/53en, Red 60hp/44en.

### 3. Implemented + VERIFIED — FIRST HEALTH-KO.
- **Vulnerability mechanic** (`damage.vulnerability_mult`, config `health.hurt_vulnerability_scale: 1.0`):
  a tired DEFENDER takes more HEALTH damage — 1.0x at full energy -> 2.0x at empty (linear). Applied in
  `damage.split` (health only; body->energy drain untouched). `runner._impact` passes `dfn.energy`. This
  makes health ACCELERATE to 0 as energy falls, so the KO lands on health before energy flatlines.
- **Slower energy drain** so energy outlasts health: `regen_per_sec 1.2->1.6`, `step_energy 0.3->0.2`.
- **Scenario preset support** (`runner`): a boxer spec can set `health`/`energy` (+ optional
  `energy_ceiling`, default = set energy so it only dwindles). New `sim/scenarios/b2_llm_60s_sim2.yaml`
  (Blue 40/53, Red 60/44). Lets us simulate a worn round in ONE fresh run instead of a 3-round carry chain.
- **RESULT (`replays/sixty_2.json`): Red wins by KO at 30.15s.** Blue health -0.1 while energy STILL 24.8;
  Red ended 12.1 hp / 14.5 en. ENERGY NEVER HIT 0 (0 frames at ~0 en, either fighter) — health crossed zero
  first exactly as asked. Finish nudge fired (Blue 7.6 -> 3.2 -> KO'd). both-WINDUP 0/0. 0 parse errors.
- New test `test_tired_defender_takes_more_health_damage` (+ body-drain NOT amplified). All 6 suites PASS.

### Broken / Open
1. **Global-balance unverified on a FRESH 100-hp round.** The vulnerability + slower-drain changes are
   GLOBAL — they make the normal `sixty.json` (round 1 from 100 hp) more damaging too. We tuned/verified
   against a WORN round-2 state only. A fresh round-1 was NOT re-run — it could now be a too-early blowout
   or still fine. **This is the #1 thing to check next** (offered, user went to /break first).
2. **`hurt_vulnerability_scale: 1.0` is the new primary KO dial.** 2.0x at empty produced a clean 30s KO
   from a worn state; if fresh rounds KO too early, this is the first knob to lower (try 0.6-0.8).
3. `forty-five.json` still a stale pre-rework baseline (deferred). Continuation->real round loop (auto-KO
   stop, scorecard, ceiling lift) still = roadmap B4. `sixty_2.json` is now the simulated-R2 KO run (was
   the carry-R2 run earlier this session — overwritten on purpose).
4. Push history: prior sessions' commits were local-only (auto-mode classifier blocked `git push`). This
   session attempts the push per /break; if blocked, user pushes manually.

## NEXT STEP (next session)
**Re-run a FRESH round-1 (`python main.py --scenario sim/scenarios/b2_llm_60s.yaml` -> `sixty.json`) and
confirm the global vulnerability + slower-drain changes still produce a COMPETITIVE ~60s fight from 100 hp**
— not an early blowout. Watch: does anyone KO before ~45-50s (too easy)? does the loser still finish in a
reasonable hp band, energy never hitting 0 before health? If it blows out early, lower
`health.hurt_vulnerability_scale` (1.0 -> ~0.7) and/or trim regen back toward 1.4. The MECHANIC is proven
(first health-KO landed from a worn state); the open question is purely whether the same numbers are
balanced from full health. (Token note: 1 fresh 60s round ≈ a few min.)

## PRIOR session — MAJOR REWORK: energy/targeting/combos. 4 user problems fixed + verified; fight flipped decisive.
User gave 4 problems after watching the prior run, asked: commit-first (done, see PRIOR entry), apply fixes,
run a fresh 60s, analyze, break. ALL FOUR fixed and confirmed in one run. Headline: real 3-punch combos now
fire, shots go upstairs, energy no longer flatlines — and the out-boxer flipped from losing to a decisive win.

### The 4 problems → fixes (all verified in `replays/sixty.json`, Red out_boxer vs Blue pressure, seed 42)
1. **Energy drained too fast (~1 after one round).** ROOT CAUSE: regen gate was `not throwing()`, and
   `throwing()` includes the long RECOVERY phase (jab 0.76s … hook 1.4s) — over a 60s round of slow
   recoveries, regen was starved. FIX: regen runs unless *actively winding up* (you breathe as the arm
   resets). New `BoxerState.winding_up()`; `runner._advance` gates on it. + `step_energy 0.4→0.3`.
   RESULT: end energy **20.9 / 20.7** (was 0.8 / 15.6), min ~20 — tired-but-functional, still cross sag(45)
   late (t≈42-44) so the wear-down chain still fires.
2. **Body shots landed too low (viewer).** Glove/flash body target was y=3.0 (belt); torso center ~3.4.
   FIX: `viewer_3d.html` bodyY 3.0→3.3 + flash body 3.0→3.3 (solar plexus/ribs). Visual — user eyeballs.
3. **Too few head shots (IRL most go head/neck).** ROOT CAUSE: fresh head guard blocked 80%
   (`block_factor 0.20`) so body (leaks 0.55) was the only rational target until sag. FIX:
   `block_factor 0.20→0.30` (headhunting a fresh guard now worthwhile; sag-leak endpoints UNCHANGED —
   jab-empty still 0.75, hook still 1.0, only fresh value moved) + prompt reframed head-primary / body-as-setup.
   RESULT: **Red 98% head (57/1), Blue 71% head (36/15)**; ALL jabs to head; all 28 clean lands to the head.
4. **No combos (punch-wait-punch one-offs).** Implemented EXPLICIT COMBOS (chosen over short-term-energy bar
   — simpler, and one LLM call per flurry keeps tokens flat). The LLM adds a `combo` list (1-3 follow-ups) to
   its lead punch; engine fires them alternating hands `combo_interval`(0.25s) apart, FORCE-overriding the
   normal recovery reset (that's what makes it a flurry), each costing energy, fighter COMMITTED (can't
   defend/re-decide until it plays out — `_needs_decision` treats a pending queue as busy; gassed mid-combo
   kills the rest). RESULT: **16 flurries each**, mostly 3-punch jab-cross-hook; 46/58 punches in bursts +
   12 singles = the measure-measure-BURST rhythm. Confirmed firing: t=2.25 jab(L)→2.5 cross(R)→2.75 hook(L).
   LLM reasons it explicitly ("jab to measure, then drive a hard cross while he's recovering, then a hook").

### BONUS — the fight flipped and got decisive
Red (out-boxer) now **WINS 55.5 / 45.5** (was losing 80.7/85.3), ~3× total damage (54.5+44.5 vs 14.8+19.3),
23 clean lands all head. The sharp combination boxer out-points the plodding pressure fighter. Still NO KO
but much closer. LLM calls 80/84 (was 78/71) — combos did NOT blow up token cost. 0 parse errors.

### Files touched
`config.yaml` (regen comment + step_energy + block_factor + timing.combo_interval/combo_max_followups),
`engine/boxer.py` (combo_queue field + winding_up()), `agents/schema.py` (parse+validate `combo`),
`sim/runner.py` (`_launch_punch` helper extracted, `_fire_combo` stage, combo scheduling in `_apply`,
regen gate, busy-includes-combo), `agents/prompts/boxer_system.txt` (head-primary + combos + item 7),
`render/viewer_3d.html` (bodyY), `tests/test_damage.py` (0.20→0.30), NEW `tests/test_combo.py`.

### Verified
- All 6 suites PASS (test_energy/damage/e2e/timing/roster + new **test_combo**: scheduling, alternating
  hands, energy cost, recovery-override, gas-out). Run exited 0, 1201 frames, 0 parse errors both fighters.

### Broken / Open
1. **Still no KO.** Fight is far more damaging + decisive (Blue to 45.5) but nobody finishes. Both end ~20
   energy / 45-55 hp. The finish-nudge (ahead fighter commits to a gassed opponent) is still not done.
2. **Combo balance unwatched on screen.** 3-punch flurries fire correctly in data but NOT eyeballed in the
   3D viewer — do they read as a flurry, and does the new bodyY look right? Open #2 from the viewer angle.
3. **block_factor 0.30 + combos = more damaging fight.** Intended, but if it ever trends toward a too-easy
   KO, 0.30 is the first dial to revisit. Right now it's well-balanced (close decision).
4. **Push blocked.** The commits this session are LOCAL only — the auto-mode classifier denied
   `git push origin main` (bypasses PR review). Must push manually (`git push origin main`) or approve.

## NEXT STEP (next session)
**Eyeball `render/viewer_3d.html` with the new `replays/sixty.json`** — confirm the 3-punch combos read as
real flurries on screen and the raised body-shot height (3.3) looks right (open #2). THEN tackle the last
gap: **the no-KO finish** (open #1) — the fight is now damaging and decisive but nobody gets stopped; add the
"ahead fighter invests energy to finish a hurt/gassed opponent" nudge (prompt and/or a mechanic) and see if
a real health-KO finally lands. (Token note: 60s round ≈ a few min.)

## PRIOR session — RAN + ANALYZED the 4-change 60s round (all 4 WORK; LLM now fights to type). User then gave 4 NEW problems; THIS commit saves the working pre-rework version.
Short session: ran the mismatched 60s round that the previous agent had wired-but-not-run, confirmed all
4 changes landed, and the LLM finally fights to type. User then handed 4 new problems for a major rework
and asked to **commit this version first** (this break), THEN apply fixes, run, analyze, break again.

### Ran the fresh mismatched 60s (`replays/sixty.json`, Red out_boxer vs Blue pressure, seed 42, GPT-5-nano)
Validated the analysis script against the OLD replay first (reproduced the documented baseline exactly:
pocket 1150/1201, Red 48jab/1power, Blue dealt 36.8) — then overwrote it with the new run. Result:
**all 4 of the previous agent's changes work.** Verdict per change (new vs baseline):

| metric | baseline (pre-changes) | this run |
|---|---|---|
| result | Blue dec 86.6 / 63.1 | **Blue dec 85.3 / 80.7** (far closer) |
| min center-distance | 0.045 ft, 872 overlap frames | **1.60 ft, 0 real overlap** (clamp pins 1.5995) |
| in-pocket frames | 1150/1201 (96%) | **961/1201 (80%)** + 220 jab-range + 20 fully out |
| Red punch mix | **48 jab / 1 power** | **8 jab / 27 power** (19 cross, 8 hook) |
| Red clean lands | 14 (all jab) | **10 (8 cross, 2 jab)** |
| Red footwork | — | **63 circle/back vs 6 forward** (steps out, doesn't march in) |
| damage Red took | 36.8 | **19.3** (survived by boxing) |
| numeric vitals in reasoning | 0 / 0 | **Red 7 / Blue 3** (acted on, not just leaked) |

- **#1 min-distance — holds.** Clamp pins center-dist at 1.5995; 0 frames below 1.59 (was 0.045 ft deep overlap).
- **#2 raw vitals — change behavior.** Red at 0 energy explicitly STOPS throwing power, circles to ride it
  out ("I'm at 0 energy, so I can't throw power shots… conserve"); Blue reads opp's sagging head to time a hook.
- **#3 firmer matchup prompts + #4 power-disadvantage reframe — landed hardest.** Red's jab-fest (48/1)
  became real combinations (8jab/27power), and he banks range as defense (circles ~10×, marches 6×).
- **Wrinkle (realistic):** Red landed 10 clean to Blue's 0, yet Blue won — Blue's heavier hands LEAKED
  19.3 dmg through the guard (21 blocked power shots) vs Red's 14.8 clean. Pressure fighter's blocked power
  still outscores the boxer's clean counters. **Still no KO** (open #2): Blue ahead w/ 15.6 en, Red gassed
  to 0.8, but Blue conserved instead of finishing.

### USER'S 4 NEW PROBLEMS (the major rework — to apply NEXT, after this commit)
1. **Energy drains too fast** — down to ~1 after ONE round. Cost too high and/or regen too low over 60s.
2. **Body shots land too LOW** — placement geometry puts body shots below where they should be.
3. **Targeting wrong** — IRL most jabs / most shots go HEAD/neck; game spreads too much to the body.
4. **No combos / fight too slow in a NEW way.** Earlier problem was constant punching (fixed). NOW the gaps
   are good but it's punch-wait-punch-wait one-offs — never a quick BURST (jab…jab…then jab-hook-jab-cross).
   Someone needs to take a risk and unload. User floats a "short-term energy bar" but says it may be prompt
   or mechanic instead — IMPLEMENTER'S CHOICE.

### Verified (this session)
- Run exited 0, 1201 frames, **0 parse errors** both fighters. No code changed this session → test suite unaffected.
- Analysis script saved at the job tmp dir; reproduces the documented baseline byte-for-byte.

## NEXT STEP (next session)
**Apply fixes for the 4 new problems, then run a fresh 60s + analyze, then break.** Likely touch
points: (1) `engine/energy.py` regen_per_sec / `punch_energy` anchors (or a per-60s budget) — energy
shouldn't bottom out at 1 after one round; (2+3) `engine/ring.py land_quality` / placement geometry +
the action-space placement weighting + prompt so shots favor HEAD and body shots sit higher; (4) combos —
evaluate a short-term/stamina "burst" pool vs a prompt-or-mechanic nudge that lets a fighter throw 2-4
punches in quick succession (relax the one-hand-at-a-time / per-step single-throw gate for a deliberate
combo) and rewards a risk-taking flurry. Decide combos approach explicitly before coding (user flagged
short-term energy "may not be the best implementation").

## PRIOR session — ONE-HAND-AT-A-TIME + STRENGTH/SPEED REWORK + FIGHTER ASYMMETRY + 4 FOLLOW-UPS
Long session. Ran the first real 60s round, then three waves of mechanics work. The headline:
**distinct fighters broke the symmetry-draw** (the long-standing KO blocker) — but exposed that the LLM
doesn't yet fight to its physical type. Ended by wiring 4 user-requested fixes; did NOT run after them
(user wants the NEXT agent to run + analyze).

### Wave 0 — ran the first real 60s round (symmetric), analyzed
- `replays/sixty.json` (renamed from `fifteen.json`; all 3 scenarios + README + viewer now use `sixty*`).
  Blue dec 62/63 — the lockstep draw. KEY: within-round fatigue WORKS over 60s (energy 99→~24, both
  cross sag(45) at t≈45, damage accelerates back-half). The "regen won't let anyone tire over a longer
  round" fear is resolved. Cleaned `replays/` to just `sixty.json` + `forty-five.json` (+ run log).

### Wave 1 — two boxing-fidelity fixes (user: "punches with both hands; rework strength/speed")
1. **One hand punches at a time.** Was leaking two ways: `_apply` started a windup on BOTH hands in one
   decision, AND the menu offered "punch" on a hand while the other was mid-punch. Fixed in
   `sim/runner.py _apply` (a hand punches only if the other isn't `busy()` and none thrown this step;
   else it holds guard) + `agents/observation.py _hand_legal` (drops "punch" while the other hand is busy)
   + prompt. Verified live: 0 frames with both hands throwing.
2. **Strength/speed rework.** `eff_speed = max(speed, strength)` — a strong shot can't be thrown slow
   (jab fixed-str 3 is unaffected, so fast-weak stays). Feeds windup + energy → power shots cost more.
   `timing.recovery_time(pt, strength, speed)` now grows with strength (committed = slow reset, dominant)
   and trims with speed (snappy hand resets quicker): jab snaps back 0.74s, power cross 1.29s, hook 1.67s.
   New config `timing.speed_recovery_scale: 0.85`. New `tests/test_timing.py`.

### Wave 2 — FIGHTER ASYMMETRY (user: "mismatch reach/height/strength/agility; LLM must know its edges")
Audited attrs: `power`, `foot_speed`, `stamina` were DEAD; no `height`; `chin` gated off. Gave each a
real mechanic, **all no-op at the 75 baseline** (so symmetric fights/tests stay byte-identical):
- **reach** → effective reach distance (`reach.attr_scale_ft`).
- **height** → head/body reach geometry (`reach.height_head_ft`/`height_body_ft`): a tall boxer tags a
  short head from range; a short boxer reaches a tall body but must get inside for the head. Threaded into
  `ring.land_quality(dist, pt, placement, reach, height, opp_height)`.
- **power** → damage dealt (`damage.power_mult`, `health.power_scale`).
- **agility** → ALL action speed: windup, reaction_delay, step distance (`ring.step_distance`). Replaces
  the old `reaction`/`hand_speed`/`foot_speed` reads.
- **chin** → head-dmg resistance (already wired). **stamina** → regen rate (`energy.stamina_regen_mult`).
- Two archetypes in `config.rosters`: **out_boxer** (tall/rangy/quick/fragile) vs **pressure**
  (short/heavy/granite/slow). Scenario picks via `red.roster`/`blue.roster`; `runner._roster()` merges
  default ← archetype ← inline `attrs`. New `tests/test_roster.py`.
- **LLM awareness:** `observation._matchup()` compares self vs opp per stat and renders a "YOUR EDGE IN
  THIS MATCHUP" block; shared prompt tells them to fight to type.
- **Ran it (`replays/sixty.json`, mismatched):** Blue (pressure) beats Red (out-boxer) **86.6 / 63.1**,
  Red gassed to 0.1 — **lockstep BROKEN** (was 62/63). But the read: fight was in the pocket **1150/1201
  frames**; Red NEVER used his range, threw 48 jabs / 1 hook and gassed; Blue used power (19 hooks/3 cross)
  + granite chin + heavier hands → dealt 36.8 dmg vs Red's 13.4. Mechanics sound; gap is now TACTICAL.

### Wave 3 — 4 follow-ups from watching that fight (DONE, NOT yet run)
1. **Min distance** — fighters were overlapping ("inside each other"). `ring.clamp_min_distance` +
   `ring.min_distance_ft: 1.6`, applied after every step in `_apply`. (1.6 < pocket 2.2 + shortest reach,
   so pocket work still happens.)
2. **Raw vitals** — `config vitals_display: bands → exact`; `observation._vitals()` now shows
   `health NN/100, energy NN/100` for BOTH fighters (was qualitative bands). NOTE: this deliberately
   overrides the long-locked "never show numbers" principle — it's a user experiment, reversible via the
   config switch. (Openings still use the 45 sag threshold internally; not shown as a number.)
3. **Firmer matchup prompts** — rewrote `_MATCHUP` lines + the prompt's matchup paragraph: each explains
   HOW to exploit the edge and WHY (at the wrong range one literally can't land), firm but "this isn't an
   order — it's the read."
4. **Power-disadvantage reframed** — the lighter fighter was pawing 48 jabs because the prompt over-sold
   "outbox, stay cheap." Fixed the POWER-disadvantage matchup line + the jab doctrine (item 4 + the punch
   bullet): the jab is a SETUP not the score; throw real combinations (cross/hook/uppercut); "a busy jab
   that never sets up a power shot wins nothing."

### Verified
- All 5 suites PASS: `test_energy`, `test_damage`, `test_e2e` (mock still Draw/300/1 — clamp doesn't bite),
  `test_timing`, `test_roster`. Archetype divergence checked numerically (at 3.0 ft the out-boxer jabs the
  pressure head but pressure can't reach back; pressure hits 24% harder; clamp pushes 0.3ft→1.6ft; raw
  vitals render correctly).

### Broken / Open
1. **LLM doesn't fight to type (the live one).** Mismatch is mechanically real but the out-boxer let
   himself be dragged into a pocket war he can't win and over-threw jabs. Waves 3.1/3.3/3.4 target exactly
   this (min distance, firmer "use your reach" prompt, throw real shots) — UNTESTED. This is the thing to
   watch next.
2. **Still no KO.** Blue won big but conserved too hard to finish a gassed Red. The "ahead fighter should
   invest in the finish" nudge (prior open item) is still not done.
3. **Raw-vitals experiment** un-evaluated — does showing numbers actually improve decisions (commit when
   opp health low / conserve when own energy low), or just leak the abstraction? Watch the reasoning logs.
4. 3D viewer still never eyeballed live; `forty-five.json` still a pre-asymmetry baseline (deferred).

## NEXT STEP (next session)
**Run the mismatched 60s round (`python main.py --scenario sim/scenarios/b2_llm_60s.yaml` → `sixty.json`)
and analyze the 4 changes.** Specifically: (a) is min distance holding — no overlap, and does it read
better? (b) does the out-boxer now USE his range — fewer pocket frames than 1150/1201, steps out when
pressured? (c) does the lighter fighter throw REAL shots now (crosses/hooks/uppercuts up from 1, jabs down
from 48)? (d) do raw vitals change behavior in the reasoning logs? Then the remaining levers are the
no-KO finish-nudge (open #2) and, if the out-boxer still won't box, a stronger start-at-range setup.

## PRIOR session — 1-MIN ROUNDS + LLM-AWARE BETWEEN-ROUND REST + GLOBAL HALF-SPEED
User asked "are we done?" then gave three concrete asks: (1) rounds should be 1 minute; (2) the LLMs
should KNOW that after a round they get +10 energy and +5 health from the rest break; (3) slow the whole
fight to half speed (his framing: "our 15-second round will end up taking 30 seconds").

### What got done (all three asks)
1. **1-minute rounds** — `round_seconds: 15 → 60` in all three scenarios (`b2_llm_15s.yaml`, `_r2`, `_r3`).
2. **Between-round rest, +10 en / +5 hp, and LLM-aware:**
   - `sim/runner.py` carry block now reads a new `rest_health` field and applies it CAPPED at full:
     `b.health = min(_H["start"], s["health"] + rest_health)`. (Energy already capped at the ratcheted
     ceiling via the existing `rest_energy` path.)
   - `_r2`/`_r3` scenarios: `rest_energy: 5 → 10`, added `rest_health: 5`.
   - `agents/prompts/boxer_system.txt` (energy paragraph): boxers now told "this is one round of several;
     between rounds you get a corner rest that gives back a good chunk of your wind and a little of your
     health, so DON'T reach the bell hoarding a full tank — spend everything on a late finish." Kept
     band-language / no raw numbers, consistent with the locked no-thresholds design.
3. **Global half-speed** — in `config.yaml`, DOUBLED every duration so relationships are preserved:
   windups (jab .18→.36 … uppercut .36→.72), recoveries (jab .38→.76 … uppercut .78→1.56),
   slip/duck durations+recoveries, `reaction_delay_base` .10→.20, and both poll intervals
   (opening .1→.2, live .15→.30). Scaling reaction_delay with the windups keeps "jab too fast to slip,
   power shots slippable" intact; doubling polls also halves idle re-poll token cost.

### Verified
- All unit tests PASS (`test_energy`, `test_damage`, `test_e2e`) — half-speed timing broke nothing.
- Mock continuation dry-run (no API) confirmed the carry math: RED hp 40→45 (+5), energy 12→22 then
  ratchets to the 25 cap; BLUE hp 98→**100** (+5 capped at full), energy 48→**50** (+10 capped at the
  ratcheted ceiling). Both caps fire correctly.
- Did NOT run a full 60s LLM fight (token cost; user repeatedly flags tokens). Offered to.

### Broken / Open
1. **Stale filenames** — scenarios are still `b2_llm_15s*.yaml` → `replays/fifteen*.json` but now run 60s.
   Left surgical; offered to rename to 60s/sixty (touches README + viewer defaults).
2. **Within-round fatigue may be lighter at half-speed** — `regen_per_sec` (1.2/s) is per REAL second and
   unchanged, so over a longer 60s round at a slower throw-rate fighters may recover more between throws.
   Cross-round ceiling wear-down is unaffected. Did NOT pre-tune (no speculative change without a real
   fight to measure). WATCH this in the first real 60s run.
3. **Pre-existing, untouched:** no KO under symmetry (identical boxers diverge never → Draw); continuation
   is still a manual 3-scenario chain (= roadmap B4); 3D viewer never eyeballed live.

## NEXT STEP (next session)
**Run the real 60s R1→R2→R3 continuation on GPT-5-nano and read the result.** Confirm (a) the half-speed
pace looks right / fewer frantic exchanges, (b) the rest carries +10 en / +5 hp between rounds as wired,
and (c) whether the prompt's "spend at the bell" nudge changes late-round behavior. CRITICAL to watch:
does the unchanged per-second regen leave nobody tired over a 60s round (open #2)? If so, the wear-down
chain dies and regen needs a tune. (Token note: a 60s round ≈ 2× the old 15s test.)

## PRIOR session — POWER SHOTS NOW PAY OFF (jab-fest broken) + 3-round continuation analysis
Goal: make power shots pay off so the fight isn't a jab-fest (open #1). Then: "run a round 3 and analyze."

### Two-lever fix (BOTH were needed)
1. **Mechanic (`engine/damage.py`)** — `block_multiplier` now takes `punch_type`; the sagging-guard
   leak SCALES BY PUNCH POWER. A fully-sagging guard still parries a jab at 0.75 (byte-identical to
   before) but a hook blasts through at ~1.0 (0.20 + 0.55·1.6, capped), cross 0.92, uppercut ~1.0.
   `raw_damage` forwards `punch_type`; runner needed NO change (already passes `pt`). New test
   `test_sagging_guard_leaks_power_more_than_jab`; updated the existing sagging test (hook now ~1.0 not
   0.75). All unit tests PASS.
2. **Prompt nudge (`agents/prompts/boxer_system.txt`, item 6)** — the mechanic ALONE did nothing
   (R2 still 32 jab / 2 cross / 1 hook clean). Diagnosis: power shots were barely THROWN (47 jab vs 4
   hook / 0 uppercut), and NOT because of range (hooks legal 62% of frames, uppercuts 40%). The reasoning
   logs showed the LLMs EXPLICITLY name the sagging openings then jab them "to conserve energy" — the
   conservation reflex overrides the finish, and it fires exactly when both (identical) fighters are
   gassed. So added a nudge: a sagging head is the moment to SPEND, a loaded hook costs barely more than
   a jab but can finish him, pecking wastes the one opening that wins the fight.

### Verified — both levers together broke the jab-fest (R2, the worn/sagging round)
| R2 metric                 | mechanic only | + prompt nudge |
|---------------------------|---------------|----------------|
| power shots THROWN        | 7             | **21**         |
| power shots CLEAN         | 3             | **14** (10 cross, 4 hook) |
| total clean lands         | 35            | **54**         |
| end health (Red / Blue)   | 59.7 / 58.1   | **36.4 / 39.7** |
| end energy                | 24 / 22       | 16.6 / 19.0    |

R1 (fresh, no sag) unchanged — nudge correctly doesn't fire there. 0 parse errors throughout.

### Round 3 (user ran it; `replays/fifteen_r3.json`) — Draw, no KO
Cumulative health arc R1→R2→R3: **75/79 → 36/40 → 20/20**; energy floor 0/0 at R3 end. Damage
ACCELERATED into R2 then DECELERATED in R3: once both fighters bottom out at 0 energy, total exhaustion
swings them BACK to maximal conservation (hook throws collapsed 8→1) and `output_factor` caps damage at
0.6, so the round grinds instead of finishing. Deeper ceiling: identical boxers on a fixed seed wear down
in LOCKSTEP (R3 ended 19.9 vs 20.5 hp, 0.0 vs 0.0 en) — neither falls far enough behind for the other to
load up while still having gas. **A KO needs ASYMMETRY between the fighters, not another balance tweak.**

### Broken / Open
1. **No KO under symmetry.** The wear-down + power-shot model is sound, but identical boxers gas in
   lockstep → Draw at the energy floor. Finish needs distinct stats/styles (deferred roster work) so one
   fighter sags first and the other can capitalize while still fresh enough to load up.
2. **Continuation is still a manual 3-scenario chain** (`b2_llm_15s.yaml` → `_r2` → `_r3`, each
   `carry_from` the prior replay). No auto round-loop / KO-stop / aggregate scorecard / between-round
   ceiling lift = roadmap B4.
3. **3D viewer still not eyeballed live** by me (carried over). R2/R3 not watched on screen — power
   shots/sagging not visually confirmed.
4. Transient: R3's first launch died on an `APIConnectionError` (network blip); a re-run succeeded. Not
   a code issue.

## NEXT STEP (next session)
**Give the boxers ASYMMETRY so a fight can actually finish** (open #1). The wear-down + power-shot levers
work; the only thing blocking a KO is that identical fighters never diverge. Options: (a) distinct
roster stats (e.g. different stamina/recovery or chin) so one sags first; (b) seed/style asymmetry. Then
re-run the R1→R2→R3 continuation and confirm the worn-down fighter eats a power-shot finish (a real
health-KO, not the removed energy-gate). Keep the 15s continuation as the test; do NOT touch
`forty-five.json`. (Token note: 15s is the everyday test, ~minutes per round.)

---

## PRIOR session — MULTI-ROUND CONTINUATION (round 2 carries round 1's state) + 15s realism analysis
Goal: read into `replays/fifteen.json`, figure out what makes the game better/more realistic. Then (if R1
looks good) run a **round 2 that CONTINUES from round 1** — same health, +5 energy each for the rest break.
Explicit: do NOT touch / regenerate `forty-five.json` this session.

### What I found in round 1 (`replays/fifteen.json`, 15s GPT-5-nano, seed 42)
- Blue wins by decision (88/78 hp). 43 lands: 17 clean / 26 blocked. No KO.
- **Jab-fest:** 37/43 lands are jabs; only 5 cross + 1 hook + 0 uppercut land. Power shots ARE thrown
  (57 hook/cross windups) but almost never connect — their long recovery exposes the thrower and the
  opponent's guard rarely opens.
- **Nobody tires:** energy ends ~58–60; regen (1.2/s) fully offsets a 15s round, so NOBODY crosses the
  sag threshold (45) → the fatigue→sagging-guard→clean-shot→KO chain never fires. This is the core
  realism gap, and it's exactly what multi-round wear-down fixes.

### What got done — continuation-round mechanic
1. **`sim/runner.py`** — new `carry_from` + `rest_energy` scenario fields. After making the boxers, if
   `carry_from` is set, read that replay's LAST frame and seed each fighter's `health`, `energy_ceiling`
   (the RATCHETED cap — carried, NOT lifted = accumulated fatigue), and `energy = min(ceiling, prev+rest)`.
   Minimal: ~10 lines + `import json`. No other engine change.
2. **`sim/scenarios/b2_llm_15s_r2.yaml`** — round 2: `carry_from: replays/fifteen.json`, `rest_energy: 5`,
   `output: replays/fifteen_r2.json`, seed 42.

### Verified — round 2 VALIDATES the realism hypothesis
- Carry seeds correctly (mock dry-run: R2 starts Red 78.2hp/~65en, Blue 88.0hp/~60en, ceiling 75).
- All unit tests (`test_energy`, `test_damage`, `test_e2e`) PASS after the runner change.
- **`replays/fifteen_r2.json` (Red wins by decision):** both fighters START worn and CROSS the sag
  threshold mid-round (Blue <45 by t6, Red by t8). Result vs R1:

  | metric            | R1 | R2 |
  |-------------------|----|----|
  | clean lands       | 17 | **35** |
  | blocked lands     | 26 | **16** |
  | health dmg to Blue| 21.8 | **36.0** |
  | both cross sag(45)| never | **yes** |
  | avoids (defense)  | 6  | **0** |
  | result            | Blue dec | Red dec |

  Cumulative: Blue 100→88→52, Red 100→78→64. A round 3 would very likely KO Blue (52hp/18en, deep sag).
  Defense COLLAPSES when tired (0 slips landed in R2) — the intended `reaction_penalty_at_empty` (0.25)
  degradation, and it reads realistic.

### Broken / Open
1. **Still jab-dominant — power shots don't pay off.** R2's clean jump (17→35) came from JABS leaking the
   sagging guard (32 jab / 3 cross / 0 hook clean), NOT from power punches. The jab already cracks a tired
   guard cheaply, so there's no incentive to risk a slow, exposing power shot. The "load the power shot
   when he sags" doctrine in the prompt isn't being acted on. THIS is the next realism lever.
2. **Continuation is a manual 2-scenario setup, not a feature.** You run R1, then run R2 pointing at R1's
   replay. No round loop, no auto-stop-on-KO, no aggregate scorecard, no viewer round-break. That's the
   roadmap B4 ("multi-round matches, between-round rest, ratchet caps lift") — `rest_energy`+ceiling-carry
   is the seed of it.
3. **3D viewer still not eyeballed live** by me (carried over from prior session); blocked-flash color
   question still open.

## NEXT STEP (next session)
**Make power shots pay off so the fight isn't a jab-fest** (open #1). Options: (a) prompt nudge — once the
opponent reads "sagging", explicitly switch to a power shot to the head; (b) mechanic — a sagging guard
should leak POWER shots far more than jabs (scale the sag block-leak by punch power), so the risk of the
slow shot is rewarded. Pick one, re-run the 15s (R1 then R2), confirm hooks/uppercuts/crosses start
landing clean on a tired guard. Keep using R1→R2 continuation as the realism test; do NOT use the 45s.

---

## PRIOR session — 3D REPLAY VIEWER (browser / Three.js)
Goal: the 2D viewer makes it hard to tell what's happening; wants a simple 3D viewer (JS is fine; NOT
Unity-level — simple human figures, simple arm movement). Past Python **Ursina** attempt was "really bad",
so Python desktop-3D options (pyvista/Panda3D) were rejected by analogy. Locked via AskUserQuestion:
**Three.js in the browser + drag-and-drop file loading** (no server, no build step, no assets).

### What got done
- **`render/viewer_3d.html`** — one self-contained file. Loads Three.js 0.160 from unpkg via importmap
  (needs internet on first open); reads the SAME replay JSON the 2D viewer uses. No engine changes.
- Boxers are primitives (sphere head, capsule torso, cylinder legs + two dynamic arms). Each arm is a
  thin cylinder re-spanned every frame from shoulder→glove + a glove sphere.
- **Poses mirror engine hand states** (`gloveLocal`): guard/free → gloves at chin, windup → cocked back,
  recovery → glove snapped out to head/body per `placement`; glove glows yellow on a live punch.
- **Defense shown**: `duck` crouches the figure, `slip_left/right` shifts the head laterally. Boxers face
  each other (rotation.y = atan2 toward opponent); lean in while punching.
- **Impact flash** on `land` events: yellow ring = `clean`, light-gray (reads whitish) ring = `blocked`.
- HUD (HP/energy bars, clock, phase, end result), per-fighter reasoning panels (toggle), OrbitControls
  camera (drag to rotate/zoom — the whole point), playback (Space, ←/→ scrub, slider, 0.25–4× speed, ⟲).
- Position interpolation between frames for smooth motion.

### Verified
- Field names checked against `replays/fifteen.json` (event `kind`/`by`/`quality`/`placement`, hand
  states, defense values all match). `node --check` on the embedded module = clean. User confirmed
  "this looks great" — but NO live-browser eyeball from my side yet (couldn't see a browser).
- Caught + fixed an axis bug pre-ship: figure faces along local +Z but arms/flash were built on +X →
  punches would've fired sideways. Converted forward to +Z throughout.

### Bug I introduced & fixed (axis convention)
`rotation.y = atan2(face.x, face.z)` makes local **+Z** = forward, but `gloveLocal`, the shoulder anchor,
and the flash offset were all written with **+X** = forward. Fixed all three to +Z.

## NEXT STEP (next session)
- **Eyeball `render/viewer_3d.html` in a real browser** with `replays/fifteen.json` — confirm punches
  extend toward the opponent (not sideways), slips/ducks read right, and clean-vs-blocked flashes are
  distinguishable. Open question raised by user re: yellow (clean) vs whitish-gray (blocked) flash being
  too subtle — offered to make blocked a distinct color (slate blue) or add a "BLOCK" label; awaiting word.

## PRIOR session — ENERGY RE-CENTERED as capacity (not a win condition)
User feedback (from watching logs): the LLMs treat "drain his energy" as the GOAL. Wrong. The only goal
is HEALTH → 0 (KO) + land the most hits. Energy is **capacity**: it gates how hard/fast you punch and how
well you defend (slip/block/move). Low energy must NOT auto-KO — it just means you can't defend, so the
opponent lands easy clean high-strength shots that take your HEALTH. Decision (locked via AskUserQuestion):
**keep body→energy as a MEANS** (drain → his defense fails → clean head shots → health → KO), not a win path.

### What got done
1. **Killed energy as a win condition.** `config.yaml` `zero_energy_next_hit_is_ko: false` (gassed-KO path
   kept config-gated for reference; `ko_energy_threshold` now unused). KO is health-only. This deliberately
   un-does last session's first-KO mechanic — on purpose.
2. **Strengthened low-energy defense degradation** so "tired = can't defend = eats clean 10s" is real:
   `reaction_penalty_at_empty` 0.12 → **0.25** (at empty, reaction delay grows past most windups → can't
   slip/block in time). Sagging-guard block-leak (0.20→0.75) already covered blocks.
3. **Reframed the prompt** (`agents/prompts/boxer_system.txt`): replaced "ENERGY IS WHAT WINS FIGHTS" with
   "YOU WIN ONE WAY: TAKE HIS HEALTH TO ZERO… energy is your CAPACITY TO FIGHT, not a way to win"; body
   plan item "DRAIN HIM" → "SAP HIM SO HE CAN'T DEFEND… the body is the means, the head is where you
   finish him"; fixed item 6 + the head/body opening line. Also fixed the bottom energy band phrase (was
   "the next clean shot ends it" — promised the now-removed gassed-KO) → "guard's dropping, wide open to
   clean shots".
4. **Replays pruned to TWO fixed files.** Renamed the two most-recent → `replays/fifteen.json` (15s) and
   `replays/forty-five.json` (45s); deleted the other 11. Each scenario now ALWAYS overwrites its own file
   via a new `output:` field (`b2_llm_15s.yaml`→fifteen, `b2_llm_45s.yaml`→forty-five) honored by
   `runner` (`output or sc.get("output") or …`). README slimmed to just those two run+watch commands and
   the tests; fixed the now-false energy-KO blurb. `test_e2e` writes its mock replay to tempdir so
   `replays/` stays exactly the two curated files.

### Verified
- `test_damage`, `test_energy` (updated the 0.25 assertion), `test_e2e` all PASS. `replays/` = exactly
  `fifteen.json` + `forty-five.json`.
- **15s GPT-5-nano, seed 42** (`replays/fifteen.json`): the framing shifted. Per-decision drain-vs-health
  term ratio **1.81:1 → 1.11:1** (vs the old sagfix run); slips now **LAND 0 → 6** (avoid events), similar
  slips chosen. Reasoning is now instrumental ("body shots… loosen his guard, setting up upstairs shots",
  "duck to absorb minimal exposure"). 0 parse errors. Result: Blue decision, end health 78/88.
- **Honest tradeoff:** the 15s fight is LESS damaging now (78/88 vs 60/66; 14 clean head vs 35) because
  with the energy-KO gone + full regen NOBODY gasses in 15s (end energy ~56–60), so the fatigue→sag→
  open-head→health chain never fires. Correct under the new model — finishes need a long round where
  someone actually tires.

## NEXT STEP (next session)
- **Regenerate `replays/forty-five.json` under the new model** (`python main.py --scenario
  sim/scenarios/b2_llm_45s.yaml`) — it's still a PRE-recenter run (shows the old gassed-out KO that can no
  longer happen). Confirm the new model still produces a FINISH over 45s — now a health-KO after fatigue
  degrades defense, NOT an energy-gate trip. This is the real test that removing the energy-KO left a
  viable path to a knockout. Token note from user: 15s is the everyday test; run 45s only occasionally.
- Still open: slips chosen often but landing improved (0→6) — watch whether timing reads right on screen.

---

## Earlier session — FIRST KO (open problem #2, RESOLVED) [superseded: energy-KO removed above]
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
