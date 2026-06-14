# Glass Joe Minds — LLM Agents Box

A 3D boxing simulator where **both boxers are LLM agents**. Each reads the fight as structured text
(plain-English condition bands, range, openings, and a list of *legal* moves), reasons in boxing
terms, and returns one JSON action per decision step — a move per hand plus optional footwork or a
slip/duck. A deterministic engine turns intent into motion, contact, damage, and energy drain. The
LLM never does geometry or math; it picks from a feature-enriched menu.

Sibling of an earlier football sim. See **`PRD.md`** for the full design and **`step_example.md`** for the
exact observation/return contract.

---

## How to Run

> On Windows, either `activate` the venv first (so `python` = the venv python), or prefix every
> command with `.venv\Scripts\python.exe` instead of `python`. All commands are run from the
> `boxing/` folder.

### 1. Setup (once)
```
python -m venv .venv
.venv\Scripts\activate                 # Windows  (Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
```

### 2. Run a fight

Two LLM-vs-LLM scenarios. Each **always overwrites its single replay file** (no pile-up):

```
python main.py --scenario sim/scenarios/b2_llm_15s.yaml    # -> replays/fifteen.json     (15s, the everyday test)
python main.py --scenario sim/scenarios/b2_llm_45s.yaml    # -> replays/forty-five.json  (45s, run occasionally)
```

Default model is **gpt-5-nano** (set `OPENAI_API_KEY` in `.env` or the environment). To run locally
on Ollama instead, install [Ollama](https://ollama.com), `ollama pull qwen3:8b && ollama serve`, then
add `--local` (optionally `--model qwen3:8b`). The terminal prints the result, both boxers' final
health/energy, LLM call counts, and parse errors.

> **Speed:** the model is called once every ~0.1–0.15s of *fight* time, so a 15s round is several
> minutes of wall-clock. Use the 15s scenario for everyday checks; the 45s only when you need a long
> round (lets a fighter actually gas out — that's where finishes come from).

### 3. Watch a replay

**2D side-view viewer (recommended — most readable):**
```
python -m render.renderer_2d replays/fifteen.json
python -m render.renderer_2d replays/forty-five.json
```
Boxers in profile with readable poses (gloves up at the chin in guard, arm cocked on windup then
extended to the head/body target on the punch, head dropped on a duck), impact flashes on landed
shots, HP/energy bars, a top-down minimap, a play-by-play log, and full reasoning panels.
Controls: `SPACE` play/pause (replays from start when at the end) · `LEFT`/`RIGHT` scrub (hold) ·
`+`/`-` speed (it's fast — drop to ~0.3x to watch cleanly) · `R` toggle reasoning · `Q`/`Esc` quit.

### 4. Verify the engine (no API key, no Ollama)
```
python -m tests.test_e2e               # full mock fight -> "--- PASS ---"
python -m tests.test_energy            # energy formula + ratchet
python -m tests.test_damage            # damage formula + block + split
```

---

## What moves the game (quick reference)

- **Health** 100 → 0 = KO — the *only* win condition. **Energy** 100 is your **capacity to fight**, not
  a way to win: it gates punch power/speed and how fast you defend (slip/block/move). As it drains you
  hit softer and react slower, so a tired fighter can't keep his guard up or get out of the way and
  eats clean head shots — that's how energy turns into lost health. Energy regens slowly while not
  throwing, but the **ratchet caps** (75/50/25) mean it only trends down.
- **Punches** {jab, cross, hook, uppercut} × **placements** {head_center, head_left, head_right,
  body_left, body_center}, with `strength` & `speed` effort (0–10). Energy cost depends on
  strength+speed only; **damage** depends on punch type, placement, range, defense, and attacker energy.
  Head shots drain health; body shots drain the opponent's energy.
- **Range** gates reach (jab > cross > hook > uppercut); close distance to land inside shots.
- **Defense**: hold a hand in `guard` (heavy block), or `slip_left/right`/`duck` (avoid if in time;
  can't punch the same step). A fast punch (short windup) can beat a slow reaction.
- Everything tunable lives in **`config.yaml`** (the single source of truth).

---

## Status

| Phase | Description | Status |
|---|---|---|
| **B1** | One LLM boxer vs scripted mock — prove every move fires + renders | **Built / Verified** (Ollama clean, 0 parse errors) |
| B2 | LLM vs LLM, 15s rounds | In progress |
| B3 | Tune energy/damage/timing (blocking currently too strong); lengthen rounds | Not started |
| B4 | Knockdowns + 10-count, multi-round matches | Not started |

See `.claude/state.md` and `.claude/left_off.md` for detail.
