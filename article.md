# LLM Boxing Agents — What We Had to Add (and Why)

Notes for an article. Tracks every scaffold/design decision made to get nano-class models to box
believably with only a fixed controller-style menu. Sibling of the football article — same thesis:
**physics owns the body, the LLM only picks intent from a feature-enriched menu.**

---

## Base Setup

- Two boxers, each an LLM (`gpt-5-nano` / local Ollama), called at *decision steps* (not every tick).
- 16x16 ft ring, deterministic physics tick at dt=0.05s. Seeded RNG; one fight reproduces exactly.
- The LLM never sees coordinates or does geometry. It is handed the full scenario in plain English
  plus a list of currently-legal moves with consequences pre-annotated, and it picks one.
- Output: one JSON action per decision step — a state for each hand (punch/guard/free), optional
  footwork, optional slip/duck — plus a `reasoning` string shown floating over the boxer in 3D.

---

## Design Decisions (pre-build, from the founding Q&A)

**Two-regime time model.** A pure event-driven loop has no "feeling-out" phase — boxers would freeze
at range forever waiting for the other to commit. So the fight opens in a *timed poll* (both boxers
asked every 0.1s) and only flips to event-driven decision steps once the first punch is thrown. The
opening is the only place we burn calls on a clock.

**Reaction-delay instead of freezing the clock.** The naive way to let a defender respond to a punch
is to pause time and ask them. But that makes every punch reactable and kills fast-hands as a skill.
Instead the clock keeps running and a chosen defense only becomes *effective* after a reaction delay —
so a low-telegraph fast punch (short windup) can land before the guard arrives. Speed is now a real,
spendable weapon, paid for in energy and in lower strength.

**Windup / impact / recovery phases as the whole risk model.** Rather than abstract "cooldowns," each
punch telegraphs (windup, which the opponent can see and which is cancel-able into a duck/slip),
strikes for one tick (impact), then locks the hand with no guard (recovery). High strength buys
damage but lengthens recovery — the exposure window *is* the cost of headhunting.

**Energy cost curve fit to human anchors.** The user gave three intuition points (10str/10spd->3,
10str/1spd->1, 1str/10spd->0.5). Rather than guess a formula we solved a 3-term model
`0.78*(s/10)+0.22*(s? )...` — strength*speed cross-term dominates, so cranking both is punishingly
expensive while a fast soft jab is nearly free. Lets the model learn to pick its spots.

**Ratchet energy caps (75/50/25).** Straight regen lets a boxer stall and fully recover, producing
boring fights. One-way descending caps mean stamina only ever trends down (with small in-band
recoveries) — fatigue is permanent-ish, so late rounds genuinely degrade. Pairs with the
"energy 0 -> next clean hit is an instant KO" cliff: gassing out is lethal, not just slow.

**Body shots drain energy, head shots drain health.** A single health bar, but each placement splits
its damage between opponent health and opponent energy. This gives the body jab/hook a *strategic*
purpose (work the body to set up the energy-0 KO) without needing a second health bar yet.

