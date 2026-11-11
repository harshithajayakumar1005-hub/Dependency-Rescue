import sqlite3
import os
import json
from datetime import datetime, timedelta
from config import Config

def get_db_connection():
    """Returns a new database connection with row factory and foreign keys enabled."""
    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def migrate_db(conn):
    """Safely adds new columns to existing tables if missing."""
    cursor = conn.cursor()
    
    # Check tasks columns
    cursor.execute("PRAGMA table_info(tasks);")
    existing_task_cols = [row['name'] for row in cursor.fetchall()]
    
    if 'progress_pct' not in existing_task_cols:
        cursor.execute("ALTER TABLE tasks ADD COLUMN progress_pct INTEGER NOT NULL DEFAULT 0;")
    if 'actual_start_date' not in existing_task_cols:
        cursor.execute("ALTER TABLE tasks ADD COLUMN actual_start_date TEXT;")
    if 'actual_completion_date' not in existing_task_cols:
        cursor.execute("ALTER TABLE tasks ADD COLUMN actual_completion_date TEXT;")
    if 'time_spent_hours' not in existing_task_cols:
        cursor.execute("ALTER TABLE tasks ADD COLUMN time_spent_hours REAL DEFAULT 0.0;")
    if 'complexity' not in existing_task_cols:
        cursor.execute("ALTER TABLE tasks ADD COLUMN complexity TEXT DEFAULT 'Medium';")

    # Check team_members columns
    cursor.execute("PRAGMA table_info(team_members);")
    existing_tm_cols = [row['name'] for row in cursor.fetchall()]
    
    if 'role_type' not in existing_tm_cols:
        cursor.execute("ALTER TABLE team_members ADD COLUMN role_type TEXT DEFAULT 'Team Member';")
    if 'status' not in existing_tm_cols:
        cursor.execute("ALTER TABLE team_members ADD COLUMN status TEXT DEFAULT 'Active';")

    conn.commit()

