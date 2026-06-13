# Glass Joe Minds — LLM Agents Box

A 3D boxing simulator where **both boxers are controlled by LLM agents**. Each agent reads the
fight as structured text, reasons in boxing terms, and at each *decision step* picks **one action
per hand plus optional footwork** from a fixed menu. A deterministic physics/timing engine turns
that intent into motion, contact, damage, and energy drain. The LLM never does geometry or math —
it is handed the full scenario and a list of legal moves and simply chooses.

This is the boxing sibling of an earlier football sim and reuses its stack and its core
design philosophy. Read that project's `README.md` for the engineering lineage.

---

## 1. Design Pillars (carried over from football)

1. **Physics controls the body; the LLM controls intent.** The model never computes angles, reach,
   reaction windows, or damage. It picks from a feature-enriched menu of *legal* moves.
2. **The observation does the feature engineering.** Every decision step we hand the agent the full
   scenario in plain English — ranges, openings, energy, what the opponent just did — and a flat list
   of currently-legal moves with their consequences pre-annotated. (Football's hardest-won lesson:
   the nano model behaves only when the math is already chewed.)
3. **Deterministic engine + seeded RNG.** Same seed + same actions → identical fight. Contact is a
   deterministic *geometry/timing gate* followed by a single seeded roll for the contested margin.
4. **Structured text in, JSON out.** One system prompt (the rules of boxing + how energy/timing
   work — timeless), one user message per decision step (the live scenario + legal moves).
5. **Clip-worthy 3D replay is the deliverable.** Ursina viewer, two primitive boxers, floating
   reasoning text per fighter. Everything serializes to a replay JSON that the viewer reads.
6. **Dual provider.** `gpt-5-nano` (OpenAI) and local Ollama, same as football's `llm_client.py`.

---

## 2. Milestones / Phasing

Mirrors football's A1→A4 incremental verification. **We do not move to the next phase until the
current one is verified watchable in the 3D viewer.**

| Phase | Description | Round length | Status |
|---|---|---|---|
| **B1** | One LLM boxer vs a **scripted/mock** opponent. Goal: prove every move (each punch, placement, block, slip, duck, step) actually fires in the engine and renders. No API spend needed for the mock. | full 2 min or KO | Not started |
| **B2** | **LLM vs LLM**, **15-second** rounds. Short rounds keep API cost and iteration time low while we confirm the two agents interact sanely (trade punches, block, gas out, KO). | 15 s or KO | Not started |
| **B3** | Tune energy/damage/timing config against B2 fights; lengthen rounds; add energy-regen ratchet + degradation polish. | grows toward 2 min | Not started |
| **B4** | Knockdowns + 10-count, multi-round matches, rest-between-round recovery. (Deferred — see §13.) | — | Not started |

**Build order within B1:** engine + config → action schema → resolution → mock opponent →
runner loop → ursina viewer. Verify each move type on screen before wiring the LLM.

---

## 3. The Ring & Coordinate Model

- **Ring:** 16 ft × 16 ft square. Internally we work in **feet**, origin at one corner,
  `x ∈ [0,16]`, `z ∈ [0,16]` (floor plane). Vertical axis `y` is height (for head/body targeting and
  the viewer). This matches the "physics owns coordinates, LLM never sees them" rule — the LLM is
  **never** given raw coordinates.
- **Boxers auto-face each other.** Orientation is computed by the engine every tick; the LLM does not
  set facing. The LLM influences position only through discrete footwork picks (§7.3).
- **Range** = center-to-center distance between the two boxers (feet). This is the boxing analog of
  football's *separation* and is the single most important spatial quantity (see §6).
- **Ring position** matters only through **cornering**: when a boxer is at/near a wall, the footwork
  options that would push them further into that wall/corner are removed from the legal-move list and
  the observation flags `CORNERED`. There is no other positional penalty in v1.

---

## 4. Time Model (the trickiest part — read carefully)

There is a continuous deterministic physics clock ticking at `DT` (config, default **0.05 s**). The
LLM is **not** called every tick. It is called at **decision steps**. There are two regimes:

