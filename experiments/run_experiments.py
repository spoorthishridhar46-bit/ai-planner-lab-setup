"""
Reproduce every experimental result in the report.

    python experiments/run_experiments.py            # all experiments
    python experiments/run_experiments.py --quick    # fewer samples / smaller k

Outputs (experiments/results/):
    exp1_algorithm_comparison.csv   all algorithms x all lab problems
    exp2_heuristic_comparison.csv   A* / Greedy with each heuristic
    exp3_scalability.csv            k workstations, k = 1..7
    exp4_arbitrary_vs_valid.csv     random sequences vs planner output
    fig_*.png                       charts used in the report / PPT
"""
from __future__ import annotations

import argparse
import itertools
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from planner.pddl_parser import load  # noqa: E402
from planner.search import ALGORITHMS, solve  # noqa: E402
from planner.validator import (random_sequence, random_walk, shuffled,  # noqa: E402
                               validate)

OUT = ROOT / "experiments" / "results"
OUT.mkdir(parents=True, exist_ok=True)

# Reference categorical palette (fixed order; see README "Charts")
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e6e5e0"

plt.rcParams.update({
    "figure.dpi": 150, "savefig.bbox": "tight", "font.size": 10,
    "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "axes.grid.axis": "y",
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
})


def problems():
    basic = ROOT / "pddl" / "lab_basic"
    ext = ROOT / "pddl" / "lab_extended"
    for pf in sorted(basic.glob("p*.pddl")):
        yield "lab-basic", load(basic / "domain.pddl", pf)
    for pf in sorted(ext.glob("p*.pddl")):
        yield "lab-extended", load(ext / "domain.pddl", pf)


def timed(problem, alg, h=None, repeats=3):
    runs = [solve(problem, alg, h) for _ in range(repeats)]
    r = runs[0]
    r.time_ms = statistics.median(x.time_ms for x in runs)
    return r


# ---------------------------------------------------------------------------
def exp1(repeats):
    rows = []
    for dom, p in problems():
        for alg in ALGORITHMS:
            r = timed(p, alg, repeats=repeats)
            row = {"domain": dom, "problem": p.name, **r.as_row()}
            row["valid"] = validate(p, r.plan).is_valid if r.solved else None
            row["plan"] = " -> ".join(r.plan)
            rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "exp1_algorithm_comparison.csv", index=False)

    # Figure: nodes expanded & plan cost on the main extended problem
    sub = df[df.problem == "p01-full-setup"].copy()
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    for ax, col, title in [(axes[0], "nodes_expanded", "Nodes expanded (log scale)"),
                           (axes[1], "plan_cost", "Plan cost (minutes) - lower is better")]:
        bars = ax.bar(sub.algorithm, sub[col], color=C[0], width=0.6)
        ax.set_title(title, loc="left", fontsize=11, color=INK)
        if col == "nodes_expanded":
            ax.set_yscale("log")
        for b, v in zip(bars, sub[col]):
            ax.annotate(f"{v:g}", (b.get_x() + b.get_width() / 2, b.get_height()),
                        ha="center", va="bottom", fontsize=8, color=INK2, xytext=(0, 2),
                        textcoords="offset points")
        ax.tick_params(axis="x", rotation=30)
    fig.suptitle("Experiment 1 - Algorithms on lab-extended / p01-full-setup", x=0.01, ha="left",
                 fontsize=12, color=INK)
    fig.subplots_adjust(top=0.80, wspace=0.25)
    fig.savefig(OUT / "fig1_algorithms_p01.png")
    plt.close(fig)
    return df


# ---------------------------------------------------------------------------
def exp2(repeats):
    rows = []
    for dom, p in problems():
        if dom != "lab-extended":
            continue
        for alg in ["A*", "Greedy"]:
            for h in ["zero", "goal_count", "h_max", "h_add"]:
                r = timed(p, alg, h, repeats)
                rows.append({"problem": p.name, **r.as_row()})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "exp2_heuristic_comparison.csv", index=False)

    solved = df[df.solved]
    piv = solved[solved.algorithm == "A*"].groupby("heuristic").nodes_expanded.mean().reindex(
        ["zero", "goal_count", "h_max", "h_add"])
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    bars = ax.bar(piv.index, piv.values, color=C[0], width=0.55)
    for b, v in zip(bars, piv.values):
        ax.annotate(f"{v:.0f}", (b.get_x() + b.get_width() / 2, v), ha="center", va="bottom",
                    fontsize=9, color=INK2, xytext=(0, 2), textcoords="offset points")
    ax.set_ylabel("Mean nodes expanded")
    ax.set_title("Experiment 2 - A* heuristic informedness (solvable lab-extended problems)",
                 loc="left", fontsize=11, color=INK)
    fig.savefig(OUT / "fig2_heuristics.png")
    plt.close(fig)
    return df


