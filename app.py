from flask import Flask, render_template, request, jsonify, send_file, make_response
import io
import os
from datetime import datetime, timedelta

from config import Config
import database
from algorithms.graph import DirectedGraph
from algorithms.cpm import CriticalPathAnalysis
from algorithms.simulator import DelaySimulator
from algorithms.risk import RiskAnalyzer
from algorithms.recovery import RecoveryEngine
from algorithms.reports import ReportGenerator
from algorithms.ai_risk_engine import AIRiskEngine
from algorithms.progress_tracker import ProgressTracker

app = Flask(__name__)
app.config.from_object(Config)

# Ensure database is initialized on startup
database.init_db()

# --- MAIN ROUTE ---
@app.route('/')
def index():
    """Serves the single-page application dashboard."""
    return render_template('index.html')


# --- PROJECTS API ---
@app.route('/api/projects', methods=['GET'])
def get_projects():
    conn = database.get_db_connection()
    projects = conn.execute('''
        SELECT p.*,
               COUNT(t.id) as total_tasks,
               SUM(CASE WHEN t.status = 'Completed' THEN 1 ELSE 0 END) as completed_tasks,
               SUM(CASE WHEN t.status = 'Delayed' THEN 1 ELSE 0 END) as delayed_tasks,
               SUM(CASE WHEN t.status = 'At Risk' THEN 1 ELSE 0 END) as at_risk_tasks
        FROM projects p
        LEFT JOIN tasks t ON p.id = t.project_id
        GROUP BY p.id
        ORDER BY p.id DESC
    ''').fetchall()
    
    result = []
    for p in projects:
        d = dict(p)
        metrics = ProgressTracker.calculate_project_metrics(d['id'], conn)
        if metrics:
            d['completion_percentage'] = int(round(metrics['overall_progress_pct']))
            d['overall_progress_pct'] = metrics['overall_progress_pct']
            d['expected_progress_pct'] = metrics['expected_progress_pct']
            d['stagnant_tasks_count'] = metrics['stagnant_tasks_count']
        else:
            tot = d['total_tasks'] or 0
            comp = d['completed_tasks'] or 0
            d['completion_percentage'] = int((comp / tot * 100)) if tot > 0 else 0
            d['overall_progress_pct'] = d['completion_percentage']
            d['expected_progress_pct'] = 0
            d['stagnant_tasks_count'] = 0
        result.append(d)
    
    conn.close()
    return jsonify({"success": True, "projects": result})


@app.route('/api/projects/<int:project_id>', methods=['GET'])
def get_project(project_id):
    conn = database.get_db_connection()
    p = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not p:
        conn.close()
        return jsonify({"success": False, "error": "Project not found"}), 404

    d = dict(p)
    # Get statistics and automated progress tracking metrics
    metrics = ProgressTracker.calculate_project_metrics(project_id, conn)
    d['stats'] = metrics or {}
    d['stats']['completion_percentage'] = int(round(metrics['overall_progress_pct'])) if metrics else 0
    d['progress_metrics'] = metrics or {}

    conn.close()
    return jsonify({"success": True, "project": d})


@app.route('/api/projects', methods=['POST'])
def create_project():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({"success": False, "error": "Project name is required."}), 400

    start_date = data.get('start_date') or datetime.now().strftime("%Y-%m-%d")
    deadline = data.get('deadline') or (datetime.now().date()).strftime("%Y-%m-%d")
    description = data.get('description', '').strip()
    status = data.get('status', 'Active')

    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO projects (name, description, start_date, deadline, status)
        VALUES (?, ?, ?, ?, ?)
    ''', (name, description, start_date, deadline, status))
    new_id = cursor.lastrowid
    database.log_activity(new_id, "Project Created", f"Created project '{name}'", conn)
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Project created successfully", "project_id": new_id}), 201


@app.route('/api/projects/<int:project_id>', methods=['PUT'])
def update_project(project_id):
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({"success": False, "error": "Project name cannot be empty."}), 400

    conn = database.get_db_connection()
    p = conn.execute('SELECT id FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not p:
        conn.close()
        return jsonify({"success": False, "error": "Project not found"}), 404

    conn.execute('''
        UPDATE projects
        SET name = ?, description = ?, start_date = ?, deadline = ?, status = ?
        WHERE id = ?
    ''', (
        name,
        data.get('description', '').strip(),
        data.get('start_date'),
        data.get('deadline'),
        data.get('status', 'Active'),
        project_id
    ))
    database.log_activity(project_id, "Project Updated", f"Updated details for '{name}'", conn)
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Project updated successfully"})


@app.route('/api/projects/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    conn = database.get_db_connection()
    p = conn.execute('SELECT name FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not p:
        conn.close()
        return jsonify({"success": False, "error": "Project not found"}), 404

    p_name = p['name']
    conn.execute('DELETE FROM projects WHERE id = ?', (project_id,))
    database.log_activity(None, "Project Deleted", f"Deleted project '{p_name}'", conn)
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"Project '{p_name}' deleted successfully"})


@app.route('/api/projects/sample', methods=['POST'])
def load_sample_project():
    """Loads a fresh copy of the Software Development Project."""
    conn = database.get_db_connection()
    new_pid = database.seed_sample_project(conn)
    conn.close()
    return jsonify({
        "success": True,
        "message": "Sample 'Software Development Project' loaded successfully with baseline tasks and dependencies.",
        "project_id": new_pid
    })


@app.route('/api/projects/sample-complex', methods=['POST'])
def load_sample_complex_project():
    """Loads a complex parallel branching DAG demonstration project with slack and multiple predecessors."""
    conn = database.get_db_connection()
    new_pid = database.seed_complex_project(conn)
    conn.close()
    return jsonify({
        "success": True,
        "message": "Complex DAG 'Enterprise Cloud Portal' loaded with concurrent parallel branches, slack float, and multi-predecessors.",
        "project_id": new_pid
    })


# --- AUTHENTICATION & RBAC API ---
@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip().lower()
    password = (data.get('password') or '').strip()

    if not username or not password:
        return jsonify({"success": False, "error": "Username and password are required."}), 400

    conn = database.get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE LOWER(username) = ?', (username,)).fetchone()
    if not user or user['password'] != password:
        conn.close()
        return jsonify({"success": False, "error": "Invalid username or password."}), 401

    uid = user['id']
    roles_rows = conn.execute('SELECT project_id, role_title, is_lead FROM user_project_roles WHERE user_id = ?', (uid,)).fetchall()
    conn.close()

    roles_map = {}
    for r in roles_rows:
        roles_map[str(r['project_id'])] = {
            "role_title": r['role_title'],
            "is_lead": bool(r['is_lead'])
        }

    return jsonify({
        "success": True,
        "message": f"Welcome back, {user['full_name']}!",
        "user": {
            "id": user['id'],
            "username": user['username'],
            "full_name": user['full_name'],
            "email": user['email'],
            "avatar_color": user['avatar_color'],
            "roles": roles_map
        }
    })


@app.route('/api/auth/register', methods=['POST'])
def auth_register():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip().lower()
    password = (data.get('password') or '').strip()
    full_name = (data.get('full_name') or '').strip()
    email = (data.get('email') or '').strip() or f"{username}@rescue.dev"
    roles = data.get('roles') or {}

    if not username or not password or not full_name:
        return jsonify({"success": False, "error": "Username, password, and full name are required."}), 400

    conn = database.get_db_connection()
    existing = conn.execute('SELECT id FROM users WHERE LOWER(username) = ?', (username,)).fetchone()
    if existing:
        conn.close()
        return jsonify({"success": False, "error": f"Username '{username}' is already taken."}), 409

    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (username, password, full_name, email)
        VALUES (?, ?, ?, ?)
    ''', (username, password, full_name, email))
    new_uid = cursor.lastrowid

    # Add to team_members
    cursor.execute('''
        INSERT INTO team_members (name, role, role_type, email)
        VALUES (?, ?, ?, ?)
    ''', (full_name, "Registered Contributor", "Team Member", email))

    projects = conn.execute('SELECT id FROM projects').fetchall()
    roles_map = {}
    for p in projects:
        pid = str(p['id'])
        r_info = roles.get(pid) or {}
        r_title = r_info.get('role_title') or 'Developer'
        is_lead = 1 if r_info.get('is_lead') else 0
        cursor.execute('''
            INSERT OR REPLACE INTO user_project_roles (user_id, project_id, role_title, is_lead)
            VALUES (?, ?, ?, ?)
        ''', (new_uid, p['id'], r_title, is_lead))
        roles_map[pid] = {"role_title": r_title, "is_lead": bool(is_lead)}

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Account '{username}' created successfully!",
        "user": {
            "id": new_uid,
            "username": username,
            "full_name": full_name,
            "email": email,
            "avatar_color": "#6366F1",
            "roles": roles_map
        }
    }), 201