### 4.1 Opening regime (before the first punch of the fight)
At fight start both boxers are idle and out of/at range. Starting at `t = 0.1 s`, **both boxers are
called on a fixed cadence** (every `opening_poll_interval`, default **0.1 s**) and may circle, step,
feint, or throw. This continues **until the first punch is thrown by either boxer.** The opening is
the only time-polled regime — it exists so the fight has a "feeling-out" phase instead of a frozen
standoff.

### 4.2 Live regime (after the first punch)
Once any punch is thrown, the fight becomes **event-driven**. A **decision step** for a given boxer is
triggered by either:
- **(a) self-completion** — that boxer's currently locked action finishes (a hand frees up, a step
  completes, a slip/duck recovers), **or**
- **(b) opponent commitment** — the opponent *initiates* a new action (most importantly a punch) that
  the boxer might need to respond to.

At a decision step we call only the boxer(s) whose state actually changed. The physics clock keeps
running underneath; we do **not** freeze time during an LLM call in the live regime — instead the
**reaction-delay model** (§4.4) governs whether a response lands in time.

### 4.3 Action phases & locks
Every hand action is a **punch** with three phases on the physics clock:

```
   WINDUP            IMPACT            RECOVERY
|------------|         |          |------------------|
 telegraph,         damage         hand locked,
 opponent can       checked        cannot guard
 see it coming      (one tick)     this hand
```

- **Windup duration** shrinks with `speed` effort and the boxer's `hand_speed` attribute. A 10-speed
  jab has almost no telegraph; a 1-speed haymaker is heavily telegraphed.
- **IMPACT** is the single tick at which contact/damage is resolved (§9).
- **RECOVERY** locks that hand (no guard, no new punch) for a duration that grows with `strength`
  effort and punch type — big power shots leave you exposed longer.
- A hand in **guard/block** or **free** has no phases; it can transition at the next decision step.
- **Defensive moves** (slip/duck/step) have a **duration + short recovery** during which the boxer is
  briefly off-balance (cannot punch; see legality rules §8).

Each phase's duration comes from `config.timing` and is scaled by attributes and effort. The agent
never sees these numbers as math — it sees consequences ("a 9-speed jab is hard to react to").

### 4.4 Reaction-delay model (why fast punches beat slow defenses)
When boxer A initiates a punch, boxer B gets a decision step **at A's windup start** (regime 4.2b).
B chooses a defense, but it only becomes **effective** after `reaction_delay` (config, modified by
B's `reaction`/`foot_speed` attributes and lowered/raised by B's energy via degradation §6.4).

Resolution at A's IMPACT tick compares timelines:
- If **B's defense is effective before A's IMPACT** → the defense applies (slip avoids, block
  reduces, etc.).
- If **A's IMPACT lands before B's defense is effective** → the punch lands clean (B got caught
  mid-reaction). This is how a fast, low-telegraph punch beats a human-late guard.

So: **fast punch = short windup = less reaction time for the opponent**, at the cost of lower
strength (and the energy/strength tradeoff). This is the central risk/reward knob.

### 4.5 Who is called, and concurrency
Both boxers may have a decision step in the same tick. We resolve **attacker-commits-then-
defender-reacts** ordering for clean causality: the puncher's initiation is registered first, then
the defender's decision step is raised with that punch already visible in its observation. In the
opening regime both are polled; ties broken by seeded RNG, then re-evaluated next tick.

---

## 5. Energy System

- **Pool:** starts at **100.0** per boxer. Energy gates power and reaction and is the slow-burning
  resource of the fight.
- **Cost of a punch** is a function of the two effort knobs the LLM sets, `strength s ∈ [0,10]` and
  `speed v ∈ [0,10]`. Fit to the user's anchor points
  `(s=10,v=10)→3.0`, `(s=10,v=1)→1.0`, `(s=1,v=10)→0.5`:

  ```
  punch_energy = 0.78·(s/10) + 0.22·(v/10) + 2.0·(s/10)·(v/10)
  ```

  (Verified: 10/10→3.00, 10/1→1.00, 1/10→0.50.) **Energy cost depends only on strength and speed —
  punch type does NOT affect it.** This keeps the menu clean: "max strength you can afford right now"
  is one number, identical across all punch types (no case where you can afford a 10 uppercut but not
  a 10 hook). Punch type still drives *damage* (§9), just not energy. **Jab uses a fixed strength**
  (`jab_fixed_strength`, default 3) so its energy is driven by speed only.
