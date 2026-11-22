# 🧪 AI Planner for Laboratory Setup

**Classical (STRIPS) planning with state-space search**: generates a valid sequence of actions that turns an unprepared engineering laboratory into a lab that is ready for a practical session.

> VTU · 5th Semester B.E. CSE · **Artificial Intelligence (BCS515B)** · Mini-project 14
> Live demo: `https://<your-app>.streamlit.app` *(add after deploying, see below)*

---

## 1. What the project does

| | |
|---|---|
| **Input** | A planning problem in PDDL: facts, actions (preconditions / add / delete effects / cost), initial state, goal |
| **Output** | A **valid plan**: an ordered list of actions, every precondition satisfied when executed, goal true at the end, or a proof that no plan exists |
| **AI technique** | Classical planning formulated as **state-space search**: forward (progression) and backward (regression) |
| **Algorithms** | BFS, DFS, IDDFS, Uniform-Cost, Greedy Best-First, A\*, Backward BFS |
| **Heuristics** | goal-count, **h_max** (admissible), **h_add**: derived automatically from the delete-relaxation |
| **Validator** | Simulates any action sequence and classifies it: `VALID PLAN`, `NOT EXECUTABLE`, or `EXECUTABLE, GOAL NOT REACHED` |
| **UI** | Streamlit web app: edit states, generate plans, visualise the search, validate your own sequences, compare algorithms |

### Arbitrary sequence vs valid plan (the central idea)

* An **arbitrary sequence** is any list of action names, e.g. `StartLab, CleanLab, ...`. Nothing guarantees it can be executed.
* A **valid plan** is a sequence ⟨a₁…aₙ⟩ where `pre(aᵢ) ⊆ sᵢ₋₁` for every step (s₀ = I, sᵢ = (sᵢ₋₁ \ del(aᵢ)) ∪ add(aᵢ)) **and** `G ⊆ sₙ`.

Experiment 4 measures this directly. Of 10,000 random sequences for the full lab problem, **0 %** are valid plans. Even the planner's own 11 actions in a random order are **never** valid. The planner's output is valid **100 %** of the time.

---

## 2. Quick start

```bash
git clone https://github.com/<your-username>/ai-lab-setup-planner.git
cd ai-lab-setup-planner
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

streamlit run app.py                 # web app  -> http://localhost:8501
python -m planner.cli                # question instance with A*
python -m planner.cli --compare      # every algorithm
python -m planner.cli -d pddl/lab_extended/domain.pddl -p pddl/lab_extended/p02_power_left_on.pddl
python -m planner.cli --validate StartLab CleanLab InstallSoftware
pytest -q                            # 31 unit tests
python experiments/run_experiments.py   # regenerate all results & figures (~3 min)
```

Requires Python ≥ 3.9. The planner core uses **only the standard library**. Streamlit, pandas and matplotlib are needed only for the UI and experiments.

---

## 3. Repository layout

```
ai-lab-setup-planner/
├── app.py                      # Streamlit web application
├── planner/
│   ├── strips.py               # STRIPS model: Action, Problem, progression & regression
│   ├── pddl_parser.py          # propositional STRIPS PDDL + :action-costs parser
│   ├── search.py               # BFS, DFS, IDDFS, UCS, Greedy, A*, Backward-BFS
│   ├── heuristics.py           # goal-count, h_max, h_add (delete relaxation)
│   ├── validator.py            # plan validator + arbitrary-sequence generators
│   └── cli.py                  # command-line interface
├── pddl/
│   ├── lab_basic/              # domain exactly as in the project question + 2 problems
│   ├── lab_extended/           # realistic domain (power, safety, network, licences, costs) + 7 problems
│   └── lab_scaled/             # auto-generated k-workstation benchmark (k = 1..7)
├── experiments/
│   ├── run_experiments.py      # reproduces every table/figure in the report
│   ├── generate_scaled.py      # generator for lab_scaled
│   └── results/                # CSV files + PNG figures + console log
├── tests/test_planner.py       # pytest suite
└── docs/DEMO_SCRIPT.md         # shot list for the demo video
```

---

## 4. Problem formulation

**Planning problem** P = ⟨F, A, I, G⟩ in STRIPS with the closed-world assumption. Negative conditions such as *projector off* are modelled as their own facts (`ProjectorOff`), because STRIPS allows only positive preconditions.

### 4.1 `lab-basic` (as given in the question)

| Action | Preconditions | Add | Delete |
|---|---|---|---|
| CleanLab | LabUnclean | LabClean | LabUnclean |
| InstallSoftware | ComputersAvailable, SoftwareNotInstalled | SoftwareReady | SoftwareNotInstalled |
| PrepareProjector | ProjectorOff | ProjectorOn | ProjectorOff |
| CallInstructor | InstructorAbsent, LabClean, SoftwareReady, ProjectorOn | InstructorPresent | InstructorAbsent |
| StartLab | ProjectorOn, LabClean, SoftwareReady, InstructorPresent | LabStarted | – |
| SwitchOffProjector *(undo)* | ProjectorOn | ProjectorOff | ProjectorOn |
| InstructorLeaves *(undo)* | InstructorPresent | InstructorAbsent | InstructorPresent |

* **I** = {ProjectorOff, ComputersAvailable, LabUnclean, SoftwareNotInstalled, InstructorAbsent}
* **G** = {ProjectorOn, LabClean, SoftwareReady, InstructorPresent, LabStarted}
* **Plan found:** `CleanLab → InstallSoftware → PrepareProjector → CallInstructor → StartLab`

