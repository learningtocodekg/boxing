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

## Observations (B3, making power shots pay — and the symmetry ceiling)

**Raising a tool's payoff does nothing if the model never reaches for the tool — and the bottleneck was
not where it looked.** We fixed the jab-fest the principled way first: the sagging-guard block-leak now
scales with punch power (a tired arm can't absorb a hook's momentum), so a fully-sagging guard still
parries a jab at 0.75 but a hook blasts through at ~1.0. Correct, unit-tested, jab behavior byte-identical
— and it moved the fight not at all (round 2 still 32 jab / 2 cross / 1 hook clean). The reason: the
models threw 47 jabs to 4 hooks and 0 uppercuts. A payoff buff on a shot that's never thrown is inert.
The natural suspect was *range* (hooks/uppercuts are short-range, must be in the pocket) — but measuring
the actual distance per frame killed that theory: hooks were legal 62% of frames, uppercuts 40%. The
constraint was purely behavioral, and only the reasoning logs revealed it: the models *explicitly named*
the sagging openings ("his guard shows head_right sagging and head_center sagging") and then chose a
"quick, cheap jab to his sagging head_center opening" — *to conserve energy*. The conservation reflex was
overriding the finish.

**The conservation reflex fires at exactly the moment it shouldn't, because the trigger and the cost peak
together.** A guard only sags when its owner is gassed — which, with identical boxers fighting in lockstep,
is exactly when the *attacker* is also gassed and most reluctant to spend. So the one opening that wins
the fight appears precisely when both fighters are most determined to save energy, and the cheap jab wins
the cost-benefit every time. Worse, the reflex was *miscalibrated*: the energy curve puts a hook at only
~1–1.5 energy, barely more than a jab, but the models reasoned about power shots as if they were
expensive. The fix that actually worked was a prompt nudge aimed squarely at this reflex — "a sagging head
is the moment to SPEND, not save; a loaded hook costs barely more than a jab but can finish him; pecking
wastes the one opening that wins the fight." With both levers in place (mechanic *and* nudge), round 2
power shots went 7→21 thrown, 3→14 clean, total clean lands 35→54, and the loser's end health dropped from
~60 to ~36. The mechanic made power *pay*; the nudge made them *throw* it. Neither alone sufficed. Lesson:
when an agent won't use a capability, separate "is it rewarded?" from "is it being selected?" — they have
different fixes, and aggregate stats answer neither; the reasoning string does.

**Identical boxers cap the fight at a Draw — the finish needs asymmetry, not more tuning.** With both
levers working, we ran the continuation out to a third round. Damage kept accumulating (cumulative end
health across R1→R2→R3: 75/79 → 36/40 → 20/20) but it *decelerated* and ended in a Draw at the energy
floor, no KO. Two coupled reasons: (1) once both fighters hit 0 energy, total exhaustion swings them
*back* to maximal conservation — power throws collapsed 8→1 in round 3 — and `output_factor` caps damage
at 0.6, so the round grinds rather than finishes; (2) the deeper ceiling is symmetry: identical boxers on
a fixed seed wear down in lockstep (R3 ended 19.9 vs 20.5 health, 0.0 vs 0.0 energy), so neither ever
falls far enough behind for the other to load up on a sagging guard while still having gas of his own — a
real KO needs one fighter to be *more* gassed than the other. The wear-down model is now sound and the
power-shot fix works; the missing ingredient for a knockout is divergence between the fighters (distinct
stats/styles), not another balance constant.

## Observations (B3, "slow it down" is a scaling problem, not a single knob)

**"Make the fight half-speed" only stays balanced if you scale the things that were tuned *against* each
other — and one of them is invisible.** The obvious move is to double the punch durations. But the whole
defense model rests on a *relationship*: `reaction_delay_base` was deliberately set below the jab/cross
windup and above the hook/uppercut windup, so straight shots land before a slip takes hold while power
shots are slippable. Double the windups and leave reaction delay alone, and every punch silently becomes
slippable — the fight's defensive character flips without a single line of obviously-wrong code. The fix
is to treat half-speed as a uniform time-dilation: every duration *and* the reaction delay scale by the
same factor, so all the relationships are preserved and only the wall-clock pace changes. The lesson is
that tuned constants come in coupled sets; a "global" pace change has to move the whole set, and the
coupling isn't visible from any one value.