@app.route('/api/auth/users', methods=['GET'])
def get_auth_users():
    conn = database.get_db_connection()
    users = conn.execute('SELECT id, username, full_name, email, avatar_color FROM users ORDER BY id ASC').fetchall()
    roles = conn.execute('SELECT user_id, project_id, role_title, is_lead FROM user_project_roles').fetchall()
    conn.close()

    roles_by_user = {}
    for r in roles:
        roles_by_user.setdefault(r['user_id'], {})[str(r['project_id'])] = {
            "role_title": r['role_title'],
            "is_lead": bool(r['is_lead'])
        }

    result = []
    for u in users:
        d = dict(u)
        d['roles'] = roles_by_user.get(u['id'], {})
        result.append(d)

    return jsonify({"success": True, "users": result})


# --- TASKS API ---
@app.route('/api/projects/<int:project_id>/tasks', methods=['GET'])
def get_project_tasks(project_id):
    user_id_param = request.args.get('user_id')
    role_filter = request.args.get('role_filter', 'false').lower() == 'true'

    conn = database.get_db_connection()

    is_lead = True
    active_role_title = "Project Lead"
    if user_id_param:
        try:
            uid = int(user_id_param)
            role_row = conn.execute(
                'SELECT role_title, is_lead FROM user_project_roles WHERE user_id = ? AND project_id = ?',
                (uid, project_id)
            ).fetchone()
            if role_row is not None:
                is_lead = bool(role_row['is_lead'])
                active_role_title = role_row['role_title']
        except Exception:
            pass

    tasks_rows = conn.execute('''
        SELECT t.*, tm.name as assignee_name, tm.role as assignee_role, tm.avatar_color
        FROM tasks t
        LEFT JOIN team_members tm ON t.assigned_to = tm.id
        WHERE t.project_id = ?
        ORDER BY t.id ASC
    ''', (project_id,)).fetchall()

    # Pre-fetch all dependencies for this project
    dep_rows = conn.execute('''
        SELECT predecessor_id, successor_id FROM dependencies WHERE project_id = ?
    ''', (project_id,)).fetchall()

    preds_map = {}
    succs_map = {}
    for d in dep_rows:
        preds_map.setdefault(d['successor_id'], []).append(d['predecessor_id'])
        succs_map.setdefault(d['predecessor_id'], []).append(d['successor_id'])

    tasks = []
    for r in tasks_rows:
        t = dict(r)
        t['predecessor_ids'] = preds_map.get(t['id'], [])
        t['successor_ids'] = succs_map.get(t['id'], [])

        # If role_filter is active and user is NOT a lead, filter to own tasks
        if role_filter and not is_lead and user_id_param:
            if t.get('assigned_to') != int(user_id_param):
                continue

        tasks.append(t)

    conn.close()
    return jsonify({
        "success": True,
        "tasks": tasks,
        "is_lead_view": is_lead,
        "role_title": active_role_title,
        "total_project_tasks": len(tasks_rows)
    })


@app.route('/api/projects/<int:project_id>/tasks', methods=['POST'])
def create_task(project_id):
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({"success": False, "error": "Task name is required."}), 400

    try:
        duration = max(1, int(data.get('duration', 1)))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Duration must be a positive integer."}), 400

    start_date = data.get('start_date') or datetime.now().strftime("%Y-%m-%d")
    deadline = data.get('deadline') or (datetime.now().date()).strftime("%Y-%m-%d")
    description = data.get('description', '').strip()
    status = data.get('status', 'Not Started')
    priority = data.get('priority', 'Medium')
    assigned_to = data.get('assigned_to') or None
    predecessor_ids = data.get('predecessor_ids', [])

    conn = database.get_db_connection()

    # Validate project exists
    p = conn.execute('SELECT id FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not p:
        conn.close()
        return jsonify({"success": False, "error": "Project not found."}), 404

    # Insert task
    progress_pct = max(0, min(100, int(data.get('progress_pct', 0))))
    complexity = data.get('complexity', 'Medium')
    time_spent_hours = max(0.0, float(data.get('time_spent_hours', 0.0)))
    actual_start_date = data.get('actual_start_date') or (start_date if progress_pct > 0 else None)
    actual_completion_date = data.get('actual_completion_date') or (datetime.now().strftime("%Y-%m-%d") if progress_pct == 100 else None)

    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tasks (
            project_id, name, description, duration, start_date, deadline,
            status, priority, assigned_to, progress_pct, actual_start_date, actual_completion_date, time_spent_hours, complexity
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        project_id, name, description, duration, start_date, deadline,
        status, priority, assigned_to, progress_pct, actual_start_date, actual_completion_date, time_spent_hours, complexity
    ))
    new_task_id = cursor.lastrowid

    # Log initial task activity
    database.log_task_activity(
        new_task_id, project_id, assigned_to, "TASK_CREATED",
        None, status, 0, progress_pct, f"Task '{name}' created with duration {duration}d and status '{status}'.", conn
    )

    # Check dependencies and prevent cycles
    if predecessor_ids:
        gr = DirectedGraph.build_from_db(project_id, conn)
        gr.add_node(new_task_id)
        for pred_id in predecessor_ids:
            pred_id = int(pred_id)
            would_cycle, cycle_path = gr.would_create_cycle(pred_id, new_task_id)
            if would_cycle:
                conn.rollback()
                conn.close()
                return jsonify({
                    "success": False,
                    "error": f"Circular dependency detected! Adding dependency would create cycle: {' -> '.join(map(str, cycle_path))}"
                }), 400
            cursor.execute('''
                INSERT OR IGNORE INTO dependencies (project_id, predecessor_id, successor_id)
                VALUES (?, ?, ?)
            ''', (project_id, pred_id, new_task_id))
            gr.add_edge(pred_id, new_task_id)

    database.log_activity(project_id, "Task Created", f"Added task '{name}' (#{new_task_id})", conn)
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Task created successfully", "task_id": new_task_id}), 201


