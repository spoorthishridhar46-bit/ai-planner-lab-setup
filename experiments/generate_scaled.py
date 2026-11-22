"""
Generate the LAB-SCALED benchmark: the same lab problem with k independent
workstations (k = 1..K). Each workstation must be booted, have software
installed and licensed, so the reachable state space grows exponentially with
k. Output is grounded STRIPS PDDL in pddl/lab_scaled/.

Usage:  python experiments/generate_scaled.py --max-k 7
"""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "pddl" / "lab_scaled"


def action(name, pre, add, dele, cost):
    pre_s = " ".join(f"({p})" for p in pre)
    eff = " ".join([f"({a})" for a in add] + [f"(not ({d}))" for d in dele])
    return (f"  (:action {name}\n    :parameters ()\n    :precondition (and {pre_s})\n"
            f"    :effect (and {eff} (increase (total-cost) {cost})))\n")


def domain(k: int) -> str:
    preds = ["MainPowerOff", "MainPowerOn", "LabUnclean", "LabClean", "NetworkDown", "NetworkUp",
             "ProjectorOff", "ProjectorOn", "InstructorAbsent", "InstructorPresent",
             "SoftwareReady", "LabStarted"]
    acts = [
        action("CleanLab", ["LabUnclean", "MainPowerOff"], ["LabClean"], ["LabUnclean"], 15),
        action("SwitchOnMainPower", ["MainPowerOff"], ["MainPowerOn"], ["MainPowerOff"], 1),
        action("ConnectNetwork", ["MainPowerOn", "NetworkDown"], ["NetworkUp"], ["NetworkDown"], 2),
        action("PrepareProjector", ["ProjectorOff", "MainPowerOn"], ["ProjectorOn"], ["ProjectorOff"], 2),
        action("SwitchOffProjector", ["ProjectorOn"], ["ProjectorOff"], ["ProjectorOn"], 1),
    ]
    for i in range(1, k + 1):
        preds += [f"PC{i}Off", f"PC{i}On", f"PC{i}SoftwareInstalled", f"PC{i}Ready"]
        acts += [
            action(f"BootPC{i}", [f"PC{i}Off", "MainPowerOn"], [f"PC{i}On"], [f"PC{i}Off"], 1),
            action(f"InstallSoftwarePC{i}", [f"PC{i}On", "NetworkUp"], [f"PC{i}SoftwareInstalled"], [], 5),
            action(f"ActivateLicensePC{i}", [f"PC{i}SoftwareInstalled", "NetworkUp"], [f"PC{i}Ready"], [], 1),
            action(f"ShutDownPC{i}", [f"PC{i}On"], [f"PC{i}Off"], [f"PC{i}On"], 1),
        ]
    acts += [
        action("VerifyAllWorkstations", [f"PC{i}Ready" for i in range(1, k + 1)], ["SoftwareReady"], [], 1),
        action("CallInstructor", ["InstructorAbsent", "LabClean", "SoftwareReady", "ProjectorOn"],
               ["InstructorPresent"], ["InstructorAbsent"], 3),
        action("StartLab", ["LabClean", "SoftwareReady", "ProjectorOn", "InstructorPresent"], ["LabStarted"], [], 1),
    ]
    p = " ".join(f"({x})" for x in preds)
    return (f";; LAB-SCALED domain with {k} workstation(s) (auto-generated)\n"
            f"(define (domain lab-scaled-k{k})\n  (:requirements :strips :action-costs)\n"
            f"  (:predicates {p})\n  (:functions (total-cost))\n" + "".join(acts) + ")\n")


def problem(k: int) -> str:
    init = ["MainPowerOff", "LabUnclean", "NetworkDown", "ProjectorOff", "InstructorAbsent"] + \
           [f"PC{i}Off" for i in range(1, k + 1)]
    goal = ["ProjectorOn", "LabClean", "SoftwareReady", "InstructorPresent", "LabStarted"]
    i_s = " ".join(f"({x})" for x in init)
    g_s = " ".join(f"({x})" for x in goal)
    return (f";; Unprepared lab with {k} workstation(s) (auto-generated)\n"
            f"(define (problem lab-scaled-k{k})\n  (:domain lab-scaled-k{k})\n"
            f"  (:init {i_s})\n  (:goal (and {g_s}))\n  (:metric minimize (total-cost)))\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-k", type=int, default=7)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for k in range(1, args.max_k + 1):
        (OUT / f"domain_k{k}.pddl").write_text(domain(k))
        (OUT / f"problem_k{k}.pddl").write_text(problem(k))
    print(f"Wrote {args.max_k} domain/problem pairs to {OUT}")


if __name__ == "__main__":
    main()
