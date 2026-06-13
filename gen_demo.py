"""Generate a mock-vs-mock fight replay — no API key required.

  python gen_demo.py        # seed 7 -> replays/demo_7.json
  python gen_demo.py 42
"""
import sys

from sim.runner import run_fight

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 7
run_fight("sim/scenarios/b1_mock.yaml", seed=seed, output=f"replays/demo_{seed}.json")
