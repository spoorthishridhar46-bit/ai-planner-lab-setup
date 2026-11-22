"""Unit tests:  pytest -q"""
import random
from pathlib import Path

import pytest

from planner.pddl_parser import PDDLError, load, loads
from planner.search import ALGORITHMS, solve
from planner.strips import Action
from planner.validator import (EXECUTABLE_NO_GOAL, NOT_EXECUTABLE, VALID, random_walk,
                               validate)

ROOT = Path(__file__).resolve().parents[1]
BASIC = ROOT / "pddl" / "lab_basic"
EXT = ROOT / "pddl" / "lab_extended"


@pytest.fixture
def basic():
    return load(BASIC / "domain.pddl", BASIC / "p01_question.pddl")


@pytest.fixture
def ext():
    return load(EXT / "domain.pddl", EXT / "p01_full_setup.pddl")


# ---------------- STRIPS semantics ----------------
def test_action_semantics():
    a = Action("Flip", frozenset({"Off"}), frozenset({"On"}), frozenset({"Off"}))
    assert a.applicable(frozenset({"Off"}))
    assert not a.applicable(frozenset({"On"}))
    assert a.apply(frozenset({"Off", "X"})) == frozenset({"On", "X"})
    assert a.regress(frozenset({"On", "X"})) == frozenset({"Off", "X"})


# ---------------- Parser ----------------
def test_parser_reads_question(basic):
    assert basic.init == {"ProjectorOff", "ComputersAvailable", "LabUnclean", "SoftwareNotInstalled", "InstructorAbsent"}
    assert {"ProjectorOn", "LabClean", "SoftwareReady", "InstructorPresent"} <= basic.goal
    a = basic.action("InstallSoftware")
    assert "ComputersAvailable" in a.pre and "SoftwareReady" in a.add


def test_parser_action_costs(ext):
    assert ext.action("InstallSoftware").cost == 20
    assert ext.action("InstallSoftwareFromUSB").cost == 40


def test_parser_rejects_parameters():
    dom = "(define (domain d) (:action a :parameters (?x) :precondition (and) :effect (and (p))))"
    with pytest.raises(PDDLError):
        loads(dom, "(define (problem p) (:domain d) (:init) (:goal (and (p))))")


# ---------------- Search ----------------
@pytest.mark.parametrize("alg", list(ALGORITHMS))
def test_every_algorithm_returns_a_valid_plan(basic, alg):
    r = solve(basic, alg)
    assert r.solved
    assert validate(basic, r.plan).verdict == VALID


def test_question_plan(basic):
    r = solve(basic, "BFS")
    assert r.length == 5
    assert r.plan[-2:] == ["CallInstructor", "StartLab"]
    assert set(r.plan[:3]) == {"CleanLab", "InstallSoftware", "PrepareProjector"}


def test_ucs_and_astar_are_cost_optimal(ext):
    ucs = solve(ext, "UCS")
    astar = solve(ext, "A*", "h_max")
    bfs = solve(ext, "BFS")
    assert ucs.cost == astar.cost == 59
    assert bfs.length <= ucs.length       # BFS: fewest actions
    assert bfs.cost >= ucs.cost           # ...but not cheapest
    assert astar.nodes_expanded < ucs.nodes_expanded  # heuristic helps


@pytest.mark.parametrize("pf", ["p02_power_left_on", "p03_software_preinstalled", "p04_instructor_early",
                                "p05_almost_ready", "p07_network_faulty"])
def test_extended_scenarios_solved_and_valid(pf):
    p = load(EXT / "domain.pddl", EXT / f"{pf}.pddl")
    for alg in ["BFS", "UCS", "A*", "Greedy", "Backward-BFS"]:
        r = solve(p, alg)
        assert r.solved, (pf, alg)
        assert validate(p, r.plan).is_valid, (pf, alg)


def test_power_left_on_requires_switching_off():
    p = load(EXT / "domain.pddl", EXT / "p02_power_left_on.pddl")
    plan = solve(p, "A*", "h_max").plan
    assert plan.index("SwitchOffMainPower") < plan.index("CleanLab") < plan.index("SwitchOnMainPower")


def test_network_fault_forces_usb_route():
    p = load(EXT / "domain.pddl", EXT / "p07_network_faulty.pddl")
    plan = solve(p, "A*", "h_max").plan
    assert "InstallSoftwareFromUSB" in plan and "ConnectNetwork" not in plan


@pytest.mark.parametrize("alg", list(ALGORITHMS))
def test_unsolvable_detected(alg):
    p = load(EXT / "domain.pddl", EXT / "p06_no_computers.pddl")
    assert not solve(p, alg).solved


def test_goal_already_true(basic):
    p = basic.with_changes(goal={"ComputersAvailable"})
    r = solve(p, "BFS")
    assert r.solved and r.plan == []


# ---------------- Validator: arbitrary sequence vs valid plan ----------------
def test_validator_verdicts(basic):
    good = ["CleanLab", "InstallSoftware", "PrepareProjector", "CallInstructor", "StartLab"]
    assert validate(basic, good).verdict == VALID
    wrong_order = ["StartLab", "CleanLab", "InstallSoftware", "PrepareProjector", "CallInstructor"]
    rep = validate(basic, wrong_order)
    assert rep.verdict == NOT_EXECUTABLE and rep.failed_at == 0
    assert "InstructorPresent" in rep.steps[0].missing
    incomplete = ["CleanLab", "InstallSoftware"]
    assert validate(basic, incomplete).verdict == EXECUTABLE_NO_GOAL


def test_unknown_action(basic):
    rep = validate(basic, ["FlyToMoon"])
    assert not rep.is_valid and rep.unknown_actions == ["FlyToMoon"]


def test_random_walks_are_always_executable(ext):
    rng = random.Random(0)
    for _ in range(200):
        assert validate(ext, random_walk(ext, 20, rng)).is_executable
