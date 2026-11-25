"""
Streamlit front-end for the AI Planner for Laboratory Setup.

Run locally:   streamlit run app.py
"""
from __future__ import annotations

import random
import tomllib
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

TEXT_FILE = ROOT / "ui_text.toml"


def load_text():
    """All wording shown on the website lives in ui_text.toml (re-read on every page refresh)."""
    try:
        with open(TEXT_FILE, "rb") as f:
            return tomllib.load(f), None
    except Exception as e:  # broken edit -> show a friendly message instead of crashing
        return None, e


T, _text_error = load_text()
st.set_page_config(page_title=(T or {}).get("page", {}).get("browser_tab_title", "AI Planner"), layout="wide")
if T is None:
    st.error(f"ui_text.toml could not be read. Undo your last edit in that file and refresh.\n\nDetails: {_text_error}")
    st.stop()

ALGO_INFO = T["algorithms"]
S, P, V = T["sidebar"], T["plan_tab"], T["verdict"]


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
    st.sidebar.header(S["problem_header"])
    src = st.sidebar.radio(S["source_label"], [S["source_builtin"], S["source_upload"]], horizontal=True)
    if src == S["source_builtin"]:
        probs = builtin_problems()
        keys = list(probs)
        default = keys.index("lab_extended / p01_full_setup") if "lab_extended / p01_full_setup" in keys else 0
        choice = st.sidebar.selectbox(S["scenario_label"], keys, index=default)
        dpath, ppath = probs[choice]
        dtext, ptext = read_text(str(dpath)), read_text(str(ppath))
    else:
        df = st.sidebar.file_uploader("domain.pddl", type=["pddl", "txt"])
        pf = st.sidebar.file_uploader("problem.pddl", type=["pddl", "txt"])
        if not (df and pf):
            st.info(S["upload_help"])
            return None
        dtext, ptext = df.read().decode(), pf.read().decode()
        choice = f"upload / {pf.name}"
    try:
        prob = loads(dtext, ptext)
    except PDDLError as e:
        st.error(S["pddl_error"].format(error=e))
        return None
    return prob, dtext, ptext, choice


