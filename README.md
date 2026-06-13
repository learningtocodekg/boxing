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
> `boxing/` folder. Every fight writes a replay JSON into `replays/` and prints the result.

### 1. Setup (once)
```
python -m venv .venv
.venv\Scripts\activate                 # Windows  (Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
```

### 2. Run a fight

Every fight is `python main.py --scenario <file> [--seed N] [--local] [--model NAME] [--output PATH]`.

| What | Command | Needs | Replay it writes |
|---|---|---|---|
| **Mock vs mock** (deterministic, no LLM) | `python main.py --scenario sim/scenarios/b1_mock.yaml --seed 42` | nothing | `replays/B1_mock_42.json` |
| **Quick demo** (mock vs mock) | `python gen_demo.py 42` | nothing | `replays/demo_42.json` |
| **LLM vs mock — short 3s check** | `python main.py --scenario sim/scenarios/b1_llm_smoke.yaml --local --seed 42` | Ollama | `replays/B1_LLM_smoke_42.json` |
| **LLM vs mock — full round** | `python main.py --scenario sim/scenarios/b1_llm_ollama.yaml --local --seed 42` | Ollama | `replays/B1_LLM_vs_mock_42.json` |
| **LLM vs LLM — short 3s check** | `python main.py --scenario sim/scenarios/b2_llm_smoke.yaml --local --seed 42` | Ollama | `replays/B2_LLM_vs_LLM_smoke_42.json` |
| **LLM vs LLM — full round** (slow) | `python main.py --scenario sim/scenarios/b2_llm_15s.yaml --local --seed 42` | Ollama | `replays/B2_LLM_vs_LLM_42.json` |

The replay filename is `replays/<scenario name with spaces as _>_<seed>.json` (override with `--output`).
The terminal prints the result, both boxers' final health/energy, LLM call counts, and parse errors.

> **Heads up on speed:** the LLM scenarios call the model once every ~0.1–0.15s of *fight* time, so a
> full 15s LLM-vs-LLM round is **many minutes** of wall-clock with a thinking model. Use the `*_smoke`
> (3s) scenarios to check things quickly first.

### 3. Where the LLM runs

**Local Ollama (no API key)** — install [Ollama](https://ollama.com), then:
```
ollama pull qwen3:8b
ollama serve                           # serves http://localhost:11434
```
Pass `--local` on any LLM scenario above to route every LLM boxer to Ollama. Override the model with
`--model qwen3:8b` (or any pulled model).

**OpenAI (gpt-5-nano)** — set a key and drop `--local`:
```
set OPENAI_API_KEY=sk-...              # Windows  (Mac/Linux: export OPENAI_API_KEY=sk-...)
python main.py --scenario sim/scenarios/b2_llm_15s.yaml --seed 42
```

### 4. Watch a replay

**2D side-view viewer (recommended — most readable):**
```
python -m render.renderer_2d replays/B2_LLM_vs_LLM_smoke_42.json
python -m render.renderer_2d replays/B1_mock_42.json
```
Boxers in profile with readable poses (gloves up at the chin in guard, arm cocked on windup then
extended to the head/body target on the punch, head dropped on a duck), impact flashes on landed
shots, HP/energy bars, a top-down minimap, a play-by-play log, and full reasoning panels.
Controls: `SPACE` play/pause (replays from start when at the end) · `LEFT`/`RIGHT` scrub (hold) ·
`+`/`-` speed · `R` toggle reasoning · `Q`/`Esc` quit.

**3D viewer (alternate):**
```
python -m render.renderer_ursina replays/B2_LLM_vs_LLM_smoke_42.json
```
Controls: `SPACE` play/pause · `LEFT`/`RIGHT` scrub · `R` reasoning · `+`/`-` speed ·
`1` side · `2` corner · `3` top · `[`/`]` zoom · `Q`/`Esc` quit.

### 5. Verify the engine (no API key, no Ollama)
```
python -m tests.test_e2e               # full mock fight -> "--- PASS ---"
python -m tests.test_energy            # energy formula + ratchet
python -m tests.test_damage            # damage formula + block + split
```

---

## What moves the game (quick reference)

- **Health** 100 → 0 = KO. **Energy** 100, gates power & reaction; at 0 the next clean hit is a KO.
  Energy regens slowly while not throwing, but the **ratchet caps** (75/50/25) mean it only trends down.
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
