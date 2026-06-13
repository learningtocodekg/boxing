# Left Off
Date: 2026-06-12

## This session — what got done
Kicked off the boxing project (`kanish/boxing`), sibling of an earlier football sim. Ran a long Q&A (27
questions) to lock the design, then wrote the PRD and scaffolded the repo.
- **`PRD.md`** — full long design doc. Covers: 16x16 ring, the two-regime time model (timed opening
  poll until first punch -> event-driven decision steps), punch phases (windup/impact/recovery) +
  reaction-delay model, energy system (cost-curve fit to user anchors, ratchet caps 75/50/25, energy-0
  KO rule, degradation), damage formula (one health bar, hook>uppercut>jab to head, body shots drain
  energy, block heavy-reduction), the full action space + legality rules, range/reach gating, the
  observation/legal-move menu, single-pass JSON schema, determinism, roster, the full directory
  layout, ursina rendering, replay format, and B1->B4 milestones.
- **`config.yaml`** — every tunable number, the injectable source of truth (user requirement).
- **Scaffold:** copied `CLAUDE.md`, `.claude/commands/{break,resume}.md`, `.claude/settings.json`
  from football; wrote `.claude/{roadmap,state}.md`, this file, and `article.md`.

## Broken / Open
- No code yet — only PRD + config + scaffold exist. `engine/`, `agents/`, `sim/`, `render/` are
  specified (PRD §14) but empty.
- A couple of B1-build decisions deliberately left open in the PRD: out-of-range punches
  (offer-with-warning vs hard-illegal), and exact phase-duration scaling — settle while building.
- No venv / requirements.txt yet.

## SESSION 3 — 2D viewer built; gameplay gaps found (CURRENT TOP OF MIND)
Replaced the hard-to-read 3D ursina view with a **2D pygame side-view** (`render/renderer_2d.py`):
boxers in profile with readable poses (guard = gloves at chin, windup = arm cocked, punch = arm
extended to head/body target colored by punch type, duck = head down, slip = head shifted), impact
flashes (yellow `-dmg` / gray `BLOCK`), HP/EN bars, top-down minimap, play-by-play log, full reasoning
panels. Headless-render smoke OK; user confirms it's readable. 3D `renderer_ursina.py` kept as alt
(fixed: colors were 0-1 not 0-255 -> all-white; no `cylinder` model -> shadow uses `quad`). `pygame`
added to requirements.

### GAMEPLAY GAPS the user observed watching replays (FIX THESE NEXT — agent/design, not the viewer):
1. **They barely move.** Boxers stand, hit, block — almost no footwork/circling. Likely: start_range
   2.4 is already jab range (no need to close), footwork costs energy + agents prioritize punching,
   lateral/circle never chosen. Viewer gap tracks true range, so "no movement" is real. Fix ideas:
   start further apart; prompt to use footwork/angles; make footwork matter more.
2. **Ducks / slips never used.** Defense is almost always `guard`, never slip/duck. Check the reactive
   `_needs_decision` trigger actually fires and `incoming` reaches the agent; prompt to slip fast shots;
   make blocking cost more so slipping is worth it.
3. **No reasoning on blocks, and reasoning not comprehensive.** Block/defensive picks often carry terse
   or `safe_default` ("fallback: cover up") reasoning; viewer shows only the latest persisted reasoning
   per fighter. Fix: make every decision (incl. guard/defense) carry real reasoning; consider showing
   reasoning tied to the current step/event; richer reasoning prompt.
4. All of the above = the **fight is too static**, which pairs with the known **blocking-too-strong**
   balance issue. B3 should tackle balance + movement + defense-usage together.

## SESSION 2 — B1 built end-to-end + verified on Ollama
Built the ENTIRE B1 stack (engine -> agents -> runner -> ursina viewer) and ran it.
- All engine modules + agents + runner + recorder + renderer written (see state.md "Built").
- `tests/{test_energy,test_damage,test_e2e}` PASS (e2e = mock-vs-mock, no API key, 300 frames, ~46 landed).
- **Ollama LLM-vs-mock (qwen3:8b, b1_llm_smoke 3s) ran clean:** Red 6 calls / 0 parse errors, coherent
  reasoning ("close range to land cross, target body to drain energy"; "step back to avoid hook then
  counter"; "block cross, counter body hook to exploit partial guard"). Damage model correct: blocked
  shots chip ~0.5-1.0, clean ~2.5 health, body shots drain more energy than health. Result: Blue
  (mock) wins by decision (health 96.5 vs 92.8).
- **LLM-vs-LLM (b2_llm_smoke 3s, Ollama)** launched to confirm two-agent interaction.
- Wrote README.md. ursina installed; renderer compiles (not yet visually run — needs a display).

### Tuning items surfaced (for B3, NOT bugs)
- Blocking too strong: block_factor 0.20 applies to ALL shots and the mock guards a lot -> most punches
  chip. Consider: guard covers only some lines; body leaks more past a high guard.
- `_openings` is coarse: a guarding opponent only exposes "partial" body lines -> LLM spams body_left.
- qwen3:8b is slow (thinking mode); a 15s LLM-vs-LLM round is many minutes. Consider appending
  "/no_think" to the Ollama prompt for speed, and/or trimming live_poll cadence.

## B1 progress (session 1, foundation)
- **Scaffolded:** `.venv` (py3.12, pyyaml+dotenv; ursina deferred to renderer step), `requirements.txt`,
  full dir tree (engine/agents/sim/replay/render/replays/tests + `__init__`s). Copied `sim/seeds.py`,
  `agents/llm_client.py`, `.env` from football unchanged.
- **`engine/config.py`** — loads `config.yaml` (the single source of truth). `CONFIG` dict.
- **`engine/energy.py`** — `punch_energy` (anchors verified 10/10->3, 10/1->1, 1/10->0.5; type-independent),
  `lower_ceiling` (ratchet, only lowers, caps regen), `regen`, `output_factor` (1.0->0.6), `reaction_penalty`.
  **`tests/test_energy.py` PASSES.**
- **`engine/damage.py`** — `raw_damage` (base*type*placement*land*output*block*roll; roll passed in for
  determinism), `split` (head->health, body->energy; chin neutral at baseline), `glancing_mult`.
  **`tests/test_damage.py` PASSES** (clean max hook=9.6, body shot drains more energy than health,
  jab fixed=1.5, block=0.20x, gassed=0.6x).

## NEXT STEP
B1 + both viewers done. Next is **making fights dynamic & legible** (the SESSION 3 gaps above) together
with **B3 balance**:
1. Get them MOVING (start further apart e.g. start_range ~4.5; prompt footwork/angles; verify circle/
   step are actually offered & chosen).
2. Get DEFENSE used (slip/duck) — verify reactive decision trigger + `incoming` reach the agent; make
   blocking cost more / leak so slipping pays off.
3. Make EVERY decision carry real reasoning (incl. guard/defense); consider per-step reasoning in the
   viewer.
4. Fix blocking-too-strong (line-specific guard; body leaks past a high guard) so clean shots + KOs happen.
Then watch with `python -m render.renderer_2d replays/<file>.json` (2D side view = the good one).

Run anything with `.venv\Scripts\python.exe ...` from the boxing/ root. Ollama must serve qwen3:8b.

## Housekeeping
- `boxing/.git` already exists (empty repo) and `.gitignore` is present (copied football's). Nothing
  committed yet — commit the PRD + scaffold when ready.
- Boxer working name "Glass Joe Minds" is a placeholder — rename if desired.