- **Cost of movement:** each footwork step costs `step_energy` (default **0.4**). Holding a guard
  costs a small `guard_energy_per_sec` trickle (default **0.2/s**). Slips/ducks cost
  `slip_energy`/`duck_energy` (default **0.3 / 0.5**).
- **Regen (ratchet):** energy slowly regenerates while a boxer is *not* throwing
  (`regen_per_sec`, default **1.2/s**, only while idle/guarding/circling). **Ratchet caps:** once
  energy drops **below 75**, it can never recover above 75; once below **50**, never above 50; once
  below **25**, never above 25. So stamina is a one-way decline punctuated by small recoveries within
  the current band. Between-round rest recovery (B4) lifts the caps partially — deferred.
- **Energy = 0 rule:** if a boxer's energy is **0**, the **next clean hit they take is an instant
  KO**, regardless of that punch's computed damage. (Gassed fighters get knocked out.)

### 5.1 Energy degradation (gradual, before the cliff)
Low energy also continuously scales a boxer's **output and reaction** (not just the 0-cliff):
- Effective punch power and effective speed are multiplied by `output_factor(energy)`, a curve from
  **1.0** at full energy down to **~0.6** near empty (`config.energy.degradation`).
- Reaction delay grows as energy falls (tired boxers react slower).

This makes gassing out *felt* — your shots get weaker and your guard gets later — well before the
0-energy KO rule triggers.

---

## 6. Range & Reach

- **Range** (center-to-center feet) gates which punches can land. Each punch type has a **reach**:
  `jab > cross > hook > uppercut` (config `reach`). A punch only reaches IMPACT if the opponent is
  within that punch's reach at the impact tick.
- To land inside shots (hook/uppercut) you must **close distance** with footwork; the jab is the
  long-range tool. The LLM is **told**, per punch, whether the opponent is currently **IN RANGE** or
  **OUT OF RANGE** — it never computes this.
- Range also feeds **land quality**: a punch landing at the very edge of its reach is **glancing**
  (`glancing_mult`, default 0.6); in the pocket it is **clean** (1.0).

---

## 7. The Action Space (what the LLM picks)

Each decision step the agent outputs an action covering the hand(s)/legs that are currently **free**
(not locked mid-phase). The full vocabulary:

### 7.1 Hands — each hand is in exactly one state
- **`punch`** — with four sub-fields:
  - `punch_type ∈ {jab, cross, hook, uppercut}`
  - `placement ∈ {head_center (chin), head_left, head_right, body_left (ribs), body_center (solar_plexus)}`
  - `strength ∈ [0,10]` (ignored/fixed for jab → `jab_fixed_strength`)
  - `speed ∈ [0,10]`
- **`guard`** — that hand is held up blocking (heavy damage reduction, §9.3; small energy trickle).
- **`free`** — hand down/neutral (no block, ready, no cost).

A boxer **may throw with both hands** (e.g. left hook + right cross) — but then **no hand is
guarding**, leaving them open. One hand punching + one hand guarding is the safe default.

### 7.2 Punch/placement damage ordering
Per the design intent, to the head: **hook > uppercut > jab** (config `punch_type_power_mult`,
default `jab 1.0, cross 1.3, uppercut 1.45, hook 1.6`). The jab's *power* is capped by its fixed
strength, so even a clean jab is a low-damage range-finder; hooks/uppercuts at high `strength` are
the fight-enders. Placement multipliers (config `placement_mult`) make head shots higher health
damage; body shots do less health but carry extra **energy** damage (body work to drain stamina) —
see §9.

