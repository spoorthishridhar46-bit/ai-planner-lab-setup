"""
State-space search algorithms for classical planning.

Forward (progression) search
    nodes  = world states (sets of true facts)
    start  = I
    goal   = any s with G ⊆ s
    succ   = { γ(s,a) | a applicable in s }

Backward (regression) search
    nodes  = subgoals (sets of facts that must hold)
    start  = G
    goal   = any g with g ⊆ I
    pred   = { regress(g,a) | a relevant for g, result consistent }

Algorithms: BFS, DFS, Iterative-Deepening DFS, Uniform-Cost, Greedy Best-First,
A*, and Backward BFS. Every algorithm returns a SearchResult with the plan and
performance counters used in the experiments.
"""
from __future__ import annotations

import heapq
import itertools
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .heuristics import HEURISTICS
from .strips import Action, Problem, State

TRACE_LIMIT = 400  # max search-tree edges kept for visualisation


@dataclass
class SearchResult:
    algorithm: str
    heuristic: Optional[str]
    solved: bool
    plan: List[str] = field(default_factory=list)
    cost: float = 0.0
    nodes_expanded: int = 0
    nodes_generated: int = 0
    max_frontier: int = 0
    time_ms: float = 0.0
    trace: List[Tuple[int, str, int]] = field(default_factory=list)  # (parent_id, action, child_id)
    trace_states: Dict[int, State] = field(default_factory=dict)
    message: str = ""

    @property
    def length(self) -> int:
        return len(self.plan)

    def as_row(self) -> dict:
        return {
            "algorithm": self.algorithm,
            "heuristic": self.heuristic or "-",
            "solved": self.solved,
            "plan_length": self.length if self.solved else None,
            "plan_cost": self.cost if self.solved else None,
            "nodes_expanded": self.nodes_expanded,
            "nodes_generated": self.nodes_generated,
            "max_frontier": self.max_frontier,
            "time_ms": round(self.time_ms, 3),
        }


class _Tracer:
    def __init__(self):
        self.ids: Dict[State, int] = {}
        self.edges: List[Tuple[int, str, int]] = []

    def id(self, s: State) -> int:
        if s not in self.ids:
            self.ids[s] = len(self.ids)
        return self.ids[s]

    def edge(self, parent: State, action: str, child: State):
        if len(self.edges) < TRACE_LIMIT:
            self.edges.append((self.id(parent), action, self.id(child)))

    def states(self) -> Dict[int, State]:
        used = {i for e in self.edges for i in (e[0], e[2])} | {0}
        return {i: s for s, i in self.ids.items() if i in used}


def _reconstruct(parents: Dict[State, Tuple[Optional[State], Optional[Action]]], s: State) -> List[Action]:
    plan = []
    while parents[s][0] is not None:
        prev, act = parents[s]
        plan.append(act)
        s = prev
    plan.reverse()
    return plan


def _finish(res: SearchResult, plan: List[Action], tracer: _Tracer, t0: float) -> SearchResult:
    res.solved = True
    res.plan = [a.name for a in plan]
    res.cost = sum(a.cost for a in plan)
    res.time_ms = (time.perf_counter() - t0) * 1000
    res.trace, res.trace_states = tracer.edges, tracer.states()
    return res


def _fail(res: SearchResult, tracer: _Tracer, t0: float, msg="No plan exists: goal unreachable from the initial state.") -> SearchResult:
    res.solved = False
    res.time_ms = (time.perf_counter() - t0) * 1000
    res.trace, res.trace_states = tracer.edges, tracer.states()
    res.message = msg
    return res


