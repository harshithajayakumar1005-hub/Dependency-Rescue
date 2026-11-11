from datetime import datetime, timedelta
from algorithms.graph import DirectedGraph
from algorithms.cpm import CriticalPathAnalysis

class DelaySimulator:
    """
    Simulates hypothetical task delays and analyzes downstream delay propagation
    without mutating or modifying persistent database records.
    """

    def __init__(self, graph: DirectedGraph, project_start_date_str=None, project_deadline_str=None):
        self.graph = graph
        try:
            self.project_start_date = datetime.strptime(project_start_date_str, "%Y-%m-%d").date() if project_start_date_str else datetime.now().date()
        except Exception:
            self.project_start_date = datetime.now().date()

        try:
            self.project_deadline = datetime.strptime(project_deadline_str, "%Y-%m-%d").date() if project_deadline_str else None
        except Exception:
            self.project_deadline = None

    def simulate(self, selected_task_id: int, delay_days: int):
        """
        Simulates adding `delay_days` to `selected_task_id`.
        Returns baseline vs simulated metrics, affected tasks breakdown, and schedule comparison.
        """
        top_order = self.graph.topological_sort()
        if top_order is None:
            return {
                "error": "Cannot simulate: Project has circular dependencies.",
                "has_cycle": True
            }

        if selected_task_id not in self.graph.nodes:
            return {
                "error": f"Task ID {selected_task_id} not found in project.",
                "has_cycle": False
            }

        # 1. Baseline CPM Calculation
        cpm = CriticalPathAnalysis(self.graph, self.project_start_date.strftime("%Y-%m-%d")).calculate()
        baseline_schedules = cpm["task_schedules"]
        baseline_duration = cpm["project_duration_days"]
        baseline_finish_date = datetime.strptime(cpm["estimated_finish_date"], "%Y-%m-%d").date()

        # 2. Simulated Forward Pass
        durations = {u: max(1, int(self.graph.nodes[u].get("duration", 1))) for u in top_order}
        
        sim_es = {}
        sim_ef = {}

        for u in top_order:
            preds = self.graph.get_predecessors(u)
            if not preds:
                sim_es[u] = 0
            else:
                sim_es[u] = max(sim_ef[p] for p in preds)

            added_delay = delay_days if u == selected_task_id else 0
            sim_ef[u] = sim_es[u] + durations[u] + added_delay

        sim_project_duration = max(sim_ef.values()) if sim_ef else 0
        sim_finish_date = self.project_start_date + timedelta(days=sim_project_duration)
        total_project_delay = sim_project_duration - baseline_duration

        # 3. BFS to identify direct vs indirect downstream reachability
        bfs_info = self.graph.bfs_downstream(selected_task_id)
        direct_reachable_set = set(bfs_info["direct_dependents"])
        indirect_reachable_set = set(bfs_info["indirect_dependents"])

        # 4. Analyze affected tasks (tasks whose completion was actually pushed by the delay)
        direct_affected = []
        indirect_affected = []
        task_comparisons = []

        for u in top_order:
            base_info = baseline_schedules[u]
            base_es_days = base_info["es_days"]
            base_ef_days = base_info["ef_days"]

            s_es_days = sim_es[u]
            s_ef_days = sim_ef[u]

            task_slip_days = s_ef_days - base_ef_days
            is_affected = (task_slip_days > 0 and u != selected_task_id)

            is_direct = (u in direct_reachable_set and is_affected)
            is_indirect = (u in indirect_reachable_set and is_affected)

            if is_direct:
                direct_affected.append(u)
            elif is_indirect:
                indirect_affected.append(u)

            base_start_dt = self.project_start_date + timedelta(days=base_es_days)
            base_end_dt = self.project_start_date + timedelta(days=base_ef_days)
            sim_start_dt = self.project_start_date + timedelta(days=s_es_days)
            sim_end_dt = self.project_start_date + timedelta(days=s_ef_days)

            node_data = self.graph.nodes[u]
            task_comparisons.append({
                "task_id": u,
                "name": node_data.get("name", f"Task {u}"),
                "assigned_to": node_data.get("assignee_name", "Unassigned"),
                "status": node_data.get("status", "Not Started"),
                "priority": node_data.get("priority", "Medium"),
                "is_selected": (u == selected_task_id),
                "is_critical": base_info["is_critical"],
                "total_float": base_info["total_float"],
                "baseline_duration": durations[u],
                "simulated_duration": durations[u] + (delay_days if u == selected_task_id else 0),
                "baseline_start": base_start_dt.strftime("%Y-%m-%d"),
                "baseline_end": base_end_dt.strftime("%Y-%m-%d"),
                "simulated_start": sim_start_dt.strftime("%Y-%m-%d"),
                "simulated_end": sim_end_dt.strftime("%Y-%m-%d"),
                "delay_experienced_days": task_slip_days,
                "is_affected": is_affected,
                "impact_type": "Direct" if is_direct else ("Indirect" if is_indirect else ("Trigger" if u == selected_task_id else "Unaffected"))
            })

        # 5. Project Deadline Assessment
        deadline_breached = False
        days_overdue = 0
        baseline_slack = None
        simulated_slack = None

        if self.project_deadline:
            deadline_breached = sim_finish_date > self.project_deadline
            if deadline_breached:
                days_overdue = (sim_finish_date - self.project_deadline).days
            baseline_slack = (self.project_deadline - baseline_finish_date).days
            simulated_slack = (self.project_deadline - sim_finish_date).days

        selected_node = self.graph.nodes[selected_task_id]

        return {
            "selected_task": {
                "id": selected_task_id,
                "name": selected_node.get("name", f"Task {selected_task_id}"),
                "delay_days": delay_days,
                "is_critical": baseline_schedules[selected_task_id]["is_critical"]
            },
            "summary": {
                "baseline_duration_days": baseline_duration,
                "simulated_duration_days": sim_project_duration,
                "total_project_delay_days": total_project_delay,
                "baseline_finish_date": baseline_finish_date.strftime("%Y-%m-%d"),
                "simulated_finish_date": sim_finish_date.strftime("%Y-%m-%d"),
                "project_deadline": self.project_deadline.strftime("%Y-%m-%d") if self.project_deadline else "None",
                "deadline_breached": deadline_breached,
                "days_overdue": days_overdue,
                "baseline_slack_days": baseline_slack,
                "simulated_slack_days": simulated_slack,
                "direct_affected_count": len(direct_affected),
                "indirect_affected_count": len(indirect_affected),
                "total_affected_count": len(direct_affected) + len(indirect_affected)
            },
            "affected_task_ids": {
                "direct": direct_affected,
                "indirect": indirect_affected,
                "all": direct_affected + indirect_affected
            },
            "task_comparisons": task_comparisons
        }