**Single-pass decisions (for now).** Football needed a two-pass read->commit split because throwing a
football is a coupled arc/timing/coordinate problem the model can't solve mentally. Boxing's action
space is discrete and the menu is pre-annotated, so we start single-pass and only add a pass if the
model picks badly. (Watching for the football failure mode: committing to an action whose consequence
it didn't actually check.)

**Identical boxers v1.** Both fighters share stats (all 75) so any difference in the fight comes from
the two LLMs, not the sheet. The roster is wired for divergence later.

---

## Observations (B1, first Ollama runs)

**The slot/scalar split made the "4000 combinations" problem vanish in practice.** We never enumerate
the move product — the model fills hand/footwork/defense slots and writes two integers (strength,
speed). qwen3:8b returned legal JSON every single call (0 parse errors across the first LLM-vs-mock
fight) without ever being shown a combinatorial menu. The legality pre-filter (out-of-range and
unaffordable punches simply absent) means the model can't pick an impossible move even if it wants to.

**Deterministic hidden bands worked first try, and the model reasoned in their language.** Without ever
being told what the phrases map to, qwen3 wrote things like "target body to drain energy" and "exploit
his partial guard" — it inferred the body-drains-energy mechanic from the system prompt's qualitative
description and acted on the "partial" opening read. Never having a number to anchor on did not hurt it.

**Coherent boxing intent emerged from a tiny action vocabulary.** Sample reasoning chain in one 3s
fight: close distance to land a cross → step back to avoid an incoming hook → block and counter to the
body. That's recognizable boxing from a model that only ever sees words and a legal-move list.

**Blocking is too strong (first tuning casualty).** block_factor=0.20 applied uniformly + a mock that
guards often = nearly every punch chips for <1 damage; the only clean shots were when a guard was down.
A single global block multiplier is too blunt — blocking needs to be line-specific (a high guard should
leak body shots). Logged for B3. Classic case of a v1 constant that's correct in shape but wrong in
balance.

**Latency is the real constraint, not capability.** qwen3:8b "thinks," so each decision is seconds of
wall-clock; a full 15s round at ~1 call/0.1-0.15s is many minutes. The sim clock is decoupled from
wall-clock (fine), but iteration speed pushes toward disabling thinking ("/no_think") or a faster model
for live play.

**3D primitives were a readability dead end; 2D side-view won.** The ursina viewer (chunky cubes/spheres,
instant teleporting movement, a top-down-ish camera) made it genuinely impossible to tell who was
guarding, who was open, or what landed — even after fixing an all-white color bug (this ursina build's
`color.rgb` wants 0-1, not 0-255) and the camera. The fix was not more 3D polish but a flat 2D pygame
side view where a pose is unambiguous: gloves at the chin = guard, arm cocked = windup, arm out to a
head/body point = the punch, head dropped = duck. Pairing the animation with an event-by-event
play-by-play log and an impact flash (clean vs BLOCK) did more for comprehension than any 3D work. Lesson:
for an agent game, the viewer's job is to make the *decision state* legible, and 2D iconography beats
low-fi 3D for that.

**Watching the replay exposed that the fight is too static — a design finding the metrics hid.** Telemetry
(health/energy/landed counts) all looked fine, but watching it, the boxers just plant and trade: almost
no footwork, zero slips/ducks (defense is always a held guard), and block decisions carry no real
reasoning. None of that showed up in "0 parse errors, coherent reasoning, correct damage." The agents
optimize the cheapest legal win (stand in range, punch, block) because nothing in the observation or
balance rewards moving, slipping, or angling. Confirms the thesis cuts both ways: a legible viewer is
itself an eval — it surfaces degenerate-but-passing behavior that aggregate numbers don't.

---

## Observations (B3, dynamics + balance pass)

**A reaction-delay model can silently make its own defense unusable.** Slips were *chosen* by the model
and *still landed* on it. The bug: the avoidance window was computed from the decision time `t`
(`active_until = t + slip_duration`) while the slip only became *effective* after the reaction delay —
so the delay ate ~0.10s out of an 0.18s window, leaving the head offline for only ~0.08s. Combined with
impact-time being rounded up to the next physics tick, a telegraphed hook landed *just* past the window.
The fix was conceptual, not numeric: anchor the window to the *effective* time (`slip_window(eff)`), so
the reaction delay *delays* the slip rather than *shortening* it. Lesson: with a delayed-effect defense,
always measure the active window from when it goes live, not from when it was ordered.

**The legality resolver silently inverted the model's intent — visible only in the reasoning string.**
The model kept writing "slip his hook, then counter to the body" as a *single* action: a defense field
*and* a punch. Our resolver's tie-break was "they chose to punch, so drop the conflicting defense" — so
the engine threw the punch and discarded the slip, i.e. the model's defensive intent was silently
converted into trading, and it ate the exact shot it meant to slip (a clean 6.73 head hook that flipped
the fight). Nothing looked wrong: legal JSON, 0 parse errors, a plausible action. The only evidence was
the mismatch between the `reasoning` ("slip...") and the applied engine state (a hook windup) in the
replay JSON. Two fixes: (1) flip the tie-break to *defense-first* (if the model bothered to name a slip,
honor it; the engine already ignores the hands while defending), and (2) tell the model in the prompt
that a slip is a *standalone step* and the counter comes on the *next* one. After the flip, the same
matchup inverted — the LLM slipped, stayed unmarked, and won. Lesson: when an action menu allows
mutually-exclusive intents, the conflict-resolution default is a real design choice, and you can only
catch a wrong one by diffing *stated intent against executed action*, not by validating the action alone.

**A symmetric scripted verifier collapses into a degenerate equilibrium that tests nothing.** The mock
exists to exercise *every* move so the engine/viewer can be checked — but mock-vs-mock produced 47/47
*blocked body shots*, zero slips, zero clean hits, zero movement after the first step. Two identical
"guard the head, dig the unslippable body" heuristics lock into a body-shot stalemate where none of the
interesting paths (head shots, slips, footwork) ever fire — so the "verifier" was silently verifying
nothing. Had to perturb it deliberately (alternate head/body targets, periodically reset range/circle)
to make the paths exercise. Lesson: a symmetric deterministic opponent is not a test fixture until you
break its symmetry; sameness produces a stable but uninformative fixed point.

**Models coach themselves into useless moves without a "why/when," not just a "what."** The first prompt
described every control precisely (what a slip does, what strength costs) but gave no game plan — and the
model fought accordingly: technically-legal moves with no strategy, e.g. slipping *body* hooks (which
can't be slipped at all) and stepping *backward* in the same move it was trying to land a punch (pulling
itself out of range → whiff). Adding a short strategic doctrine — energy is the battery the fight is
fought over, make him spend while you conserve, slip>block, pick power shots for openings, work the body
to drain — visibly changed the reasoning chains and the outcomes. The model has the capability; it needs
the *objective function* spelled out, because a pile of correct mechanics doesn't imply a strategy.

---

## Observations (B3, dynamic-openings pass)

**The prompt asked for upstairs work; the *observation* made it impossible — and the observation won.**
The fight was a monotonous `body_left` spam (92% body, 82% blocked) despite a prompt that explicitly says
"soften the body, the head opens up, go for the finish." We almost rewrote the prompt again. The real
culprit was the feature layer: `_openings` read the head as permanently `GUARDED` whenever the opponent
held any guard, so a head shot was *always* a strictly-dominated choice and the model — correctly —
never threw one. The model's reasoning even narrated the right plan ("drain the body, then go up top")
while its hands couldn't, because "up top" never appeared as available. Lesson: an LLM agent's behavior
is bounded by what the observation makes *representable*, not by what the prompt *requests*. A degenerate
policy is often a rational response to an impoverished state read, not a reasoning failure — fix the menu
before touching the prompt.

**One observation change cascaded into four emergent behaviors.** Rebuilding `_openings` to read the
opponent's *actual* per-hand state (a hand mid-punch or in recovery isn't guarding its side → that side
is `OPEN`) plus a fatigue-driven `sagging` head read, and reframing the range line so "out of range" is
described as free defense + a chance to recover — in one 15s LLM-vs-LLM fight (same seed/model), head
shots went 4→17, ring movement 10→41 footwork steps (distinct floor cells 2→7), slip *attempts* 3→16,
and parse errors 8→0. We changed *what the model can see*, not what it's told to do, and the strategy it
was already reasoning about became executable.