# --------------------------------------------------------------------------
# Uninformed forward search
# --------------------------------------------------------------------------
def breadth_first_search(problem: Problem, max_nodes: int = 2_000_000) -> SearchResult:
    """BFS: complete; optimal in number of actions (not in cost)."""
    t0, res, tr = time.perf_counter(), SearchResult("BFS", None, False), _Tracer()
    start = problem.init
    tr.id(start)
    if problem.is_goal(start):
        return _finish(res, [], tr, t0)
    frontier = deque([start])
    parents = {start: (None, None)}
    while frontier:
        res.max_frontier = max(res.max_frontier, len(frontier))
        s = frontier.popleft()
        res.nodes_expanded += 1
        if res.nodes_expanded > max_nodes:
            return _fail(res, tr, t0, "Node limit reached")
        for a in problem.applicable_actions(s):
            child = a.apply(s)
            res.nodes_generated += 1
            if child in parents:
                continue
            parents[child] = (s, a)
            tr.edge(s, a.name, child)
            if problem.is_goal(child):  # goal test on generation
                return _finish(res, _reconstruct(parents, child), tr, t0)
            frontier.append(child)
    return _fail(res, tr, t0)


def depth_first_search(problem: Problem, depth_limit: int = 50) -> SearchResult:
    """Graph-search DFS: finds *a* plan quickly but usually not the shortest one."""
    t0, res, tr = time.perf_counter(), SearchResult("DFS", None, False), _Tracer()
    start = problem.init
    tr.id(start)
    stack = [(start, 0)]
    parents = {start: (None, None)}
    while stack:
        res.max_frontier = max(res.max_frontier, len(stack))
        s, d = stack.pop()
        res.nodes_expanded += 1
        if problem.is_goal(s):
            return _finish(res, _reconstruct(parents, s), tr, t0)
        if d >= depth_limit:
            continue
        # reversed so that the first listed action is explored first
        for a in reversed(list(problem.applicable_actions(s))):
            child = a.apply(s)
            res.nodes_generated += 1
            if child in parents:
                continue
            parents[child] = (s, a)
            tr.edge(s, a.name, child)
            stack.append((child, d + 1))
    return _fail(res, tr, t0)


def iterative_deepening_search(problem: Problem, max_depth: int = 30, max_nodes: int = 1_000_000) -> SearchResult:
    """IDDFS: BFS-like optimality (in #actions) with DFS-like memory."""
    t0, res, tr = time.perf_counter(), SearchResult("IDDFS", None, False), _Tracer()
    tr.id(problem.init)

    class _Limit(Exception):
        pass

    def dls(s: State, depth: int, path: List[Action], on_path: set) -> Optional[List[Action]]:
        res.nodes_expanded += 1
        if res.nodes_expanded > max_nodes:
            raise _Limit
        if problem.is_goal(s):
            return path
        if depth == 0:
            return None
        for a in problem.applicable_actions(s):
            child = a.apply(s)
            res.nodes_generated += 1
            if child in on_path:  # avoid cycles along current path
                continue
            tr.edge(s, a.name, child)
            on_path.add(child)
            found = dls(child, depth - 1, path + [a], on_path)
            on_path.discard(child)
            if found is not None:
                return found
        return None

    for limit in range(max_depth + 1):
        res.max_frontier = max(res.max_frontier, limit)
        try:
            found = dls(problem.init, limit, [], {problem.init})
        except _Limit:
            return _fail(res, tr, t0, f"Node limit ({max_nodes:,}) reached at depth {limit}")
        if found is not None:
            return _finish(res, found, tr, t0)
    return _fail(res, tr, t0, f"No plan within depth {max_depth}")


# --------------------------------------------------------------------------
# Best-first family (UCS, Greedy, A*)
# --------------------------------------------------------------------------
def _best_first(problem: Problem, name: str, heuristic: Optional[str], w_g: float, w_h: float,
                max_nodes: int = 2_000_000) -> SearchResult:
    t0, res, tr = time.perf_counter(), SearchResult(name, heuristic, False), _Tracer()
    h = HEURISTICS[heuristic or "zero"](problem)
    start = problem.init
    tr.id(start)
    counter = itertools.count()  # FIFO tie-breaking
    h0 = h(start)
    if h0 == float("inf"):
        return _fail(res, tr, t0, "Heuristic proves goal unreachable (relaxed problem unsolvable).")
    frontier = [(w_g * 0 + w_h * h0, h0, next(counter), start)]
    best_g = {start: 0.0}
    parents = {start: (None, None)}
    closed = set()
    while frontier:
        res.max_frontier = max(res.max_frontier, len(frontier))
        _, _, _, s = heapq.heappop(frontier)
        if s in closed:
            continue
        closed.add(s)
        res.nodes_expanded += 1
        if problem.is_goal(s):  # goal test on expansion (needed for optimality)
            return _finish(res, _reconstruct(parents, s), tr, t0)
        if res.nodes_expanded > max_nodes:
            return _fail(res, tr, t0, "Node limit reached")
        g = best_g[s]
        for a in problem.applicable_actions(s):
            child = a.apply(s)
            res.nodes_generated += 1
            g2 = g + a.cost
            if child in closed or g2 >= best_g.get(child, float("inf")):
                continue
            hc = h(child)
            if hc == float("inf"):
                continue  # dead end in relaxed problem -> dead end in real problem
            best_g[child] = g2
            parents[child] = (s, a)
            tr.edge(s, a.name, child)
            heapq.heappush(frontier, (w_g * g2 + w_h * hc, hc, next(counter), child))
    return _fail(res, tr, t0)


