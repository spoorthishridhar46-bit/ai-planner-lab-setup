"""
Streamlit front-end for the AI Planner for Laboratory Setup.

Run locally:   streamlit run app.py
"""
from __future__ import annotations

import random
from pathlib import Path

import pandas as pd
import streamlit as st

from planner.heuristics import HEURISTIC_INFO
from planner.pddl_parser import PDDLError, loads
from planner.search import ALGORITHMS, USES_HEURISTIC, solve
from planner.strips import Problem
from planner.validator import (EXECUTABLE_NO_GOAL, NOT_EXECUTABLE, VALID, random_sequence,
                               random_walk, shuffled, validate)

ROOT = Path(__file__).resolve().parent
PDDL = ROOT / "pddl"

st.set_page_config(page_title="AI Planner for Lab Setup", page_icon="🧪", layout="wide")

ALGO_INFO = {
    "BFS": "Breadth-first: complete, fewest actions, ignores cost.",
    "DFS": "Depth-first: quick to find *a* plan, usually not shortest/cheapest.",
    "IDDFS": "Iterative deepening: BFS-optimal length with DFS memory, re-expands nodes.",
    "UCS": "Uniform-cost (Dijkstra): cheapest plan, blind.",
    "Greedy": "Greedy best-first: follows heuristic only. Fast, not optimal.",
    "A*": "A*: f = g + h. Optimal when h is admissible (h_max).",
    "Backward-BFS": "Regression search from the goal back to the initial state.",
}


# ---------------------------------------------------------------------------
# Problem loading
# ---------------------------------------------------------------------------
def builtin_problems():
    out = {}
    for dom_dir in ["lab_basic", "lab_extended"]:
        d = PDDL / dom_dir
        for pf in sorted(d.glob("p*.pddl")):
            out[f"{dom_dir} / {pf.stem}"] = (d / "domain.pddl", pf)
    sd = PDDL / "lab_scaled"
    for k in range(1, 8):
        if (sd / f"problem_k{k}.pddl").exists():
            out[f"lab_scaled / {k} workstation(s)"] = (sd / f"domain_k{k}.pddl", sd / f"problem_k{k}.pddl")
    return out


@st.cache_data(show_spinner=False)
def read_text(path: str) -> str:
    return Path(path).read_text()


def get_problem():
    st.sidebar.header("1 · Problem")
    src = st.sidebar.radio("Source", ["Built-in scenario", "Upload PDDL"], horizontal=True)
    if src == "Built-in scenario":
        probs = builtin_problems()
        keys = list(probs)
        default = keys.index("lab_extended / p01_full_setup") if "lab_extended / p01_full_setup" in keys else 0
        choice = st.sidebar.selectbox("Scenario", keys, index=default)
        dpath, ppath = probs[choice]
        dtext, ptext = read_text(str(dpath)), read_text(str(ppath))
    else:
        df = st.sidebar.file_uploader("domain.pddl", type=["pddl", "txt"])
        pf = st.sidebar.file_uploader("problem.pddl", type=["pddl", "txt"])
        if not (df and pf):
            st.info("Upload a propositional STRIPS domain and problem file (see the files in `pddl/` for the format).")
            return None
        dtext, ptext = df.read().decode(), pf.read().decode()
        choice = f"upload / {pf.name}"
    try:
        prob = loads(dtext, ptext)
    except PDDLError as e:
        st.error(f"PDDL error: {e}")
        return None
    return prob, dtext, ptext, choice


def editable_problem(prob: Problem, key: str) -> Problem:
    """Let the user change the initial state and goal in the sidebar."""
    st.sidebar.header("2 · Customise states")
    facts = sorted(prob.facts)
    init = st.sidebar.multiselect("Initial state (true facts)", facts, default=sorted(prob.init),
                                  key=f"init::{key}")
    goal = st.sidebar.multiselect("Goal (facts that must hold)", facts, default=sorted(prob.goal),
                                  key=f"goal::{key}")
    p = prob.with_changes(init=init, goal=goal)
    p.compute_mutex_pairs()
    return p


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------
def fact_chips(facts, kind="neutral"):
    colors = {"neutral": "#eef2f7", "add": "#dff5e8", "del": "#fde5e3", "goal": "#fff3d6", "miss": "#fde5e3"}
    bg = colors[kind]
    return " ".join(
        f"<span style='background:{bg};border-radius:6px;padding:2px 7px;margin:2px;display:inline-block;"
        f"font-size:0.82rem;color:#1b1b1b'>{f}</span>" for f in sorted(facts)) or "∅"