**A rate that's denominated in real seconds doesn't scale when you stretch the clock — so slowing the
fight can quietly neuter fatigue.** Energy regen is `1.2/sec`. Punch *costs* are per-action, so halving
the throw-rate halves the spend-rate — but regen keeps ticking at 1.2 per real second regardless of pace.
Stretch a round from 15s to 60s at half-throw-rate and the budget quietly tilts toward recovery: fighters
get far more idle seconds to bank energy between the same number of throws. The wear-down chain
(fatigue → sagging guard → open head) depends on fighters actually tiring, so a pure "slow it down + make
rounds longer" change can dissolve the very mechanic the project was built around — not through a bug, but
through a rate that doesn't participate in the rescaling. We shipped it unchanged on purpose (no
speculative tuning without a real fight to measure) but flagged it as the first thing to watch.

**When the user hands you exact numbers for the model to "know," the band-language principle still wins.**
The ask was "the LLMs should know they get +10 energy and +5 health between rounds." The locked design is
that the system prompt never exposes raw thresholds — the model reasons in phrases, not integers. Putting
"+10/+5" in the prompt would be the first numeric leak and wouldn't even help: 10 out of a tank that
ratchets down has no meaning in band-space. So the knowledge went in qualitatively — "a corner rest gives
back a good chunk of your wind and a little of your health" — which conveys both the asymmetry (more
energy than health) and the strategic point (don't hoard at the bell) without breaking the abstraction.
The user's numbers belong in the *mechanic* (the runner's carry math), not the *prompt*.

## Observations (B3, fighter asymmetry — the draw breaks but the model won't box)

**Half the "roster" was config theater.** The boxers had `power`, `foot_speed`, `stamina` attributes,
assigned per fighter, sitting in `config.yaml` looking like tunable knobs. None were read by any engine
code — `power` never touched damage, `foot_speed` never touched movement, `stamina` never touched regen.
`chin` was wired but baseline-gated to a no-op. A stat that exists in config but isn't consumed isn't a
feature, it's a comment that looks like one — and it's invisible precisely because nothing breaks. The
asymmetry work was less "add new stats" and more "make the stats we already pretended to have actually do
something," with every effect designed to be a no-op at the 75 baseline so symmetric fights stayed
byte-identical and the whole existing test suite stayed green.

**Distinct fighters finally broke the symmetry-draw ceiling — but the LLM still wouldn't fight to its
type.** For many sessions, identical boxers on a fixed seed wore down in lockstep and every fight ended a
draw at the energy floor; the diagnosis was "a KO needs asymmetry, not more tuning." Asymmetry delivered:
a tall/rangy/quick out-boxer vs a short/heavy/granite pressure fighter produced a decisive 86.6–63.1
result with one man gassed. The surprise was *which* man. The rangy boxer — whose entire mechanical edge
is that at distance he lands and the other man literally cannot reach him — spent **1150 of 1201 frames in
the pocket**, threw 48 jabs and one power shot, and gassed out, despite a matchup card in his prompt that
said in plain words "you're longer, plant at that range, the moment he closes step out and reset." A
coherent strategic brief did not survive contact with the moment-to-moment pull toward the nearest visible
target. The lesson: telling an LLM its optimal style is not the same as getting it to execute that style
turn by turn — the local "there's an opening, hit it" reflex overrides the global plan, the same way the
"conserve energy" reflex earlier overrode "load the power shot." Imposing a style may need mechanical
scaffolding (a minimum range, a start-at-distance), not just better prose.

**A "you're the weaker puncher" framing made the model stop punching.** Told it hit lighter and should
"outbox, stay cheap, don't trade," the low-power fighter pawed 48 jabs and threw exactly one real shot —
doing almost no damage and gassing anyway from sheer volume of nothing. The model read "you're weaker" as
"don't throw power," which is the opposite of boxing: a lighter hitter still throws crosses and hooks, he
just doesn't stand and swap bombs. A disadvantage has to be framed as *what to do instead* (throw real
combinations, then slide off) — not only *what to avoid* — because the model over-applies pure avoidance
into passivity. Same failure shape as an over-tuned "conserve" doctrine: a negative instruction with no
positive target collapses to doing nothing.

## Observations (B3, the scaffolding hypothesis paid off — and a "who won" surprise)