@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({"success": False, "error": "Task name cannot be empty."}), 400

    try:
        duration = max(1, int(data.get('duration', 1)))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Duration must be a positive integer."}), 400

    conn = database.get_db_connection()
    t = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if not t:
        conn.close()
        return jsonify({"success": False, "error": "Task not found."}), 404

    project_id = t['project_id']
    new_preds = [int(p) for p in data.get('predecessor_ids', []) if int(p) != task_id]

    # Check circular dependency if dependencies are changing
    cursor = conn.cursor()
    # Temporarily build graph without current task's incoming dependencies to test new incoming edges
    gr = DirectedGraph()
    all_tasks = cursor.execute('SELECT id, name, duration, start_date, deadline, status, priority FROM tasks WHERE project_id = ?', (project_id,)).fetchall()
    for task_row in all_tasks:
        gr.add_node(task_row['id'], dict(task_row))
    all_deps = cursor.execute('SELECT predecessor_id, successor_id FROM dependencies WHERE project_id = ? AND successor_id != ?', (project_id, task_id)).fetchall()
    for dep in all_deps:
        gr.add_edge(dep['predecessor_id'], dep['successor_id'])

    for p_id in new_preds:
        would_cycle, cycle_path = gr.would_create_cycle(p_id, task_id)
        if would_cycle:
            conn.close()
            return jsonify({
                "success": False,
                "error": f"Circular dependency detected! Dependency chain creates cycle: {' -> '.join(map(str, cycle_path))}"
            }), 400
        gr.add_edge(p_id, task_id)

    # Apply updates
    progress_pct = max(0, min(100, int(data.get('progress_pct', t['progress_pct'] or 0))))
    complexity = data.get('complexity', t['complexity'] or 'Medium')
    time_spent_hours = max(0.0, float(data.get('time_spent_hours', t['time_spent_hours'] or 0.0)))
    status = data.get('status', t['status'])
    actual_start_date = t['actual_start_date']
    actual_completion_date = t['actual_completion_date']

    now_date_str = datetime.now().strftime("%Y-%m-%d")
    if progress_pct == 100:
        status = 'Completed'
        if not actual_completion_date:
            actual_completion_date = now_date_str
        if not actual_start_date:
            actual_start_date = now_date_str
    elif progress_pct > 0 and status == 'Not Started':
        status = 'In Progress'
        if not actual_start_date:
            actual_start_date = now_date_str
    elif progress_pct < 100 and status == 'Completed':
        status = 'In Progress'
        actual_completion_date = None

    cursor.execute('''
        UPDATE tasks
        SET name = ?, description = ?, duration = ?, start_date = ?, deadline = ?,
            status = ?, priority = ?, assigned_to = ?, progress_pct = ?,
            actual_start_date = ?, actual_completion_date = ?, time_spent_hours = ?, complexity = ?
        WHERE id = ?
    ''', (
        name,
        data.get('description', '').strip(),
        duration,
        data.get('start_date'),
        data.get('deadline'),
        status,
        data.get('priority', 'Medium'),
        data.get('assigned_to') or None,
        progress_pct,
        actual_start_date,
        actual_completion_date,
        time_spent_hours,
        complexity,
        task_id
    ))

    # Log in task activity history if status or progress changed
    if t['status'] != status or (t['progress_pct'] or 0) != progress_pct:
        database.log_task_activity(
            task_id, project_id, data.get('assigned_to') or t['assigned_to'],
            "STATUS_AND_PROGRESS_CHANGE" if t['status'] != status and (t['progress_pct'] or 0) != progress_pct else ("STATUS_CHANGE" if t['status'] != status else "PROGRESS_UPDATE"),
            t['status'], status, t['progress_pct'] or 0, progress_pct,
            f"Updated task: status '{t['status']}' -> '{status}', progress {t['progress_pct'] or 0}% -> {progress_pct}%.",
            conn
        )

    # Re-sync dependencies
    cursor.execute('DELETE FROM dependencies WHERE project_id = ? AND successor_id = ?', (project_id, task_id))
    for p_id in new_preds:
        cursor.execute('''
            INSERT OR IGNORE INTO dependencies (project_id, predecessor_id, successor_id)
            VALUES (?, ?, ?)
        ''', (project_id, p_id, task_id))

    database.log_activity(project_id, "Task Updated", f"Updated task '{name}' (#{task_id})", conn)
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Task updated successfully."})


@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    conn = database.get_db_connection()
    t = conn.execute('SELECT project_id, name FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if not t:
        conn.close()
        return jsonify({"success": False, "error": "Task not found."}), 404

    project_id = t['project_id']
    name = t['name']
    conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    database.log_activity(project_id, "Task Deleted", f"Deleted task '{name}' (#{task_id})", conn)
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"Task '{name}' deleted successfully."})


# --- AUTOMATIC PROGRESS TRACKING API ---
@app.route('/api/tasks/<int:task_id>/progress', methods=['PUT'])
def update_task_progress_route(task_id):
    """
    Allows a team member or manager to record verified progress and time spent,
    triggering automatic status lifecycle transitions and logging an audit history entry.
    """
    data = request.get_json() or {}
    progress_pct = data.get('progress_pct')
    status = data.get('status')
    member_id = data.get('member_id')
    hours_spent = data.get('hours_spent', 0.0)
    comments = data.get('comments', '')

    if progress_pct is None:
        return jsonify({"success": False, "error": "progress_pct is required"}), 400

    conn = database.get_db_connection()
    result = ProgressTracker.update_task_progress(
        task_id=task_id,
        new_progress=int(progress_pct),
        new_status=status,
        member_id=member_id,
        hours_spent=float(hours_spent or 0.0),
        comments=comments,
        conn=conn
    )
    conn.close()

    if not result.get("success"):
        return jsonify(result), 400

    return jsonify(result)


@app.route('/api/tasks/<int:task_id>/history', methods=['GET'])
def get_task_activity_history(task_id):
    conn = database.get_db_connection()
    logs = conn.execute('''
        SELECT h.*, tm.name as member_name, tm.avatar_color
        FROM task_activity_history h
        LEFT JOIN team_members tm ON h.team_member_id = tm.id
        WHERE h.task_id = ?
        ORDER BY h.id DESC
    ''', (task_id,)).fetchall()
    conn.close()
    return jsonify({"success": True, "history": [dict(l) for l in logs]})


@app.route('/api/projects/<int:project_id>/activity-history', methods=['GET'])
def get_project_task_activity_history(project_id):
    conn = database.get_db_connection()
    logs = conn.execute('''
        SELECT h.*, t.name as task_name, tm.name as member_name, tm.avatar_color
        FROM task_activity_history h
        JOIN tasks t ON h.task_id = t.id
        LEFT JOIN team_members tm ON h.team_member_id = tm.id
        WHERE h.project_id = ?
        ORDER BY h.id DESC LIMIT 50
    ''', (project_id,)).fetchall()
    conn.close()
    return jsonify({"success": True, "history": [dict(l) for l in logs]})


@app.route('/api/projects/<int:project_id>/progress-metrics', methods=['GET'])
def get_project_progress_metrics(project_id):
    conn = database.get_db_connection()
    metrics = ProgressTracker.calculate_project_metrics(project_id, conn)
    conn.close()
    if not metrics:
        return jsonify({"success": False, "error": "Project not found"}), 404
    return jsonify({"success": True, "metrics": metrics})


