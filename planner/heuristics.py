"""
Domain-independent heuristics for forward state-space search.

All heuristics are computed automatically from the STRIPS model, so they work
for any domain the parser can load (no hand-written lab knowledge).

h_zero        : 0 everywhere -> A* degenerates to Uniform-Cost Search.
h_goal_count  : number of goal facts not yet true. Cheap, intuitive, but NOT
                admissible in general (one action may achieve several goals).
h_max         : delete-relaxation, cost of the most expensive goal fact
                (Bonet & Geffner, 2001). ADMISSIBLE -> A* returns optimal plans.
h_add         : delete-relaxation, sum of goal-fact costs (Bonet & Geffner, 2001).
                More informed but NOT admissible -> fast, possibly suboptimal.
"""
from __future__ import annotations

import math
from typing import Callable, Dict

from .strips import Problem, State

Heuristic = Callable[[State], float]


def h_zero(problem: Problem) -> Heuristic:
    return lambda s: 0.0


def h_goal_count(problem: Problem) -> Heuristic:
    goal = problem.goal
    return lambda s: float(len(goal - s))


def _relaxed_costs(problem: Problem, state: State, combine) -> Dict[str, float]:
    """Fixed-point computation of fact costs in the delete-relaxed problem."""
    cost = {f: math.inf for f in problem.facts}
    for f in state:
        cost[f] = 0.0
    changed = True
    while changed:
        changed = False
        for a in problem.actions:
            pre_cost = combine([cost.get(p, math.inf) for p in a.pre]) if a.pre else 0.0
            if pre_cost == math.inf:
                continue
            c = pre_cost + a.cost
            for f in a.add:
                if c < cost.get(f, math.inf):
                    cost[f] = c
                    changed = True
    return cost


def _make_relaxed(problem: Problem, combine) -> Heuristic:
    goal = problem.goal
    cache: Dict[State, float] = {}

    def h(state: State) -> float:
        if state in cache:
            return cache[state]
        cost = _relaxed_costs(problem, state, combine)
        val = combine([cost.get(g, math.inf) for g in goal]) if goal else 0.0
        cache[state] = val
        return val

    return h


def h_max(problem: Problem) -> Heuristic:
    return _make_relaxed(problem, lambda xs: max(xs) if xs else 0.0)


def h_add(problem: Problem) -> Heuristic:
    return _make_relaxed(problem, lambda xs: sum(xs) if xs else 0.0)


HEURISTICS = {
    "zero": h_zero,
    "goal_count": h_goal_count,
    "h_max": h_max,
    "h_add": h_add,
}

HEURISTIC_INFO = {
    "zero": "h(s)=0 (blind)",
    "goal_count": "Unsatisfied goal facts (inadmissible in general)",
    "h_max": "Delete-relaxation, max over goals (admissible)",
    "h_add": "Delete-relaxation, sum over goals (inadmissible, informed)",
}