def actions_table(prob: Problem) -> pd.DataFrame:
    return pd.DataFrame([{
        "Action": a.name,
        "Preconditions": ", ".join(sorted(a.pre)),
        "Add effects": ", ".join(sorted(a.add)),
        "Delete effects": ", ".join(sorted(a.delete)),
        "Cost": a.cost,
    } for a in prob.actions])


def plan_graph(prob: Problem, plan: list[str]) -> str:
    lines = ['digraph G { rankdir=LR; node [shape=box, style="rounded,filled", fontname="Helvetica", '
             'fontsize=9, fillcolor="#eef2f7", color="#9aa5b1"]; edge [fontname="Helvetica", fontsize=9];']
    s = prob.init
    lines.append(f'S0 [label="S0\\n(initial)", fillcolor="#dbe8fb"];')
    for i, name in enumerate(plan, 1):
        a = prob.action(name)
        s2 = a.apply(s)
        added = "\\n".join("+" + f for f in sorted(s2 - s))
        fill = "#dff5e8" if i == len(plan) and prob.is_goal(s2) else "#eef2f7"
        lab = f"S{i}" + ("\\n(goal)" if i == len(plan) and prob.is_goal(s2) else "") + (f"\\n{added}" if added else "")
        lines.append(f'S{i} [label="{lab}", fillcolor="{fill}"];')
        lines.append(f'S{i - 1} -> S{i} [label="{name}"];')
        s = s2
    lines.append("}")
    return "\n".join(lines)


def search_tree_graph(res, prob: Problem, max_edges=120) -> str:
    plan_states = {prob.init}
    s = prob.init
    for name in res.plan:
        s = prob.action(name).apply(s)
        plan_states.add(s)
    id_of = {v: k for k, v in res.trace_states.items()}
    on_plan = {id_of[x] for x in plan_states if x in id_of}
    lines = ['digraph T { node [shape=circle, style=filled, fontname="Helvetica", fontsize=8, width=0.35, '
             'fillcolor="#e9ecef", color="#adb5bd"]; edge [fontsize=7, fontname="Helvetica", color="#adb5bd"];']
    for (p, a, c) in res.trace[:max_edges]:
        for n in (p, c):
            fill = "#2a78d6" if n in on_plan and res.algorithm != "Backward-BFS" else "#e9ecef"
            font = "white" if fill == "#2a78d6" else "black"
            lines.append(f'n{n} [label="{n}", fillcolor="{fill}", fontcolor="{font}"];')
        hl = (p in on_plan and c in on_plan and res.algorithm != "Backward-BFS")
        lines.append(f'n{p} -> n{c} [label="{a}"' + (', color="#2a78d6", penwidth=2' if hl else "") + "];")
    lines.append("}")
    return "\n".join(lines)