# --- DAILY TEAM WORK UPDATES API ---
@app.route('/api/projects/<int:project_id>/daily-updates', methods=['GET'])
def get_daily_updates(project_id):
    date_filter = request.args.get('date')
    member_filter = request.args.get('member_id')
    task_filter = request.args.get('task_id')
    user_id_param = request.args.get('user_id')
    role_filter = request.args.get('role_filter', 'false').lower() == 'true'

    conn = database.get_db_connection()

    is_lead = True
    active_role_title = "Project Lead"
    if user_id_param:
        try:
            uid = int(user_id_param)
            role_row = conn.execute(
                'SELECT role_title, is_lead FROM user_project_roles WHERE user_id = ? AND project_id = ?',
                (uid, project_id)
            ).fetchone()
            if role_row is not None:
                is_lead = bool(role_row['is_lead'])
                active_role_title = role_row['role_title']
        except Exception:
            pass

    query = '''
        SELECT u.*, tm.name as member_name, tm.role as member_role, tm.avatar_color,
               t.name as task_name, t.duration as task_duration, t.status as task_status
        FROM daily_work_updates u
        JOIN team_members tm ON u.team_member_id = tm.id
        JOIN tasks t ON u.task_id = t.id
        WHERE u.project_id = ?
    '''
    params = [project_id]

    if date_filter:
        query += " AND u.submission_date = ?"
        params.append(date_filter)

    # Privacy constraint: non-lead team member can only see their own updates
    if role_filter and not is_lead and user_id_param:
        query += " AND u.team_member_id = ?"
        params.append(int(user_id_param))
    elif member_filter:
        query += " AND u.team_member_id = ?"
        params.append(member_filter)

    if task_filter:
        query += " AND u.task_id = ?"
        params.append(task_filter)

    query += " ORDER BY u.submission_date DESC, u.id DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    return jsonify({
        "success": True,
        "updates": [dict(r) for r in rows],
        "is_lead_view": is_lead,
        "role_title": active_role_title
    })


@app.route('/api/projects/<int:project_id>/daily-updates', methods=['POST'])
def submit_daily_update(project_id):
    data = request.get_json() or {}
    member_id = data.get('team_member_id')
    task_id = data.get('task_id')
    work_desc = data.get('work_description', '').strip()
    progress_pct = data.get('progress_pct', 0)
    remaining_work = data.get('remaining_work', '').strip()
    problems_faced = data.get('problems_faced', '').strip()
    est_remaining_days = data.get('estimated_remaining_days', 1)
    submission_date = data.get('submission_date') or datetime.now().strftime("%Y-%m-%d")

    if not member_id or not task_id or not work_desc:
        return jsonify({"success": False, "error": "Team member, task, and today's work description are required."}), 400

    try:
        progress_pct = max(0, min(100, int(progress_pct)))
        est_remaining_days = max(0, int(est_remaining_days))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Progress and remaining days must be valid numbers."}), 400

    conn = database.get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO daily_work_updates (
            project_id, task_id, team_member_id, work_description, progress_pct,
            remaining_work, problems_faced, estimated_remaining_days, submission_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        project_id, task_id, member_id, work_desc, progress_pct,
        remaining_work, problems_faced, est_remaining_days, submission_date
    ))
    new_update_id = cursor.lastrowid

    # Automatically update task's verified progress
    ProgressTracker.update_task_progress(
        task_id=task_id,
        new_progress=progress_pct,
        new_status='Completed' if progress_pct == 100 else 'In Progress',
        member_id=member_id,
        hours_spent=6.0, # Standard daily work allocation
        comments=f"Daily Report: {work_desc[:120]}",
        conn=conn
    )

    database.log_activity(project_id, "Daily Update Submitted", f"Update submitted for Task #{task_id} by Member #{member_id} ({progress_pct}% complete)", conn)
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Daily work update recorded and task progress synchronized.", "update_id": new_update_id}), 201


