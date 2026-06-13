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