**A 1.6 ft floor and a reframed prompt got the model to box.** The prior entry ended on a hypothesis:
imposing a style may need mechanical scaffolding (a minimum range), not just better prose. Tested it. Two
changes — a hard `min_distance_ft` clamp so fighters can't occupy the same square, plus rewriting the
weak-puncher's brief from "outbox, stay cheap" to "the jab is a SETUP not the score, throw real
combinations" — flipped the out-boxer's behavior wholesale: 48 jabs/1 power shot became 8 jabs/27 power,
time-in-pocket dropped 96%→80%, and he started stepping out and countering with crosses instead of being
dragged into a brawl. Damage taken fell from 36.8 to 19.3. The interesting part is that the clamp is a
crude, almost dumb mechanism — it doesn't *teach* range, it just makes overlap physically impossible — and
yet it was enough to let the prose instructions finally take. The plan didn't need to be more persuasive;
the world needed to stop offering the move the plan told him to avoid. That's the same lesson as removing
illegal moves from the menu: the cheapest way to change an LLM's behavior is often to change what's
*possible*, not what it's *told*.

**The model landed 10 clean shots to zero and still lost — correctly.** A pleasant accident of the
damage model: the out-boxer out-landed the pressure fighter 10 clean to 0, yet lost the decision, because
the pressure fighter's *blocked* power shots leaked 19.3 health through a tiring guard while the boxer's
clean-but-lighter counters did 14.8. Nobody designed "blocked bombs beat clean pawing" — it fell out of
the line-specific block factor plus power-scaled leak interacting with two asymmetric stat lines. It's
exactly how a pressure fighter beats a busier boxer in real life, and it appeared without being asked for,
which is the rare good kind of emergent behavior (the usual kind is a degenerate jab-fest).

## Observations (B3, the rework: a regen gate, rational body-punching, and combos as recovery-override)

**"Energy drains too fast" was a phase-boundary bug, not a balance number.** A fighter ended a 60-second
round on ~1 energy out of 100 — flatlined. The instinct is to nudge a cost or a regen rate, but the real
cause was a category error in one line: regen ran only while `not throwing()`, and `throwing()` was true
through the *entire* punch — including the long RECOVERY phase where the arm is just coming back to guard
(0.76s for a jab, 1.4s for a hook). So a busy fighter spent most of the round mechanically forbidden from
breathing. The fix wasn't a number, it was splitting one predicate into two: you hold your breath on the
*windup* (the exertion), and you get it back during the recovery (the reset). End energy went from ~1 to
~21 with no rate change at all. The lesson is the usual one for these sims — when a tuned-looking quantity
is wildly off, suspect a state-machine boundary before you suspect the constant.

**The model wasn't mis-targeting the body — it was being rational about an 80% wall.** The complaint was
"real boxers throw mostly to the head; this throws too much body." But a fresh high guard blocked 80% of
head shots (`block_factor 0.20`) while the body leaked 55%, so until a fighter gassed, the body was simply
the higher-EV target and the model went there — correctly, given the rules. No amount of "aim upstairs"
prose fixes a payoff matrix that punishes upstairs. Dropping the fresh-guard block to leak 30% (a guard
that stops 70% is still a strong guard) flipped the EV, and head-targeting jumped to 98%/71% across the two
fighters with the same prompt nudge that had done nothing before. Third time this project has hit the same
wall: the model's "bad" behavior was the rational read of the mechanics, and the cheap fix is the mechanic,
not the paragraph.

**Combos are just "fire the next punch before the hand has reset" — and that one override carried the
whole feature.** The fight had good *gaps* but no *bursts*: every exchange was one punch, then a full
recovery, then a re-poll — structurally one-offs, because a hand can't throw again until it resets and the
other hand is pinned to guard while it's busy (a rule added earlier to stop both fists firing at once). The
question was whether to add a second "short-term energy" resource (the user's own first guess) or something
simpler. The simpler thing won: a combo is a single decision that schedules 2-3 follow-up punches which
*force-fire on the alternating hand even while the previous hand is still recovering* — overriding exactly
the reset that was serializing everything. That one override is the entire mechanic; no second resource, no
new bar. It also turned out to be token-*cheaper* than the status quo, because one LLM call now buys a whole
flurry instead of one punch — calls stayed flat (80 vs 78) while punches thrown rose ~60%. And it produced
the rhythm the user wanted on the first run: measure, measure, then a three-punch jab-cross-hook, with the
model reasoning about it explicitly ("jab to measure, then drive the cross while he's recovering, then the
hook"). Worth noting what *didn't* need touching: the renderer reads hand states per frame, so rapid
alternating windups animate as a flurry for free — the feature was visible without a single line of viewer
code. The combined effect (combos + viable head shots) flipped the result outright: the rangy boxer who'd
been losing in a brawl now out-pointed the pressure fighter 55-46 by stringing clean head combinations —
the asymmetry finally expressing itself as *style* rather than just a damage-leak accounting quirk.