@app.route('/api/daily-updates/<int:update_id>', methods=['PUT'])
def edit_daily_update(update_id):
    data = request.get_json() or {}
    work_desc = data.get('work_description', '').strip()
    progress_pct = data.get('progress_pct')
    remaining_work = data.get('remaining_work', '').strip()
    problems_faced = data.get('problems_faced', '').strip()
    est_remaining_days = data.get('estimated_remaining_days')

    if not work_desc:
        return jsonify({"success": False, "error": "Work description cannot be empty."}), 400

    conn = database.get_db_connection()
    current = conn.execute('SELECT * FROM daily_work_updates WHERE id = ?', (update_id,)).fetchone()
    if not current:
        conn.close()
        return jsonify({"success": False, "error": "Daily update not found"}), 404

    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE daily_work_updates
        SET work_description = ?, progress_pct = COALESCE(?, progress_pct),
            remaining_work = ?, problems_faced = ?,
            estimated_remaining_days = COALESCE(?, estimated_remaining_days),
            updated_at = ?
        WHERE id = ?
    ''', (work_desc, progress_pct, remaining_work, problems_faced, est_remaining_days, now_ts, update_id))

    if progress_pct is not None:
        ProgressTracker.update_task_progress(
            task_id=current['task_id'],
            new_progress=int(progress_pct),
            new_status='Completed' if int(progress_pct) == 100 else 'In Progress',
            member_id=current['team_member_id'],
            hours_spent=0.0,
            comments=f"Edited daily report #{update_id}: progress adjusted to {progress_pct}%.",
            conn=conn
        )

    database.log_activity(current['project_id'], "Daily Update Edited", f"Edited report #{update_id} for Task #{current['task_id']}", conn)
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Daily update modified with audit trail."})


@app.route('/api/daily-updates/<int:update_id>', methods=['DELETE'])
def delete_daily_update(update_id):
    conn = database.get_db_connection()
    current = conn.execute('SELECT project_id, task_id FROM daily_work_updates WHERE id = ?', (update_id,)).fetchone()
    if not current:
        conn.close()
        return jsonify({"success": False, "error": "Daily update not found"}), 404

    conn.execute('DELETE FROM daily_work_updates WHERE id = ?', (update_id,))
    database.log_activity(current['project_id'], "Daily Update Removed", f"Removed daily update #{update_id}", conn)
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Daily report removed."})


@app.route('/api/projects/<int:project_id>/daily-updates/summary', methods=['GET'])
def get_daily_updates_summary(project_id):
    conn = database.get_db_connection()
    today_str = datetime.now().strftime("%Y-%m-%d")

    # 1. Today's submissions
    today_count = conn.execute('''
        SELECT COUNT(id) as count FROM daily_work_updates
        WHERE project_id = ? AND submission_date = ?
    ''', (project_id, today_str)).fetchone()['count']

    # 2. Members with pending updates (have active task but haven't submitted today)
    active_assigned_members = conn.execute('''
        SELECT DISTINCT tm.id, tm.name, tm.role, tm.avatar_color
        FROM tasks t
        JOIN team_members tm ON t.assigned_to = tm.id
        WHERE t.project_id = ? AND t.status IN ('In Progress', 'Not Started', 'At Risk', 'Delayed')
    ''', (project_id,)).fetchall()

    submitted_member_ids = set([r['team_member_id'] for r in conn.execute('''
        SELECT DISTINCT team_member_id FROM daily_work_updates
        WHERE project_id = ? AND submission_date = ?
    ''', (project_id, today_str)).fetchall()])

    pending_members = [dict(m) for m in active_assigned_members if m['id'] not in submitted_member_ids]

    # 3. Stagnant tasks (active tasks with no report in >= 3 days)
    progress_metrics = ProgressTracker.calculate_project_metrics(project_id, conn)
    stagnant_tasks = progress_metrics.get("stagnant_tasks", []) if progress_metrics else []

    # 4. Weekly submissions trend (last 7 days)
    weekly_trend = []
    for i in range(6, -1, -1):
        d_str = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        c = conn.execute('''
            SELECT COUNT(id) as count FROM daily_work_updates
            WHERE project_id = ? AND submission_date = ?
        ''', (project_id, d_str)).fetchone()['count']
        weekly_trend.append({"date": d_str, "count": c})

    conn.close()
    total_assigned_count = len(active_assigned_members)
    submitted_count = len([m for m in active_assigned_members if m['id'] in submitted_member_ids])
    compliance_rate = round((submitted_count / total_assigned_count * 100), 1) if total_assigned_count > 0 else 100.0

    return jsonify({
        "success": True,
        "today_submissions_count": today_count,
        "compliance_rate_pct": compliance_rate,
        "pending_members_count": len(pending_members),
        "pending_members": pending_members,
        "stagnant_tasks_count": len(stagnant_tasks),
        "stagnant_tasks": stagnant_tasks,
        "weekly_trend": weekly_trend
    })


# --- AI-BASED RISK PREDICTION & MACHINE LEARNING API ---
@app.route('/api/projects/<int:project_id>/ai-risk-prediction', methods=['GET'])
def get_ai_risk_prediction(project_id):
    conn = database.get_db_connection()
    result = AIRiskEngine.predict_project_risk(project_id, conn)
    conn.close()
    if not result.get("success"):
        return jsonify({"success": False, "error": result.get("error", "Error predicting risk")}), 400
    return jsonify(result)


@app.route('/api/ai/train-model', methods=['POST'])
def train_ai_model():
    """
    Trains/retrains the Scikit-Learn Random Forest Classifier on historical project
    records and industry benchmarks, logging accuracy metrics and feature importances.
    """
    conn = database.get_db_connection()
    metadata = AIRiskEngine.train_ml_model(conn)
    database.log_activity(None, "AI Model Trained", f"Retrained Scikit-Learn Random Forest model with {metadata['accuracy']}% test accuracy.", conn)
    conn.close()
    return jsonify({"success": True, "message": "Scikit-Learn Random Forest model trained and evaluated successfully.", "metadata": metadata})


@app.route('/api/ai/model-status', methods=['GET'])
def get_ai_model_status():
    conn = database.get_db_connection()
    status = AIRiskEngine.get_model_status(conn)
    conn.close()
    return jsonify({"success": True, "status": status})


# --- TEAM PERFORMANCE & ROLES API ---
@app.route('/api/projects/<int:project_id>/team-performance', methods=['GET'])
def get_team_performance(project_id):
    conn = database.get_db_connection()
    members = conn.execute('SELECT * FROM team_members ORDER BY id ASC').fetchall()
    
    performance = []
    for m in members:
        mid = m['id']
        tasks = conn.execute('''
            SELECT id, duration, progress_pct, status, time_spent_hours
            FROM tasks WHERE project_id = ? AND assigned_to = ?
        ''', (project_id, mid)).fetchall()

        updates = conn.execute('''
            SELECT COUNT(id) as count, MAX(submission_date) as last_update
            FROM daily_work_updates WHERE project_id = ? AND team_member_id = ?
        ''', (project_id, mid)).fetchone()

        tot_tasks = len(tasks)
        comp_tasks = sum(1 for t in tasks if t['status'] == 'Completed')
        delayed_tasks = sum(1 for t in tasks if t['status'] == 'Delayed')
        pending_tasks = tot_tasks - comp_tasks
        total_hours = sum(t['time_spent_hours'] or 0.0 for t in tasks)
        avg_progress = round(sum(t['progress_pct'] or 0 for t in tasks) / max(1, tot_tasks), 1)

        # Productivity scoring formula: progress velocity vs delayed penalty
        base_score = avg_progress
        if delayed_tasks > 0:
            base_score = max(10, base_score - (delayed_tasks * 15))
        if updates['count'] >= 2:
            base_score = min(100, base_score + 10)

        is_overloaded = pending_tasks >= 3 or sum(t['duration'] for t in tasks if t['status'] != 'Completed') >= 10

        performance.append({
            "member_id": mid,
            "name": m['name'],
            "role": m['role'],
            "role_type": m['role_type'] or 'Team Member',
            "avatar_color": m['avatar_color'],
            "total_assigned_tasks": tot_tasks,
            "completed_tasks": comp_tasks,
            "pending_tasks": pending_tasks,
            "delayed_tasks": delayed_tasks,
            "average_task_progress": avg_progress,
            "total_hours_spent": round(total_hours, 1),
            "daily_reports_submitted": updates['count'] or 0,
            "last_report_date": updates['last_update'] or "None",
            "productivity_score": round(base_score, 1),
            "is_overloaded": is_overloaded
        })

    conn.close()
    return jsonify({"success": True, "team_performance": performance})


@app.route('/api/team/<int:member_id>', methods=['PUT'])
def update_team_member(member_id):
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    role = data.get('role', '').strip()
    role_type = data.get('role_type', 'Team Member')
    email = data.get('email', '').strip()
    avatar_color = data.get('avatar_color', '#6366F1')
    status = data.get('status', 'Active')

    if not name or not role:
        return jsonify({"success": False, "error": "Name and role are required."}), 400

    conn = database.get_db_connection()
    conn.execute('''
        UPDATE team_members
        SET name = ?, role = ?, role_type = ?, email = ?, avatar_color = ?, status = ?
        WHERE id = ?
    ''', (name, role, role_type, email, avatar_color, status, member_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Team member details updated."})


@app.route('/api/team/<int:member_id>', methods=['DELETE'])
def delete_team_member(member_id):
    conn = database.get_db_connection()
    conn.execute('DELETE FROM team_members WHERE id = ?', (member_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Team member removed."})


# --- SMART DASHBOARD UNIFIED ENDPOINT ---
@app.route('/api/projects/<int:project_id>/smart-dashboard', methods=['GET'])
def get_smart_dashboard(project_id):
    """
    Returns unified metrics for the Smart Dashboard:
    - 8 summary cards
    - Progress variance
    - AI risk highlights
    - Daily reports activity summary
    """
    conn = database.get_db_connection()
    project = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        conn.close()
        return jsonify({"success": False, "error": "Project not found"}), 404

    # 1. Automated Progress Metrics
    metrics = ProgressTracker.calculate_project_metrics(project_id, conn)

    # 2. AI Risk Predictions
    ai_risk = AIRiskEngine.predict_project_risk(project_id, conn)

    # 3. Team Member count
    team_count = conn.execute('SELECT COUNT(*) as count FROM team_members').fetchone()['count']

    # 4. Total projects count
    total_projects = conn.execute('SELECT COUNT(*) as count FROM projects').fetchone()['count']

    # 5. Daily updates summary
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_reports = conn.execute('''
        SELECT COUNT(id) as count FROM daily_work_updates
        WHERE project_id = ? AND submission_date = ?
    ''', (project_id, today_str)).fetchone()['count']

    conn.close()

    return jsonify({
        "success": True,
        "project": dict(project),
        "summary_cards": {
            "total_projects": total_projects,
            "total_tasks": metrics.get("total_tasks", 0),
            "completed_tasks": metrics.get("completed_tasks", 0),
            "pending_tasks": metrics.get("total_tasks", 0) - metrics.get("completed_tasks", 0),
            "overall_project_progress": metrics.get("overall_progress_pct", 0),
            "expected_project_progress": metrics.get("expected_progress_pct", 0),
            "progress_variance": metrics.get("progress_variance_pct", 0),
            "high_risk_tasks_count": ai_risk.get("high_risk_tasks_count", 0),
            "team_members_count": team_count,
            "predicted_completion_date": ai_risk.get("predicted_project_completion_date", project['deadline']),
            "project_delay_probability": ai_risk.get("project_delay_probability", 10.0),
            "overall_project_risk": ai_risk.get("overall_project_risk", "LOW RISK")
        },
        "ai_insights": {
            "model_type": ai_risk.get("ai_engine_type"),
            "deadline_breached": ai_risk.get("deadline_breached", False),
            "predicted_overdue_days": ai_risk.get("predicted_overdue_days", 0),
            "highest_risk_tasks": ai_risk.get("high_risk_tasks", [])[:4]
        },
        "daily_reports_today": today_reports,
        "stagnant_tasks_count": metrics.get("stagnant_tasks_count", 0)
    })



# --- DEPENDENCIES API ---
@app.route('/api/projects/<int:project_id>/dependencies', methods=['GET'])
def get_dependencies(project_id):
    conn = database.get_db_connection()
    deps = conn.execute('''
        SELECT d.id, d.predecessor_id, d.successor_id,
               tp.name as predecessor_name,
               ts.name as successor_name
        FROM dependencies d
        JOIN tasks tp ON d.predecessor_id = tp.id
        JOIN tasks ts ON d.successor_id = ts.id
        WHERE d.project_id = ?
        ORDER BY d.id ASC
    ''', (project_id,)).fetchall()
    conn.close()
    return jsonify({"success": True, "dependencies": [dict(d) for d in deps]})


@app.route('/api/projects/<int:project_id>/dependencies', methods=['POST'])
def add_dependency(project_id):
    data = request.get_json() or {}
    pred_id = data.get('predecessor_id')
    succ_id = data.get('successor_id')

    if not pred_id or not succ_id:
        return jsonify({"success": False, "error": "Both predecessor_id and successor_id are required."}), 400

    pred_id = int(pred_id)
    succ_id = int(succ_id)

    if pred_id == succ_id:
        return jsonify({"success": False, "error": "A task cannot depend on itself (Self-loop cycle)."}), 400

    conn = database.get_db_connection()
    gr = DirectedGraph.build_from_db(project_id, conn)

    # Check for cycle
    would_cycle, cycle_path = gr.would_create_cycle(pred_id, succ_id)
    if would_cycle:
        conn.close()
        cycle_str = " -> ".join(map(str, cycle_path))
        return jsonify({
            "success": False,
            "error": f"Circular dependency detected! Path: {cycle_str}. A task cannot depend on its own downstream successor."
        }), 400

    try:
        conn.execute('''
            INSERT INTO dependencies (project_id, predecessor_id, successor_id)
            VALUES (?, ?, ?)
        ''', (project_id, pred_id, succ_id))
        database.log_activity(project_id, "Dependency Added", f"Added dependency: Task #{pred_id} ➔ Task #{succ_id}", conn)
        conn.commit()
    except Exception as e:
        conn.close()
        return jsonify({"success": False, "error": "This dependency already exists or is invalid."}), 400

    conn.close()
    return jsonify({"success": True, "message": "Dependency established successfully."})


@app.route('/api/dependencies/<int:dep_id>', methods=['DELETE'])
def delete_dependency(dep_id):
    conn = database.get_db_connection()
    dep = conn.execute('SELECT project_id, predecessor_id, successor_id FROM dependencies WHERE id = ?', (dep_id,)).fetchone()
    if not dep:
        conn.close()
        return jsonify({"success": False, "error": "Dependency record not found."}), 404

    project_id = dep['project_id']
    conn.execute('DELETE FROM dependencies WHERE id = ?', (dep_id,))
    database.log_activity(project_id, "Dependency Removed", f"Removed dependency #{dep['predecessor_id']} ➔ #{dep['successor_id']}", conn)
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Dependency removed successfully."})


# --- GRAPH & ALGORITHMS API ---
@app.route('/api/projects/<int:project_id>/graph', methods=['GET'])
def get_graph_data(project_id):
    """
    Returns graph data formatted for vis-network with status colors,
    critical path identification, node labels, and badges.
    """
    conn = database.get_db_connection()
    project = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        conn.close()
        return jsonify({"success": False, "error": "Project not found"}), 404

    gr = DirectedGraph.build_from_db(project_id, conn)
    cpm = CriticalPathAnalysis(gr, project['start_date']).calculate()
    conn.close()

    critical_tasks = set(cpm.get('critical_task_ids', []))
    critical_edges_set = set(cpm.get('critical_edges', []))

    # Node status color mapping for modern dark navy UI
    status_colors = {
        'Completed': {'bg': '#065F46', 'border': '#10B981', 'highlight': '#34D399'},
        'In Progress': {'bg': '#1E3A8A', 'border': '#3B82F6', 'highlight': '#60A5FA'},
        'Delayed': {'bg': '#7F1D1D', 'border': '#EF4444', 'highlight': '#F87171'},
        'At Risk': {'bg': '#78350F', 'border': '#F59E0B', 'highlight': '#FBBF24'},
        'Not Started': {'bg': '#334155', 'border': '#64748B', 'highlight': '#94A3B8'}
    }

    nodes = []
    for nid, data in gr.nodes.items():
        st = data.get('status', 'Not Started')
        col = status_colors.get(st, status_colors['Not Started'])
        is_crit = nid in critical_tasks
        
        # Format label with duration & status
        label_text = f"{data.get('name', f'Task {nid}')}\n({data.get('duration', 1)}d • {st})"
        tooltip = (
            f"<b>#{nid} {data.get('name')}</b><br/>"
            f"Status: {st}<br/>"
            f"Priority: {data.get('priority', 'Medium')}<br/>"
            f"Duration: {data.get('duration', 1)} day(s)<br/>"
            f"Assignee: {data.get('assignee_name', 'Unassigned')}<br/>"
            f"Critical Path: {'YES (Zero Float)' if is_crit else 'No'}"
        )

        nodes.append({
            "id": nid,
            "label": label_text,
            "title": tooltip,
            "shape": "box",
            "margin": 10,
            "color": {
                "background": col['bg'],
                "border": '#F43F5E' if is_crit else col['border'],
                "highlight": {
                    "background": col['highlight'],
                    "border": '#FB7185'
                }
            },
            "font": {
                "color": "#F8FAFC",
                "face": "Inter, system-ui, sans-serif",
                "size": 13,
                "bold": True
            },
            "borderWidth": 3 if is_crit else 1.5,
            "shadow": {
                "enabled": True,
                "color": 'rgba(244, 63, 94, 0.4)' if is_crit else 'rgba(0,0,0,0.5)',
                "size": 8
            },
            "is_critical": is_crit,
            "task_data": data
        })

    edges = []
    for u in gr.adj:
        for v in gr.adj[u]:
            is_crit_edge = (u, v) in critical_edges_set
            edges.append({
                "from": u,
                "to": v,
                "arrows": "to",
                "color": {
                    "color": "#F43F5E" if is_crit_edge else "#475569",
                    "highlight": "#FB7185" if is_crit_edge else "#818CF8",
                    "hover": "#FB7185" if is_crit_edge else "#818CF8"
                },
                "width": 3 if is_crit_edge else 1.5,
                "dashes": False,
                "smooth": {"type": "cubicBezier", "roundness": 0.3},
                "is_critical": is_crit_edge
            })

    return jsonify({
        "success": True,
        "nodes": nodes,
        "edges": edges,
        "critical_task_ids": list(critical_tasks),
        "has_cycle": cpm.get("has_cycle", False),
        "critical_path_duration": cpm.get("project_duration_days", 0)
    })


@app.route('/api/projects/<int:project_id>/dependency-analysis/<int:task_id>', methods=['GET'])
def analyze_task_dependency(project_id, task_id):
    """
    Runs BFS and DFS algorithms on the selected task to produce level-by-level
    downstream impact analysis and complete dependency traversal chains.
    """
    conn = database.get_db_connection()
    gr = DirectedGraph.build_from_db(project_id, conn)
    conn.close()

    if task_id not in gr.nodes:
        return jsonify({"success": False, "error": f"Task #{task_id} not found."}), 404

    bfs_result = gr.bfs_downstream(task_id)
    dfs_chains = gr.dfs_chains(task_id)

    # Attach human-readable names and assignees to nodes
    def enrich_ids(id_list):
        return [
            {
                "id": tid,
                "name": gr.nodes[tid].get("name", f"Task {tid}"),
                "status": gr.nodes[tid].get("status", "Not Started"),
                "duration": gr.nodes[tid].get("duration", 1),
                "assignee": gr.nodes[tid].get("assignee_name", "Unassigned")
            }
            for tid in id_list if tid in gr.nodes
        ]

    enriched_levels = {
        lvl: enrich_ids(t_ids) for lvl, t_ids in bfs_result["levels"].items()
    }

    chain_descriptions = []
    for chain in dfs_chains:
        chain_descriptions.append([
            {"id": tid, "name": gr.nodes.get(tid, {}).get("name", str(tid))}
            if isinstance(tid, int) else {"id": None, "name": str(tid)}
            for tid in chain
        ])

    return jsonify({
        "success": True,
        "task": {
            "id": task_id,
            "name": gr.nodes[task_id].get("name"),
            "status": gr.nodes[task_id].get("status"),
            "duration": gr.nodes[task_id].get("duration")
        },
        "bfs": {
            "direct_dependents": enrich_ids(bfs_result["direct_dependents"]),
            "indirect_dependents": enrich_ids(bfs_result["indirect_dependents"]),
            "all_downstream": enrich_ids(bfs_result["all_downstream"]),
            "levels": enriched_levels,
            "direct_count": len(bfs_result["direct_dependents"]),
            "indirect_count": len(bfs_result["indirect_dependents"]),
            "total_count": bfs_result["total_affected"]
        },
        "dfs": {
            "chains": chain_descriptions,
            "chain_count": len(dfs_chains)
        }
    })


@app.route('/api/projects/<int:project_id>/critical-path', methods=['GET'])
def get_critical_path(project_id):
    conn = database.get_db_connection()
    project = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        conn.close()
        return jsonify({"success": False, "error": "Project not found"}), 404

    gr = DirectedGraph.build_from_db(project_id, conn)
    conn.close()

    cpm = CriticalPathAnalysis(gr, project['start_date']).calculate()
    return jsonify({"success": True, "cpm": cpm})


# --- WHAT-IF DELAY SIMULATOR API ---
@app.route('/api/projects/<int:project_id>/simulate', methods=['POST'])
def simulate_delay(project_id):
    """
    Hypothetical delay simulation.
    Crucial: DOES NOT modify the baseline database records!
    Logs result to simulation_history table for auditing.
    """
    data = request.get_json() or {}
    task_id = data.get('task_id')
    delay_days = data.get('delay_days')
    save_history = data.get('save_history', True)

    if task_id is None or delay_days is None:
        return jsonify({"success": False, "error": "Both task_id and delay_days are required."}), 400

    try:
        task_id = int(task_id)
        delay_days = max(1, int(delay_days))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid task_id or delay_days value."}), 400

    conn = database.get_db_connection()
    project = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        conn.close()
        return jsonify({"success": False, "error": "Project not found"}), 404

    gr = DirectedGraph.build_from_db(project_id, conn)
    simulator = DelaySimulator(gr, project['start_date'], project['deadline'])
    result = simulator.simulate(task_id, delay_days)

    if result.get("error"):
        conn.close()
        return jsonify({"success": False, "error": result["error"]}), 400

    # Save to simulation_history table
    if save_history:
        cursor = conn.cursor()
        summary = result["summary"]
        sel = result["selected_task"]
        cursor.execute('''
            INSERT INTO simulation_history (
                project_id, task_id, task_name, delay_days,
                direct_affected_count, indirect_affected_count, total_affected_count,
                original_completion_date, simulated_completion_date,
                project_delay_days, deadline_breached
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            project_id,
            task_id,
            sel['name'],
            delay_days,
            summary['direct_affected_count'],
            summary['indirect_affected_count'],
            summary['total_affected_count'],
            summary['baseline_finish_date'],
            summary['simulated_finish_date'],
            summary['total_project_delay_days'],
            1 if summary['deadline_breached'] else 0
        ))
        database.log_activity(
            project_id,
            "Delay Simulation",
            f"Simulated {delay_days}d delay on '{sel['name']}'. Downstream slip: +{summary['total_project_delay_days']}d. Affected: {summary['total_affected_count']} tasks.",
            conn
        )
        conn.commit()

    conn.close()
    return jsonify({"success": True, "simulation": result})


