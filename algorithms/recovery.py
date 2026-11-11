from datetime import datetime, timedelta
from algorithms.graph import DirectedGraph
from algorithms.cpm import CriticalPathAnalysis
from algorithms.risk import RiskAnalyzer

class RecoveryEngine:
    """
    Analyzes project dependencies, critical paths, and simulated/actual delays
    to formulate actionable, prioritized recovery recommendations.
    """

    def __init__(self, graph: DirectedGraph, project_start_date_str=None, project_deadline_str=None, team_members_data=None):
        self.graph = graph
        self.project_start_date_str = project_start_date_str
        self.project_deadline_str = project_deadline_str
        self.team_members = team_members_data or []

    def generate_suggestions(self, simulation_result=None):
        """
        Generates structured, intelligent recovery strategies based on the current
        project state or an active hypothetical delay simulation.
        """
        cpm = CriticalPathAnalysis(self.graph, self.project_start_date_str).calculate()
        if cpm.get("has_cycle"):
            return [{
                "id": "REC-00",
                "title": "Resolve Circular Dependency",
                "type": "Architecture Fix",
                "priority": "Critical",
                "recommendation": "Break the circular dependency cycle in the project task graph.",
                "reason": "Circular dependencies halt scheduling calculations and freeze project pipeline execution.",
                "expected_impact": "Restores mathematical validity to project timeline and enables pipeline resumption."
            }]

        risk_analysis = RiskAnalyzer(self.graph, self.project_start_date_str, self.project_deadline_str).analyze()
        suggestions = []
        rec_counter = 1

        task_schedules = cpm["task_schedules"]
        critical_task_ids = cpm["critical_task_ids"]

        # Check if we are analyzing a simulated scenario or baseline
        is_simulation = simulation_result is not None
        deadline_breached = False
        overdue_days = 0

        if is_simulation:
            summary = simulation_result.get("summary", {})
            deadline_breached = summary.get("deadline_breached", False)
            overdue_days = summary.get("days_overdue", 0)
            delayed_task_id = simulation_result.get("selected_task", {}).get("id")
            delayed_task_name = simulation_result.get("selected_task", {}).get("name")
        else:
            deadline_slack = risk_analysis.get("deadline_slack_days")
            if deadline_slack is not None and deadline_slack < 0:
                deadline_breached = True
                overdue_days = abs(deadline_slack)

        # 1. Critical Path Crashing (Schedule Compression)
        # Find critical tasks with duration >= 3 days that could be compressed by adding personnel
        crashable_tasks = [
            task_schedules[tid] for tid in critical_task_ids
            if task_schedules[tid]["duration"] >= 3
        ]

        if crashable_tasks:
            target = crashable_tasks[0]
            recoverable_days = max(1, target["duration"] // 2)
            suggestions.append({
                "id": f"REC-0{rec_counter}",
                "title": f"Crash Critical Path: '{target['name']}'",
                "type": "Schedule Compression (Crashing)",
                "priority": "High" if deadline_breached else "Medium",
                "recommendation": f"Allocate secondary developers or pair-programming support to '{target['name']}' to compress duration from {target['duration']} to {target['duration'] - recoverable_days} days.",
                "reason": f"'{target['name']}' is on the critical path with zero total float. Shortening it immediately reduces project completion date.",
                "expected_impact": f"Recovers approximately {recoverable_days} working day(s) across all downstream milestones."
            })
            rec_counter += 1

        # 2. Fast-Tracking (Parallel Task Execution)
        # Identify consecutive dependent tasks that could partially overlap
        for u in critical_task_ids:
            succs = [s for s in self.graph.get_successors(u) if s in critical_task_ids]
            if succs:
                v = succs[0]
                u_name = task_schedules[u]["name"]
                v_name = task_schedules[v]["name"]
                suggestions.append({
                    "id": f"REC-0{rec_counter}",
                    "title": f"Fast-Track Dependencies: '{u_name}' & '{v_name}'",
                    "type": "Fast-Tracking (Parallelism)",
                    "priority": "High" if deadline_breached else "Medium",
                    "recommendation": f"Stage a soft handoff: start preliminary work on '{v_name}' when '{u_name}' is 50% complete rather than strictly sequential finish-to-start.",
                    "reason": f"Overlapping these two critical milestones removes sequential blocking idle time.",
                    "expected_impact": f"Potential savings of 1-2 days on downstream critical path schedule."
                })
                rec_counter += 1
                break

        # 3. Workload Redistribution / Member Rebalancing
        # Check team member workload if member data is available
        member_task_counts = {}
        for tid, sched in task_schedules.items():
            assignee = sched.get("assigned_to")
            if assignee and assignee != "Unassigned":
                member_task_counts[assignee] = member_task_counts.get(assignee, 0) + 1

        if member_task_counts:
            sorted_workload = sorted(member_task_counts.items(), key=lambda x: x[1], reverse=True)
            max_worker = sorted_workload[0]
            min_worker = sorted_workload[-1]

            if max_worker[1] >= 2 and min_worker[1] <= 1:
                suggestions.append({
                    "id": f"REC-0{rec_counter}",
                    "title": f"Rebalance Team Load: {max_worker[0]} → {min_worker[0]}",
                    "type": "Resource Rebalancing",
                    "priority": "Medium",
                    "recommendation": f"Transfer non-critical backlog tasks from {max_worker[0]} ({max_worker[1]} assigned tasks) to {min_worker[0]} ({min_worker[1]} assigned tasks).",
                    "reason": f"Heavy task concentration on single contributors introduces bottleneck vulnerability.",
                    "expected_impact": "Prevents burnout delays and ensures critical tasks receive undivided developer focus."
                })
                rec_counter += 1

        # 4. Float Utilization on Non-Critical Tasks
        tasks_with_float = [
            task_schedules[tid] for tid in task_schedules
            if task_schedules[tid]["total_float"] > 0
        ]
        if tasks_with_float:
            f_task = max(tasks_with_float, key=lambda x: x["total_float"])
            suggestions.append({
                "id": f"REC-0{rec_counter}",
                "title": f"Exploit Schedule Float: '{f_task['name']}'",
                "type": "Float Optimization",
                "priority": "Low",
                "recommendation": f"Temporarily de-prioritize '{f_task['name']}' and utilize its {f_task['total_float']} days of total float.",
                "reason": f"This task has generous slack and can be safely delayed without impacting the final project deadline.",
                "expected_impact": "Frees up developer bandwidth for critical path blockers without penalty."
            })
            rec_counter += 1

        # 5. Deadline Renegotiation or Scope Review (if breached)
        if deadline_breached:
            suggestions.append({
                "id": f"REC-0{rec_counter}",
                "title": "Stakeholder Deadline Alignment",
                "type": "Scope & Governance",
                "priority": "Critical",
                "recommendation": f"Engage project stakeholders with the simulation impact report to negotiate a {overdue_days}-day deadline buffer extension or descope non-MVP requirements.",
                "reason": f"Simulated delays exceed available float and breach the commitment target by {overdue_days} day(s).",
                "expected_impact": "Restores project viability and sets transparent client expectations early."
            })
            rec_counter += 1

        # Ensure at least 3 recovery suggestions are always available
        if len(suggestions) < 3:
            suggestions.append({
                "id": f"REC-0{rec_counter}",
                "title": "Daily Standup Critical Path Review",
                "type": "Process Optimization",
                "priority": "Medium",
                "recommendation": "Implement 15-minute daily syncs focusing exclusively on unblocking active critical path tasks.",
                "reason": "Early detection of dependencies prevents compound downstream delays.",
                "expected_impact": "Reduces inter-task latency and prevents unforeseen blockers."
            })

        return suggestions

    def generate_executive_advisory(self, project_name, api_key=None, provider="gemini"):
        """
        Dual-mode executive recovery advisory:
        1. If api_key provided and online -> calls Google Gemini or OpenAI LLM API.
        2. If offline, timeout (>3.5s), or no key -> returns rich local heuristic advisory.
        """
        import os
        import json
        import urllib.request

        cpm = CriticalPathAnalysis(self.graph, self.project_start_date_str).calculate()
        risk = RiskAnalyzer(self.graph, self.project_start_date_str, self.project_deadline_str).analyze()
        suggestions = self.generate_suggestions()

        duration = cpm.get("project_duration_days", 0)
        critical_count = len(cpm.get("critical_task_ids", []))
        slack = risk.get("deadline_slack_days")
        overdue_count = risk.get("overdue_tasks_count", 0)
        risk_level = risk.get("overall_risk_level", "LOW")
        risk_score = risk.get("risk_score", 15)

        # Check for key in param or environment variables
        resolved_key = (api_key or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()

        if resolved_key:
            try:
                top_recs = "; ".join([s.get("title", "") for s in suggestions[:3]])
                prompt = (
                    f"You are an executive Agile Project Director and Scrum Coach. A software project titled '{project_name}' has: "
                    f"Critical Path: {duration} days ({critical_count} critical tasks with 0 float). "
                    f"Deadline Slack/Buffer: {slack} days. "
                    f"Overdue Tasks: {overdue_count}. "
                    f"Current Risk Level: {risk_level} (Score: {risk_score}/100). "
                    f"Algorithmic Action Recommendations: {top_recs}. "
                    f"Write a concise, high-impact 3-4 sentence Executive Recovery Brief with natural, professional advice for the engineering lead."
                )

                if provider.lower() == "openai" or resolved_key.startswith("sk-"):
                    url = "https://api.openai.com/v1/chat/completions"
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {resolved_key}"
                    }
                    payload = json.dumps({
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": "You are an executive project management advisor."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 250,
                        "temperature": 0.7
                    }).encode("utf-8")
                    req = urllib.request.Request(url, data=payload, headers=headers)
                    with urllib.request.urlopen(req, timeout=3.5) as resp:
                        res_data = json.loads(resp.read().decode("utf-8"))
                        text = res_data["choices"][0]["message"]["content"].strip()
                        return {
                            "mode": "cloud_llm",
                            "provider": "OpenAI (GPT-4o-mini)",
                            "status_badge": "Cloud AI Active (OpenAI)",
                            "is_online": True,
                            "text": text
                        }
                else:
                    # Default to Google Gemini 1.5 Flash
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={resolved_key}"
                    payload = json.dumps({
                        "contents": [{"parts": [{"text": prompt}]}]
                    }).encode("utf-8")
                    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=3.5) as resp:
                        res_data = json.loads(resp.read().decode("utf-8"))
                        text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        return {
                            "mode": "cloud_llm",
                            "provider": "Google Gemini 1.5 Flash",
                            "status_badge": "Cloud AI Active (Gemini)",
                            "is_online": True,
                            "text": text
                        }
            except Exception:
                # Silently catch network errors or timeouts and fallback smoothly
                pass

        # Offline Fallback Heuristic
        slack_desc = f"a razor-thin buffer of only {slack} day(s)" if (slack is not None and slack <= 2) else (f"a healthy buffer of {slack} days" if slack else "zero buffer")
        offline_brief = (
            f"Executive Recovery Brief for {project_name}: The project is currently evaluated at {risk_level} "
            f"(Score: {risk_score}/100) with {slack_desc} before the contractual deadline. "
            f"Because {critical_count} critical path milestones carry zero float flexibility, we recommend "
            f"immediately implementing '{suggestions[0]['title'] if suggestions else 'Schedule Compression'}' "
            f"and reallocating non-critical bandwidth to protect downstream milestone delivery."
        )

        return {
            "mode": "offline_heuristic",
            "provider": "Local Heuristic Engine",
            "status_badge": "Offline Mode Active (Local Rule Engine)",
            "is_online": False,
            "text": offline_brief
        }

