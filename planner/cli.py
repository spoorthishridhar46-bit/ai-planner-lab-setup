"""
Command-line interface.

Examples
    python -m planner.cli                                   # question instance, A*
    python -m planner.cli -d pddl/lab_extended/domain.pddl -p pddl/lab_extended/p01_full_setup.pddl -a BFS
    python -m planner.cli --compare                         # run every algorithm
    python -m planner.cli --validate CleanLab InstallSoftware StartLab
"""
import argparse
from pathlib import Path

from .pddl_parser import load
from .search import ALGORITHMS, solve
from .strips import state_str
from .validator import validate

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description="AI Planner for Laboratory Setup (classical STRIPS planning)")
    ap.add_argument("-d", "--domain", default=str(ROOT / "pddl/lab_basic/domain.pddl"))
    ap.add_argument("-p", "--problem", default=str(ROOT / "pddl/lab_basic/p01_question.pddl"))
    ap.add_argument("-a", "--algorithm", default="A*", choices=list(ALGORITHMS))
    ap.add_argument("--heuristic", default=None, choices=["zero", "goal_count", "h_max", "h_add"])
    ap.add_argument("--compare", action="store_true", help="run all algorithms")
    ap.add_argument("--validate", nargs="+", metavar="ACTION", help="validate a given action sequence")
    args = ap.parse_args()

    prob = load(args.domain, args.problem)
    print(f"Problem : {prob.name}  (domain {prob.domain_name})")
    print(f"Initial : {state_str(prob.init)}")
    print(f"Goal    : {state_str(prob.goal)}\n")

    if args.validate:
        rep = validate(prob, args.validate)
        for st in rep.steps:
            mark = "OK " if st.applicable else "ERR"
            extra = f"+{st.added} -{st.deleted}" if st.applicable else f"missing {st.missing}"
            print(f"  [{mark}] {st.index + 1}. {st.action:24s} {extra}")
        print(f"\nVerdict: {rep.verdict} - {rep.explain()}")
        return

    algs = list(ALGORITHMS) if args.compare else [args.algorithm]
    for alg in algs:
        r = solve(prob, alg, args.heuristic)
        print(f"== {alg}{' (' + r.heuristic + ')' if r.heuristic else ''}")
        if not r.solved:
            print(f"   {r.message}")
        else:
            for i, a in enumerate(r.plan, 1):
                print(f"   {i:2d}. {a}")
            print(f"   length={r.length} cost={r.cost:g} expanded={r.nodes_expanded} "
                  f"generated={r.nodes_generated} time={r.time_ms:.2f}ms "
                  f"-> {validate(prob, r.plan).verdict}")
        print()


if __name__ == "__main__":
    main()
