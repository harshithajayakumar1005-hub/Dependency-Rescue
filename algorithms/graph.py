from collections import deque, defaultdict

class DirectedGraph:
    """
    Directed Graph representation for project task dependencies.
    An edge (u, v) indicates that task u must be completed before task v can start.
    (u is predecessor, v is successor/dependent).
    """

    def __init__(self):
        self.nodes = {}           # node_id -> node_data dict
        self.adj = defaultdict(list)     # predecessor -> list of successors
        self.rev_adj = defaultdict(list) # successor -> list of predecessors

    def add_node(self, node_id, data=None):
        """Adds a task node with optional metadata."""
        self.nodes[node_id] = data or {}
        if node_id not in self.adj:
            self.adj[node_id] = []
        if node_id not in self.rev_adj:
            self.rev_adj[node_id] = []

    def add_edge(self, u, v):
        """Adds a directed dependency: u -> v."""
        if u not in self.nodes:
            self.add_node(u)
        if v not in self.nodes:
            self.add_node(v)
        if v not in self.adj[u]:
            self.adj[u].append(v)
        if u not in self.rev_adj[v]:
            self.rev_adj[v].append(u)

    def get_successors(self, u):
        """Returns direct downstream tasks that depend on u."""
        return list(self.adj.get(u, []))

    def get_predecessors(self, v):
        """Returns direct upstream tasks that v depends on."""
        return list(self.rev_adj.get(v, []))

    def bfs_downstream(self, start_id):
        """
        Executes Breadth-First Search (BFS) from start_id to explore all downstream tasks level-by-level.
        Distinguishes between Direct Dependent Tasks (Level 1) and Indirect Dependent Tasks (Level 2+).
        """
        if start_id not in self.nodes:
            return {
                "start_id": start_id,
                "direct_dependents": [],
                "indirect_dependents": [],
                "all_downstream": [],
                "levels": {},
                "total_affected": 0
            }

        visited = {start_id: 0}
        queue = deque([(start_id, 0)])
        levels = defaultdict(list)

        while queue:
            curr, level = queue.popleft()
            for succ in self.adj.get(curr, []):
                if succ not in visited:
                    visited[succ] = level + 1
                    levels[level + 1].append(succ)
                    queue.append((succ, level + 1))

        direct = levels.get(1, [])
        indirect = []
        for lvl in sorted(levels.keys()):
            if lvl > 1:
                indirect.extend(levels[lvl])

        all_downstream = direct + indirect

        return {
            "start_id": start_id,
            "direct_dependents": direct,
            "indirect_dependents": indirect,
            "all_downstream": all_downstream,
            "levels": dict(levels),
            "total_affected": len(all_downstream)
        }

    def dfs_chains(self, start_id):
        """
        Executes Depth-First Search (DFS) to traverse complete downstream dependency chains starting from start_id.
        Returns all paths from start_id to terminal downstream tasks.
        """
        if start_id not in self.nodes:
            return []

        chains = []

        def dfs(current, current_path, visited_in_path):
            successors = self.adj.get(current, [])
            if not successors:
                chains.append(list(current_path))
                return

            for succ in successors:
                if succ not in visited_in_path:
                    visited_in_path.add(succ)
                    current_path.append(succ)
                    dfs(succ, current_path, visited_in_path)
                    current_path.pop()
                    visited_in_path.remove(succ)
                else:
                    # Detected path revisit / potential cycle in path
                    cycle_subpath = current_path[current_path.index(succ):] + [succ]
                    chains.append(list(current_path) + [f"Cycle to {succ}"])

        dfs(start_id, [start_id], {start_id})
        return chains

    def find_cycle(self):
        """
        Uses 3-color DFS (WHITE=0, GRAY=1, BLACK=2) to detect any directed cycle in the graph.
        Returns:
            (has_cycle: bool, cycle_path: list of node_ids or None)
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node: WHITE for node in self.nodes}
        parent = {}
        cycle_path = []

        def dfs(u):
            nonlocal cycle_path
            color[u] = GRAY
            for v in self.adj.get(u, []):
                if color.get(v, WHITE) == GRAY:
                    # Cycle found: reconstruct path from v to u, then back to v
                    curr = u
                    path = [v, curr]
                    while curr != v and curr in parent:
                        curr = parent[curr]
                        path.append(curr)
                    cycle_path = list(reversed(path))
                    return True
                if color.get(v, WHITE) == WHITE:
                    parent[v] = u
                    if dfs(v):
                        return True
            color[u] = BLACK
            return False

        for node in list(self.nodes.keys()):
            if color[node] == WHITE:
                if dfs(node):
                    return True, cycle_path

        return False, []

    def would_create_cycle(self, u, v):
        """
        Checks if adding an edge u -> v would create a cycle.
        An edge u -> v creates a cycle if and only if:
        1. u == v (self-loop)
        2. There is already a path from v to u (which would complete a loop v -> ... -> u -> v).
        """
        if u == v:
            return True, [u, u]

        # Check if u is reachable from v
        queue = deque([v])
        visited = {v}
        parent = {}

        while queue:
            curr = queue.popleft()
            if curr == u:
                # Reconstruct cycle path: v -> ... -> u -> v
                path = [u]
                step = u
                while step != v and step in parent:
                    step = parent[step]
                    path.append(step)
                cycle_path = list(reversed(path)) + [v]
                return True, cycle_path

            for neighbor in self.adj.get(curr, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    parent[neighbor] = curr
                    queue.append(neighbor)

        return False, []

    def topological_sort(self):
        """
        Kahn's Algorithm for Topological Sort.
        Returns valid ordering of node_ids, or None if a cycle exists.
        """
        in_degree = {n: 0 for n in self.nodes}
        for u in self.adj:
            for v in self.adj[u]:
                if v in in_degree:
                    in_degree[v] += 1

        queue = deque([n for n, deg in in_degree.items() if deg == 0])
        order = []

        while queue:
            u = queue.popleft()
            order.append(u)
            for v in self.adj.get(u, []):
                if v in in_degree:
                    in_degree[v] -= 1
                    if in_degree[v] == 0:
                        queue.append(v)

        if len(order) == len(self.nodes):
            return order
        return None  # Graph has a cycle

    @classmethod
    def build_from_db(cls, project_id, conn):
        """Builds a DirectedGraph instance from database records for a given project."""
        graph = cls()
        cursor = conn.cursor()

        # Load tasks
        cursor.execute('''
            SELECT t.id, t.name, t.duration, t.start_date, t.deadline, t.status, t.priority,
                   tm.name as assignee_name, tm.avatar_color
            FROM tasks t
            LEFT JOIN team_members tm ON t.assigned_to = tm.id
            WHERE t.project_id = ?
            ORDER BY t.id
        ''', (project_id,))
        tasks = cursor.fetchall()

        for t in tasks:
            graph.add_node(t['id'], dict(t))

        # Load dependencies
        cursor.execute('''
            SELECT predecessor_id, successor_id
            FROM dependencies
            WHERE project_id = ?
        ''', (project_id,))
        deps = cursor.fetchall()

        for d in deps:
            graph.add_edge(d['predecessor_id'], d['successor_id'])

        return graph

