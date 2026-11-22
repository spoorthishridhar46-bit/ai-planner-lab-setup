"""
Plan validation: the heart of the distinction between

    (1) an ARBITRARY sequence of actions  – any ordering of action names, and
    (2) a VALID PLAN                      – a sequence where every action's
                                            preconditions hold when it is executed
                                            AND the final state satisfies the goal.

The validator simulates a sequence step by step (like the VAL tool used at the
International Planning Competition) and classifies it into one of three verdicts.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional

from .strips import Problem, State

VALID = "VALID PLAN"
NOT_EXECUTABLE = "NOT EXECUTABLE"           # some precondition violated
EXECUTABLE_NO_GOAL = "EXECUTABLE, GOAL NOT REACHED"


@dataclass
class Step:
    index: int
    action: str
    applicable: bool
    missing: List[str]
    state_before: State
    state_after: Optional[State]
    added: List[str] = field(default_factory=list)
    deleted: List[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    sequence: List[str]
    steps: List[Step]
    verdict: str
    final_state: State
    unmet_goals: List[str]
    failed_at: Optional[int] = None
    cost: float = 0.0
    unknown_actions: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return self.verdict == VALID

    @property
    def is_executable(self) -> bool:
        return self.verdict in (VALID, EXECUTABLE_NO_GOAL)

    def explain(self) -> str:
        if self.unknown_actions:
            return f"Unknown action(s): {', '.join(self.unknown_actions)}"
        if self.verdict == VALID:
            return (f"Every precondition was satisfied and all goals hold after "
                    f"{len(self.sequence)} action(s) (cost {self.cost:g}).")
        if self.verdict == NOT_EXECUTABLE:
            st = self.steps[self.failed_at]
            return (f"Step {st.index + 1} '{st.action}' cannot be executed: "
                    f"missing precondition(s) {', '.join(st.missing)}.")
        return f"All actions executed, but goal fact(s) not achieved: {', '.join(self.unmet_goals)}."


def validate(problem: Problem, sequence: List[str]) -> ValidationReport:
    names = {a.name.lower(): a for a in problem.actions}
    unknown = [n for n in sequence if n.lower() not in names]
    if unknown:
        return ValidationReport(sequence, [], NOT_EXECUTABLE, problem.init,
                                sorted(problem.goal - problem.init), 0, 0.0, unknown)
    state = problem.init
    steps: List[Step] = []
    cost = 0.0
    for i, n in enumerate(sequence):
        a = names[n.lower()]
        missing = sorted(a.missing_preconditions(state))
        if missing:
            steps.append(Step(i, a.name, False, missing, state, None))
            return ValidationReport(sequence, steps, NOT_EXECUTABLE, state,
                                    sorted(problem.goal - state), i, cost)
        nxt = a.apply(state)
        steps.append(Step(i, a.name, True, [], state, nxt,
                          sorted(nxt - state), sorted(state - nxt)))
        cost += a.cost
        state = nxt
    unmet = sorted(problem.goal - state)
    verdict = VALID if not unmet else EXECUTABLE_NO_GOAL
    return ValidationReport(sequence, steps, verdict, state, unmet, None, cost)


# --------------------------------------------------------------------------
# Generators of arbitrary sequences (used for the comparison experiment)
# --------------------------------------------------------------------------
def random_sequence(problem: Problem, length: int, rng: random.Random) -> List[str]:
    """Arbitrary sequence: actions chosen uniformly, preconditions ignored."""
    names = [a.name for a in problem.actions]
    return [rng.choice(names) for _ in range(length)]


def random_walk(problem: Problem, length: int, rng: random.Random) -> List[str]:
    """Executable-by-construction sequence: only applicable actions are chosen,
    but with no goal-directed reasoning."""
    s, seq = problem.init, []
    for _ in range(length):
        app = list(problem.applicable_actions(s))
        if not app:
            break
        a = rng.choice(app)
        seq.append(a.name)
        s = a.apply(s)
        if problem.is_goal(s):
            break
    return seq


def shuffled(sequence: List[str], rng: random.Random) -> List[str]:
    """Same actions as a plan, random order."""
    seq = list(sequence)
    rng.shuffle(seq)
    return seq