**An advisory opening the damage layer doesn't honor is a lie the model faithfully acts on.** The new
`sagging` read (a gassed opponent's high guard is dropping → head is openable) got the model to throw
upstairs — 17 head shots — but **zero landed clean**; every one was blocked or glancing. `sagging` is a
*fatigue* cue, but the guard is still mechanically UP, and the damage resolver only checks the binary
`guarding()` and applies the full block multiplier. So the observation invited a shot the engine then
fully blocked. The model did exactly as told and got nothing. Lesson: every opening you surface in the
read must be backed by the impact-resolution layer — a feature that *suggests* an opportunity the physics
won't *honor* trains the model to waste energy on a mirage.

**Rewarding movement without re-tuning drain trades one stalemate for another.** Framing distance as
defense worked almost too well: fighters circled out, banked energy (ending ~55 vs ~22 before), and
took far less damage (health 86/90 vs 65/73), and whiffs jumped 2→15 as punches chased opponents who'd
stepped off. The fight looks dynamic but became *less* decisive — nobody gasses now, so the energy-0 KO
moved further away. The body-spam stalemate became a keep-away stalemate. Lesson: defense and aggression
are coupled through the energy economy; buffing the safe option (move/retreat/recover) without also
raising the cost of passivity or the reward of pressure just relocates the degenerate equilibrium.

## Observations (B3, KO + watchability pass)

**A discrete KO trigger on a continuous variable that regenerates is effectively unreachable.** The
finishing rule — "at energy 0, the next clean shot is an instant KO" — never once fired, even after we
lengthened the round until *both* fighters bottomed out at ~0.2 energy and 66 clean shots landed. The
condition was `defender_energy <= 0.0` checked at the moment of impact. But energy regenerates at
1.2/s (0.06/tick), so a spent fighter always bounces a hair off zero between hits: at every clean
landing the defender read 0.05, 0.17, 0.43 — never exactly 0. The exact-equality test on a variable
with a restoring force is a measure-zero event. Worse, this was the *same* observation-vs-mechanics
disagreement as the sagging guard: the bottom energy band already tells both fighters "completely spent
— the next clean shot ends it" (floor = 1.0), while the engine demanded 0.0. The fix was to make the
KO threshold the floor of the band the observation already advertises (`ko_energy_threshold: 1.0`), not
to hunt for the magic instant of zero. First KO in the project landed immediately after: a fighter
emptied his tank throwing a punch and got countered clean while spent. Lesson: when a state read
promises a consequence, the mechanic must trigger on the *same boundary* the read uses — and a KO gate
on a self-restoring quantity needs a band, never an equality.

**Slowing punches for watchability silently un-did the decisiveness work.** A previous agent lengthened
windup/recovery so a human could see each punch land (recovery jab .15→.38s, up to .78s for an
uppercut). It worked visually, but longer recovery means fewer punches per second, which means fewer
exchanges, which means less accumulated damage: the same 15s fight ended at health 80/83 (vs 60/66) and
energy 58/52 (vs 30/27) — prettier and *less* decisive. Pacing and outcome are coupled through
throughput. The fix was to decouple them on a different axis: keep the slow, legible pace and buy back
the lost exchanges with round length (15s → 45s) rather than re-speeding the punches. Lesson: when a
readability change moves an outcome metric, don't trade one against the other on the same knob — find
the orthogonal lever (here, time) that restores the outcome without giving back the readability.

## Observations (B3, energy re-centered as capacity, not objective)

**The "drain his energy" strategy was prompt-induced, not emergent.** Reading the fight logs, both
fighters obsessively reasoned about draining the opponent's energy ("targeting energy drain and opening
the head", "drain him with body shots", "bank energy") — it looked like a sophisticated war-of-attrition
strategy the models had discovered. It wasn't. The system prompt literally opened a paragraph with
"ENERGY IS WHAT WINS FIGHTS — TREAT IT AS YOUR BATTERY" and "whoever still has gas in the late going
wins", and plan item 2 was "DRAIN HIM WITH THE BODY". The mechanics backed it (a gassed-out KO path,
body shots dumping damage into an energy bar). The models were just faithfully optimizing the objective
we *told* them was the objective. Lesson: before reading agent behavior as emergent strategy, check
whether you wrote it into the prompt. A goal stated in the system prompt will be pursued as a terminal
goal, even when you meant it as a means.