def show_validation(prob: Problem, rep):
    icon = {VALID: "✅", NOT_EXECUTABLE: "❌", EXECUTABLE_NO_GOAL: "⚠️"}[rep.verdict]
    box = {VALID: st.success, NOT_EXECUTABLE: st.error, EXECUTABLE_NO_GOAL: st.warning}[rep.verdict]
    box(f"{icon} **{rep.verdict}** — {rep.explain()}")
    rows = []
    for stp in rep.steps:
        rows.append({
            "Step": stp.index + 1,
            "Action": stp.action,
            "Preconditions met?": "✅" if stp.applicable else "❌",
            "Missing": ", ".join(stp.missing),
            "Added": ", ".join(stp.added),
            "Deleted": ", ".join(stp.deleted),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    c1, c2 = st.columns(2)
    c1.markdown("**Final state reached**<br>" + fact_chips(rep.final_state), unsafe_allow_html=True)
    c2.markdown("**Goal facts still missing**<br>" + (fact_chips(rep.unmet_goals, "miss") if rep.unmet_goals else "none 🎉"),
                unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
st.title("🧪 AI Planner for Laboratory Setup")
st.caption("Classical (STRIPS) planning with state-space search · VTU BCS515B Artificial Intelligence · Project 14")

loaded = get_problem()
if loaded is None:
    st.stop()
base_prob, dtext, ptext, key = loaded
prob = editable_problem(base_prob, key)

st.sidebar.header("3 · Search")
algo = st.sidebar.selectbox("Algorithm", list(ALGORITHMS), index=list(ALGORITHMS).index("A*"),
                            help="\n\n".join(f"**{k}** – {v}" for k, v in ALGO_INFO.items()))
heur = None
if algo in USES_HEURISTIC:
    heur = st.sidebar.selectbox("Heuristic", list(HEURISTIC_INFO), index=2 if algo == "A*" else 3,
                                format_func=lambda h: f"{h} — {HEURISTIC_INFO[h]}")
st.sidebar.caption(ALGO_INFO[algo])

tabs = st.tabs(["📋 Problem", "🤖 Generate plan", "✅ Validate a sequence", "📊 Compare algorithms",
                "🎲 Arbitrary vs valid", "📘 Theory"])

# ---- Tab 1: problem --------------------------------------------------------
with tabs[0]:
    st.subheader(f"{prob.name}  ·  domain `{prob.domain_name}`")
    if prob.description:
        st.write(prob.description)
    c1, c2 = st.columns(2)
    c1.markdown("**Initial state I**<br>" + fact_chips(prob.init), unsafe_allow_html=True)
    c2.markdown("**Goal G**<br>" + fact_chips(prob.goal, "goal"), unsafe_allow_html=True)
    st.markdown(f"**|F| = {len(prob.facts)} facts, |A| = {len(prob.actions)} actions** → "
                f"up to 2^{len(prob.facts)} = {2 ** len(prob.facts):,} possible states.")
    st.markdown("**Actions (preconditions → effects)**")
    st.dataframe(actions_table(prob), hide_index=True, width="stretch")
    with st.expander("View PDDL source"):
        a, b = st.columns(2)
        a.code(dtext, language="lisp")
        b.code(ptext, language="lisp")

# ---- Tab 2: plan -----------------------------------------------------------
with tabs[1]:
    st.subheader(f"Plan with {algo}" + (f" + {heur}" if heur else ""))
    if st.button("▶ Generate plan", type="primary"):
        with st.spinner("Searching the state space…"):
            st.session_state["result"] = (key, prob.init, prob.goal, solve(prob, algo, heur))
    stored = st.session_state.get("result")
    if stored and stored[0] == key and stored[1] == prob.init and stored[2] == prob.goal:
        res = stored[3]
        m = st.columns(5)
        m[0].metric("Plan length", res.length if res.solved else "—")
        m[1].metric("Plan cost", f"{res.cost:g}" if res.solved else "—")
        m[2].metric("Nodes expanded", f"{res.nodes_expanded:,}")
        m[3].metric("Nodes generated", f"{res.nodes_generated:,}")
        m[4].metric("Time", f"{res.time_ms:.1f} ms")
        if not res.solved:
            st.error(f"❌ {res.message}")
        else:
            rep = validate(prob, res.plan)
            st.success(f"Plan found by **{res.algorithm}** and independently re-checked by the validator: "
                       f"**{rep.verdict}**.")
            st.markdown("**Plan**  \n" + "  \n".join(f"{i}. `{a}`" for i, a in enumerate(res.plan, 1)))
            st.session_state["last_plan"] = res.plan
            st.markdown("**State transitions** (each box shows facts added by the action)")
            try:
                st.graphviz_chart(plan_graph(prob, res.plan), width="stretch")
            except Exception:
                pass
            with st.expander("Step-by-step trace"):
                show_validation(prob, rep)
        with st.expander(f"Explored search tree (first {min(len(res.trace), 120)} edges; plan path in blue)"):
            try:
                st.graphviz_chart(search_tree_graph(res, prob))
            except Exception as e:
                st.write(e)
            st.caption("Node numbers are state IDs in generation order. "
                       "For backward search the nodes are sub-goals, not world states.")
    else:
        st.info("Press **Generate plan**. Change the scenario, the states or the algorithm in the sidebar.")

# ---- Tab 3: validate -------------------------------------------------------
with tabs[2]:
    st.subheader("Is this sequence a valid plan?")
    st.write("Type any sequence of action names (one per line) — or generate one — and the validator "
             "simulates it from the initial state, checking every precondition and finally the goal.")
    names = [a.name for a in prob.actions]
    rng = random.Random()
    c = st.columns(4)
    if c[0].button("🎲 Random sequence"):
        n = len(st.session_state.get("last_plan", [])) or 6
        st.session_state["seq_text"] = "\n".join(random_sequence(prob, n, rng))
    if c[1].button("🚶 Random walk"):
        st.session_state["seq_text"] = "\n".join(random_walk(prob, 30, rng))
    if c[2].button("🔀 Shuffle planner's plan"):
        st.session_state["seq_text"] = "\n".join(shuffled(st.session_state.get("last_plan", []), rng))
    if c[3].button("🤖 Use planner's plan"):
        st.session_state["seq_text"] = "\n".join(st.session_state.get("last_plan", []))
    txt = st.text_area("Action sequence", key="seq_text", height=200,
                       placeholder="CleanLab\nInstallSoftware\nPrepareProjector\nCallInstructor\nStartLab")
    st.caption("Available actions: " + ", ".join(f"`{n}`" for n in names))
    seq = [line.strip() for line in txt.splitlines() if line.strip()]
    if seq:
        show_validation(prob, validate(prob, seq))

# ---- Tab 4: compare --------------------------------------------------------
with tabs[3]:
    st.subheader("All algorithms on the current problem")
    if st.button("Run comparison"):
        rows = []
        configs = [(a, None) for a in ALGORITHMS if a not in USES_HEURISTIC] + \
                  [("Greedy", "goal_count"), ("Greedy", "h_add"), ("A*", "goal_count"), ("A*", "h_max"), ("A*", "h_add")]
        if len(prob.facts) > 22:
            configs = [c for c in configs if c[0] not in ("IDDFS", "Backward-BFS")]
            st.caption("IDDFS and Backward-BFS are skipped on large instances (they need far too many nodes).")
        bar = st.progress(0.0)
        for i, (a, h) in enumerate(configs):
            r = solve(prob, a, h)
            row = r.as_row()
            row["label"] = a + (f" ({h})" if h else "")
            row["valid"] = validate(prob, r.plan).is_valid if r.solved else None
            rows.append(row)
            bar.progress((i + 1) / len(configs))
        df = pd.DataFrame(rows).set_index("label")
        st.dataframe(df[["solved", "valid", "plan_length", "plan_cost", "nodes_expanded", "nodes_generated",
                         "max_frontier", "time_ms"]], width="stretch")
        c1, c2 = st.columns(2)
        c1.markdown("**Nodes expanded** (fewer = more efficient search)")
        c1.bar_chart(df["nodes_expanded"])
        c2.markdown("**Plan cost** (lower = better plan)")
        c2.bar_chart(df["plan_cost"])

# ---- Tab 5: arbitrary vs valid --------------------------------------------
with tabs[4]:
    st.subheader("Arbitrary sequences vs valid plans")
    st.write("We sample many action sequences that were **not** produced by planning and check how many "
             "of them are actually valid plans.")
    n = st.slider("Samples per method", 100, 20000, 2000, step=100)
    if st.button("Run experiment"):
        ref = solve(prob, "A*", "h_max")
        if not ref.solved:
            st.error("The current problem has no plan, so no sequence can be valid.")
        else:
            L, r = len(ref.plan), random.Random(42)
            methods = {
                f"Random sequence (len {L})": [random_sequence(prob, L, r) for _ in range(n)],
                "Random walk (applicable only)": [random_walk(prob, 3 * L, r) for _ in range(n)],
                "Planner's actions, shuffled": [shuffled(ref.plan, r) for _ in range(n)],
                "Planner (A*)": [ref.plan],
            }
            rows = []
            for name, seqs in methods.items():
                reps = [validate(prob, s) for s in seqs]
                valid = [x for x in reps if x.is_valid]
                rows.append({"method": name,
                             "executable %": 100 * sum(x.is_executable for x in reps) / len(reps),
                             "valid plan %": 100 * len(valid) / len(reps),
                             "avg cost of valid ones": (sum(x.cost for x in valid) / len(valid)) if valid else None})
            df = pd.DataFrame(rows).set_index("method")
            st.dataframe(df.style.format("{:.2f}", na_rep="—"), width="stretch")
            st.bar_chart(df[["executable %", "valid plan %"]], stack=False)
            st.info("Random sequences almost never satisfy all preconditions. Random walks are executable by "
                    "construction but rarely reach the goal, and when they do the plan is long and costly. "
                    "Only goal-directed search guarantees a valid (and, with UCS/A*-h_max, optimal) plan.")

# ---- Tab 6: theory ---------------------------------------------------------
with tabs[5]:
    st.subheader("Classical planning in one page")
    st.markdown(r"""
**Problem** $P = \langle F, A, I, G \rangle$ — facts, actions, initial state, goal (STRIPS, closed-world).

**Action** $a = \langle pre(a), add(a), del(a)\rangle$ is *applicable* in state $s$ iff $pre(a) \subseteq s$,
and produces $\gamma(s,a) = (s \setminus del(a)) \cup add(a)$.

**Arbitrary sequence**: any list $\langle a_1,\dots,a_n\rangle$ of action names. Nothing guarantees it can be executed.

**Valid plan**: a sequence such that for every $i$, $pre(a_i) \subseteq s_{i-1}$ where
$s_0 = I,\; s_i = \gamma(s_{i-1}, a_i)$ — **and** $G \subseteq s_n$.

**State-space search** explores the graph whose nodes are states and whose edges are applicable actions:
- *Progression* (forward) from $I$ until a state satisfies $G$ — BFS, DFS, IDDFS, UCS, Greedy, A*.
- *Regression* (backward) from $G$, replacing goals by preconditions until $I$ satisfies the sub-goal.

**Heuristics** are derived automatically by ignoring delete effects (the *relaxed* problem):
$h_{max}$ is admissible (A* stays optimal); $h_{add}$ is more informed but may overestimate.
""")
