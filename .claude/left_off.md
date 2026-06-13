# Left Off
Date: 2026-06-13

## This session — B3 dynamics + balance + strategy prompt (what got done)
Tackled the SESSION 3 gaps (static fights: no movement, no slips, sparse reasoning, blocking too
strong) together with B3 balance and a real strategy prompt. All no-API tests pass; validated twice on
Ollama (qwen3:8b, LLM-vs-mock 3s) reading the replay JSON directly.

1. **Slips never worked — fixed a real correctness bug** (`sim/runner.py::_apply`). The slip/duck
   avoidance window was computed from decision time `t` (`slip_window(t)`), but the reaction delay
   (~0.10s) ate into it, leaving the head offline only ~0.08s; telegraphed hooks (impact grid-rounded
   up a tick) landed just past it. Now the window is anchored to the EFFECTIVE time (`slip_window(eff)`),
   so the delay delays the slip instead of shortening it. Mock fight: 0 → 7 successful slips.
2. **Schema flipped to DEFENSE-FIRST** (`agents/schema.py`). The model kept writing "slip then counter"
   as one action (defense + punch); the old tie-break dropped the defense and kept the punch, silently
   turning a slip into a trade — Red ate a clean 6.73 head hook that flipped a fight. Now if both are
   present, the defense is honored and hands/footwork dropped (engine already ignores hands while
   defending). Re-run: Red slipped, stayed unmarked, WON (97.0 vs 95.2) — exact inverse of before.
3. **Blocking made line-specific** (`engine/damage.py`, `config.yaml`). Head shots into a guard stay
   0.20x; body shots LEAK past a high guard (`body_block_factor 0.55`) — digging the body drains a
   turtle. New test `test_body_leaks_past_guard` locks it in.
4. **Slips made viable** (`config.yaml`): `reaction_delay_base 0.18 → 0.10` so power shots
   (hook/uppercut) can be slipped but fast straight shots (jab/cross) can't — a real read.
5. **Movement**: `start_range 2.4 → 4.0` (all scenarios + runner default) so they start out of range
   and must close; mock now alternates head/body targets and periodically resets range / circles (so the
   verifier actually exercises slips, head shots, footwork — it provably didn't before: 47/47 blocked
   body shots, 0 slips, 0 movement).
6. **Strategy prompt rewrite** (`agents/prompts/boxer_system.txt`). The prompt taught controls but no
   game plan. Added a "HOW TO WIN" doctrine (energy is the battery; outlast/conserve; slip>block; pick
   power shots for openings; work the body; read the moment) — all in qualitative band-language, NEVER
   revealing the numeric thresholds (design rule). Also clarified: a slip is a STANDALONE step (set
   defense only, counter next step); slips only beat HEAD shots (can't slip the body); don't step back
   out of your own punch; keep the free hand guarding. LLM reasoning became visibly strategic
   ("close distance to set up body shots and drain his energy"; "slip his hook... setting up a finish").

## Verified
- `tests/test_energy`, `tests/test_damage` (+ new body-leak test), `tests/test_e2e` — ALL PASS.
- Ollama smoke 1 (`replays/strat_smoke.json`): new prompt → strategic reasoning, 0 parse errors, but
  slips silently dropped (led to fixes #1/#2).
- Ollama smoke 2 (`replays/strat_smoke2.json`): slips now register (`avoid via=slip_left`), Red wins,
  0 parse errors. Residual: model wasted some slips on body hooks → added the "slips only beat the head"
  prompt line after.

## Broken / Open
- **Not yet visually watched** in the 2D viewer this session — only analyzed via replay JSON. Watch
  `strat_smoke2.json` (and a fresh LLM-vs-LLM) to confirm it reads well:
  `.venv\Scripts\python.exe -m render.renderer_2d replays/strat_smoke2.json`
- **The last prompt line (slips-only-beat-head) is untested on the LLM** — added after smoke 2, no run
  since. First thing to verify next session.
- **No clean head shots from the body-drain style yet** — fights are close, body-heavy, defensively
  sound, but nobody opens the head for a finish. May need: a tiring opponent's guard to drop, or prompt
  nudge to switch to the head once the body's done its work. Watch whether longer rounds produce KOs.
- LLM-vs-LLM (B2) not re-run this session with all the new changes — that's the real watchable target.

## NEXT STEP
**Run B2 LLM-vs-LLM with all the new changes and WATCH it in the 2D viewer** (not just JSON), to confirm
the fight is now dynamic and legible end-to-end:
`.venv\Scripts\python.exe main.py --scenario sim/scenarios/b2_llm_smoke.yaml --output replays/b2_check.json`
then `.venv\Scripts\python.exe -m render.renderer_2d replays/b2_check.json`.
Verify: movement/angles, slips landing (avoid events), body work draining energy, every decision carries
real reasoning, and blocking no longer makes it a stalemate. Then tune toward KOs / longer rounds (B3→B4).

Run anything with `.venv\Scripts\python.exe ...` from boxing/ root. Ollama must serve qwen3:8b
(`ollama serve`; model is installed). qwen3:8b is slow (thinking mode) — a 3s sim is minutes; run LLM
fights in the background.