### 7.3 Footwork (legs) — one discrete pick, optional
`step ∈ {forward (close range), back (open range), left, right, circle_left, circle_right, none}`,
fixed small distance per step (`step_distance`, default ~1.0 ft). Footwork can be combined with a
hand action (step-in jab), **except** it cannot be combined with a slip/duck (those lock the legs).
At a wall/corner, illegal directions are removed and `CORNERED` is flagged.

### 7.4 Defense (head/upper body) — reactive
- **`slip_left` / `slip_right`** — head movement off-line; avoids a head punch on that side if
  effective in time (§4.4). Brief recovery; cannot punch during it.
- **`duck`** — drop under a head punch (avoids head shots, exposes to body shots/uppercuts). Brief
  recovery; cannot punch.
- **block** is just a hand in `guard` state (§7.1), not a separate move.

A boxer can **cancel a punch's WINDUP to duck/slip** (as the user described) — but **cannot duck and
punch simultaneously** (§8).

---

## 8. Legality Rules (what gets removed/locked each step)

The engine computes the **legal move list** every decision step; the observation only ever offers
legal moves, so the LLM cannot pick an impossible action. Rules:

1. A hand in WINDUP/IMPACT/RECOVERY is **locked** — no new action for it (but its WINDUP may be
   **cancel-able** into a duck/slip, which forfeits the punch).
2. **Cannot duck/slip and punch in the same step** (off-balance). If one hand is mid-punch and the
   boxer ducks, the in-flight punch is **canceled**.
3. **Footwork ⊕ slip/duck are mutually exclusive** (slip/duck lock the legs).
4. **Cornered:** footwork directions into the wall/corner are removed; `back` is illegal when backed
   up; lateral steps into the wall are illegal.
5. **Out-of-range punches** are still *offerable* but flagged `OUT OF RANGE (will miss)`; the engine
   may instead simply mark them illegal in B1 to keep the menu tight — decided during build.
6. **Energy floors:** a punch whose energy cost exceeds remaining energy is illegal (you cannot throw
   what you cannot afford). At energy 0 you may only move/guard.

The observation explains *why* a move is missing ("cannot step back — you are against the ropes";
"right hand locked: recovering from your cross until +0.3 s").

---

## 9. Health & Damage Resolution

- **One health bar**, starts at **100.0** per boxer. **0 health = instant KO**, fight over (no
  knockdown/count in v1 — deferred to B4).
- Resolution runs **only at a punch's IMPACT tick**, and only if the geometry/timing gate passes.

### 9.1 The gate (deterministic)
A punch reaches IMPACT and is eligible to land iff:
1. opponent within the punch's **reach** at impact (range gate, §6), **and**
2. the opponent's chosen **defense is not effective in time** (timing gate, §4.4) for the relevant
   line (a left-slip beats a right-side head punch, a duck beats head punches, etc.).

If the gate fails → **miss/avoided** (no damage; the attacker still paid energy + is in RECOVERY).

### 9.2 The damage formula
If the gate passes:

```
strength_value = jab_fixed_strength            if punch_type == jab
               = strength (0–10)               otherwise

base        = strength_value · DAMAGE_PER_STRENGTH         # DAMAGE_PER_STRENGTH = 0.5  → 10 str ≈ 5.0
raw         = base
            · punch_type_power_mult[punch_type]            # jab 1.0, cross 1.3, uppercut 1.45, hook 1.6
            · placement_mult[placement]                    # head vs body weighting
            · land_quality                                 # clean 1.0 / glancing 0.6 (range edge)
            · output_factor(attacker_energy)               # 1.0 → ~0.6 as attacker gasses (§5.1)
            · block_factor                                 # 1.0 if unblocked; heavy reduction if blocked (§9.3)
            · contest_roll                                 # seeded RNG margin, ~[0.9,1.1] (§9.4)

health_damage = raw · placement_health_share[placement]
energy_damage = raw · placement_energy_share[placement]    # body shots drain more opponent energy
```

- A clean max hook to the chin (`s=10`): `5.0·1.6·placement·1.0·1.0·1.0·~1.0 ≈` high single hit
  (tuned so a fight lasts a realistic number of clean shots; exact via config).