**We deleted the first KO one session after shipping it — on purpose.** The gassed-out KO (energy < 1.0
+ clean hit) made *energy* a win condition, which is the wrong model: in a real fight low energy doesn't
end you, it just means you can't defend, so you eat clean head shots that take your *health*. So energy
should be **capacity** (it gates punch power/speed and defense reaction), never an objective. The fix was
almost entirely subtraction + reframing, not new machinery — the capacity model already existed
(`output_factor`, `reaction_penalty`, the sagging-guard block-leak all keyed off energy). We flipped off
the energy-KO, rewrote the prompt to "YOU WIN ONE WAY: TAKE HIS HEALTH TO ZERO… energy is your capacity
to fight, not a way to win", and reframed body work as "sap him so he can't defend → open the head".
Measured on the same seed: the drain-vs-health framing ratio in the reasoning went 1.81:1 → 1.11:1, and
slips actually *landed* 0 → 6 times — the models gravitated to taking zero damage once getting hit, not
draining a tank, was the thing that mattered.

**Removing a discrete win-condition makes short rounds less decisive — correctly.** With the energy-KO
gone and regen intact, nobody bottoms out in 15s (end energy ~56–60), so the fatigue → guard-sags →
head-opens → health-falls chain never fires, and the fight is a low-damage feeling-out (end health
78/88, decision). That's not a regression — it's the honest consequence of the new model: a finish now
*requires* actually wearing someone down over a long enough round, instead of a cheap threshold trip.
The decisiveness lever moved from "trip the energy gate" to "round length × accumulated fatigue", which
is where it belongs.