@app.route('/api/projects/<int:project_id>/simulations', methods=['GET'])
def get_simulation_history(project_id):
    conn = database.get_db_connection()
    sims = conn.execute('''
        SELECT s.*, p.name as project_name
        FROM simulation_history s
        JOIN projects p ON s.project_id = p.id
        WHERE s.project_id = ?
        ORDER BY s.id DESC
    ''', (project_id,)).fetchall()
    conn.close()
    return jsonify({"success": True, "history": [dict(s) for s in sims]})


@app.route('/api/simulations/<int:sim_id>', methods=['DELETE'])
def delete_simulation(sim_id):
    conn = database.get_db_connection()
    conn.execute('DELETE FROM simulation_history WHERE id = ?', (sim_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Simulation history entry deleted."})


# --- RISK & RECOVERY API ---
@app.route('/api/projects/<int:project_id>/risk-analysis', methods=['GET'])
def get_risk_analysis(project_id):
    conn = database.get_db_connection()
    project = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        conn.close()
        return jsonify({"success": False, "error": "Project not found"}), 404

    gr = DirectedGraph.build_from_db(project_id, conn)
    conn.close()

    analyzer = RiskAnalyzer(gr, project['start_date'], project['deadline'])
    analysis = analyzer.analyze()
    return jsonify({"success": True, "risk": analysis})


@app.route('/api/projects/<int:project_id>/recovery-suggestions', methods=['GET'])
def get_recovery_suggestions(project_id):
    conn = database.get_db_connection()
    project = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        conn.close()
        return jsonify({"success": False, "error": "Project not found"}), 404

    # Ensure app_settings exists
    conn.execute("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT)")
    ai_key_row = conn.execute("SELECT value FROM app_settings WHERE key = 'ai_api_key'").fetchone()
    ai_prov_row = conn.execute("SELECT value FROM app_settings WHERE key = 'ai_provider'").fetchone()
    ai_key = ai_key_row['value'] if ai_key_row else None
    ai_prov = ai_prov_row['value'] if ai_prov_row else 'gemini'

    gr = DirectedGraph.build_from_db(project_id, conn)
    members = [dict(m) for m in conn.execute('SELECT * FROM team_members').fetchall()]
    conn.close()

    engine = RecoveryEngine(gr, project['start_date'], project['deadline'], members)
    suggestions = engine.generate_suggestions()
    advisory = engine.generate_executive_advisory(project['name'], api_key=ai_key, provider=ai_prov)

    return jsonify({
        "success": True,
        "executive_advisory": advisory,
        "suggestions": suggestions
    })


@app.route('/api/settings/ai-config', methods=['GET', 'POST'])
def handle_ai_config():
    conn = database.get_db_connection()
    conn.execute("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT)")

    if request.method == 'POST':
        data = request.get_json() or {}
        key_val = (data.get('api_key') or '').strip()
        prov_val = (data.get('provider') or 'gemini').strip()

        conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('ai_api_key', ?)", (key_val,))
        conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('ai_provider', ?)", (prov_val,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Generative AI settings saved successfully."})

    key_row = conn.execute("SELECT value FROM app_settings WHERE key = 'ai_api_key'").fetchone()
    prov_row = conn.execute("SELECT value FROM app_settings WHERE key = 'ai_provider'").fetchone()
    conn.close()

    raw_key = key_row['value'] if key_row else ''
    masked_key = (raw_key[:4] + '...' + raw_key[-4:]) if len(raw_key) > 8 else ('' if not raw_key else '****')

    return jsonify({
        "success": True,
        "has_key": bool(raw_key),
        "masked_key": masked_key,
        "provider": prov_row['value'] if prov_row else 'gemini'
    })


