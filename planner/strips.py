"""
STRIPS representation of a classical planning problem.

A classical planning problem is the tuple  P = <F, A, I, G>
    F : finite set of propositional facts (fluents)
    A : finite set of actions, each a = <pre(a), add(a), del(a), cost(a)>
    I : initial state, I ⊆ F   (closed-world assumption: facts not in I are false)
    G : goal condition, G ⊆ F  (a state s is a goal state iff G ⊆ s)

An action a is APPLICABLE in state s iff pre(a) ⊆ s.
The RESULT of applying a in s is   γ(s, a) = (s \\ del(a)) ∪ add(a).

A PLAN is a sequence <a1, ..., an> such that every ai is applicable in the state
produced by a1..a(i-1), and the final state satisfies G.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, Iterable, List

State = FrozenSet[str]


@dataclass(frozen=True)
class Action:
    name: str
    pre: FrozenSet[str]
    add: FrozenSet[str]
    delete: FrozenSet[str]
    cost: float = 1.0

    # ---- forward (progression) semantics -------------------------------
    def applicable(self, state: State) -> bool:
        return self.pre <= state

    def apply(self, state: State) -> State:
        return frozenset((state - self.delete) | self.add)

    def missing_preconditions(self, state: State) -> FrozenSet[str]:
        return frozenset(self.pre - state)

    # ---- backward (regression) semantics -------------------------------
    def relevant(self, subgoal: State) -> bool:
        """a is relevant for subgoal g iff it achieves part of g and deletes none of g."""
        return bool(self.add & subgoal) and not (self.delete & subgoal)

    def regress(self, subgoal: State) -> State:
        """Regression of g through a:  (g \\ add(a)) ∪ pre(a)."""
        return frozenset((subgoal - self.add) | self.pre)

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.name


@dataclass
class Problem:
    name: str
    domain_name: str
    facts: FrozenSet[str]
    actions: List[Action]
    init: State
    goal: State
    description: str = ""
    mutex_pairs: List[tuple] = field(default_factory=list)

    def is_goal(self, state: State) -> bool:
        return self.goal <= state

    def applicable_actions(self, state: State) -> Iterable[Action]:
        return (a for a in self.actions if a.applicable(state))

    def action(self, name: str) -> Action:
        for a in self.actions:
            if a.name.lower() == name.lower():
                return a
        raise KeyError(f"Unknown action: {name}")

    def with_changes(self, init=None, goal=None) -> "Problem":
        """Return a copy with a different initial state and/or goal."""
        return Problem(
            name=self.name,
            domain_name=self.domain_name,
            facts=self.facts,
            actions=self.actions,
            init=frozenset(init) if init is not None else self.init,
            goal=frozenset(goal) if goal is not None else self.goal,
            description=self.description,
            mutex_pairs=self.mutex_pairs,
        )

    def compute_mutex_pairs(self) -> List[tuple]:
        """Cheap static mutex detection: p, q are treated as mutually exclusive when
        they are never true together in I and every action that adds one deletes
        the other (e.g. ProjectorOn / ProjectorOff). Used to prune impossible
        subgoals during backward search."""
        pairs = []
        facts = sorted(self.facts)
        for i, p in enumerate(facts):
            for q in facts[i + 1:]:
                if p in self.init and q in self.init:
                    continue
                adders = [a for a in self.actions if p in a.add or q in a.add]
                if not adders:
                    continue
                ok = all(
                    (p not in a.add or q in a.delete) and (q not in a.add or p in a.delete)
                    for a in adders
                )
                if ok:
                    pairs.append((p, q))
        self.mutex_pairs = pairs
        return pairs

    def consistent(self, subgoal: State) -> bool:
        return not any(p in subgoal and q in subgoal for p, q in self.mutex_pairs)


def state_str(state: Iterable[str]) -> str:
    return ", ".join(sorted(state)) if state else "∅"