## Observations (B3, 3D viewer in a different language entirely)

**A clean replay format let a renderer in a different language drop in with zero engine changes.** The
sim writes a flat JSON replay (per-tick positions, hand states, placements, defense, events) that the
pygame 2D viewer already consumes. When "2D is hard to read" came up, adding a *browser* 3D viewer
(Three.js, JavaScript) was a pure additive renderer — no touch to the engine, the recorder, or the
Python side at all. The payoff of the recorder/viewer split from B2 wasn't really visible until a viewer
showed up in a language the engine can't even import. If the renderer had been reading engine objects
instead of a serialized snapshot, this would have been a port, not a new file.

**Rejecting a bad tool meant rejecting its whole category, not just the library.** A prior Python
**Ursina** attempt had been "really bad". The reflexive next step is "try a different Python 3D lib"
(pyvista, Panda3D). But Ursina *is* Panda3D underneath, and the thing that made it bad — a heavyweight
desktop-3D window with clunky playback — is shared across the Python desktop-3D category, not specific to
Ursina. The better move was to leave the category: a browser + Three.js gives a free orbit camera,
hot-reload, drag-and-drop file loading, and no asset pipeline, for a stick-figure-grade scene. Lesson:
when a tool fails, ask whether the failure is the library or the category before swapping within it.

## Observations (B3, a fully-built balance mechanic that was dead on arrival)

**A mechanic can be correct, unit-tested, and still never fire — because the operating regime never
reaches its trigger.** The whole wear-down model (fatigue → guard sags below 45 energy → block leaks →
clean shots → health KO) was built and passing tests. But reading a 15-second fight's replay showed it
was *inert*: energy regen (1.2/s) fully offsets a 15s round, so neither fighter ever drops below the sag
threshold — 37 of 43 landed punches were jabs, 17 clean / 26 blocked, no finish, ever. The bug wasn't in
the mechanic; it was that a single short round never enters the regime where the mechanic does anything.
The fix was therefore *not* to retune the fatigue numbers but to change the regime: run a **second round
that carries the first round's health and the ratcheted energy ceiling, with only a +5 rest bump**. Same
fighters, same prompt, same everything — except now they start worn. Round 2 immediately validated the
model: both fighters crossed the sag threshold mid-round, clean shots doubled (17→35), blocks halved,
the loser ate 36 health (vs 21.8 in round 1), and defense collapsed (slips landed 6→0, the intended
"too tired to react" degradation). The lesson: before tuning a mechanic that "isn't doing anything,"
check whether the scenario ever satisfies its precondition — the answer changes whether you touch the
formula or the harness around it. Carrying the *ratcheted ceiling* (not lifting it) is what makes fatigue
accumulate across rounds, which is the realistic path to a knockout that no single short round can produce.

**Opening the head doesn't get power shots thrown — it gets more jabs thrown.** Even once guards sagged
and clean shots doubled, the models still won with jabs: of 35 clean lands in round 2, 32 were jabs, 3
crosses, and zero hooks/uppercuts. The reasoning is rational — a cheap, fast jab already cracks a tired
guard, so why risk a slow power shot with a long, exposing recovery for the same opening? An observation
that *advertises* an opening ("he's sagging") plus a prompt that *says* "load the power shot" is not
enough; the model won't pay the power shot's cost unless the opening rewards power specifically (e.g. a
sagging guard should leak hooks far more than jabs). Telling the model an opening exists and rewarding it
for exploiting that opening with the expensive tool are two different things.
