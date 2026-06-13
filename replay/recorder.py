"""Collects per-tick snapshots + events into a replay JSON the ursina viewer reads (PRD §16)."""
import json
from pathlib import Path

from engine import boxer as B


def _hand(h: B.Hand) -> dict:
    d = {"state": h.state}
    if h.state in (B.WINDUP, B.RECOVERY) or h.punch_type:
        d.update(punch_type=h.punch_type, placement=h.placement)
    return d


def _boxer(b: B.BoxerState) -> dict:
    return {
        "name": b.name,
        "pos": [round(b.pos[0], 3), round(b.pos[1], 3)],
        "health": round(b.health, 2),
        "energy": round(b.energy, 2),
        "energy_ceiling": round(b.energy_ceiling, 2),
        "left": _hand(b.left),
        "right": _hand(b.right),
        "defense": b.defense,
    }


class Recorder:
    def __init__(self, header: dict):
        self.header = header
        self.frames: list[dict] = []
        self._events: list[dict] = []

    def event(self, t: float, kind: str, data: dict):
        self._events.append({"t": round(t, 3), "kind": kind, **data})

    def snapshot(self, t: float, phase: str, red: B.BoxerState, blue: B.BoxerState, decisions: dict):
        self.frames.append({
            "t": round(t, 3), "phase": phase,
            "red": _boxer(red), "blue": _boxer(blue),
            "decisions": decisions, "events": self._events,
        })
        self._events = []

    def save(self, path: str, footer: dict):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"header": self.header, "frames": self.frames, "footer": footer}, f)
        return path