### 4.2 `lab-extended` (realistic, with costs in minutes)

16 actions over 23 facts, including electrical **SafetyInspection**, **Main power** (cleaning only with power *off*), **network**, **software install** (network 20 min / USB 40 min), **licence activation** (online 2 min / offline 10 min), **lab manuals**, and *undo* actions such as `SwitchOffMainPower`, which also shuts down the PCs, projector and network.

| Scenario | What makes it interesting |
|---|---|
| p01_full_setup | Everything unprepared. BFS gives 10 actions / 85 min; A\* gives 11 actions / **59 min** |
| p02_power_left_on | Lab is dirty with power ON. The planner installs software first, then switches off, cleans, and powers on again |
| p03_software_preinstalled | Only the licence is needed. Booting the PCs is skipped |
| p04_instructor_early | Goal fact already true. `CallInstructor` is omitted |
| p05_almost_ready | 2-step plan |
| p06_no_computers | **Unsolvable**. Every algorithm correctly reports *no plan* |
| p07_network_faulty | Forces the USB + offline-licence route |

---

## 5. Experimental results (summary)

Full CSVs are in `experiments/results/`.

**Exp 1 – algorithms on `lab-extended/p01_full_setup`**

| Algorithm | Plan length | Cost (min) | Nodes expanded | Optimal cost? |
|---|---|---|---|---|
| BFS | 10 | 85 | 110 | ✗ (fewest actions only) |
| DFS | 11 | 87 | 12 | ✗ |
| IDDFS | 10 | 85 | 25,347 | ✗ |
| UCS | 11 | **59** | 121 | ✓ |
| Greedy (h_add) | 11 | 59 | **12** | not guaranteed |
| **A\* (h_max)** | 11 | **59** | 77 | ✓ guaranteed |
| Backward-BFS | 10 | 85 | 1,799 | ✗ |

**Exp 3 – scalability (k workstations).** Blind search grows exponentially (BFS: 43 → 1,114,037 nodes for k = 1 → 7). A\* with h_add stays almost linear (11 → 29 nodes).

**Exp 4 – arbitrary vs valid** (10,000 samples each)

| Sequence type | lab-basic: valid % | lab-extended: valid % |
|---|---|---|
| Random sequence (plan length) | 0.05 % | 0 % |
| Plan's actions in random order | 5 % (6 of 120 orderings) | 0 % |
| Random walk (applicable actions only) | 63 % (mean 9.6 steps) | 19.8 % (mean 25.6 steps, 99.6 min) |
| **Planner** | **100 %** | **100 %** (11 steps, 59 min) |

---

## 6. Deploying the Streamlit app (free)

1. Push this repository to GitHub (public).
2. Go to <https://share.streamlit.io>, sign in with GitHub, click **Create app**.
3. Pick the repository, branch `main`, main file `app.py`, then **Deploy**.
4. Copy the `*.streamlit.app` URL into this README and into the project report.

---

## 7. Dataset and references

### Dataset

No external dataset is used. Classical planning works from a **symbolic model**, not training data. The "dataset" of this project is the set of **planning instances authored by the team** in PDDL (`pddl/`):

* `lab_basic`: 1 domain, 2 problems, taken from the project statement.
* `lab_extended`: 1 domain, 7 problems, designed by the team.
* `lab_scaled`: 7 domain/problem pairs, generated by `experiments/generate_scaled.py`.

The instances follow the PDDL language [2] and the file conventions of the International Planning Competition benchmarks [8]. Action costs use the `:action-costs` requirement introduced at IPC-2008 [9].

### References

1. R. E. Fikes and N. J. Nilsson, "STRIPS: A new approach to the application of theorem proving to problem solving," *Artificial Intelligence*, vol. 2, no. 3–4, pp. 189–208, 1971.
2. D. McDermott, M. Ghallab, A. Howe, C. Knoblock, A. Ram, M. Veloso, D. Weld and D. Wilkins, "PDDL – The Planning Domain Definition Language," Tech. Rep. CVC TR-98-003, Yale Center for Computational Vision and Control, 1998.
3. S. Russell and P. Norvig, *Artificial Intelligence: A Modern Approach*, 4th ed. Pearson, 2021. Ch. 3 (Search) and Ch. 11 (Automated Planning).
4. M. Ghallab, D. Nau and P. Traverso, *Automated Planning: Theory and Practice*. Morgan Kaufmann, 2004.
5. B. Bonet and H. Geffner, "Planning as heuristic search," *Artificial Intelligence*, vol. 129, no. 1–2, pp. 5–33, 2001.
6. P. E. Hart, N. J. Nilsson and B. Raphael, "A formal basis for the heuristic determination of minimum cost paths," *IEEE Trans. Systems Science and Cybernetics*, vol. 4, no. 2, pp. 100–107, 1968.
7. R. Howey, D. Long and M. Fox, "VAL: Automatic plan validation, continuous effects and mixed initiative planning using PDDL," in *Proc. 16th IEEE ICTAI*, 2004, pp. 294–301.
8. International Planning Competition benchmark collection (PDDL instances). <https://github.com/potassco/pddl-instances>
9. M. Helmert, M. Do and I. Refanidis, *IPC-2008 Deterministic Track: Changes to PDDL 3.1* (action costs), 2008.

---

## 8. Team

| Name | USN | Role |
|---|---|---|
| | | |

Guide: ____________ · Department of CSE · ____________ College

## License

MIT, see `LICENSE`.
