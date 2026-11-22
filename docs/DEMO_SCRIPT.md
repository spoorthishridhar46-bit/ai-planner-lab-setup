# Demo video script (target 5–6 minutes)

Record the screen with OBS Studio or the Windows Game Bar (Win + G), 1080p. Keep the browser zoom at 110 % so text is readable.

| # | Time | On screen | What to say |
|---|---|---|---|
| 1 | 0:00–0:30 | Title slide of the PPT | Project name, team, subject code BCS515B. "We built a classical planner that prepares an engineering lab for a practical session." |
| 2 | 0:30–1:00 | GitHub repo page | Show the folder structure (planner/, pddl/, experiments/, app.py) and the green *tests* badge / Actions tab. |
| 3 | 1:00–1:40 | App → **Problem** tab, scenario `lab_basic / p01_question` | Read out the initial state and goal from the question. Show the actions table: "every action has preconditions, add effects and delete effects." Open *View PDDL source*. |
| 4 | 1:40–2:20 | **Generate plan** with BFS | Plan: CleanLab → InstallSoftware → PrepareProjector → CallInstructor → StartLab. Show the state-transition diagram and the explored search tree. |
| 5 | 2:20–3:20 | **Validate a sequence** tab | Type `StartLab, CleanLab, …` → ❌ NOT EXECUTABLE (missing InstructorPresent…). Click *Use planner's plan* → ✅ VALID. Type only `CleanLab, InstallSoftware` → ⚠️ executable but goal not reached. "This is the difference between an arbitrary sequence and a valid plan." |
| 6 | 3:20–4:10 | Switch to `lab_extended / p01_full_setup`. Generate with BFS, then A* (h_max) | BFS: 10 actions, 85 min (USB route). A*: 11 actions, 59 min. "Shortest is not cheapest. A* with an admissible heuristic guarantees the cheapest plan." |
| 7 | 4:10–4:40 | Scenario `p02_power_left_on` with A* | "Cleaning needs power off, so the planner finishes the software install first, then switches off, cleans and powers back on." |
| 8 | 4:40–5:00 | Scenario `p06_no_computers` | "No computers: the planner proves no plan exists instead of returning a wrong sequence." |
| 9 | 5:00–5:30 | **Compare algorithms** and **Arbitrary vs valid** tabs | Run both. Point at nodes expanded and the 0 % valid rate of random sequences. |
| 10 | 5:30–6:00 | `fig3_scalability.png` | "Blind search grows exponentially with the number of workstations. A* with h_add stays almost flat." Close with the deployed URL. |
