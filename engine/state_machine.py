"""Fight phases (PRD §4): OPENING (both boxers polled until the first punch) -> LIVE (event-driven
decision steps) -> END (KO or time)."""


class FightPhase:
    OPENING = "OPENING"
    LIVE = "LIVE"
    END = "END"
