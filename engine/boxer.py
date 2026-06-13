"""BoxerState and hand state — the mutable fight state the runner advances each tick (PRD §4, §5).

Logic lives in sim/runner.py; this module is data + small predicates so the state is easy to inspect
and serialize for replays.
"""
from dataclasses import dataclass, field

from .config import CONFIG

# Hand states
FREE = "free"        # hand down, no guard, ready
GUARD = "guard"      # held up, blocking
WINDUP = "windup"    # punch telegraphing, pre-impact (cancel-able into a slip/duck)
RECOVERY = "recovery"  # post-impact, hand locked, no guard


@dataclass
class Hand:
    state: str = GUARD
    windup_end: float = 0.0
    impact_t: float = 0.0
    recovery_end: float = 0.0
    impact_pending: bool = False
    punch_type: str = ""
    placement: str = ""
    strength: float = 0.0
    speed: float = 0.0

    def busy(self) -> bool:
        return self.state in (WINDUP, RECOVERY)

    def locked(self) -> bool:
        """Cannot be reassigned by a decision this step."""
        return self.busy()

    def guarding(self) -> bool:
        return self.state == GUARD


@dataclass
class BoxerState:
    name: str
    pos: list[float]
    attrs: dict
    health: float = field(default=CONFIG["health"]["start"])
    energy: float = field(default=CONFIG["energy"]["start"])
    energy_ceiling: float = field(default=CONFIG["energy"]["start"])
    left: Hand = field(default_factory=lambda: Hand(state=GUARD))
    right: Hand = field(default_factory=lambda: Hand(state=GUARD))
    # active defense (slip/duck)
    defense: str | None = None
    defense_effective_t: float = 0.0
    defense_active_until: float = 0.0
    defense_locked_until: float = 0.0
    # bookkeeping
    last_call_t: float = -999.0
    last_commit_t: float = -999.0   # last time this boxer STARTED a punch
    last_action_desc: str = "squares up"

    @property
    def hands(self) -> tuple[Hand, Hand]:
        return self.left, self.right

    def throwing(self) -> bool:
        return self.left.busy() or self.right.busy()

    def in_defense(self) -> bool:
        return self.defense is not None

    def fully_locked(self) -> bool:
        """No hand free to punch/block AND no ability to start a new defense."""
        return self.left.locked() and self.right.locked() and self.in_defense()

    def guarding(self) -> bool:
        return self.left.guarding() or self.right.guarding()

    def has_pending_punch(self, after_t: float) -> bool:
        return ((self.left.impact_pending and self.left.impact_t > after_t) or
                (self.right.impact_pending and self.right.impact_t > after_t))


def make_boxer(name: str, pos: list[float], attrs: dict) -> BoxerState:
    return BoxerState(name=name, pos=list(pos), attrs=dict(attrs))
