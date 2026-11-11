from datetime import datetime, timedelta
import sqlite3

class ProgressTracker:
    """
    Automated Task & Project Progress Tracking Engine for Dependency Rescue.
    Maintains verified status transitions, duration-weighted project completion %,
    stagnation detection, and complete task activity audit logging.
    """

    @staticmethod
    def calculate_project_metrics(project_id: int, conn):
        """
        Calculates comprehensive progress metrics for a project:
        - Weighted completion percentage (by duration)
        - Expected completion percentage based on schedule elapsed time
        - Breakdown by status (Completed, In Progress, Delayed, At Risk, Not Started)
        - Stagnant tasks (no update in >= 3 days)
        """
        project = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
        if not project:
            return None

        tasks = conn.execute('''
            SELECT id, name, duration, start_date, deadline, status, priority,
                   progress_pct, actual_start_date, actual_completion_date,
                   time_spent_hours, assigned_to
            FROM tasks
            WHERE project_id = ?
        ''', (project_id,)).fetchall()

        total_tasks = len(tasks)
        if total_tasks == 0:
            return {
                "total_tasks": 0,
                "completed_tasks": 0,
                "in_progress_tasks": 0,
                "delayed_tasks": 0,
                "at_risk_tasks": 0,
                "not_started_tasks": 0,
                "overall_progress_pct": 0,
                "expected_progress_pct": 0,
                "progress_variance_pct": 0,
                "total_planned_hours": 0,
                "total_spent_hours": 0.0,
                "stagnant_tasks_count": 0
            }

        today_dt = datetime.now().date()
        total_duration = sum(max(1, t['duration']) for t in tasks)
        weighted_progress_sum = 0.0
        weighted_expected_sum = 0.0
        total_spent_hours = 0.0

        completed_count = 0
        in_progress_count = 0
        delayed_count = 0
        at_risk_count = 0
        not_started_count = 0

        # Query latest updates per task to evaluate stagnation
        updates_rows = conn.execute('''
            SELECT task_id, MAX(submission_date) as last_update_date
            FROM daily_work_updates
            WHERE project_id = ?
            GROUP BY task_id
        ''', (project_id,)).fetchall()
        last_update_map = {r['task_id']: r['last_update_date'] for r in updates_rows}

        stagnant_tasks = []

        for t in tasks:
            dur = max(1, t['duration'])
            prog = min(100, max(0, t['progress_pct'] or 0))
            st = t['status']
            total_spent_hours += (t['time_spent_hours'] or 0.0)

            # Check status counters
            if st == 'Completed':
                completed_count += 1
            elif st == 'In Progress':
                in_progress_count += 1
            elif st == 'Delayed':
                delayed_count += 1
            elif st == 'At Risk':
                at_risk_count += 1
            else:
                not_started_count += 1

            # Weighted progress
            weighted_progress_sum += dur * prog

            # Expected progress
            try:
                s_dt = datetime.strptime(t['start_date'], "%Y-%m-%d").date()
                d_dt = datetime.strptime(t['deadline'], "%Y-%m-%d").date()
            except Exception:
                s_dt = today_dt
                d_dt = today_dt + timedelta(days=dur)

            if today_dt <= s_dt:
                exp = 0.0
            elif today_dt >= d_dt:
                exp = 100.0
            else:
                span = max(1, (d_dt - s_dt).days)
                elapsed = (today_dt - s_dt).days
                exp = min(100.0, (elapsed / span) * 100.0)

            weighted_expected_sum += dur * exp

            # Stagnation check: active task with no update in >= 3 days
            if st in ['In Progress', 'At Risk', 'Delayed']:
                last_sub = last_update_map.get(t['id'])
                if last_sub:
                    try:
                        sub_dt = datetime.strptime(last_sub, "%Y-%m-%d").date()
                        days_silent = (today_dt - sub_dt).days
                        if days_silent >= 3:
                            stagnant_tasks.append({
                                "task_id": t['id'],
                                "name": t['name'],
                                "days_silent": days_silent,
                                "last_update": last_sub
                            })
                    except Exception:
                        pass
                else:
                    stagnant_tasks.append({
                        "task_id": t['id'],
                        "name": t['name'],
                        "days_silent": 4,
                        "last_update": "Never"
                    })

        overall_progress_pct = round(weighted_progress_sum / total_duration, 1) if total_duration > 0 else 0.0
        expected_progress_pct = round(weighted_expected_sum / total_duration, 1) if total_duration > 0 else 0.0
        progress_variance_pct = round(overall_progress_pct - expected_progress_pct, 1)

        return {
            "total_tasks": total_tasks,
            "completed_tasks": completed_count,
            "in_progress_tasks": in_progress_count,
            "delayed_tasks": delayed_count,
            "at_risk_tasks": at_risk_count,
            "not_started_tasks": not_started_count,
            "overall_progress_pct": overall_progress_pct,
            "expected_progress_pct": expected_progress_pct,
            "progress_variance_pct": progress_variance_pct,
            "total_planned_hours": total_duration * 8,
            "total_spent_hours": round(total_spent_hours, 1),
            "stagnant_tasks_count": len(stagnant_tasks),
            "stagnant_tasks": stagnant_tasks
        }

    @staticmethod
    def update_task_progress(task_id: int, new_progress: int, new_status: str, member_id: int, hours_spent: float, comments: str, conn):
        """
        Updates task progress and automatically applies status lifecycle rules:
        - If progress == 100, sets status to 'Completed' and sets actual_completion_date.
        - If progress > 0 and status is 'Not Started', sets status to 'In Progress' and sets actual_start_date.
        - Records complete activity history entry.
        """
        cursor = conn.cursor()
        current = cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
        if not current:
            return {"success": False, "error": "Task not found"}

        project_id = current['project_id']
        old_status = current['status']
        old_progress = current['progress_pct'] or 0
        old_hours = current['time_spent_hours'] or 0.0
        now_date_str = datetime.now().strftime("%Y-%m-%d")

        progress_pct = max(0, min(100, int(new_progress)))
        status = new_status or old_status

        # Automatic lifecycle rules based on verified progress
        actual_start = current['actual_start_date']
        actual_comp = current['actual_completion_date']

        if progress_pct == 100:
            status = 'Completed'
            if not actual_comp:
                actual_comp = now_date_str
            if not actual_start:
                actual_start = now_date_str
        elif progress_pct > 0 and status == 'Not Started':
            status = 'In Progress'
            if not actual_start:
                actual_start = now_date_str
        elif progress_pct < 100 and status == 'Completed':
            # Re-opened
            status = 'In Progress'
            actual_comp = None

        total_hours = old_hours + max(0.0, float(hours_spent or 0.0))

        cursor.execute('''
            UPDATE tasks
            SET progress_pct = ?, status = ?, actual_start_date = ?,
                actual_completion_date = ?, time_spent_hours = ?
            WHERE id = ?
        ''', (progress_pct, status, actual_start, actual_comp, total_hours, task_id))

        # Record activity log
        action_type = "PROGRESS_UPDATE"
        if old_status != status and old_progress != progress_pct:
            action_type = "STATUS_AND_PROGRESS_CHANGE"
        elif old_status != status:
            action_type = "STATUS_CHANGE"

        cursor.execute('''
            INSERT INTO task_activity_history (
                task_id, project_id, team_member_id, action_type,
                old_status, new_status, old_progress, new_progress, comments
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            task_id, project_id, member_id, action_type,
            old_status, status, old_progress, progress_pct,
            comments or f"Updated task progress to {progress_pct}% with status '{status}'."
        ))

        conn.commit()

        return {
            "success": True,
            "task_id": task_id,
            "old_status": old_status,
            "new_status": status,
            "old_progress": old_progress,
            "new_progress": progress_pct,
            "actual_start_date": actual_start,
            "actual_completion_date": actual_comp,
            "time_spent_hours": total_hours
        }