def uniform_cost_search(problem: Problem) -> SearchResult:
    """UCS (Dijkstra): optimal w.r.t. action costs."""
    return _best_first(problem, "UCS", None, 1.0, 0.0)


def greedy_best_first_search(problem: Problem, heuristic: str = "h_add") -> SearchResult:
    """GBFS: expands the node that *looks* closest to the goal. Fast, not optimal."""
    return _best_first(problem, "Greedy", heuristic, 0.0, 1.0)


def astar_search(problem: Problem, heuristic: str = "h_max") -> SearchResult:
    """A*: f = g + h. Optimal when h is admissible (e.g. h_max)."""
    return _best_first(problem, "A*", heuristic, 1.0, 1.0)


# --------------------------------------------------------------------------
# Backward (regression) search
# --------------------------------------------------------------------------
def backward_search(problem: Problem, max_nodes: int = 2_000_000) -> SearchResult:
    """Breadth-first regression search from the goal towards the initial state."""
    t0, res, tr = time.perf_counter(), SearchResult("Backward-BFS", None, False), _Tracer()
    if not problem.mutex_pairs:
        problem.compute_mutex_pairs()
    start = problem.goal
    tr.id(start)
    if start <= problem.init:
        return _finish(res, [], tr, t0)
    frontier = deque([start])
    parents: Dict[State, Tuple[Optional[State], Optional[Action]]] = {start: (None, None)}
    while frontier:
        res.max_frontier = max(res.max_frontier, len(frontier))
        g = frontier.popleft()
        res.nodes_expanded += 1
        if res.nodes_expanded > max_nodes:
            return _fail(res, tr, t0, "Node limit reached")
        for a in problem.actions:
            if not a.relevant(g):
                continue
            g2 = a.regress(g)
            res.nodes_generated += 1
            if g2 in parents or not problem.consistent(g2):
                continue
            parents[g2] = (g, a)
            tr.edge(g, a.name, g2)
            if g2 <= problem.init:
                # actions were collected goal -> init, so reverse order is already forward
                plan, cur = [], g2
                while parents[cur][0] is not None:
                    prev, act = parents[cur]
                    plan.append(act)
                    cur = prev
                return _finish(res, plan, tr, t0)
            frontier.append(g2)
    return _fail(res, tr, t0)


# --------------------------------------------------------------------------
ALGORITHMS = {
    "BFS": lambda p, h=None: breadth_first_search(p),
    "DFS": lambda p, h=None: depth_first_search(p),
    "IDDFS": lambda p, h=None: iterative_deepening_search(p),
    "UCS": lambda p, h=None: uniform_cost_search(p),
    "Greedy": lambda p, h="h_add": greedy_best_first_search(p, h or "h_add"),
    "A*": lambda p, h="h_max": astar_search(p, h or "h_max"),
    "Backward-BFS": lambda p, h=None: backward_search(p),
}

USES_HEURISTIC = {"Greedy", "A*"}


def solve(problem: Problem, algorithm: str = "A*", heuristic: Optional[str] = None) -> SearchResult:
    if algorithm not in ALGORITHMS:
        raise ValueError(f"Unknown algorithm {algorithm}. Choose from {list(ALGORITHMS)}")
    return ALGORITHMS[algorithm](problem, heuristic)