def init_db():
    """Initializes all tables in the SQLite database and seeds default data."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.executescript('''
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        start_date TEXT NOT NULL,
        deadline TEXT NOT NULL,
        status TEXT DEFAULT 'Active',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS team_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        role_type TEXT DEFAULT 'Team Member',
        email TEXT,
        avatar_color TEXT DEFAULT '#6366F1',
        status TEXT DEFAULT 'Active'
    );

    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        duration INTEGER NOT NULL DEFAULT 1,
        start_date TEXT NOT NULL,
        deadline TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Not Started',
        priority TEXT NOT NULL DEFAULT 'Medium',
        assigned_to INTEGER,
        progress_pct INTEGER NOT NULL DEFAULT 0,
        actual_start_date TEXT,
        actual_completion_date TEXT,
        time_spent_hours REAL DEFAULT 0.0,
        complexity TEXT DEFAULT 'Medium',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
        FOREIGN KEY (assigned_to) REFERENCES team_members(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS dependencies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        predecessor_id INTEGER NOT NULL,
        successor_id INTEGER NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
        FOREIGN KEY (predecessor_id) REFERENCES tasks(id) ON DELETE CASCADE,
        FOREIGN KEY (successor_id) REFERENCES tasks(id) ON DELETE CASCADE,
        UNIQUE (project_id, predecessor_id, successor_id)
    );

    CREATE TABLE IF NOT EXISTS daily_work_updates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        task_id INTEGER NOT NULL,
        team_member_id INTEGER NOT NULL,
        work_description TEXT NOT NULL,
        progress_pct INTEGER NOT NULL DEFAULT 0,
        remaining_work TEXT,
        problems_faced TEXT,
        estimated_remaining_days INTEGER DEFAULT 1,
        submission_date TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
        FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
        FOREIGN KEY (team_member_id) REFERENCES team_members(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS task_activity_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL,
        project_id INTEGER NOT NULL,
        team_member_id INTEGER,
        action_type TEXT NOT NULL,
        old_status TEXT,
        new_status TEXT,
        old_progress INTEGER,
        new_progress INTEGER,
        comments TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
        FOREIGN KEY (team_member_id) REFERENCES team_members(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS ai_risk_predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        task_id INTEGER NOT NULL,
        risk_level TEXT NOT NULL,
        delay_probability REAL NOT NULL,
        expected_delay_days REAL NOT NULL,
        model_type TEXT DEFAULT 'Rule-Based Heuristic',
        factors_json TEXT,
        predicted_completion_date TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
        FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS ml_training_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model_name TEXT NOT NULL,
        accuracy_score REAL NOT NULL,
        samples_count INTEGER NOT NULL,
        feature_importances_json TEXT,
        trained_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );

    CREATE TABLE IF NOT EXISTS simulation_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        task_id INTEGER NOT NULL,
        task_name TEXT NOT NULL,
        delay_days INTEGER NOT NULL,
        direct_affected_count INTEGER DEFAULT 0,
        indirect_affected_count INTEGER DEFAULT 0,
        total_affected_count INTEGER DEFAULT 0,
        original_completion_date TEXT,
        simulated_completion_date TEXT,
        project_delay_days INTEGER DEFAULT 0,
        deadline_breached INTEGER DEFAULT 0,
        simulated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS activity_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        action TEXT NOT NULL,
        details TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT,
        avatar_color TEXT DEFAULT '#6366F1',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS user_project_roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        project_id INTEGER NOT NULL,
        role_title TEXT NOT NULL,
        is_lead INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
        UNIQUE (user_id, project_id)
    );
    ''')
    conn.commit()

    # Run migration in case tables pre-existed
    migrate_db(conn)

    # Seed team members if not existing
    cursor.execute("SELECT COUNT(*) as count FROM team_members")
    if cursor.fetchone()['count'] == 0:
        default_members = [
            ("Alex Chen", "Lead System Architect", "Project Administrator", "alex.chen@rescue.dev", "#8B5CF6"),
            ("Sarah Connor", "Senior UI/UX Designer", "Team Member", "sarah.c@rescue.dev", "#EC4899"),
            ("David Miller", "Full-Stack Engineer", "Team Member", "david.m@rescue.dev", "#3B82F6"),
            ("Priya Sharma", "Lead QA Automation", "Project Manager", "priya.s@rescue.dev", "#10B981"),
            ("Marcus Vance", "DevOps & Cloud Engineer", "Team Member", "marcus.v@rescue.dev", "#F59E0B")
        ]
        cursor.executemany(
            "INSERT INTO team_members (name, role, role_type, email, avatar_color) VALUES (?, ?, ?, ?, ?)",
            default_members
        )
        conn.commit()

    # Seed users and project-scoped roles
    seed_users_and_roles(conn)

    # Check if any project exists; if not, seed the default sample projects
    cursor.execute("SELECT COUNT(*) as count FROM projects")
    if cursor.fetchone()['count'] == 0:
        seed_sample_project(conn)
        seed_complex_project(conn)
        seed_mobile_ai_project(conn)

    conn.close()

def seed_users_and_roles(conn=None):
    """Seeds default user accounts and project-scoped roles."""
    close_after = False
    if conn is None:
        conn = get_db_connection()
        close_after = True

    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, full_name TEXT NOT NULL, email TEXT, avatar_color TEXT DEFAULT '#6366F1', created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    cursor.execute("CREATE TABLE IF NOT EXISTS user_project_roles (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, project_id INTEGER NOT NULL, role_title TEXT NOT NULL, is_lead INTEGER DEFAULT 0, UNIQUE (user_id, project_id))")

    cursor.execute("SELECT COUNT(*) as count FROM users")
    if cursor.fetchone()['count'] == 0:
        default_users = [
            ("alex", "alex123", "Alex Chen", "alex.chen@rescue.dev", "#8B5CF6"),
            ("sarah", "sarah123", "Sarah Connor", "sarah.c@rescue.dev", "#EC4899"),
            ("david", "david123", "David Miller", "david.m@rescue.dev", "#3B82F6"),
            ("priya", "priya123", "Priya Sharma", "priya.s@rescue.dev", "#10B981"),
            ("marcus", "marcus123", "Marcus Vance", "marcus.v@rescue.dev", "#F59E0B")
        ]
        cursor.executemany(
            "INSERT INTO users (username, password, full_name, email, avatar_color) VALUES (?, ?, ?, ?, ?)",
            default_users
        )

        # Seed per-project roles:
        # Project 1: Alex is Project Lead (Full Access), others are Members
        # Project 2: Sarah is Project Lead (Full Access), others are Members
        # Project 3: Alex is Project Lead, Sarah is Mobile Specialist, Priya is QA Lead
        default_roles = [
            # User 1 (Alex Chen)
            (1, 1, "Project Lead", 1),
            (1, 2, "Full-Stack Architect", 0),
            (1, 3, "Project Lead", 1),
            # User 2 (Sarah Connor)
            (2, 1, "UI/UX Designer", 0),
            (2, 2, "Project Lead & Product Manager", 1),
            (2, 3, "Mobile UI Specialist", 0),
            # User 3 (David Miller)
            (3, 1, "Backend Developer", 0),
            (3, 2, "Core Services Engineer", 0),
            (3, 3, "ML Pipeline Engineer", 0),
            # User 4 (Priya Sharma)
            (4, 1, "QA Automation Engineer", 0),
            (4, 2, "Lead QA Automation", 0),
            (4, 3, "Security & Release Lead", 0),
            # User 5 (Marcus Vance)
            (5, 1, "DevOps Engineer", 0),
            (5, 2, "Cloud Infrastructure Lead", 0),
            (5, 3, "API Gateway Engineer", 0)
        ]
        cursor.executemany(
            "INSERT OR IGNORE INTO user_project_roles (user_id, project_id, role_title, is_lead) VALUES (?, ?, ?, ?)",
            default_roles
        )
        conn.commit()

    if close_after:
        conn.close()

def log_activity(project_id, action, details, conn=None):
    """Utility to record an audit activity log entry."""
    close_after = False
    if conn is None:
        conn = get_db_connection()
        close_after = True
    try:
        conn.execute(
            "INSERT INTO activity_logs (project_id, action, details) VALUES (?, ?, ?)",
            (project_id, action, details)
        )
        conn.commit()
    except Exception as e:
        print(f"Error logging activity: {e}")
    finally:
        if close_after:
            conn.close()

def log_task_activity(task_id, project_id, team_member_id, action_type, old_status, new_status, old_prog, new_prog, comments, conn=None):
    """Utility to record structured task progress and status changes with audit trail."""
    close_after = False
    if conn is None:
        conn = get_db_connection()
        close_after = True
    try:
        conn.execute('''
            INSERT INTO task_activity_history (
                task_id, project_id, team_member_id, action_type,
                old_status, new_status, old_progress, new_progress, comments
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (task_id, project_id, team_member_id, action_type, old_status, new_status, old_prog, new_prog, comments))
        conn.commit()
    except Exception as e:
        print(f"Error logging task activity: {e}")
    finally:
        if close_after:
            conn.close()

def seed_sample_project(conn=None):
    """Creates or reloads the default sample project 'Software Development Project'."""
    close_after = False
    if conn is None:
        conn = get_db_connection()
        close_after = True

    cursor = conn.cursor()

    # Start dates around current time
    base_date = datetime.now().date()
    p_start = base_date.strftime("%Y-%m-%d")
    p_deadline = (base_date + timedelta(days=16)).strftime("%Y-%m-%d")

    cursor.execute('''
        INSERT INTO projects (name, description, start_date, deadline, status)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        "Software Development Project",
        "Demonstration project showcasing task dependency chains, critical path scheduling, and delay propagation.",
        p_start,
        p_deadline,
        "Active"
    ))
    project_id = cursor.lastrowid

    cursor.execute("SELECT id, name FROM team_members ORDER BY id")
    members = {row['name']: row['id'] for row in cursor.fetchall()}

    t1_start = base_date
    t1_end = t1_start + timedelta(days=2)

    t2_start = t1_end
    t2_end = t2_start + timedelta(days=3)

    t3_start = t2_end
    t3_end = t3_start + timedelta(days=5)

    t4_start = t3_end
    t4_end = t4_start + timedelta(days=3)

    t5_start = t4_end
    t5_end = t5_start + timedelta(days=1)

    # Initial realistic progress percentages & time spent
    tasks_data = [
        ("Requirement Analysis", "Gather user stories, formulate SRS, and establish architecture guidelines.", 2, t1_start.strftime("%Y-%m-%d"), t1_end.strftime("%Y-%m-%d"), "Completed", "High", members.get("Alex Chen"), 100, t1_start.strftime("%Y-%m-%d"), (t1_start + timedelta(days=2)).strftime("%Y-%m-%d"), 16.0, "Medium"),
        ("UI/UX Design", "Build responsive wireframes, design dark navy UI components, and finalize user journey.", 3, t2_start.strftime("%Y-%m-%d"), t2_end.strftime("%Y-%m-%d"), "In Progress", "Medium", members.get("Sarah Connor"), 45, t2_start.strftime("%Y-%m-%d"), None, 12.5, "Medium"),
        ("Development", "Implement Flask backend REST APIs, graph algorithms, and frontend SPA interface.", 5, t3_start.strftime("%Y-%m-%d"), t3_end.strftime("%Y-%m-%d"), "Not Started", "Critical", members.get("David Miller"), 0, None, None, 0.0, "High"),
        ("Testing", "Execute automated unit tests, critical path validation, and dependency graph verification.", 3, t4_start.strftime("%Y-%m-%d"), t4_end.strftime("%Y-%m-%d"), "Not Started", "High", members.get("Priya Sharma"), 0, None, None, 0.0, "Medium"),
        ("Deployment", "Provision production server, configure WSGI, and deploy application to production.", 1, t5_start.strftime("%Y-%m-%d"), t5_end.strftime("%Y-%m-%d"), "Not Started", "Critical", members.get("Marcus Vance"), 0, None, None, 0.0, "High"),
    ]

    task_ids = []
    for t in tasks_data:
        cursor.execute('''
            INSERT INTO tasks (
                project_id, name, description, duration, start_date, deadline,
                status, priority, assigned_to, progress_pct, actual_start_date, actual_completion_date, time_spent_hours, complexity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (project_id, *t))
        task_ids.append(cursor.lastrowid)

    # Dependencies: 1->2, 2->3, 3->4, 4->5
    deps = [
        (project_id, task_ids[0], task_ids[1]),
        (project_id, task_ids[1], task_ids[2]),
        (project_id, task_ids[2], task_ids[3]),
        (project_id, task_ids[3], task_ids[4]),
    ]
    cursor.executemany('''
        INSERT INTO dependencies (project_id, predecessor_id, successor_id)
        VALUES (?, ?, ?)
    ''', deps)

    # Seed initial task activity history
    log_task_activity(task_ids[0], project_id, members.get("Alex Chen"), "STATUS_CHANGE", "In Progress", "Completed", 50, 100, "Finalized SRS documentation and signed off on system architecture.", conn)
    log_task_activity(task_ids[1], project_id, members.get("Sarah Connor"), "PROGRESS_UPDATE", "In Progress", "In Progress", 20, 45, "Completed initial figma mockups and responsive wireframes.", conn)

    # Seed sample daily work update reports
    today_str = datetime.now().strftime("%Y-%m-%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    cursor.execute('''
        INSERT INTO daily_work_updates (
            project_id, task_id, team_member_id, work_description, progress_pct,
            remaining_work, problems_faced, estimated_remaining_days, submission_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        project_id, task_ids[0], members.get("Alex Chen"),
        "Conducted stakeholder interviews and finalized functional requirements specifications.",
        100, "None - task deliverables verified and completed.", "None", 0, yesterday_str
    ))

    cursor.execute('''
        INSERT INTO daily_work_updates (
            project_id, task_id, team_member_id, work_description, progress_pct,
            remaining_work, problems_faced, estimated_remaining_days, submission_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        project_id, task_ids[1], members.get("Sarah Connor"),
        "Designed dark navy dashboard theme, graph node styles, and schedule comparison cards.",
        45, "Finish mobile responsiveness and icon alignments.",
        "Waiting on final SVG assets for custom graph nodes.", 2, today_str
    ))

    log_activity(project_id, "Project Created", "Sample 'Software Development Project' seeded with tasks and daily work logs.", conn)
    conn.commit()

    if close_after:
        conn.close()

    return project_id

def seed_complex_project(conn=None):
    """Creates a complex multi-branch DAG demonstration project with parallel tasks and slack."""
    close_after = False
    if conn is None:
        conn = get_db_connection()
        close_after = True

    cursor = conn.cursor()
    base_date = datetime.now().date()
    p_start = base_date.strftime("%Y-%m-%d")
    p_deadline = (base_date + timedelta(days=19)).strftime("%Y-%m-%d")

    cursor.execute('''
        INSERT INTO projects (name, description, start_date, deadline, status)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        "Enterprise Cloud Portal (Parallel DAG)",
        "Advanced multi-branch DAG with concurrent frontend/backend development, multiple predecessors, and schedule float.",
        p_start,
        p_deadline,
        "Active"
    ))
    project_id = cursor.lastrowid

    cursor.execute("SELECT id, name FROM team_members ORDER BY id")
    members = {row['name']: row['id'] for row in cursor.fetchall()}

    tasks_data = [
        ("System Architecture", "Define microservices schema, authentication boundaries, and API contracts.", 2, base_date.strftime("%Y-%m-%d"), (base_date + timedelta(days=2)).strftime("%Y-%m-%d"), "Completed", "Critical", members.get("Alex Chen"), 100, base_date.strftime("%Y-%m-%d"), (base_date + timedelta(days=2)).strftime("%Y-%m-%d"), 16.0, "High"),
        ("Core Backend Services", "Build Python/Flask high-throughput REST APIs and business logic.", 6, (base_date + timedelta(days=2)).strftime("%Y-%m-%d"), (base_date + timedelta(days=8)).strftime("%Y-%m-%d"), "In Progress", "Critical", members.get("David Miller"), 40, (base_date + timedelta(days=2)).strftime("%Y-%m-%d"), None, 18.0, "High"),
        ("Frontend UI Components", "Construct interactive HTML5 components and graph visualizers.", 3, (base_date + timedelta(days=2)).strftime("%Y-%m-%d"), (base_date + timedelta(days=5)).strftime("%Y-%m-%d"), "In Progress", "Medium", members.get("Sarah Connor"), 60, (base_date + timedelta(days=2)).strftime("%Y-%m-%d"), None, 12.0, "Medium"),
        ("Database & Caching Layer", "Provision PostgreSQL tables, indexing strategies, and Redis cache clusters.", 3, (base_date + timedelta(days=2)).strftime("%Y-%m-%d"), (base_date + timedelta(days=5)).strftime("%Y-%m-%d"), "Not Started", "High", members.get("Marcus Vance"), 0, None, None, 0.0, "Medium"),
        ("System Integration & API Binding", "Wire backend endpoints to frontend views and integrate data contracts.", 4, (base_date + timedelta(days=8)).strftime("%Y-%m-%d"), (base_date + timedelta(days=12)).strftime("%Y-%m-%d"), "Not Started", "Critical", members.get("Alex Chen"), 0, None, None, 0.0, "High"),
        ("QA Automation & Load Testing", "Execute end-to-end regression tests and simulate network failovers.", 3, (base_date + timedelta(days=12)).strftime("%Y-%m-%d"), (base_date + timedelta(days=15)).strftime("%Y-%m-%d"), "Not Started", "High", members.get("Priya Sharma"), 0, None, None, 0.0, "Medium"),
        ("Production Deployment", "Automate blue-green WSGI deployment and configure DNS routing.", 1, (base_date + timedelta(days=15)).strftime("%Y-%m-%d"), (base_date + timedelta(days=16)).strftime("%Y-%m-%d"), "Not Started", "Critical", members.get("Marcus Vance"), 0, None, None, 0.0, "High")
    ]

    task_ids = []
    for t in tasks_data:
        cursor.execute('''
            INSERT INTO tasks (
                project_id, name, description, duration, start_date, deadline,
                status, priority, assigned_to, progress_pct, actual_start_date, actual_completion_date, time_spent_hours, complexity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (project_id, *t))
        task_ids.append(cursor.lastrowid)

    deps = [
        (project_id, task_ids[0], task_ids[1]),
        (project_id, task_ids[0], task_ids[2]),
        (project_id, task_ids[0], task_ids[3]),
        (project_id, task_ids[1], task_ids[4]),
        (project_id, task_ids[2], task_ids[4]),
        (project_id, task_ids[3], task_ids[5]),
        (project_id, task_ids[4], task_ids[5]),
        (project_id, task_ids[5], task_ids[6]),
    ]
    cursor.executemany('''
        INSERT INTO dependencies (project_id, predecessor_id, successor_id)
        VALUES (?, ?, ?)
    ''', deps)

    log_activity(project_id, "Project Created", "Sample 'Enterprise Cloud Portal (Parallel DAG)' seeded with 7 branching tasks.", conn)
    conn.commit()

    if close_after:
        conn.close()

    return project_id

def seed_mobile_ai_project(conn=None):
    """Creates a third project: 'AI Mobile App & Recommendation Engine' with parallel workflows."""
    close_after = False
    if conn is None:
        conn = get_db_connection()
        close_after = True

    cursor = conn.cursor()
    base_date = datetime.now().date()
    p_start = base_date.strftime("%Y-%m-%d")
    p_deadline = (base_date + timedelta(days=22)).strftime("%Y-%m-%d")

    cursor.execute('''
        INSERT INTO projects (name, description, start_date, deadline, status)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        "AI Mobile App & Recommendation Engine",
        "Cross-platform mobile client with machine learning recommendation engine, real-time sync, and edge caching.",
        p_start,
        p_deadline,
        "Active"
    ))
    project_id = cursor.lastrowid

    cursor.execute("SELECT id, name FROM team_members ORDER BY id")
    members = {row['name']: row['id'] for row in cursor.fetchall()}

    tasks_data = [
        ("User Research & UX Wireframes", "Conduct user surveys, map customer journey, and design mobile Figma wireframes.", 3, base_date.strftime("%Y-%m-%d"), (base_date + timedelta(days=3)).strftime("%Y-%m-%d"), "Completed", "High", members.get("Sarah Connor"), 100, base_date.strftime("%Y-%m-%d"), (base_date + timedelta(days=3)).strftime("%Y-%m-%d"), 20.0, "Medium"),
        ("Dataset Collection & Feature Pipeline", "Collect user interaction logs, clean training vectors, and engineer feature pipelines.", 4, (base_date + timedelta(days=3)).strftime("%Y-%m-%d"), (base_date + timedelta(days=7)).strftime("%Y-%m-%d"), "In Progress", "Critical", members.get("David Miller"), 65, (base_date + timedelta(days=3)).strftime("%Y-%m-%d"), None, 22.0, "High"),
        ("ML Recommendation Model Training", "Train collaborative filtering model, evaluate precision/recall, and export ONNX model.", 5, (base_date + timedelta(days=7)).strftime("%Y-%m-%d"), (base_date + timedelta(days=12)).strftime("%Y-%m-%d"), "In Progress", "Critical", members.get("Alex Chen"), 35, (base_date + timedelta(days=7)).strftime("%Y-%m-%d"), None, 14.0, "High"),
        ("Mobile Client UI (Flutter)", "Build responsive cross-platform screens, local caching, and state management in Flutter.", 5, (base_date + timedelta(days=3)).strftime("%Y-%m-%d"), (base_date + timedelta(days=8)).strftime("%Y-%m-%d"), "In Progress", "Medium", members.get("Sarah Connor"), 50, (base_date + timedelta(days=3)).strftime("%Y-%m-%d"), None, 18.0, "Medium"),
        ("API Gateway & Cloud Sync", "Implement secure REST/WebSocket gateway, rate-limiting, and PostgreSQL synchronization.", 4, (base_date + timedelta(days=12)).strftime("%Y-%m-%d"), (base_date + timedelta(days=16)).strftime("%Y-%m-%d"), "Not Started", "Critical", members.get("Marcus Vance"), 0, None, None, 0.0, "High"),
        ("Security Audit & Pen Testing", "Conduct vulnerability scans, API token penetration tests, and privacy compliance review.", 3, (base_date + timedelta(days=16)).strftime("%Y-%m-%d"), (base_date + timedelta(days=19)).strftime("%Y-%m-%d"), "Not Started", "High", members.get("Priya Sharma"), 0, None, None, 0.0, "Medium"),
        ("App Store Submission & Launch", "Prepare App Store & Play Store assets, build release bundles, and deploy to production.", 2, (base_date + timedelta(days=19)).strftime("%Y-%m-%d"), (base_date + timedelta(days=21)).strftime("%Y-%m-%d"), "Not Started", "Critical", members.get("Priya Sharma"), 0, None, None, 0.0, "High")
    ]

    task_ids = []
    for t in tasks_data:
        cursor.execute('''
            INSERT INTO tasks (
                project_id, name, description, duration, start_date, deadline,
                status, priority, assigned_to, progress_pct, actual_start_date, actual_completion_date, time_spent_hours, complexity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (project_id, *t))
        task_ids.append(cursor.lastrowid)

    deps = [
        (project_id, task_ids[0], task_ids[1]),
        (project_id, task_ids[0], task_ids[3]),
        (project_id, task_ids[1], task_ids[2]),
        (project_id, task_ids[2], task_ids[4]),
        (project_id, task_ids[3], task_ids[4]),
        (project_id, task_ids[4], task_ids[5]),
        (project_id, task_ids[5], task_ids[6]),
    ]
    cursor.executemany('''
        INSERT INTO dependencies (project_id, predecessor_id, successor_id)
        VALUES (?, ?, ?)
    ''', deps)

    # Seed sample daily update
    today_str = datetime.now().strftime("%Y-%m-%d")
    cursor.execute('''
        INSERT INTO daily_work_updates (
            project_id, task_id, team_member_id, work_description, progress_pct,
            remaining_work, problems_faced, estimated_remaining_days, submission_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        project_id, task_ids[1], members.get("David Miller"),
        "Engineered feature vectors from raw event logs; normalized matrix dimensions.",
        65, "Export final dataset split for model training.",
        "None", 1, today_str
    ))

    log_activity(project_id, "Project Created", "Sample 'AI Mobile App & Recommendation Engine' seeded with 7 tasks and parallel DAG dependencies.", conn)
    conn.commit()

    if close_after:
        conn.close()

    return project_id
