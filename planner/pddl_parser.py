"""
Minimal parser for propositional STRIPS PDDL (plus the :action-costs extension).

Supported subset
----------------
domain : (define (domain NAME)
           (:requirements :strips [:action-costs])
           (:predicates (P1) (P2) ...)
           [(:functions (total-cost))]
           (:action NAME
              :parameters ()
              :precondition (and (P) ...)        ; or a single (P)
              :effect (and (Q) (not (R)) [(increase (total-cost) N)])))
problem: (define (problem NAME) (:domain NAME)
           (:init (P) ...)
           (:goal (and (P) ...))
           [(:metric minimize (total-cost))])

Predicates are 0-ary (propositional). Parameterised schemas are out of scope:
the lab domain is naturally propositional, and the scaled benchmark generator
emits already-grounded PDDL.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple, Union

from .strips import Action, Problem

SExpr = Union[str, list]


class PDDLError(ValueError):
    pass


def _tokenize(text: str) -> List[str]:
    text = re.sub(r";[^\n]*", "", text)  # strip comments
    return re.findall(r"\(|\)|[^\s()]+", text)


def _parse_sexpr(tokens: List[str]) -> SExpr:
    if not tokens:
        raise PDDLError("Unexpected end of input")
    tok = tokens.pop(0)
    if tok == "(":
        out = []
        while tokens and tokens[0] != ")":
            out.append(_parse_sexpr(tokens))
        if not tokens:
            raise PDDLError("Missing ')'")
        tokens.pop(0)
        return out
    if tok == ")":
        raise PDDLError("Unexpected ')'")
    return tok


def parse_sexpr(text: str) -> SExpr:
    tokens = _tokenize(text)
    expr = _parse_sexpr(tokens)
    if tokens:
        raise PDDLError("Trailing tokens after top-level expression")
    return expr


def _atom(expr: SExpr) -> str:
    if isinstance(expr, list) and len(expr) == 1 and isinstance(expr[0], str):
        return expr[0]
    if isinstance(expr, list) and len(expr) > 1:
        raise PDDLError(f"Only 0-ary predicates are supported, got {expr}")
    raise PDDLError(f"Malformed atom: {expr}")


def _conj(expr: SExpr) -> List[SExpr]:
    """Flatten (and a b c) / single literal / () into a list of literals."""
    if expr == [] or expr is None:
        return []
    if isinstance(expr, list) and expr and expr[0] == "and":
        return expr[1:]
    return [expr]


def _parse_effect(expr: SExpr) -> Tuple[set, set, float]:
    add, delete, cost = set(), set(), 1.0
    has_cost = False
    for lit in _conj(expr):
        if isinstance(lit, list) and lit and lit[0] == "not":
            delete.add(_atom(lit[1]))
        elif isinstance(lit, list) and lit and lit[0] == "increase":
            cost = float(lit[2])
            has_cost = True
        else:
            add.add(_atom(lit))
    return add, delete, (cost if has_cost else 1.0)


def parse_domain(text: str) -> Tuple[str, List[str], List[Action]]:
    expr = parse_sexpr(text)
    if not (isinstance(expr, list) and expr and expr[0] == "define"):
        raise PDDLError("Domain must start with (define ...)")
    name = None
    predicates: List[str] = []
    actions: List[Action] = []
    for item in expr[1:]:
        if not isinstance(item, list) or not item:
            continue
        head = item[0]
        if head == "domain":
            name = item[1]
        elif head == ":predicates":
            predicates = [_atom(p) for p in item[1:]]
        elif head == ":action":
            aname = item[1]
            fields = {}
            i = 2
            while i < len(item):
                key = item[i]
                fields[key] = item[i + 1] if i + 1 < len(item) else []
                i += 2
            if fields.get(":parameters", []) not in ([], None):
                raise PDDLError(f"Action {aname}: parameters are not supported (ground the domain first)")
            pre = {_atom(p) for p in _conj(fields.get(":precondition", []))}
            add, delete, cost = _parse_effect(fields.get(":effect", []))
            actions.append(Action(aname, frozenset(pre), frozenset(add), frozenset(delete), cost))
    if name is None:
        raise PDDLError("Domain name not found")
    # Declared predicates plus anything mentioned in actions
    mentioned = set(predicates)
    for a in actions:
        mentioned |= a.pre | a.add | a.delete
    return name, sorted(mentioned), actions


def parse_problem(text: str, domain_name: str, facts: List[str], actions: List[Action]) -> Problem:
    expr = parse_sexpr(text)
    if not (isinstance(expr, list) and expr and expr[0] == "define"):
        raise PDDLError("Problem must start with (define ...)")
    pname, pdomain, init, goal = None, None, set(), set()
    for item in expr[1:]:
        if not isinstance(item, list) or not item:
            continue
        head = item[0]
        if head == "problem":
            pname = item[1]
        elif head == ":domain":
            pdomain = item[1]
        elif head == ":init":
            init = {_atom(p) for p in item[1:] if not (isinstance(p, list) and p and p[0] == "=")}
        elif head == ":goal":
            goal = {_atom(p) for p in _conj(item[1])}
    if pdomain and pdomain.lower() != domain_name.lower():
        raise PDDLError(f"Problem is for domain '{pdomain}', but domain is '{domain_name}'")
    all_facts = frozenset(set(facts) | init | goal)
    prob = Problem(
        name=pname or "problem",
        domain_name=domain_name,
        facts=all_facts,
        actions=actions,
        init=frozenset(init),
        goal=frozenset(goal),
    )
    prob.compute_mutex_pairs()
    return prob


def _leading_comment(text: str) -> str:
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(";"):
            lines.append(s.lstrip(";").strip())
        elif s:
            break
    return " ".join(l for l in lines if l and not set(l) <= {"="})


def load(domain_path: Union[str, Path], problem_path: Union[str, Path]) -> Problem:
    return loads(Path(domain_path).read_text(), Path(problem_path).read_text())


def loads(domain_text: str, problem_text: str) -> Problem:
    dname, facts, actions = parse_domain(domain_text)
    prob = parse_problem(problem_text, dname, facts, actions)
    prob.description = _leading_comment(problem_text)
    return prob