# --- WORKLOAD API ---
@app.route('/api/projects/<int:project_id>/workload', methods=['GET'])
def get_project_workload(project_id):
    conn = database.get_db_connection()
    members = conn.execute('''
        SELECT tm.id, tm.name, tm.role, tm.email, tm.avatar_color,
               COUNT(t.id) as total_tasks,
               SUM(CASE WHEN t.status = 'Completed' THEN 1 ELSE 0 END) as completed_tasks,
               SUM(CASE WHEN t.status = 'In Progress' THEN 1 ELSE 0 END) as in_progress_tasks,
               SUM(CASE WHEN t.status = 'Delayed' THEN 1 ELSE 0 END) as delayed_tasks,
               SUM(CASE WHEN t.status = 'At Risk' THEN 1 ELSE 0 END) as at_risk_tasks,
               SUM(CASE WHEN t.status = 'Not Started' THEN 1 ELSE 0 END) as not_started_tasks,
               COALESCE(SUM(t.duration), 0) as total_duration_days
        FROM team_members tm
        LEFT JOIN tasks t ON tm.id = t.assigned_to AND t.project_id = ?
        GROUP BY tm.id
        ORDER BY tm.name ASC
    ''', (project_id,)).fetchall()

    result = []
    overloaded_members = []
    for m in members:
        d = dict(m)
        d['pending_tasks'] = (d['total_tasks'] or 0) - (d['completed_tasks'] or 0)
        # Determine overload state: > 3 pending tasks or > 10 days total workload
        is_overloaded = d['pending_tasks'] >= 3 or d['total_duration_days'] >= 10
        d['is_overloaded'] = is_overloaded
        if is_overloaded:
            overloaded_members.append(d['name'])
        result.append(d)

    conn.close()
    return jsonify({
        "success": True,
        "team_workload": result,
        "overloaded_members": overloaded_members
    })


