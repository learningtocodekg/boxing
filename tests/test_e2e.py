"""End-to-end smoke test: a full mock-vs-mock fight, no API key. Verifies the loop runs, the replay
serializes, and a valid result is produced.
Run: .venv\\Scripts\\python.exe -m tests.test_e2e   (from the boxing/ root)
"""
import json

from sim.runner import run_fight

VALID_ENDINGS = ("wins by KO", "wins by gassed-out KO", "wins by decision", "Draw")


def test_mock_fight():
    res = run_fight("sim/scenarios/b1_mock.yaml", seed=42, output="replays/test_mock.json", verbose=False)
    assert res["frames"] > 0, "no frames recorded"
    assert any(res["result"].endswith(e) or res["result"] == e for e in VALID_ENDINGS), res["result"]
    assert res["footer"]["red"]["parse_errors"] == 0 and res["footer"]["blue"]["parse_errors"] == 0
    # replay is well-formed
    data = json.load(open("replays/test_mock.json", encoding="utf-8"))
    assert data["header"]["seed"] == 42
    assert len(data["frames"]) == res["frames"]
    assert "result" in data["footer"]
    landed = sum(1 for fr in data["frames"] for e in fr["events"] if e["kind"] == "land")
    return res["result"], res["frames"], landed


if __name__ == "__main__":
    result, frames, landed = test_mock_fight()
    print(f"--- PASS --- e2e mock fight: {result} | {frames} frames | {landed} landed punches")
