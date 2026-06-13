# Decision-Step Example (build reference)

One worked LLM decision step: the exact USER message the agent sees, and the JSON it returns.
The SYSTEM prompt (not shown) holds the timeless rules — boxing, energy, timing, range, KO, vocabulary.

This is the contract `agents/observation.py` (builds the USER message) and `agents/schema.py` (parses
the return) must satisfy. See PRD.md §10–§11.

---

## Why there is no "4000-combo menu"
A move is composed from independent slots, each tiny; the two effort knobs are free integers the model
writes, never enumerated:
- right/left hand intent: guard | free | punch   (a hand mid-phase is LOCKED → slot removed)
- └ punch type: ≤4, range-filtered  ·  placement: 5, each tagged OPEN/GUARDED
- └ strength, speed: model writes two integers 0–10 (NOT a menu)
- footwork: ≤7, corner-filtered  ·  defense: ≤3 (mutually exclusive with punching)

We never show the cartesian product. Out-of-range and out-of-energy punches are filtered OUT (never
offered). Energy cost is strength & speed only, so "max strength you can afford" is one number for all
punch types.

---

## USER MESSAGE the agent sees

```
=== ROUND 1 · 9.4s left ===

YOU (Red):
  Condition: lightly touched up; starting to blow, arms getting heavy.
             You've spent past your second wind — you won't fully get this energy back this round.
  Left hand:  LOCKED — recovering from your jab, frees shortly. (you do not set it this step)
  Right hand: FREE, up in guard.
  Position:   CORNERED against the back ropes.

OPPONENT (Blue):
  Condition: unmarked, fresh; breathing easy, plenty left.
  Guard: his RIGHT glove is dropped low — his head-left and body-left are OPEN. Center/right of his head are covered.
  JUST DID: threw a LEFT HOOK at your head (your right side), heavy and a touch telegraphed.
            It is coming fast — you have time to slip or block it, but NOT to land a counter before it lands.

RANGE: IN THE POCKET — every punch reaches.

YOUR LEGAL MOVES THIS STEP:

RIGHT HAND:
  • keep GUARD  — covers the incoming hook on your right side (~80% reduction).
  • FREE        — drops your guard (the hook would land clean unless you also slip).
  • PUNCH       — in range now: jab, cross, hook, uppercut (max strength you can afford: 10 — same for every type).
                  placement reads on Blue:  head_left: OPEN ·  body_left: OPEN ·  body_center: partial
                                            head_center: GUARDED ·  head_right: GUARDED
                  (punching frees no hand to block — the hook lands unless you slip, and you can't slip + punch.)

DEFENSE (upper body — cannot also punch this step):
  • slip_left   — head off-line left; clears the hook AND slides you off the ropes out of the corner. Brief off-balance after.
  • slip_right  — moves INTO the hook. Legal, not advised.
  • duck        — drop under the hook; clears it but exposes you to an uppercut.

FOOTWORK (cannot combine with slip/duck):
  • forward · left · circle_left · none
  • ILLEGAL (cornered): back, right, circle_right.

Return one JSON action.
```

---

## RETURN — option A (slip the hook, escape the corner)
Left hand omitted because it is LOCKED.
```json
{
  "right_hand": { "action": "free" },
  "footwork": null,
  "defense": "slip_left",
  "reasoning": "It says I have time to slip but not counter — slip_left clears the hook and slides me off the ropes out of the corner. Left's still recovering so I can't counter anyway; reset with guard up next step."
}
```

## RETURN — option B (trade: eat the hook, rip the open body — shows punch fields)
```json
{
  "right_hand": { "action": "punch", "punch_type": "hook", "placement": "body_left", "strength": 8, "speed": 7 },
  "footwork": null,
  "defense": null,
  "reasoning": "His right is down — body_left is wide open. I eat the hook but bank big energy damage on his ribs to set up the gas-out. 8 strength, quick at 7 so it lands before his recovery."
}
```

---

## Schema (parsed by agents/schema.py)
Per hand (omit a hand if the observation says LOCKED):
- `{ "action": "free" }`
- `{ "action": "guard" }`
- `{ "action": "punch", "punch_type": jab|cross|hook|uppercut, "placement": head_center|head_left|head_right|body_left|body_center, "strength": 0–10, "speed": 0–10 }`

Top level: `right_hand?`, `left_hand?`, `footwork: <legal>|null`, `defense: slip_left|slip_right|duck|null`, `reasoning: string`.

Validation:
- `defense` set → neither hand may punch and `footwork` must be null (slip/duck locks legs + punching).
- locked hand → any provided action ignored.
- punch must be in the offered legal set (type in range, placement valid, strength ≤ max affordable).
- footwork must be in the legal set.
- any violation → safe default: free hands → guard, footwork null, defense null. Scalars clamped 0–10.