- **Body shots** trade health for **energy damage** — working the body to gas the opponent toward the
  energy-0 KO rule. **Head shots** (esp. `head_center`/chin) carry the most health damage.
- **Energy-0 override:** if the defender's energy is 0 and the gate passes → **instant KO**.

### 9.3 Blocking
A hand in `guard` covering the struck side applies `block_factor` (default **0.2** → 80% reduction —
"heavy reduction," per design). Blocked power shots still leak a little health and cost the blocker a
little energy (absorbing the shot). A block only covers the side/line it is held on; a body shot
under a high guard still gets through.

### 9.4 Determinism
`make_rng(seed)` (copied from football `sim/seeds.py`) seeds one RNG. The only randomness is
`contest_roll` (the contested margin) and opening-regime tie-breaks. Same seed + same agent outputs →
identical fight, byte-for-byte replay.

---

## 10. The Observation (what the LLM is handed)

Per the user: **"we give it the full scenario and available moves. It simply chooses a move. No
geometric stuff."** The observation is plain English, no coordinates, no trig. It contains:

1. **Fight clock & round:** time left, round number.
2. **Your state:** health and energy as **deterministic band phrases** (see §10.1) — never raw numbers;
   plus what each hand is doing and when it frees up, footwork status, whether you are `CORNERED`.
