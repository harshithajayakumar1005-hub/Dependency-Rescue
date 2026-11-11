from datetime import datetime, timedelta
from algorithms.graph import DirectedGraph

class CriticalPathAnalysis:
    """
    Implements the Critical Path Method (CPM) using Forward Pass and Backward Pass.
    Calculates Earliest Start (ES), Earliest Finish (EF), Latest Start (LS),
    Latest Finish (LF), Total Float (TF), Free Float (FF), and identifies Critical Tasks & Paths.
    """

    def __init__(self, graph: DirectedGraph, project_start_date_str=None):
        self.graph = graph
        self.project_start_date = None
        if project_start_date_str:
            try:
                self.project_start_date = datetime.strptime(project_start_date_str, "%Y-%m-%d").date()
            except ValueError:
                self.project_start_date = datetime.now().date()
        else:
            self.project_start_date = datetime.now().date()

    def calculate(self):
        """
        Runs CPM on the graph.
        Returns a dictionary with comprehensive CPM metrics, task schedules, and critical paths.
        """
        top_order = self.graph.topological_sort()
        if top_order is None:
            return {
                "error": "Cannot calculate Critical Path: Circular dependency detected in project tasks.",
                "has_cycle": True
            }

        # Initialize schedule data
        es = {}
        ef = {}
        durations = {}

        for node_id in top_order:
            node_data = self.graph.nodes.get(node_id, {})
            durations[node_id] = max(1, int(node_data.get("duration", 1)))

        # --- 1. FORWARD PASS ---
        # ES(i) = max(EF(predecessors)) or 0
        # EF(i) = ES(i) + duration(i)
        for u in top_order:
            preds = self.graph.get_predecessors(u)
            if not preds:
                es[u] = 0
            else:
                es[u] = max(ef[p] for p in preds)
            ef[u] = es[u] + durations[u]

        # Total project duration (critical path duration in days)
        project_duration = max(ef.values()) if ef else 0

        # --- 2. BACKWARD PASS ---
        # LF(i) = min(LS(successors)) or project_duration
        # LS(i) = LF(i) - duration(i)
        lf = {}
        ls = {}
        for u in reversed(top_order):
            succs = self.graph.get_successors(u)
            if not succs:
                lf[u] = project_duration
            else:
                lf[u] = min(ls[s] for s in succs)
            ls[u] = lf[u] - durations[u]

        # --- 3. FLOAT CALCULATIONS & CRITICAL TASKS ---
        total_float = {}
        free_float = {}
        critical_tasks = []
        task_results = {}

        for u in top_order:
            tf = ls[u] - es[u]
            total_float[u] = tf

            succs = self.graph.get_successors(u)
            if not succs:
                ff = project_duration - ef[u]
            else:
                ff = min(es[s] for s in succs) - ef[u]
            free_float[u] = max(0, ff)

            is_critical = (tf == 0)
            if is_critical:
                critical_tasks.append(u)

            # Calculate calendar dates
            cal_es = self.project_start_date + timedelta(days=es[u])
            cal_ef = self.project_start_date + timedelta(days=ef[u])
            cal_ls = self.project_start_date + timedelta(days=ls[u])
            cal_lf = self.project_start_date + timedelta(days=lf[u])

            node_data = self.graph.nodes.get(u, {})
            task_results[u] = {
                "task_id": u,
                "name": node_data.get("name", f"Task {u}"),
                "duration": durations[u],
                "assigned_to": node_data.get("assignee_name", "Unassigned"),
                "status": node_data.get("status", "Not Started"),
                "priority": node_data.get("priority", "Medium"),
                "es_days": es[u],
                "ef_days": ef[u],
                "ls_days": ls[u],
                "lf_days": lf[u],
                "total_float": tf,
                "free_float": free_float[u],
                "is_critical": is_critical,
                "es_date": cal_es.strftime("%Y-%m-%d"),
                "ef_date": cal_ef.strftime("%Y-%m-%d"),
                "ls_date": cal_ls.strftime("%Y-%m-%d"),
                "lf_date": cal_lf.strftime("%Y-%m-%d"),
                "predecessors": self.graph.get_predecessors(u),
                "successors": self.graph.get_successors(u)
            }

        # --- 4. IDENTIFY CRITICAL PATH CHAINS ---
        critical_set = set(critical_tasks)
        critical_edges = []
        for u in critical_tasks:
            for v in self.graph.get_successors(u):
                if v in critical_set and ef[u] == es[v]:
                    critical_edges.append((u, v))

        # Build paths along critical edges
        critical_paths = []
        start_criticals = [n for n in critical_tasks if not [p for p in self.graph.get_predecessors(n) if p in critical_set]]
        
        def build_critical_paths(curr, path):
            next_crit = [v for v in self.graph.get_successors(curr) if v in critical_set and ef[curr] == es[v]]
            if not next_crit:
                critical_paths.append(list(path))
                return
            for nxt in next_crit:
                path.append(nxt)
                build_critical_paths(nxt, path)
                path.pop()

        for start_node in start_criticals:
            build_critical_paths(start_node, [start_node])

        # Overall estimated finish date
        est_finish_date = self.project_start_date + timedelta(days=project_duration)

        return {
            "has_cycle": False,
            "project_duration_days": project_duration,
            "project_start_date": self.project_start_date.strftime("%Y-%m-%d"),
            "estimated_finish_date": est_finish_date.strftime("%Y-%m-%d"),
            "critical_task_ids": critical_tasks,
            "critical_edges": critical_edges,
            "critical_paths": critical_paths,
            "task_schedules": task_results,
            "total_tasks": len(top_order),
            "critical_tasks_count": len(critical_tasks)
        }

