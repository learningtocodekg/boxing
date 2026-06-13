"""Entry point. Run a fight from a scenario; replay saved under replays/.

  python main.py --scenario sim/scenarios/b1_mock.yaml --seed 42
  python main.py --scenario sim/scenarios/b1_llm_ollama.yaml --local --seed 42   # Ollama, no API key
"""
import argparse

from sim.runner import run_fight


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--output")
    ap.add_argument("--local", action="store_true", help="route LLM boxers to local Ollama")
    ap.add_argument("--model", help="override the model for LLM boxers")
    args = ap.parse_args()
    run_fight(args.scenario, args.seed, args.output, local=args.local, model=args.model)


if __name__ == "__main__":
    main()
