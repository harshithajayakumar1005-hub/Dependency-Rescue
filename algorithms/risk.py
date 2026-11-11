from datetime import datetime, timedelta
from algorithms.graph import DirectedGraph
from algorithms.cpm import CriticalPathAnalysis

class RiskAnalyzer:
    """
    Performs comprehensive deadline risk analysis on a project, assessing
    schedule flexibility (floats), overdue tasks, critical path vulnerabilities,
    and deadline proximity with clear human-readable explanations.
    """

    def __init__(self, graph: DirectedGraph, project_start_date_str=None, project_deadline_str=None, current_date=None):
        self.graph = graph
        try:
            self.project_start_date = datetime.strptime(project_start_date_str, "%Y-%m-%d").date() if project_start_date_str else datetime.now().date()
        except Exception:
            self.project_start_date = datetime.now().date()

        try:
            self.project_deadline = datetime.strptime(project_deadline_str, "%Y-%m-%d").date() if project_deadline_str else None
        except Exception:
            self.project_deadline = None

        self.current_date = current_date or datetime.now().date()

    def analyze(self):
        """
        Analyzes the project risk.
        Returns:
            - overall_risk_level: 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
            - risk_score: 0 - 100
            - explanation: why the project has this risk level
            - risk_factors: list of detailed risk points
            - task_risks: list of task-specific risk evaluations
        """
        cpm = CriticalPathAnalysis(self.graph, self.project_start_date.strftime("%Y-%m-%d")).calculate()
        if cpm.get("has_cycle"):
            return {
                "overall_risk_level": "CRITICAL",
                "risk_score": 100,
                "explanation": "Critical circular dependency detected in tasks. Project execution is blocked.",
                "risk_factors": [{"factor": "Circular Dependency", "severity": "CRITICAL", "description": cpm.get("error")}],
                "task_risks": []
            }

        task_schedules = cpm["task_schedules"]
        est_finish_date = datetime.strptime(cpm["estimated_finish_date"], "%Y-%m-%d").date()

        risk_score = 15  # Baseline minimal operational uncertainty
        risk_factors = []
        task_risks = []

        # 1. Project Deadline Buffer Analysis
        deadline_slack = None
        if self.project_deadline:
            deadline_slack = (self.project_deadline - est_finish_date).days
            if deadline_slack < 0:
                risk_score += 45
                risk_factors.append({
                    "factor": "Project Deadline Breach",
                    "severity": "CRITICAL",
                    "description": f"Estimated project finish ({est_finish_date}) exceeds hard project deadline ({self.project_deadline}) by {abs(deadline_slack)} days."
                })
            elif deadline_slack == 0:
                risk_score += 30
                risk_factors.append({
                    "factor": "Zero Project Buffer",
                    "severity": "HIGH",
                    "description": f"Estimated project finish ({est_finish_date}) matches project deadline exactly. Any subsequent delay will breach the deadline."
                })
            elif deadline_slack <= 2:
                risk_score += 20
                risk_factors.append({
                    "factor": "Razor-Thin Buffer",
                    "severity": "MEDIUM",
                    "description": f"Project deadline buffer is only {deadline_slack} days. Minimal margin for unforeseen bottlenecks."
                })
            else:
                risk_factors.append({
                    "factor": "Healthy Buffer",
                    "severity": "LOW",
                    "description": f"Project has a comfortable buffer of {deadline_slack} days before the deadline."
                })

        # 2. Individual Task Risk Assessments
        critical_count = 0
        overdue_count = 0
        at_risk_count = 0

        for task_id, sched in task_schedules.items():
            t_data = self.graph.nodes.get(task_id, {})
            name = sched["name"]
            status = sched["status"]
            priority = sched["priority"]
            is_critical = sched["is_critical"]
            total_float = sched["total_float"]
            deadline_str = t_data.get("deadline")
            
            task_deadline = None
            if deadline_str:
                try:
                    task_deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
                except Exception:
                    pass

            t_score = 0
            t_factors = []
            
            # Check overdue status
            is_overdue = False
            if task_deadline and status != "Completed" and self.current_date > task_deadline:
                is_overdue = True
                overdue_count += 1
                t_score += 40
                t_factors.append(f"Task is overdue by {(self.current_date - task_deadline).days} days.")

            # Check critical path
            if is_critical:
                critical_count += 1
                t_score += 25
                t_factors.append("Task lies on the Critical Path (Zero Total Float). Any delay delays the entire project.")

            # Check current status
            if status == "Delayed":
                t_score += 35
                t_factors.append("Task is actively marked as Delayed.")
            elif status == "At Risk":
                t_score += 25
                at_risk_count += 1
                t_factors.append("Task is flagged as At Risk by team leads.")

            # High/Critical priority sensitivity
            if priority in ["High", "Critical"] and is_critical:
                t_score += 15
                t_factors.append(f"{priority} priority task with zero float.")

            # Determine task risk level
            if t_score >= 60:
                t_level = "CRITICAL"
            elif t_score >= 40:
                t_level = "HIGH"
            elif t_score >= 20:
                t_level = "MEDIUM"
            else:
                t_level = "LOW"

            task_risks.append({
                "task_id": task_id,
                "name": name,
                "assigned_to": sched["assigned_to"],
                "status": status,
                "priority": priority,
                "is_critical": is_critical,
                "total_float": total_float,
                "is_overdue": is_overdue,
                "risk_level": t_level,
                "risk_score": min(100, t_score),
                "reasons": t_factors if t_factors else ["Task is proceeding within expected parameters with sufficient buffer."]
            })

        # Aggregated risk score increments
        if overdue_count > 0:
            risk_score += min(30, overdue_count * 15)
            risk_factors.append({
                "factor": "Overdue Tasks Present",
                "severity": "CRITICAL" if overdue_count > 1 else "HIGH",
                "description": f"{overdue_count} task(s) currently exceed their target completion deadlines."
            })

        if at_risk_count > 0:
            risk_score += min(20, at_risk_count * 10)
            risk_factors.append({
                "factor": "Tasks Flagged At Risk",
                "severity": "HIGH",
                "description": f"{at_risk_count} task(s) have been flagged as experiencing potential delivery obstacles."
            })

        # Ratio of critical tasks
        crit_ratio = critical_count / max(1, len(task_schedules))
        if crit_ratio > 0.7:
            risk_score += 10
            risk_factors.append({
                "factor": "High Critical Path Density",
                "severity": "MEDIUM",
                "description": f"{int(crit_ratio * 100)}% of tasks are on the critical path, creating high dependency rigidity."
            })

        risk_score = max(5, min(100, risk_score))

        # Classify overall risk level
        if risk_score >= 75:
            overall_level = "CRITICAL"
            summary_desc = "Project completion is severely threatened by overdue milestones or negative schedule slack. Immediate intervention required."
        elif risk_score >= 50:
            overall_level = "HIGH"
            summary_desc = "Significant schedule vulnerability detected. Critical path tasks have thin or zero safety margins."
        elif risk_score >= 30:
            overall_level = "MEDIUM"
            summary_desc = "Moderate risk. Project is currently viable, but key dependencies require vigilant monitoring."
        else:
            overall_level = "LOW"
            summary_desc = "Project is in good health with acceptable buffers and no critical path bottlenecks."

        return {
            "overall_risk_level": overall_level,
            "risk_score": risk_score,
            "explanation": summary_desc,
            "deadline_slack_days": deadline_slack,
            "overdue_tasks_count": overdue_count,
            "critical_tasks_count": critical_count,
            "at_risk_tasks_count": at_risk_count,
            "risk_factors": risk_factors,
            "task_risks": sorted(task_risks, key=lambda x: x["risk_score"], reverse=True)
        }