3. **Opponent state:** their health/energy as the **same deterministic band phrases** (you *read* them —
   "fresh and loose" / "gassing badly, legs going"). Incoming punch power is read from its **windup
   telegraph** ("a heavy, telegraphed hook" vs "a quick jab"), not a number. Plus their guard posture
   (which lines are open: "their right side is low — body_right is OPEN"), and **what they just
   did** (the trigger event: "opponent threw a
   left hook at your head — it is mid-windup", or "opponent is circling left", or "nothing — they are
   resetting").
4. **Range read:** one line, plain English — "you are IN THE POCKET (hooks and uppercuts reach)" or
   "you are AT JAB RANGE (only the jab reaches; step in to land hooks)".
5. **Legal move menu:** a flat list of the moves available *this step*, each annotated with its
   consequence given current geometry/energy — e.g.:
   - `jab → head_center: IN RANGE, fast, ~2 energy. Their guard is high here (likely blocked).`
   - `hook → body_left: IN RANGE, their right hand is low → OPEN. Costs ~12 energy at 8 strength.`
   - `slip_left: avoids a punch coming to your head-left. Brief off-balance.`
   - `step_back: ILLEGAL — you are against the ropes.`

This menu is where all feature-engineering lives. The model reads the situation and the consequences
and **just picks**. (Mirrors football's "feature-enriched menu so the nano model never does math.")

### 10.1 Deterministic vitals bands (hidden mapping)
Health and energy are **never** shown as raw numbers. Each is mapped through a **deterministic**
number→phrase table (`config.observation.energy_bands` / `health_bands`) — the same hidden number
always produces the same words, for **both fighters**. Example energy bands: `≥90 "fresh and loose,
full tank"`, `45–60 "starting to blow, arms getting heavy"`, `15–30 "gassing badly, legs going"`,
`0 "completely spent — wide open, the next clean shot ends it"`.

**Crucially, the system prompt never reveals the thresholds or that a phrase corresponds to a number
range.** The agent is told only "you read your and your opponent's condition in words" and is trusted
to be smart enough to act on it. This keeps the read realistic (you sense a tired/hurt fighter, you
don't get a HUD number) and avoids the model gaming exact thresholds. `vitals_display: exact` exists
only as an A/B escape hatch if bands prove too opaque for nano. **Timing reads are qualitative the
same way** — the agent is told "the hook is coming fast — time to slip or block, but not to counter,"
never "lands in 0.24s."

---

## 11. Decision Flow & Schema

- **Single pass** (per the user — boxing's action space is discrete enough). The agent returns one
  JSON object selecting a move from the offered menu:

  ```json
  {
    "left_hand":  {"action": "punch", "punch_type": "hook", "placement": "body_left", "strength": 8, "speed": 6},
    "right_hand": {"action": "guard"},
    "footwork":   "forward",
    "defense":    null,
    "reasoning":  "He drops his right when he resets — step in and rip the body to bank energy damage, keep my right up."
  }
  ```

  Or a defensive step:

  ```json
  {"left_hand": {"action": "free"}, "right_hand": {"action": "guard"},
   "footwork": null, "defense": "slip_left",
   "reasoning": "His left hook is mid-windup at my head — slip outside it."}
  ```

- **Validation/parsing** mirrors football `agents/schema.py`: strip markdown fences, validate against
  the legal-move list, and **fall back to a safe default** (`both hands guard, no footwork`) on any
  parse/illegal-move error. Illegal picks (locked hand, out-of-range, unaffordable energy) are
  rejected with the boxer holding guard that step. `reasoning` is free text shown in the viewer.
- The system prompt is **timeless** (rules of boxing, how energy/timing/range/KO work, the move
  vocabulary). The user message each step is the live observation (§10). Same split as football.

---

## 12. Boxer Attributes (roster)

Madden-style 0–99, but **identical for both boxers in v1** (differences should come from the LLMs,
per the user). Stats wired into config so they can diverge later:

| Attr | Drives |
|---|---|
| `power` | scales effective strength → damage |
| `hand_speed` | shortens windup; faster punches |
| `foot_speed` | step distance/speed; lateral reaction |
| `reaction` | base `reaction_delay` (§4.4) |
| `chin` | damage resistance (incoming health-damage divisor) |
| `stamina` | energy pool size + `regen_per_sec` |
| `reach` | small global reach bonus |

Default roster: both boxers at a flat baseline (e.g. all 75). Stored in `sim/rosters/default.yaml`.

---

## 13. Config — the single source of truth

**Everything tunable lives in `boxing/config.yaml`** and is injected into the engine/agents so we can
retune without touching code (explicit user requirement). Full v1 default config:

```yaml
observation:
  vitals_display: bands          # "bands" (deterministic word read) | "exact" (raw numbers, A/B only)
  # Deterministic number->phrase maps; apply to BOTH fighters. SYSTEM PROMPT never reveals thresholds.
  energy_bands:   # [floor, phrase], read top-down
    - [90, "fresh and loose, full tank"]
    - [75, "breathing easy, plenty left"]
    - [60, "working but comfortable"]
    - [45, "starting to blow, arms getting heavy"]
    - [30, "tiring, breathing hard"]
    - [15, "gassing badly, legs going"]
    - [1,  "running on empty, barely keeping the guard up"]
    - [0,  "completely spent — wide open, the next clean shot ends it"]
  health_bands:
    - [90, "unmarked, fresh"]
    - [75, "lightly touched up"]
    - [60, "marked up, taken some"]
    - [45, "hurt, feeling those shots"]
    - [30, "badly hurt, unsteady"]
    - [15, "on the edge, barely standing"]
    - [1,  "out on his feet, one shot from done"]

ring:
  size_ft: 16.0
  corner_margin_ft: 2.0          # within this of a wall = cornered for that direction

time:
  dt: 0.05                       # physics tick (s)
  opening_poll_interval: 0.1     # cadence both boxers are polled before the first punch
  round_seconds: 120             # B1 full round; B2 overrides to 15
  reaction_delay_base: 0.18      # s before a chosen defense is effective (modified by reaction/energy)

energy:
  start: 100.0
  # punch_energy = a*(s/10) + b*(v/10) + c*(s/10)*(v/10)   (fits 10/10→3, 10/1→1, 1/10→0.5)
  cost_a: 0.78
  cost_b: 0.22
  cost_c: 2.00     # energy cost is strength & speed ONLY — punch type does not affect it
  step_energy: 0.4
  slip_energy: 0.3
  duck_energy: 0.5
  guard_energy_per_sec: 0.2
  regen_per_sec: 1.2             # only while not throwing (idle/guard/circle)
  ratchet_caps: [75, 50, 25]     # once below a cap, can never exceed it again this round
  zero_energy_next_hit_is_ko: true
  degradation:                   # output_factor(energy): linear from full→empty
    full_factor: 1.0
    empty_factor: 0.6
    reaction_penalty_at_empty: 0.12   # added seconds to reaction_delay when gassed

health:
  start: 100.0
  damage_per_strength: 0.5       # 10 strength → 5.0 base (before mults)
  jab_fixed_strength: 3.0
  punch_type_power_mult: {jab: 1.0, cross: 1.3, uppercut: 1.45, hook: 1.6}
  placement_mult:                # overall potency by target
    head_center: 1.20
    head_left:   1.00
    head_right:  1.00
    body_left:   0.90
    body_center: 0.95
  placement_health_share:        # fraction of raw that becomes HEALTH damage
    head_center: 1.00
    head_left:   1.00
    head_right:  1.00
    body_left:   0.55
    body_center: 0.60
  placement_energy_share:        # fraction of raw that becomes opponent ENERGY damage
    head_center: 0.10
    head_left:   0.10
    head_right:  0.10
    body_left:   0.70
    body_center: 0.65
  block_factor: 0.20             # blocked damage multiplier (heavy reduction)
  block_leak_energy: 0.5         # energy the blocker pays absorbing a power shot
  glancing_mult: 0.6             # land quality at the edge of reach
  contest_roll: [0.9, 1.1]       # seeded margin range
  zero_health_is_ko: true

reach:                            # feet, by punch type
  jab: 3.2
  cross: 2.8
  hook: 2.0
  uppercut: 1.8
  pocket_ft: 2.2                  # at/under this range = "in the pocket"

footwork:
  step_distance_ft: 1.0

timing:                           # phase durations (s) at neutral effort/attrs; scaled by speed/strength/hand_speed
  windup: {jab: 0.12, cross: 0.18, hook: 0.22, uppercut: 0.24}
  impact_ticks: 1
  recovery: {jab: 0.15, cross: 0.28, hook: 0.34, uppercut: 0.36}
  slip_duration: 0.18
  slip_recovery: 0.12
  duck_duration: 0.22
  duck_recovery: 0.15
  speed_windup_scale: 0.6        # windup *= lerp(1.0 .. speed_windup_scale) as speed 0→10
  strength_recovery_scale: 1.4   # recovery *= lerp(1.0 .. strength_recovery_scale) as strength 0→10

roster_default:
  power: 75
  hand_speed: 75
  foot_speed: 75
  reaction: 75
  chin: 75
  stamina: 75
  reach: 75
```

(Numbers are first-pass estimates the user delegated; we tune against B2 fights.)

---

## 14. Architecture / Directory Structure

Mirrors football one-to-one so the patterns transfer:

```
boxing/
├── main.py                         # entry: run_fight(scenario, roster, seed, output)
├── config.yaml                     # ALL tunable numbers (§13) — injected everywhere
├── gen_demo.py                     # mock-vs-mock fight, no API key
├── requirements.txt                # openai, ursina, pyyaml, python-dotenv
│
├── engine/
│   ├── ring.py                     # ring constants, cornering, range/reach helpers
│   ├── timing.py                   # phase clocks, windup/impact/recovery, reaction-delay model
│   ├── energy.py                   # punch_energy(), regen + ratchet caps, degradation curve
│   ├── damage.py                   # damage formula, block, body-vs-head split, KO rules
│   ├── boxer.py                    # BoxerState (health, energy, hand phases, footing, posture)
│   └── state_machine.py            # FightPhase: OPENING → LIVE → KO/END (+ round states later)
│
├── agents/
│   ├── llm_client.py               # copied from football (OpenAI gpt-5-nano + Ollama)
│   ├── schema.py                   # parse_action() — JSON parse + legality validation + safe default
│   ├── observation.py              # build_observation() — full scenario + annotated legal-move menu
│   ├── boxer_agent.py              # BoxerAgent: calls LLM, tracks errors, single-pass decide()
│   ├── scripted.py                 # ScriptedBoxer (mock opponent for B1)
│   └── prompts/
│       └── boxer_system.txt        # the rules of boxing / energy / timing / range / KO (timeless)
│
├── sim/
│   ├── runner.py                   # run_fight() — opening poll loop → event-driven decision steps
│   ├── seeds.py                    # make_rng(seed) (copied)
│   ├── rosters/default.yaml        # two identical boxers
│   └── scenarios/                  # b1_mock.yaml, b2_llm_15s.yaml, ...
│
├── replay/
│   └── recorder.py                 # per-decision + per-tick snapshots → replay JSON
│
├── render/
│   └── renderer_ursina.py          # 3D viewer: two primitive boxers + floating reasoning
│
├── replays/                        # *.json fights
└── tests/
    └── test_e2e.py                 # mock-vs-mock smoke test, no API key (asserts a KO or decision)
```

---

## 15. Rendering (3D, ursina)

- **Primitives only (v1):** each boxer = a **rectangular torso + a circle/sphere head**, with **two
  arms** that extend toward the opponent on a punch (length/angle keyed to punch type + placement),
  retract on guard, drop when free. Head bobs/shifts on slip/duck. (Per the user: "just start with
  rectangles with arms and circles for head.")
- **Ring:** a 16×16 floor with rope lines.
- **Floating reasoning overlay** per boxer (toggleable), the clip-worthy feature — shows the latest
  `reasoning` string and the chosen move, like football's renderer.
- **HUD:** two health bars + two energy bars (with ratchet-cap ticks), round clock, KO banner.
- **Controls** (match football): `SPACE` play/pause · `←/→` step · `R` toggle reasoning · `+/-` speed
  · `Q/Esc` quit.
- **No 2D viewer** (per the user — 3D only). A lightweight **text decision-log** dump may be added for
  debugging.

---

## 16. Replay Format

JSON, same spirit as football `replay/recorder.py`: a header (seed, config snapshot, roster, round
length), a list of frames (each tick: `t`, phase, both boxers' full state — health, energy, hand
phases, position, posture — plus any decision made that tick with its `reasoning`, and events:
`punch_thrown`, `landed`, `blocked`, `slipped`, `body_shot`, `KO`), and a footer (result, KO time,
landed/thrown/blocked tallies, energy curves). The viewer reads only the replay; the sim and the
viewer never run in the same process (matches football).

---

## 17. LLM Integration

- `agents/llm_client.py` is **copied from football** unchanged: singleton OpenAI client
  (`gpt-5-nano`, `reasoning_effort`, JSON response_format, token budget) + Ollama client
  (`localhost:11434/v1`, temperature, lenient parse). `--local` routes both boxers to Ollama.
- Default model `gpt-5-nano`, `reasoning_effort="low"`. B2 (15-second rounds) keeps call volume and
  cost down while iterating.
- Both boxers can share the system prompt; each gets its own observation. In a live regime tick where
  both must decide, calls can be issued in parallel (attacker registered first for causality, §4.5).

---

## 18. Open Questions / Deferred (revisit before the relevant phase)

- **Match structure** (rounds count, between-round rest + how much the ratchet caps lift) — user said
  decide later (B4).
- **Knockdowns + 10-count + TKO** — deferred to B4; data model leaves room (one KO event for now).
- **Separate head/body health** — single bar for v1; `placement_*_share` already tracks the split so
  we can promote body damage to its own bar later.
- **Two-pass decisions** — start single-pass; add a pass only if the model picks badly (the football
  evolution path).
- **Distinct boxer stats / styles** — identical in v1; roster is ready for divergence.
- **Out-of-range punches:** offer-with-warning vs hard-illegal — decide during B1 build.

---

## 19. Success Criteria

- **B1:** every move type (4 punches × 5 placements, guard, slip L/R, duck, all footwork) provably
  fires in the engine and renders correctly against the mock; a mock-vs-mock fight reaches a KO or
  decision and serializes a clean replay; `tests/test_e2e.py` passes with no API key.
- **B2:** two `gpt-5-nano` boxers fight a 15 s round that a viewer would find legible — they trade,
  block, work the body, gas out, and someone gets KO'd or wins on health — with 0 schema parse errors
  in a clean run.
```