@app.route('/api/team', methods=['GET'])
def get_team():
    conn = database.get_db_connection()
    members = conn.execute('SELECT * FROM team_members ORDER BY id ASC').fetchall()
    conn.close()
    return jsonify({"success": True, "team": [dict(m) for m in members]})


@app.route('/api/team', methods=['POST'])
def add_team_member():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    role = data.get('role', '').strip()
    email = data.get('email', '').strip()
    avatar_color = data.get('avatar_color', '#6366F1')

    if not name or not role:
        return jsonify({"success": False, "error": "Name and role are required."}), 400

    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO team_members (name, role, email, avatar_color)
        VALUES (?, ?, ?, ?)
    ''', (name, role, email, avatar_color))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({"success": True, "member_id": new_id, "message": "Team member added."}), 201


# --- ACTIVITY LOGS API ---
@app.route('/api/activity-logs', methods=['GET'])
def get_activity_logs():
    project_id = request.args.get('project_id')
    conn = database.get_db_connection()
    if project_id:
        logs = conn.execute('''
            SELECT a.*, p.name as project_name
            FROM activity_logs a
            LEFT JOIN projects p ON a.project_id = p.id
            WHERE a.project_id = ?
            ORDER BY a.id DESC LIMIT 25
        ''', (project_id,)).fetchall()
    else:
        logs = conn.execute('''
            SELECT a.*, p.name as project_name
            FROM activity_logs a
            LEFT JOIN projects p ON a.project_id = p.id
            ORDER BY a.id DESC LIMIT 25
        ''').fetchall()
    conn.close()
    return jsonify({"success": True, "logs": [dict(l) for l in logs]})


# --- PDF REPORT DOWNLOAD API ---
@app.route('/api/projects/<int:project_id>/report/pdf', methods=['GET'])
def download_pdf_report(project_id):
    """
    Generates and downloads the complete 8-section audit PDF report.
    """
    conn = database.get_db_connection()
    project = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        conn.close()
        return jsonify({"success": False, "error": "Project not found"}), 404

    tasks = [dict(r) for r in conn.execute('''
        SELECT t.*, tm.name as assignee_name
        FROM tasks t
        LEFT JOIN team_members tm ON t.assigned_to = tm.id
        WHERE t.project_id = ?
        ORDER BY t.id ASC
    ''', (project_id,)).fetchall()]

    deps = [dict(r) for r in conn.execute('SELECT * FROM dependencies WHERE project_id = ?', (project_id,)).fetchall()]
    gr = DirectedGraph.build_from_db(project_id, conn)
    cpm = CriticalPathAnalysis(gr, project['start_date']).calculate()
    risk = RiskAnalyzer(gr, project['start_date'], project['deadline']).analyze()
    recovery = RecoveryEngine(gr, project['start_date'], project['deadline']).generate_suggestions()
    ai_risk = AIRiskEngine.predict_project_risk(project_id, conn)

    daily_updates = [dict(r) for r in conn.execute('''
        SELECT u.*, tm.name as member_name, t.name as task_name
        FROM daily_work_updates u
        JOIN team_members tm ON u.team_member_id = tm.id
        JOIN tasks t ON u.task_id = t.id
        WHERE u.project_id = ?
        ORDER BY u.submission_date DESC, u.id DESC LIMIT 10
    ''', (project_id,)).fetchall()]

    # Check for latest simulation if any
    latest_sim = conn.execute('''
        SELECT * FROM simulation_history WHERE project_id = ? ORDER BY id DESC LIMIT 1
    ''', (project_id,)).fetchone()
    conn.close()

    sim_data = None
    if latest_sim:
        sim_simulator = DelaySimulator(gr, project['start_date'], project['deadline'])
        sim_data = sim_simulator.simulate(latest_sim['task_id'], latest_sim['delay_days'])

    pdf_bytes = ReportGenerator(
        dict(project),
        tasks,
        deps,
        cpm,
        risk,
        recovery,
        sim_data,
        ai_risk,
        daily_updates
    ).build_pdf()

    clean_name = project['name'].replace(' ', '_').lower()
    filename = f"DependencyRescue_Report_{clean_name}_{datetime.now().strftime('%Y%m%d')}.pdf"

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )


# --- SYSTEM RESET API ---
@app.route('/api/system/network-status', methods=['GET'])
def get_network_status():
    """Detects whether internet connectivity is available for cloud AI."""
    import socket
    is_online = False
    try:
        socket.setdefaulttimeout(1.2)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("8.8.8.8", 53))
        s.close()
        is_online = True
    except Exception:
        is_online = False

    return jsonify({
        "success": True,
        "is_online": is_online,
        "mode": "Cloud AI Enabled (Online)" if is_online else "Local Heuristic Engine (Offline)"
    })


@app.route('/api/system/reset', methods=['POST'])
def reset_database():
    """Resets the database and restores the default sample project and team members."""
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.executescript('''
        DROP TABLE IF EXISTS simulation_history;
        DROP TABLE IF EXISTS activity_logs;
        DROP TABLE IF EXISTS dependencies;
        DROP TABLE IF EXISTS tasks;
        DROP TABLE IF EXISTS projects;
        DROP TABLE IF EXISTS team_members;
    ''')
    conn.commit()
    conn.close()
    
    database.init_db()
    return jsonify({"success": True, "message": "System database successfully reset and seeded with default sample project."})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