# ---------------------------------------------------------------------------
def exp3(max_k, time_budget_s):
    scaled = ROOT / "pddl" / "lab_scaled"
    if not (scaled / f"problem_k{max_k}.pddl").exists():
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "experiments" / "generate_scaled.py"),
                        "--max-k", str(max_k)], check=True)
    configs = [("BFS", None), ("UCS", None), ("A*", "h_max"), ("A*", "h_add"), ("Greedy", "h_add")]
    rows, gave_up = [], set()
    for k in range(1, max_k + 1):
        p = load(scaled / f"domain_k{k}.pddl", scaled / f"problem_k{k}.pddl")
        for alg, h in configs:
            label = alg + (f"({h})" if h else "")
            if label in gave_up:
                continue
            t = time.perf_counter()
            r = solve(p, alg, h)
            elapsed = time.perf_counter() - t
            rows.append({"k": k, "config": label, "facts": len(p.facts), "actions": len(p.actions),
                         **r.as_row()})
            if elapsed > time_budget_s:
                gave_up.add(label)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "exp3_scalability.csv", index=False)

    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    styles = ["-", "--", "-", "-", "--"]
    markers = ["o", "s", "o", "o", "s"]
    for i, label in enumerate(df.config.unique()):
        d = df[df.config == label]
        ax.plot(d.k, d.nodes_expanded, marker=markers[i], markersize=7, linewidth=2, color=C[i], label=label,
                linestyle=styles[i], markeredgecolor="white", markeredgewidth=1.2)
    ax.text(7.1, df[df.config == "BFS"].nodes_expanded.max(), "BFS ≈ UCS", fontsize=8, color=INK2, va="center")
    ax.text(7.1, df[df.config == "A*(h_add)"].nodes_expanded.max(), "A*(h_add) ≈\nGreedy(h_add)",
            fontsize=8, color=INK2, va="center")
    ax.set_xlim(0.7, 8.0)
    ax.set_yscale("log")
    ax.set_xlabel("Number of workstations k")
    ax.set_ylabel("Nodes expanded (log)")
    ax.set_title("Experiment 3 - Scalability: blind vs heuristic search", loc="left", fontsize=11, color=INK)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.set_xticks(sorted(df.k.unique()))
    fig.savefig(OUT / "fig3_scalability.png")
    plt.close(fig)
    return df


# ---------------------------------------------------------------------------
def exp4(samples, seed=42):
    rng = random.Random(seed)
    rows = []
    targets = [
        load(ROOT / "pddl/lab_basic/domain.pddl", ROOT / "pddl/lab_basic/p01_question.pddl"),
        load(ROOT / "pddl/lab_extended/domain.pddl", ROOT / "pddl/lab_extended/p01_full_setup.pddl"),
    ]
    for p in targets:
        plan = solve(p, "A*", "h_max").plan
        L = len(plan)

        def stats(name, seqs):
            reps = [validate(p, s) for s in seqs]
            n = len(reps)
            rows.append({
                "problem": p.name, "method": name, "samples": n,
                "executable_pct": round(100 * sum(r.is_executable for r in reps) / n, 2),
                "valid_plan_pct": round(100 * sum(r.is_valid for r in reps) / n, 2),
                "mean_len_of_valid": round(statistics.mean(len(r.sequence) for r in reps if r.is_valid), 2)
                if any(r.is_valid for r in reps) else None,
                "mean_cost_of_valid": round(statistics.mean(r.cost for r in reps if r.is_valid), 2)
                if any(r.is_valid for r in reps) else None,
            })

        stats(f"Random sequence (length {L})", [random_sequence(p, L, rng) for _ in range(samples)])
        stats(f"Random walk (applicable only, <= {3 * L} steps)",
              [random_walk(p, 3 * L, rng) for _ in range(samples)])
        if L <= 8:
            stats(f"All {L}! orderings of the plan's actions",
                  [list(x) for x in itertools.permutations(plan)])
        else:
            stats("Shuffled plan (same actions, random order)", [shuffled(plan, rng) for _ in range(samples)])
        stats("Planner (A*, h_max)", [plan])
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "exp4_arbitrary_vs_valid.csv", index=False)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), sharey=True)
    for ax, (pname, d) in zip(axes, df.groupby("problem", sort=False)):
        def short(m):
            if m.startswith("Random sequence"): return "Random\nsequence"
            if m.startswith("Random walk"): return "Random walk\n(applicable only)"
            if m.startswith("All") or m.startswith("Shuffled"): return "Plan's actions,\nreordered"
            return "Planner\n(A*, h_max)"
        labels = [short(m) for m in d.method]
        x = range(len(d))
        w = 0.38
        b1 = ax.bar([i - w / 2 - 0.01 for i in x], d.executable_pct, w, color=C[0], label="Executable")
        b2 = ax.bar([i + w / 2 + 0.01 for i in x], d.valid_plan_pct, w, color=C[1], label="Valid plan")
        for bars in (b1, b2):
            for b in bars:
                ax.annotate(f"{b.get_height():.1f}%", (b.get_x() + b.get_width() / 2, b.get_height()),
                            ha="center", va="bottom", fontsize=7.5, color=INK2, xytext=(0, 2),
                            textcoords="offset points")
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, fontsize=8)
        ax.set_title(pname, loc="left", fontsize=11, color=INK)
        ax.set_ylim(0, 112)
    axes[0].set_ylabel("% of sequences")
    axes[0].legend(frameon=False, fontsize=8, loc="upper left")
    fig.suptitle("Experiment 4 - Arbitrary action sequences vs valid plans", x=0.01, ha="left",
                 fontsize=12, color=INK)
    fig.subplots_adjust(top=0.84)
    fig.savefig(OUT / "fig4_arbitrary_vs_valid.png")
    plt.close(fig)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    print("Experiment 1 ..."); d1 = exp1(1 if a.quick else 5)
    print(d1.drop(columns=["plan"]).to_string(index=False))
    print("\nExperiment 2 ..."); print(exp2(1 if a.quick else 3).to_string(index=False))
    print("\nExperiment 3 ..."); print(exp3(4 if a.quick else 7, 20 if a.quick else 60).to_string(index=False))
    print("\nExperiment 4 ..."); print(exp4(1000 if a.quick else 10000).to_string(index=False))
    print(f"\nResults written to {OUT}")


if __name__ == "__main__":
    main()