def editable_problem(prob: Problem, key: str) -> Problem:
    """Let the user change the initial state and goal in the sidebar."""
    st.sidebar.header(S["states_header"])
    facts = sorted(prob.facts)
    init = st.sidebar.multiselect(S["initial_label"], facts, default=sorted(prob.init),
                                  key=f"init::{key}")
    goal = st.sidebar.multiselect(S["goal_label"], facts, default=sorted(prob.goal),
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
        T["problem_tab"]["col_action"]: a.name,
        T["problem_tab"]["col_pre"]: ", ".join(sorted(a.pre)),
        T["problem_tab"]["col_add"]: ", ".join(sorted(a.add)),
        T["problem_tab"]["col_del"]: ", ".join(sorted(a.delete)),
        T["problem_tab"]["col_cost"]: a.cost,
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
    label = {VALID: V["valid"], NOT_EXECUTABLE: V["not_executable"], EXECUTABLE_NO_GOAL: V["no_goal"]}[rep.verdict]
    box = {VALID: st.success, NOT_EXECUTABLE: st.error, EXECUTABLE_NO_GOAL: st.warning}[rep.verdict]
    box(f"**{label}**: {rep.explain()}")
    rows = []
    for stp in rep.steps:
        rows.append({
            V["col_step"]: stp.index + 1,
            V["col_action"]: stp.action,
            V["col_ok"]: V["yes"] if stp.applicable else V["no"],
            V["col_missing"]: ", ".join(stp.missing),
            V["col_added"]: ", ".join(stp.added),
            V["col_deleted"]: ", ".join(stp.deleted),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    c1, c2 = st.columns(2)
    c1.markdown(f"**{V['final_state']}**<br>" + fact_chips(rep.final_state), unsafe_allow_html=True)
    c2.markdown(f"**{V['missing_goals']}**<br>" + (fact_chips(rep.unmet_goals, "miss") if rep.unmet_goals else V["none_missing"]),
                unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
st.title(T["page"]["title"])
st.caption(T["page"]["subtitle"])

loaded = get_problem()
if loaded is None:
    st.stop()
base_prob, dtext, ptext, key = loaded
prob = editable_problem(base_prob, key)

st.sidebar.header(S["search_header"])
algo = st.sidebar.selectbox(S["algorithm_label"], list(ALGORITHMS), index=list(ALGORITHMS).index("A*"),
                            help="\n\n".join(f"**{k}**: {v}" for k, v in ALGO_INFO.items()))
heur = None
if algo in USES_HEURISTIC:
    heur = st.sidebar.selectbox(S["heuristic_label"], list(HEURISTIC_INFO), index=2 if algo == "A*" else 3,
                                format_func=lambda h: f"{h}: {HEURISTIC_INFO[h]}")
st.sidebar.caption(ALGO_INFO.get(algo, ""))

TB = T["tabs"]
tabs = st.tabs([TB["problem"], TB["plan"], TB["validate"], TB["compare"], TB["arbitrary"], TB["theory"]])

# ---- Tab 1: problem --------------------------------------------------------
with tabs[0]:
    PT = T["problem_tab"]
    st.subheader(f"{prob.name}  |  {PT['domain_word']} `{prob.domain_name}`")
    if prob.description:
        st.write(prob.description)
    c1, c2 = st.columns(2)
    c1.markdown(f"**{PT['initial_state']}**<br>" + fact_chips(prob.init), unsafe_allow_html=True)
    c2.markdown(f"**{PT['goal']}**<br>" + fact_chips(prob.goal, "goal"), unsafe_allow_html=True)
    st.markdown(PT["size_line"].format(facts=len(prob.facts), actions=len(prob.actions),
                                       states=f"{2 ** len(prob.facts):,}"))
    st.markdown(f"**{PT['actions_heading']}**")
    st.dataframe(actions_table(prob), hide_index=True, width="stretch")
    with st.expander(PT["pddl_expander"]):
        a, b = st.columns(2)
        a.code(dtext, language="lisp")
        b.code(ptext, language="lisp")

# ---- Tab 2: plan -----------------------------------------------------------
with tabs[1]:
    st.subheader(P["heading_with_heuristic"].format(algo=algo, heuristic=heur) if heur
                 else P["heading"].format(algo=algo))
    if st.button(P["button"], type="primary"):
        with st.spinner(P["spinner"]):
            st.session_state["result"] = (key, prob.init, prob.goal, solve(prob, algo, heur))
    stored = st.session_state.get("result")
    if stored and stored[0] == key and stored[1] == prob.init and stored[2] == prob.goal:
        res = stored[3]
        m = st.columns(5)
        m[0].metric(P["metric_length"], res.length if res.solved else "—")
        m[1].metric(P["metric_cost"], f"{res.cost:g}" if res.solved else "—")
        m[2].metric(P["metric_expanded"], f"{res.nodes_expanded:,}")
        m[3].metric(P["metric_generated"], f"{res.nodes_generated:,}")
        m[4].metric(P["metric_time"], f"{res.time_ms:.1f} ms")
        if not res.solved:
            st.error(res.message)
        else:
            rep = validate(prob, res.plan)
            verdict_label = {VALID: V["valid"], NOT_EXECUTABLE: V["not_executable"],
                             EXECUTABLE_NO_GOAL: V["no_goal"]}[rep.verdict]
            st.success(P["found"].format(algo=res.algorithm, verdict=verdict_label))
            st.markdown(f"**{P['plan_heading']}**  \n" + "  \n".join(f"{i}. `{a}`" for i, a in enumerate(res.plan, 1)))
            st.session_state["last_plan"] = res.plan
            st.markdown(P["transitions_heading"])
            try:
                st.graphviz_chart(plan_graph(prob, res.plan), width="stretch")
            except Exception:
                pass
            with st.expander(P["trace_expander"]):
                show_validation(prob, rep)
        with st.expander(P["tree_expander"].format(n=min(len(res.trace), 120))):
            try:
                st.graphviz_chart(search_tree_graph(res, prob))
            except Exception as e:
                st.write(e)
            st.caption(P["tree_caption"])
    else:
        st.info(P["start_hint"])

# ---- Tab 3: validate -------------------------------------------------------
with tabs[2]:
    VT = T["validate_tab"]
    st.subheader(VT["heading"])
    st.write(VT["intro"])
    names = [a.name for a in prob.actions]
    rng = random.Random()
    c = st.columns(4)
    if c[0].button(VT["btn_random"]):
        n = len(st.session_state.get("last_plan", [])) or 6
        st.session_state["seq_text"] = "\n".join(random_sequence(prob, n, rng))
    if c[1].button(VT["btn_walk"]):
        st.session_state["seq_text"] = "\n".join(random_walk(prob, 30, rng))
    if c[2].button(VT["btn_shuffle"]):
        st.session_state["seq_text"] = "\n".join(shuffled(st.session_state.get("last_plan", []), rng))
    if c[3].button(VT["btn_use_plan"]):
        st.session_state["seq_text"] = "\n".join(st.session_state.get("last_plan", []))
    txt = st.text_area(VT["text_label"], key="seq_text", height=200,
                       placeholder="CleanLab\nInstallSoftware\nPrepareProjector\nCallInstructor\nStartLab")
    st.caption(VT["available"].format(names=", ".join(f"`{n}`" for n in names)))
    seq = [line.strip() for line in txt.splitlines() if line.strip()]
    if seq:
        show_validation(prob, validate(prob, seq))

# ---- Tab 4: compare --------------------------------------------------------
with tabs[3]:
    CT = T["compare_tab"]
    st.subheader(CT["heading"])
    if st.button(CT["button"]):
        rows = []
        configs = [(a, None) for a in ALGORITHMS if a not in USES_HEURISTIC] + \
                  [("Greedy", "goal_count"), ("Greedy", "h_add"), ("A*", "goal_count"), ("A*", "h_max"), ("A*", "h_add")]
        if len(prob.facts) > 22:
            configs = [c for c in configs if c[0] not in ("IDDFS", "Backward-BFS")]
            st.caption(CT["skipped"])
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
        c1.markdown(CT["chart_nodes"])
        c1.bar_chart(df["nodes_expanded"])
        c2.markdown(CT["chart_cost"])
        c2.bar_chart(df["plan_cost"])

# ---- Tab 5: arbitrary vs valid --------------------------------------------
with tabs[4]:
    AT = T["arbitrary_tab"]
    st.subheader(AT["heading"])
    st.write(AT["intro"])
    n = st.slider(AT["slider"], 100, 20000, 2000, step=100)
    if st.button(AT["button"]):
        ref = solve(prob, "A*", "h_max")
        if not ref.solved:
            st.error(AT["no_plan"])
        else:
            L, r = len(ref.plan), random.Random(42)
            methods = {
                AT["m_random"].format(n=L): [random_sequence(prob, L, r) for _ in range(n)],
                AT["m_walk"]: [random_walk(prob, 3 * L, r) for _ in range(n)],
                AT["m_shuffle"]: [shuffled(ref.plan, r) for _ in range(n)],
                AT["m_planner"]: [ref.plan],
            }
            rows = []
            for name, seqs in methods.items():
                reps = [validate(prob, s) for s in seqs]
                valid = [x for x in reps if x.is_valid]
                rows.append({AT["col_method"]: name,
                             AT["col_exec"]: 100 * sum(x.is_executable for x in reps) / len(reps),
                             AT["col_valid"]: 100 * len(valid) / len(reps),
                             AT["col_cost"]: (sum(x.cost for x in valid) / len(valid)) if valid else None})
            df = pd.DataFrame(rows).set_index(AT["col_method"])
            st.dataframe(df.style.format("{:.2f}", na_rep="—"), width="stretch")
            st.bar_chart(df[[AT["col_exec"], AT["col_valid"]]], stack=False)
            st.info(AT["conclusion"])

# ---- Tab 6: theory ---------------------------------------------------------
with tabs[5]:
    st.subheader(T["theory_tab"]["heading"])
    st.markdown(T["theory_tab"]["body"])
