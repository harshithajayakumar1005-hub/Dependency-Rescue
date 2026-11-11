# DEPENDENCY RESCUE
### Project Schedule Optimization, Dependency Graph Analysis & What-If Delay Prediction System

**Dependency Rescue** is a full-stack project management and delay prediction web application engineered to model complex task dependencies, detect critical paths, assess deadline risks, and simulate hypothetical delays before they impact delivery timelines.

---

## 1. System Architecture & Tech Stack

- **Frontend:** HTML5, CSS3 (Modern Dark Navy SaaS Theme with responsive cards & glow accents), Vanilla JavaScript SPA (Modular state architecture).
- **Visualization:** [vis-network](https://visjs.github.io/vis-network/docs/network/) (Interactive physics & hierarchical DAG graph) and [Chart.js](https://www.chartjs.org/) (Real-time progress, status distribution, and workload balancing).
- **Backend:** Python 3 with Flask RESTful API.
- **Algorithms:**
  - **Directed Graph (DAG):** Adjacency list representation with incoming and outgoing dependency edges.
  - **Breadth-First Search (BFS):** Level-by-level downstream reachability (distinguishes Level 1 Direct vs Level 2+ Indirect affected tasks).
  - **Depth-First Search (DFS):** Complete downstream path traversal, upstream predecessor exploration, and 3-color circular dependency cycle detection.
  - **Critical Path Method (CPM):** Forward pass (ES, EF), Backward pass (LS, LF), Total Float ($TF = LS - ES$), Free Float, and Critical Path duration.
  - **Delay Propagation Engine:** Topologically sorted delay propagation for hypothetical "What-If" scenarios without mutating persistent baseline records.
  - **Deadline Risk Analyzer:** Quantitative risk scoring (LOW, MEDIUM, HIGH, CRITICAL) based on schedule slack, overdue tasks, and critical path sensitivity.
  - **Automated Recovery Engine:** Actionable schedule compression (Crashing, Fast-Tracking, Resource Rebalancing, and Float Optimization).
- **Database:** SQLite 3 with foreign key cascades, automatic transactions, and audit activity logging.
- **Reporting:** Downloadable 8-section audit PDF reports dynamically generated via Python `reportlab`.

---

## 2. Main Modules

1. **Executive Dashboard:** Live metrics calculated directly from database records (Total Projects, Total Tasks, Completed, Pending, Delayed, Tasks at Risk, Overall Completion %, and Upcoming Deadlines with slack badges).
2. **Project Management:** Complete project lifecycle operations (Create, Edit, Delete, Switch Active Project, and Load Sample Project).
3. **Task Management (CRUD):** Task creation with duration, dates, priority, assignee, and multi-predecessor dependencies. Enforces circular dependency prevention.
4. **Dependency Analysis:** Interactive Directed Acyclic Graph (DAG) with node color coding by status, glowing critical path edges, BFS level-by-level downstream breakdown, and DFS complete chain viewer.
5. **What-If Delay Simulator:** Select a task, enter hypothetical delay in days, and observe the downstream ripple effect, revised completion dates, project deadline slip, and side-by-side Gantt-like schedule comparison without changing original database records.
6. **Critical Path Analysis:** Detailed CPM calculations displaying Earliest Start (ES), Earliest Finish (EF), Latest Start (LS), Latest Finish (LF), Total Float, and highlights zero-float critical tasks.
7. **Deadline Risk Analysis:** Explains *why* tasks are risky (overdue, zero float, razor-thin buffer) and provides project-level health scoring.
8. **Recovery Suggestions:** Mathematically justified strategies (Crashing, Fast-Tracking, Member Rebalancing, Float Optimization) to recover slipped working days.
9. **Team Workload Analysis:** Visualizes team allocation, total working days, pending tasks, and detects developer burnout/bottlenecks.
10. **History & Reports:** Persistent simulation audit log and instant 8-section downloadable PDF report.

---

## 3. Quick Start & Execution

### Prerequisites
- Python 3.9+ installed.

### Installation & Run

1. Open a terminal in the project directory:
   ```bash
   cd "Dependency Rescue"
   ```

2. Install dependencies (if not already installed in your Python environment):
   ```bash
   python -m pip install -r requirements.txt
   ```

3. Launch the application:
   ```bash
   python app.py
   ```

4. Open your web browser and navigate to:
   ```
   http://127.0.0.1:5000
   ```

---

## 4. Demonstrating the Core Features (College Mini-Project Guide)

### Demo 1: Pre-Populated Sample Project
1. On initial startup, the system automatically initializes `dependency_rescue.db` and loads the **Software Development Project**.
2. Tasks:
   - **Requirement Analysis** (2 days, In Progress, Alex Chen)
   - **UI/UX Design** (3 days, Dep: Requirement Analysis, Sarah Connor)
   - **Development** (5 days, Dep: UI/UX Design, David Miller)
   - **Testing** (3 days, Dep: Development, Priya Sharma)
   - **Deployment** (1 day, Dep: Testing, Marcus Vance)
3. Total critical path duration = $2 + 3 + 5 + 3 + 1 = 14$ days.

### Demo 2: Circular Dependency Prevention
1. Navigate to **Task Management** or **Dependency Analysis**.
2. Click **+ Add Dependency Edge**.
3. Select **Predecessor: Deployment (#5)** and **Successor: Requirement Analysis (#1)**.
4. Click **Create Dependency**.
5. The system runs cycle detection DFS, blocks the creation, and returns:
   `Circular dependency detected! Path: 1 -> 2 -> 3 -> 4 -> 5 -> 1. A task cannot depend on its own downstream successor.`

### Demo 3: What-If Delay Simulation (The Core Scenario)
1. Navigate to **What-If Simulator** from the sidebar.
2. Select **Task: UI/UX Design (#2)**.
3. Set **Hypothetical Delay: 3 Days**.
4. Click **Simulate Delay**.
5. Observe:
   - **Total Project Delay:** +3 working days.
   - **Directly Affected Tasks:** Development (#3).
   - **Indirectly Affected Tasks:** Testing (#4), Deployment (#5).
   - **Deadline Status:** Breaches project deadline target by 1 day.
   - **Gantt Comparison:** Side-by-side visualization shows the revised schedules while the original database records remain intact!
   - Click **Reset Simulation** to return to baseline.

### Demo 4: Downloading the Executive PDF Report
1. Click **Download PDF** from the top bar or navigate to **History & Reports**.
2. Click **Download Executive PDF Report**.
3. Inspect the professional PDF document featuring:
   - Section 1: Project Overview
   - Section 2: Task Details & Statuses
   - Section 3: Dependency Analysis (Directed Graph Representation)
   - Section 4: Critical Path Analysis (CPM ES, EF, LS, LF, Float)
   - Section 5: Delay Simulation Results
   - Section 6: Baseline vs Simulated Schedule Comparison
   - Section 7: Deadline Risk Analysis
   - Section 8: Actionable Recovery Suggestions

