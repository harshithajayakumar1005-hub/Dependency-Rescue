/**
 * DEPENDENCY RESCUE - Full-Stack Application Logic
 * Implements SPA navigation, REST API interactions, Vis.js graph visualizations,
 * Chart.js dashboards, What-If delay simulations, and schedule risk assessments.
 */

const App = {
  // Global State
  activeProjectId: null,
  projects: [],
  tasks: [],
  teamMembers: [],
  dependencies: [],
  currentView: 'dashboard',

  // Network Graphs & Charts instances
  visNetwork: null,
  simVisNetwork: null,
  statusChart: null,
  progressChart: null,
  workloadChart: null,
  networkLayoutMode: 'hierarchical', // 'hierarchical' or 'physics'

  // User Authentication & Scoped RBAC State
  currentUser: {
    id: 1,
    username: 'alex',
    full_name: 'Alex Chen',
    avatar_color: '#8B5CF6',
    roles: {
      "1": { role_title: "Project Lead", is_lead: true },
      "2": { role_title: "Full-Stack Architect", is_lead: false },
      "3": { role_title: "Project Lead", is_lead: true }
    }
  },
  authUsers: [],

  // --- INITIALIZATION ---
  init() {
    this.bindEvents();
    this.initNetworkDetector();
    this.loadTeamMembers();
    this.loadAuthUsers();
    this.loadProjects().then(() => {
      this.updateUserSessionHeader();
      this.switchView('dashboard');
    });
  },

  bindEvents() {
    // Nav Items click
    document.querySelectorAll('.nav-item').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const view = item.getAttribute('data-view');
        this.switchView(view);
      });
    });

    // Active project change
    const projSelect = document.getElementById('active-project-select');
    if (projSelect) {
      projSelect.addEventListener('change', (e) => {
        this.setActiveProject(parseInt(e.target.value));
      });
    }

    // Persona Switcher
    const activeUserSel = document.getElementById('active-user-select');
    if (activeUserSel) {
      activeUserSel.addEventListener('change', (e) => {
        this.showToast(`Switched active persona to ${e.target.options[e.target.selectedIndex].text}`, 'info');
      });
    }

    // Load sample buttons
    const loadSampleBtn = document.getElementById('load-sample-btn');
    if (loadSampleBtn) loadSampleBtn.addEventListener('click', () => this.loadSampleProject());

    const projLoadSampleBtn = document.getElementById('projects-load-sample-btn');
    if (projLoadSampleBtn) projLoadSampleBtn.addEventListener('click', () => this.loadSampleProject());

    const loadComplexBtn = document.getElementById('load-complex-btn');
    if (loadComplexBtn) loadComplexBtn.addEventListener('click', () => this.loadComplexProject());

    const projLoadComplexBtn = document.getElementById('projects-load-complex-btn');
    if (projLoadComplexBtn) projLoadComplexBtn.addEventListener('click', () => this.loadComplexProject());

    // System reset button
    const sysResetBtn = document.getElementById('system-reset-db-btn');
    if (sysResetBtn) sysResetBtn.addEventListener('click', () => this.resetSystem());

    // Topbar action shortcuts
    document.getElementById('topbar-new-task-btn')?.addEventListener('click', () => this.openTaskModal());
    document.getElementById('topbar-simulate-btn')?.addEventListener('click', () => this.switchView('simulator'));
    document.getElementById('topbar-download-pdf-btn')?.addEventListener('click', () => this.downloadPDFReport());

    // Simulator slider sync
    const simInput = document.getElementById('sim-delay-input');
    const simSlider = document.getElementById('sim-delay-slider');
    if (simInput && simSlider) {
      simInput.addEventListener('input', () => { simSlider.value = simInput.value; });
      simSlider.addEventListener('input', () => { simInput.value = simSlider.value; });
    }

    // Simulator buttons
    document.getElementById('sim-run-btn')?.addEventListener('click', () => this.runSimulation());
    document.getElementById('sim-reset-btn')?.addEventListener('click', () => this.resetSimulation());

    // Dependency analysis buttons
    document.getElementById('dep-analyze-btn')?.addEventListener('click', () => {
      const tid = document.getElementById('dep-task-selector')?.value;
      if (tid) this.runTaskAnalysis(parseInt(tid));
    });
    document.getElementById('dep-fit-graph-btn')?.addEventListener('click', () => {
      if (this.visNetwork) this.visNetwork.fit({ animation: true });
    });
    document.getElementById('dep-toggle-layout-btn')?.addEventListener('click', () => this.toggleGraphLayout());
    document.getElementById('dep-add-dependency-btn')?.addEventListener('click', () => this.openDependencyModal());

    // Project search
    document.getElementById('project-search-input')?.addEventListener('input', (e) => {
      this.filterProjectsTable(e.target.value);
    });

    // Task filters
    ['task-search-input', 'task-filter-status', 'task-filter-priority', 'task-filter-assignee'].forEach(id => {
      document.getElementById(id)?.addEventListener('input', () => this.renderTasksTable());
      document.getElementById(id)?.addEventListener('change', () => this.renderTasksTable());
    });

    // System reset button
    document.getElementById('system-reset-db-btn')?.addEventListener('click', () => this.resetDatabase());
  },

  // --- NAVIGATION & VIEWS ---
  switchView(viewName) {
    this.currentView = viewName;

    // Update nav active state
    document.querySelectorAll('.nav-item').forEach(item => {
      if (item.getAttribute('data-view') === viewName) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    // Update view panels
    document.querySelectorAll('.view-panel').forEach(panel => {
      if (panel.id === `view-${viewName}`) {
        panel.classList.add('active');
      } else {
        panel.classList.remove('active');
      }
    });

    // Load data for specific view
    if (!this.activeProjectId && viewName !== 'projects' && viewName !== 'settings') {
      return;
    }

    switch (viewName) {
      case 'dashboard':
        this.loadDashboard();
        break;
      case 'projects':
        this.loadProjects();
        break;
      case 'tasks':
        this.loadTasks();
        break;
      case 'dependencies':
        this.loadDependencyAnalysis();
        break;
      case 'simulator':
        this.initSimulator();
        break;
      case 'risk-recovery':
        this.loadRiskRecovery();
        break;
      case 'workload':
        this.loadWorkload();
        break;
      case 'reports':
        this.loadReports();
        break;
      case 'daily-updates':
        this.loadDailyUpdates();
        break;
      case 'team-progress':
        this.loadTeamProgress();
        break;
      case 'ai-risk':
        this.loadAIRisk();
        break;
      case 'team-performance':
        this.loadTeamPerformance();
        break;
      case 'ai-recommendations':
        this.loadAIRecommendations();
        break;
    }
  },

  // --- TOAST NOTIFICATIONS ---
  showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let iconSvg = '';
    if (type === 'success') {
      iconSvg = `<svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="#10b981"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>`;
    } else if (type === 'error') {
      iconSvg = `<svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="#ef4444"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>`;
    } else {
      iconSvg = `<svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="#6366f1"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`;
    }

    toast.innerHTML = `
      <div style="flex-shrink:0;">${iconSvg}</div>
      <div style="flex:1;">${this.escapeHtml(message)}</div>
    `;

    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(40px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  },

  // --- PROJECTS MANAGEMENT ---
  async loadProjects() {
    try {
      const res = await fetch('/api/projects');
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      this.projects = data.projects;
      this.renderProjectSelector();
      this.renderProjectsTable();

      // Set active project if not set
      if (!this.activeProjectId && this.projects.length > 0) {
        await this.setActiveProject(this.projects[0].id, false);
      } else if (this.activeProjectId) {
        this.updateActiveProjectHeader();
      }

      document.getElementById('nav-project-count').textContent = this.projects.length;
    } catch (err) {
      console.error("Failed to load projects:", err);
      this.showToast(err.message, 'error');
    }
  },

  renderProjectSelector() {
    const select = document.getElementById('active-project-select');
    if (!select) return;

    select.innerHTML = '';
    this.projects.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = `${p.name} (#${p.id})`;
      if (p.id === this.activeProjectId) opt.selected = true;
      select.appendChild(opt);
    });
  },

  async setActiveProject(projectId, notify = true) {
    this.activeProjectId = projectId;
    const select = document.getElementById('active-project-select');
    if (select && parseInt(select.value) !== projectId) {
      select.value = projectId;
    }

    this.updateActiveProjectHeader();

    // 1. Fetch tasks for this active project
    await this.loadTasks();

    // 2. Re-render projects table if visible
    this.renderProjectsTable();

    // 3. Re-render active view so all metrics, charts, and tables update immediately
    if (this.currentView !== 'projects' && this.currentView !== 'settings') {
      this.switchView(this.currentView);
    }

    if (notify) {
      const proj = this.projects.find(p => p.id === projectId);
      const pName = proj ? proj.name : `#${projectId}`;
      this.showToast(`Switched active workspace to: ${pName}`, 'info');
    }
  },

  updateActiveProjectHeader() {
    const proj = this.projects.find(p => p.id === this.activeProjectId);
    if (!proj) return;

    this.updateUserSessionHeader();

    const descElem = document.getElementById('dashboard-project-desc');
    if (descElem) {
      descElem.textContent = proj.description || `Tracking schedule, critical paths, and dependencies for ${proj.name}.`;
    }

    const pills = [
      'dashboard-active-project-pill',
      'tasks-active-project-pill',
      'daily-active-project-pill',
      'progress-active-project-pill',
      'dep-active-project-pill',
      'sim-active-project-pill',
      'risk-active-project-pill',
      'workload-active-project-pill',
      'ai-active-project-pill',
      'perf-active-project-pill',
      'recom-active-project-pill'
    ];
    pills.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = `Project: ${proj.name} (#${proj.id})`;
    });
  },

  renderProjectsTable() {
    const tbody = document.getElementById('projects-table-body');
    if (!tbody) return;

    if (this.projects.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 24px; color: var(--text-muted);">No projects found. Create one or load the sample project.</td></tr>`;
      return;
    }

    tbody.innerHTML = this.projects.map(p => `
      <tr style="${p.id === this.activeProjectId ? 'background: rgba(99, 102, 241, 0.08);' : ''}">
        <td><b>#${p.id}</b></td>
        <td>
          <div style="font-weight: 700; color: #fff;">${this.escapeHtml(p.name)}</div>
          <div style="font-size: 11px; color: var(--text-muted);">${this.escapeHtml(p.description || '')}</div>
        </td>
        <td>
          <div style="font-size: 12px;">${p.start_date} ➔ ${p.deadline}</div>
        </td>
        <td>${this.renderStatusBadge(p.status)}</td>
        <td><b>${p.total_tasks || 0}</b> tasks</td>
        <td>
          <div style="display: flex; align-items: center; gap: 8px;">
            <div style="flex: 1; height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; overflow: hidden; min-width: 60px;">
              <div style="width: ${p.completion_percentage || 0}%; height: 100%; background: var(--status-completed);"></div>
            </div>
            <span style="font-size: 11px; font-weight: 700;">${p.completion_percentage || 0}%</span>
          </div>
        </td>
        <td style="text-align: right; white-space: nowrap;">
          ${p.id !== this.activeProjectId ? `
            <button class="quick-action-btn btn-secondary" style="padding: 4px 10px; font-size: 11px; display: inline-flex;" onclick="App.setActiveProject(${p.id})">Set Active</button>
          ` : `
            <span class="badge badge-completed" style="margin-right: 6px;">Active</span>
          `}
          <button class="quick-action-btn btn-secondary" style="padding: 4px 10px; font-size: 11px; display: inline-flex;" onclick="App.openProjectModal(${p.id})">Edit</button>
          <button class="quick-action-btn btn-danger" style="padding: 4px 10px; font-size: 11px; display: inline-flex;" onclick="App.deleteProject(${p.id})">Delete</button>
        </td>
      </tr>
    `).join('');
  },

  filterProjectsTable(query) {
    const q = query.toLowerCase().trim();
    document.querySelectorAll('#projects-table-body tr').forEach(row => {
      const text = row.innerText.toLowerCase();
      row.style.display = text.includes(q) ? '' : 'none';
    });
  },

  openProjectModal(projectId = null) {
    const modal = document.getElementById('project-modal');
    const title = document.getElementById('project-modal-title');
    const formId = document.getElementById('proj-form-id');
    const formName = document.getElementById('proj-form-name');
    const formDesc = document.getElementById('proj-form-desc');
    const formStart = document.getElementById('proj-form-start');
    const formDeadline = document.getElementById('proj-form-deadline');
    const formStatus = document.getElementById('proj-form-status');

    if (projectId) {
      const p = this.projects.find(x => x.id === projectId);
      if (!p) return;
      title.textContent = "Edit Project";
      formId.value = p.id;
      formName.value = p.name;
      formDesc.value = p.description || '';
      formStart.value = p.start_date;
      formDeadline.value = p.deadline;
      formStatus.value = p.status || 'Active';
    } else {
      title.textContent = "Create New Project";
      formId.value = "";
      formName.value = "";
      formDesc.value = "";
      const now = new Date();
      formStart.value = now.toISOString().split('T')[0];
      const future = new Date();
      future.setDate(future.getDate() + 21);
      formDeadline.value = future.toISOString().split('T')[0];
      formStatus.value = "Active";
    }

    modal.classList.add('active');
  },

  closeProjectModal() {
    document.getElementById('project-modal')?.classList.remove('active');
  },

  async saveProject() {
    const id = document.getElementById('proj-form-id').value;
    const name = document.getElementById('proj-form-name').value.trim();
    const description = document.getElementById('proj-form-desc').value.trim();
    const start_date = document.getElementById('proj-form-start').value;
    const deadline = document.getElementById('proj-form-deadline').value;
    const status = document.getElementById('proj-form-status').value;

    if (!name || !start_date || !deadline) {
      this.showToast("Please provide project name, start date, and deadline.", "error");
      return;
    }

    const payload = { name, description, start_date, deadline, status };
    try {
      let res;
      if (id) {
        res = await fetch(`/api/projects/${id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      } else {
        res = await fetch('/api/projects', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      }
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      this.showToast(data.message, 'success');
      this.closeProjectModal();
      await this.loadProjects();

      if (!id && data.project_id) {
        this.setActiveProject(data.project_id);
      }
    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  async deleteProject(projectId) {
    const p = this.projects.find(x => x.id === projectId);
    const name = p ? p.name : `#${projectId}`;
    if (!confirm(`Are you sure you want to permanently delete project '${name}' and all associated tasks?`)) {
      return;
    }

    try {
      const res = await fetch(`/api/projects/${projectId}`, { method: 'DELETE' });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      this.showToast(data.message, 'success');
      if (this.activeProjectId === projectId) {
        this.activeProjectId = null;
      }
      await this.loadProjects();
    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  async loadSampleProject() {
    try {
      const res = await fetch('/api/projects/sample', { method: 'POST' });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      this.showToast(data.message, 'success');
      await this.loadProjects();
      if (data.project_id) {
        this.setActiveProject(data.project_id);
      }
    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  // --- MODULE 1: DASHBOARD ---
  async loadDashboard() {
    if (!this.activeProjectId) return;

    try {
      const [projRes, tasksRes, cpmRes, logsRes] = await Promise.all([
        fetch(`/api/projects/${this.activeProjectId}`).then(r => r.json()),
        fetch(`/api/projects/${this.activeProjectId}/tasks`).then(r => r.json()),
        fetch(`/api/projects/${this.activeProjectId}/critical-path`).then(r => r.json()),
        fetch(`/api/activity-logs?project_id=${this.activeProjectId}`).then(r => r.json())
      ]);

      if (!projRes.success) throw new Error(projRes.error);
      const proj = projRes.project;
      const tasks = tasksRes.tasks || [];
      const cpm = cpmRes.cpm || {};
      const logs = logsRes.logs || [];

      // Update stat cards dynamically from actual database records
      const stats = proj.stats || {};
      document.getElementById('dash-total-projects').textContent = this.projects.length;
      document.getElementById('dash-total-tasks').textContent = stats.total_tasks || 0;
      document.getElementById('dash-completed-tasks').textContent = stats.completed_tasks || 0;
      document.getElementById('dash-pending-tasks').textContent = (stats.total_tasks || 0) - (stats.completed_tasks || 0);
      document.getElementById('dash-delayed-tasks').textContent = stats.delayed_tasks || 0;
      document.getElementById('dash-risk-tasks').textContent = stats.at_risk_tasks || 0;

      const completionPct = stats.completion_percentage || 0;
      document.getElementById('dash-completion-rate').textContent = `${completionPct}% overall completion rate`;

      // CPM summary badge
      const cpmSummary = document.getElementById('dash-critical-path-summary');
      if (cpm.has_cycle) {
        cpmSummary.textContent = "CIRCULAR DEPENDENCY DETECTED";
        cpmSummary.className = "badge badge-delayed";
      } else {
        cpmSummary.textContent = `Critical Path: ${cpm.project_duration_days || 0} Days (${(cpm.critical_task_ids || []).length} critical tasks)`;
        cpmSummary.className = "badge badge-critical-path";
      }

      // Render Charts
      this.renderStatusDoughnutChart(stats);
      this.renderProgressChart(tasks, cpm);

      // Render Upcoming Deadlines Table
      this.renderUpcomingDeadlines(tasks, cpm);

      // Render Activity Logs
      this.renderActivityLogs(logs);

    } catch (err) {
      console.error("Dashboard load failed:", err);
      this.showToast(err.message, 'error');
    }
  },

  renderStatusDoughnutChart(stats) {
    const ctx = document.getElementById('task-status-chart')?.getContext('2d');
    if (!ctx) return;

    if (this.statusChart) this.statusChart.destroy();

    const data = [
      stats.completed_tasks || 0,
      stats.in_progress_tasks || 0,
      stats.delayed_tasks || 0,
      stats.at_risk_tasks || 0,
      stats.not_started_tasks || 0
    ];

    this.statusChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Completed', 'In Progress', 'Delayed', 'At Risk', 'Not Started'],
        datasets: [{
          data: data,
          backgroundColor: ['#10B981', '#3B82F6', '#EF4444', '#F59E0B', '#64748B'],
          borderColor: '#1E293B',
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'right',
            labels: { color: '#94A3B8', font: { family: 'Inter', size: 11 } }
          }
        },
        cutout: '70%'
      }
    });
  },

  renderProgressChart(tasks, cpm) {
    const ctx = document.getElementById('project-progress-chart')?.getContext('2d');
    if (!ctx) return;

    if (this.progressChart) this.progressChart.destroy();

    const taskSchedules = cpm.task_schedules || {};
    const labels = [];
    const esData = [];
    const durationData = [];
    const colors = [];

    tasks.forEach(t => {
      labels.push(t.name.length > 20 ? t.name.substring(0, 18) + '...' : t.name);
      const sched = taskSchedules[t.id] || {};
      esData.push(sched.es_days || 0);
      durationData.push(t.duration || 1);
      colors.push(sched.is_critical ? '#F43F5E' : '#3B82F6');
    });

    this.progressChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Start Offset (Days)',
            data: esData,
            backgroundColor: 'transparent',
            borderColor: 'transparent',
            stack: 'Schedule'
          },
          {
            label: 'Duration (Days)',
            data: durationData,
            backgroundColor: colors,
            borderRadius: 4,
            stack: 'Schedule'
          }
        ]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (context) => {
                if (context.datasetIndex === 0) return null;
                const idx = context.dataIndex;
                const tid = tasks[idx].id;
                const sched = taskSchedules[tid] || {};
                return `Duration: ${context.raw}d | Float: ${sched.total_float || 0}d ${sched.is_critical ? '(CRITICAL)' : ''}`;
              }
            }
          }
        },
        scales: {
          x: {
            stacked: true,
            grid: { color: 'rgba(255,255,255,0.06)' },
            ticks: { color: '#94A3B8', font: { family: 'Inter' } },
            title: { display: true, text: 'Timeline Days', color: '#64748B' }
          },
          y: {
            stacked: true,
            grid: { display: false },
            ticks: { color: '#F8FAFC', font: { family: 'Inter', size: 12 } }
          }
        }
      }
    });
  },

  renderUpcomingDeadlines(tasks, cpm) {
    const tbody = document.getElementById('dash-upcoming-deadlines-body');
    if (!tbody) return;

    if (tasks.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 16px; color: var(--text-muted);">No tasks scheduled.</td></tr>`;
      return;
    }

    const taskSchedules = cpm.task_schedules || {};
    // Sort by deadline
    const sorted = [...tasks].sort((a, b) => new Date(a.deadline) - new Date(b.deadline)).slice(0, 5);

    tbody.innerHTML = sorted.map(t => {
      const sched = taskSchedules[t.id] || {};
      const float = sched.total_float !== undefined ? sched.total_float : 0;
      const slackBadge = sched.is_critical 
        ? `<span class="badge badge-critical-path">0d Slack (Critical)</span>`
        : `<span class="badge badge-completed">+${float}d Slack</span>`;

      return `
        <tr>
          <td><b style="color: #fff;">${this.escapeHtml(t.name)}</b></td>
          <td>${this.escapeHtml(t.assignee_name || 'Unassigned')}</td>
          <td><code>${t.deadline}</code></td>
          <td>${this.renderStatusBadge(t.status)}</td>
          <td>${slackBadge}</td>
        </tr>
      `;
    }).join('');
  },

  renderActivityLogs(logs) {
    const container = document.getElementById('dash-activity-list');
    if (!container) return;

    if (logs.length === 0) {
      container.innerHTML = `<div style="color: var(--text-muted); font-size: 12px;">No activity logged yet.</div>`;
      return;
    }

    container.innerHTML = logs.slice(0, 7).map(l => `
      <div style="display: flex; gap: 10px; font-size: 12px; align-items: flex-start; padding-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.04);">
        <div style="width: 7px; height: 7px; border-radius: 50%; background: var(--primary); margin-top: 5px; flex-shrink: 0;"></div>
        <div style="flex: 1;">
          <div style="display: flex; justify-content: space-between;">
            <b style="color: var(--text-primary);">${this.escapeHtml(l.action)}</b>
            <span style="font-size: 10px; color: var(--text-muted);">${(l.timestamp || '').split(' ')[1] || ''}</span>
          </div>
          <div style="color: var(--text-secondary); margin-top: 2px;">${this.escapeHtml(l.details || '')}</div>
        </div>
      </div>
    `).join('');
  },

  // --- MODULE 3: TASK MANAGEMENT & CRUD ---
  async loadTasks() {
    if (!this.activeProjectId) return;

    try {
      const uid = this.currentUser ? this.currentUser.id : 1;
      const res = await fetch(`/api/projects/${this.activeProjectId}/tasks?user_id=${uid}&role_filter=true`);
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      this.tasks = data.tasks;
      document.getElementById('nav-task-count').textContent = this.tasks.length;
      document.getElementById('task-table-count').textContent = this.tasks.length;

      // Update Task Privacy Banner
      const tPrivBanner = document.getElementById('task-privacy-banner');
      const tPrivText = document.getElementById('task-privacy-text');
      const tPrivIcon = document.getElementById('task-privacy-icon');
      if (tPrivBanner && tPrivText) {
        if (data.is_lead_view) {
          tPrivBanner.style.background = 'rgba(99, 102, 241, 0.15)';
          tPrivBanner.style.borderColor = 'rgba(99, 102, 241, 0.35)';
          tPrivBanner.style.color = '#c7d2fe';
          if (tPrivIcon) tPrivIcon.textContent = '👑';
          tPrivText.innerHTML = `<b>Project Lead Access (${this.escapeHtml(this.currentUser.full_name)}):</b> Full workspace visibility enabled. Viewing all ${data.total_project_tasks || this.tasks.length} team tasks.`;
        } else {
          tPrivBanner.style.background = 'rgba(245, 158, 11, 0.15)';
          tPrivBanner.style.borderColor = 'rgba(245, 158, 11, 0.35)';
          tPrivBanner.style.color = '#fde68a';
          if (tPrivIcon) tPrivIcon.textContent = '🔒';
          tPrivText.innerHTML = `<b>Private Member View (${this.escapeHtml(this.currentUser.full_name)} - ${this.escapeHtml(data.role_title)}):</b> Showing only tasks assigned to you. Other team members' tasks are hidden for data privacy.`;
        }
      }

      this.renderTasksTable();
      this.populateAssigneeFilter();
    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  populateAssigneeFilter() {
    const filter = document.getElementById('task-filter-assignee');
    if (!filter) return;
    const currentVal = filter.value;
    filter.innerHTML = `<option value="">All Assignees</option>`;
    this.teamMembers.forEach(m => {
      filter.innerHTML += `<option value="${m.id}">${this.escapeHtml(m.name)}</option>`;
    });
    filter.value = currentVal;
  },

  renderTasksTable() {
    const tbody = document.getElementById('tasks-table-body');
    if (!tbody) return;

    const search = (document.getElementById('task-search-input')?.value || '').toLowerCase().trim();
    const statusFilter = document.getElementById('task-filter-status')?.value || '';
    const priorityFilter = document.getElementById('task-filter-priority')?.value || '';
    const assigneeFilter = document.getElementById('task-filter-assignee')?.value || '';

    let filtered = this.tasks.filter(t => {
      const matchSearch = !search || t.name.toLowerCase().includes(search) || (t.description || '').toLowerCase().includes(search);
      const matchStatus = !statusFilter || t.status === statusFilter;
      const matchPriority = !priorityFilter || t.priority === priorityFilter;
      const matchAssignee = !assigneeFilter || String(t.assigned_to) === assigneeFilter;
      return matchSearch && matchStatus && matchPriority && matchAssignee;
    });

    if (filtered.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding: 24px; color: var(--text-muted);">No tasks match the selected filter criteria.</td></tr>`;
      return;
    }

    const taskNameMap = {};
    this.tasks.forEach(t => { taskNameMap[t.id] = t.name; });

    tbody.innerHTML = filtered.map(t => {
      const preds = (t.predecessor_ids || []).map(pid => `
        <span class="badge badge-notstarted" title="${this.escapeHtml(taskNameMap[pid] || '')}">#${pid}</span>
      `).join(' ') || '<span style="color:var(--text-muted); font-size:11px;">None</span>';

      return `
        <tr>
          <td><b>#${t.id}</b></td>
          <td>
            <div style="font-weight: 700; color: #fff;">${this.escapeHtml(t.name)}</div>
            <div style="font-size: 11px; color: var(--text-muted);">${this.escapeHtml(t.description || '')}</div>
          </td>
          <td><b>${t.duration}d</b></td>
          <td style="font-size: 12px; white-space: nowrap;">
            ${t.start_date}<br/><span style="color:var(--text-muted);">to</span> ${t.deadline}
          </td>
          <td>${preds}</td>
          <td>${this.renderStatusBadge(t.status)}</td>
          <td><span class="priority-${(t.priority || 'medium').toLowerCase()}">${t.priority}</span></td>
          <td>
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="avatar-circle" style="background: ${t.avatar_color || '#6366F1'};">
                ${this.getInitials(t.assignee_name || 'U')}
              </span>
              <span style="font-size: 12px;">${this.escapeHtml(t.assignee_name || 'Unassigned')}</span>
            </div>
          </td>
          <td style="text-align: right; white-space: nowrap;">
            <button class="quick-action-btn btn-secondary" style="padding: 4px 10px; font-size: 11px; display: inline-flex;" onclick="App.openTaskModal(${t.id})">Edit</button>
            <button class="quick-action-btn btn-danger" style="padding: 4px 10px; font-size: 11px; display: inline-flex;" onclick="App.deleteTask(${t.id})">Delete</button>
          </td>
        </tr>
      `;
    }).join('');
  },

  resetTaskFilters() {
    if (document.getElementById('task-search-input')) document.getElementById('task-search-input').value = '';
    if (document.getElementById('task-filter-status')) document.getElementById('task-filter-status').value = '';
    if (document.getElementById('task-filter-priority')) document.getElementById('task-filter-priority').value = '';
    if (document.getElementById('task-filter-assignee')) document.getElementById('task-filter-assignee').value = '';
    this.renderTasksTable();
  },

  openTaskModal(taskId = null) {
    if (!this.activeProjectId) {
      this.showToast("Please select or create an active project first.", "error");
      return;
    }

    const modal = document.getElementById('task-modal');
    const title = document.getElementById('task-modal-title');
    const formId = document.getElementById('task-form-id');
    const formName = document.getElementById('task-form-name');
    const formDesc = document.getElementById('task-form-desc');
    const formDuration = document.getElementById('task-form-duration');
    const formAssignee = document.getElementById('task-form-assignee');
    const formStart = document.getElementById('task-form-start');
    const formDeadline = document.getElementById('task-form-deadline');
    const formStatus = document.getElementById('task-form-status');
    const formPriority = document.getElementById('task-form-priority');
    const depContainer = document.getElementById('task-form-dependencies-container');

    // Populate assignees
    formAssignee.innerHTML = `<option value="">Unassigned</option>`;
    this.teamMembers.forEach(m => {
      formAssignee.innerHTML += `<option value="${m.id}">${this.escapeHtml(m.name)} (${m.role})</option>`;
    });

    let currentPreds = [];

    if (taskId) {
      const t = this.tasks.find(x => x.id === taskId);
      if (!t) return;
      title.textContent = "Edit Task";
      formId.value = t.id;
      formName.value = t.name;
      formDesc.value = t.description || '';
      formDuration.value = t.duration;
      formAssignee.value = t.assigned_to || '';
      formStart.value = t.start_date;
      formDeadline.value = t.deadline;
      formStatus.value = t.status;
      formPriority.value = t.priority;
      currentPreds = t.predecessor_ids || [];
    } else {
      title.textContent = "Add New Task";
      formId.value = "";
      formName.value = "";
      formDesc.value = "";
      formDuration.value = 3;
      formAssignee.value = "";
      const now = new Date();
      formStart.value = now.toISOString().split('T')[0];
      const end = new Date();
      end.setDate(end.getDate() + 3);
      formDeadline.value = end.toISOString().split('T')[0];
      formStatus.value = "Not Started";
      formPriority.value = "Medium";
      currentPreds = [];
    }

    // Populate dependencies checkboxes (exclude self)
    const availablePreds = this.tasks.filter(t => !taskId || t.id !== taskId);
    if (availablePreds.length === 0) {
      depContainer.innerHTML = `<div style="font-size: 12px; color: var(--text-muted);">No other tasks in this project yet.</div>`;
    } else {
      depContainer.innerHTML = availablePreds.map(p => `
        <label style="display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--text-primary); cursor: pointer;">
          <input type="checkbox" name="pred_task" value="${p.id}" ${currentPreds.includes(p.id) ? 'checked' : ''} style="accent-color: var(--primary);">
          <span><b>#${p.id}</b> ${this.escapeHtml(p.name)} (${p.duration}d)</span>
        </label>
      `).join('');
    }

    modal.classList.add('active');
  },

  closeTaskModal() {
    document.getElementById('task-modal')?.classList.remove('active');
  },

  async saveTask() {
    const id = document.getElementById('task-form-id').value;
    const name = document.getElementById('task-form-name').value.trim();
    const description = document.getElementById('task-form-desc').value.trim();
    const duration = parseInt(document.getElementById('task-form-duration').value);
    const assigned_to = document.getElementById('task-form-assignee').value || null;
    const start_date = document.getElementById('task-form-start').value;
    const deadline = document.getElementById('task-form-deadline').value;
    const status = document.getElementById('task-form-status').value;
    const priority = document.getElementById('task-form-priority').value;

    const selectedPreds = Array.from(document.querySelectorAll('input[name="pred_task"]:checked'))
      .map(cb => parseInt(cb.value));

    if (!name || isNaN(duration) || duration <= 0 || !start_date || !deadline) {
      this.showToast("Please provide valid task name, positive duration, and dates.", "error");
      return;
    }

    const payload = {
      name,
      description,
      duration,
      assigned_to: assigned_to ? parseInt(assigned_to) : null,
      start_date,
      deadline,
      status,
      priority,
      predecessor_ids: selectedPreds
    };

    try {
      let res;
      if (id) {
        res = await fetch(`/api/tasks/${id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      } else {
        res = await fetch(`/api/projects/${this.activeProjectId}/tasks`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      }

      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      this.showToast(data.message, 'success');
      this.closeTaskModal();
      await this.loadTasks();

      // If on dashboard or dependency view, refresh them
      if (this.currentView === 'dashboard') this.loadDashboard();
      if (this.currentView === 'dependencies') this.loadDependencyAnalysis();
    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  async deleteTask(taskId) {
    const t = this.tasks.find(x => x.id === taskId);
    const name = t ? t.name : `#${taskId}`;
    if (!confirm(`Are you sure you want to delete task '${name}'? All dependencies to and from this task will be removed.`)) {
      return;
    }

    try {
      const res = await fetch(`/api/tasks/${taskId}`, { method: 'DELETE' });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      this.showToast(data.message, 'success');
      await this.loadTasks();
      if (this.currentView === 'dashboard') this.loadDashboard();
      if (this.currentView === 'dependencies') this.loadDependencyAnalysis();
    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  // --- MODULE 4: DEPENDENCY ANALYSIS & DIRECTED GRAPH ---
  async loadDependencyAnalysis() {
    if (!this.activeProjectId) return;

    try {
      const [graphRes, depsRes] = await Promise.all([
        fetch(`/api/projects/${this.activeProjectId}/graph`).then(r => r.json()),
        fetch(`/api/projects/${this.activeProjectId}/dependencies`).then(r => r.json())
      ]);

      if (!graphRes.success) throw new Error(graphRes.error);
      this.dependencies = depsRes.dependencies || [];

      // Populate task selector
      const selector = document.getElementById('dep-task-selector');
      if (selector) {
        selector.innerHTML = '';
        graphRes.nodes.forEach(n => {
          const opt = document.createElement('option');
          opt.value = n.id;
          opt.textContent = `#${n.id} ${n.task_data.name}`;
          selector.appendChild(opt);
        });
      }

      // Render Vis.js Network
      this.renderVisNetwork(graphRes.nodes, graphRes.edges);

      // Render active edges table
      this.renderDependencyEdgesTable();

      // Run analysis on first task if available
      if (graphRes.nodes.length > 0) {
        this.runTaskAnalysis(graphRes.nodes[0].id);
      }
    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  renderVisNetwork(nodesData, edgesData) {
    const container = document.getElementById('network-graph-canvas');
    if (!container) return;

    const data = {
      nodes: new vis.DataSet(nodesData),
      edges: new vis.DataSet(edgesData)
    };

    const options = {
      layout: this.networkLayoutMode === 'hierarchical' ? {
        hierarchical: {
          direction: 'LR', // Left-to-Right layout
          sortMethod: 'directed',
          levelSeparation: 190,
          nodeSpacing: 120
        }
      } : {
        improvedLayout: true
      },
      physics: {
        enabled: this.networkLayoutMode === 'physics',
        solver: 'forceAtlas2Based',
        forceAtlas2Based: {
          gravitationalConstant: -50,
          centralGravity: 0.01,
          springLength: 100,
          springConstant: 0.08
        }
      },
      interaction: {
        hover: true,
        tooltipDelay: 100,
        navigationButtons: true,
        keyboard: true
      }
    };

    if (this.visNetwork) this.visNetwork.destroy();
    this.visNetwork = new vis.Network(container, data, options);

    // Node click handler
    this.visNetwork.on('click', (params) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0];
        const selector = document.getElementById('dep-task-selector');
        if (selector) selector.value = nodeId;
        this.runTaskAnalysis(nodeId);
      }
    });
  },

  toggleGraphLayout() {
    this.networkLayoutMode = this.networkLayoutMode === 'hierarchical' ? 'physics' : 'hierarchical';
    this.loadDependencyAnalysis();
    this.showToast(`Switched layout mode to: ${this.networkLayoutMode.toUpperCase()}`, 'info');
  },

  async runTaskAnalysis(taskId) {
    if (!this.activeProjectId || !taskId) return;

    try {
      const res = await fetch(`/api/projects/${this.activeProjectId}/dependency-analysis/${taskId}`);
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      const bfs = data.bfs;
      const dfs = data.dfs;
      const task = data.task;

      // Update Target Task Header
      document.getElementById('bfs-target-task-name').textContent = `Downstream Impact of '#${task.id} ${task.name}'`;
      document.getElementById('bfs-total-badge').textContent = `Total Downstream Affected: ${bfs.total_count} tasks`;

      // Update Counts
      document.getElementById('bfs-direct-count').textContent = bfs.direct_count;
      document.getElementById('bfs-indirect-count').textContent = bfs.indirect_count;

      // Render Direct list
      const directList = document.getElementById('bfs-direct-list');
      if (bfs.direct_dependents.length === 0) {
        directList.innerHTML = `<span style="font-size:11px; color:var(--text-muted);">No direct downstream successors.</span>`;
      } else {
        directList.innerHTML = bfs.direct_dependents.map(t => `
          <div style="font-size: 12px; display: flex; align-items: center; justify-content: space-between; background: rgba(255,255,255,0.03); padding: 4px 8px; border-radius: 4px;">
            <span><b>#${t.id}</b> ${this.escapeHtml(t.name)}</span>
            ${this.renderStatusBadge(t.status)}
          </div>
        `).join('');
      }

      // Render Indirect list
      const indirectList = document.getElementById('bfs-indirect-list');
      if (bfs.indirect_dependents.length === 0) {
        indirectList.innerHTML = `<span style="font-size:11px; color:var(--text-muted);">No indirect downstream tasks.</span>`;
      } else {
        indirectList.innerHTML = bfs.indirect_dependents.map(t => `
          <div style="font-size: 12px; display: flex; align-items: center; justify-content: space-between; background: rgba(255,255,255,0.03); padding: 4px 8px; border-radius: 4px;">
            <span><b>#${t.id}</b> ${this.escapeHtml(t.name)}</span>
            ${this.renderStatusBadge(t.status)}
          </div>
        `).join('');
      }

      // Render BFS Level-by-Level Breakdown
      const levelsContainer = document.getElementById('bfs-levels-breakdown');
      levelsContainer.innerHTML = `<div style="font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 8px;">BFS Level-by-Level Propagation</div>`;
      
      const levelKeys = Object.keys(bfs.levels).map(Number).sort((a,b) => a-b);
      if (levelKeys.length === 0) {
        levelsContainer.innerHTML += `<div style="font-size: 12px; color: var(--text-muted);">This task has no downstream dependencies (it is a terminal leaf node).</div>`;
      } else {
        levelsContainer.innerHTML += levelKeys.map(lvl => {
          const tasksAtLevel = bfs.levels[lvl];
          const taskPills = tasksAtLevel.map(t => `
            <span class="badge ${lvl === 1 ? 'badge-inprogress' : 'badge-completed'}" style="font-size: 11px;">
              #${t.id} ${this.escapeHtml(t.name)} (${t.duration}d)
            </span>
          `).join(' ');

          return `
            <div style="display: flex; gap: 12px; align-items: center; margin-bottom: 6px;">
              <span style="font-size: 11px; font-weight: 700; color: #fff; width: 65px; flex-shrink: 0;">Level ${lvl}:</span>
              <div style="display: flex; gap: 6px; flex-wrap: wrap;">${taskPills}</div>
            </div>
          `;
        }).join('');
      }

      // Render DFS Chains
      const dfsContainer = document.getElementById('dfs-chains-container');
      document.getElementById('dfs-chain-count').textContent = `${dfs.chain_count} Paths`;
      if (dfs.chains.length === 0) {
        dfsContainer.innerHTML = `<div style="font-size: 12px; color: var(--text-muted);">No outgoing paths.</div>`;
      } else {
        dfsContainer.innerHTML = dfs.chains.map((chain, idx) => {
          const pathSteps = chain.map((node, i) => `
            <span style="font-weight: 700; color: ${i === 0 ? '#60A5FA' : (i === chain.length - 1 ? '#34D399' : '#CBD5E1')};">
              #${node.id || '?'} ${this.escapeHtml(node.name)}
            </span>
          `).join(' <span style="color:var(--accent-purple); font-weight:bold;">➔</span> ');

          return `
            <div style="background: rgba(15, 23, 42, 0.4); padding: 8px 12px; border-radius: var(--radius-sm); border: 1px solid var(--border-color); font-size: 12px;">
              <div style="font-size: 10px; color: var(--text-muted); text-transform: uppercase;">Path ${idx + 1}</div>
              <div style="margin-top: 3px;">${pathSteps}</div>
            </div>
          `;
        }).join('');
      }

      // Highlight in Vis.js Network
      if (this.visNetwork) {
        const allAffectedIds = [taskId, ...bfs.all_downstream.map(t => t.id)];
        this.visNetwork.selectNodes(allAffectedIds);
      }

    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  renderDependencyEdgesTable() {
    const tbody = document.getElementById('dep-edges-table-body');
    const countElem = document.getElementById('dep-edge-count');
    if (!tbody) return;

    countElem.textContent = this.dependencies.length;

    if (this.dependencies.length === 0) {
      tbody.innerHTML = `<tr><td colspan="3" style="text-align:center; padding: 14px; color: var(--text-muted);">No dependency edges defined yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = this.dependencies.map(d => `
      <tr>
        <td><b>#${d.predecessor_id}</b> ${this.escapeHtml(d.predecessor_name)}</td>
        <td><b>#${d.successor_id}</b> ${this.escapeHtml(d.successor_name)}</td>
        <td style="text-align: right;">
          <button class="quick-action-btn btn-danger" style="padding: 2px 8px; font-size: 11px; display: inline-flex;" onclick="App.deleteDependency(${d.id})">Remove</button>
        </td>
      </tr>
    `).join('');
  },

  openDependencyModal() {
    if (!this.activeProjectId) return;
    const modal = document.getElementById('dependency-modal');
    const predSelect = document.getElementById('dep-form-predecessor');
    const succSelect = document.getElementById('dep-form-successor');

    predSelect.innerHTML = '';
    succSelect.innerHTML = '';

    this.tasks.forEach(t => {
      predSelect.innerHTML += `<option value="${t.id}">#${t.id} ${this.escapeHtml(t.name)}</option>`;
      succSelect.innerHTML += `<option value="${t.id}">#${t.id} ${this.escapeHtml(t.name)}</option>`;
    });

    if (this.tasks.length > 1) {
      succSelect.selectedIndex = 1;
    }

    modal.classList.add('active');
  },

  closeDependencyModal() {
    document.getElementById('dependency-modal')?.classList.remove('active');
  },

  async saveDependency() {
    const predId = document.getElementById('dep-form-predecessor').value;
    const succId = document.getElementById('dep-form-successor').value;

    if (!predId || !succId) {
      this.showToast("Please choose both predecessor and successor.", "error");
      return;
    }

    try {
      const res = await fetch(`/api/projects/${this.activeProjectId}/dependencies`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ predecessor_id: predId, successor_id: succId })
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      this.showToast(data.message, 'success');
      this.closeDependencyModal();
      await this.loadDependencyAnalysis();
      await this.loadTasks();
    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  async deleteDependency(depId) {
    if (!confirm("Are you sure you want to remove this dependency edge?")) return;

    try {
      const res = await fetch(`/api/dependencies/${depId}`, { method: 'DELETE' });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      this.showToast(data.message, 'success');
      await this.loadDependencyAnalysis();
      await this.loadTasks();
    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  // --- MODULE 5: WHAT-IF DELAY SIMULATOR ---
  async initSimulator() {
    if (!this.activeProjectId) return;

    // Always fetch latest tasks for the active project
    await this.loadTasks();

    const select = document.getElementById('sim-task-select');
    if (!select) return;

    select.innerHTML = '';
    this.tasks.forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.id;
      opt.textContent = `#${t.id} ${t.name} (${t.duration}d duration, status: ${t.status})`;
      select.appendChild(opt);
    });

    if (this.tasks.length >= 2) {
      select.selectedIndex = 1;
    } else if (this.tasks.length > 0) {
      select.selectedIndex = 0;
    }

    // Reset previous simulation output for clean view
    const simSummary = document.getElementById('sim-summary-container');
    if (simSummary) simSummary.style.display = 'none';
    const simComp = document.getElementById('sim-comparison-card');
    if (simComp) simComp.style.display = 'none';
    const simGraph = document.getElementById('sim-graph-card');
    if (simGraph) simGraph.style.display = 'none';
  },

  async runSimulation() {
    const taskId = document.getElementById('sim-task-select')?.value;
    const delayDays = document.getElementById('sim-delay-input')?.value;
    const saveHistory = document.getElementById('sim-save-history')?.checked;

    if (!taskId || !delayDays) {
      this.showToast("Please select a task and enter delay duration.", "error");
      return;
    }

    try {
      const res = await fetch(`/api/projects/${this.activeProjectId}/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_id: parseInt(taskId),
          delay_days: parseInt(delayDays),
          save_history: saveHistory
        })
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      const sim = data.simulation;
      this.displaySimulationResults(sim);
      this.showToast(`Hypothetical simulation executed: +${sim.summary.total_project_delay_days}d project slip.`, 'success');
    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  displaySimulationResults(sim) {
    const summary = sim.summary;
    const selTask = sim.selected_task;

    // 1. Show & Populate Impact Banner
    const banner = document.getElementById('sim-impact-banner');
    banner.style.display = 'flex';
    banner.className = `sim-impact-banner ${summary.deadline_breached ? 'breached' : 'safe'}`;

    document.getElementById('sim-banner-subtitle').textContent = `HYPOTHETICAL SIMULATION: '${selTask.name}' (+${selTask.delay_days} DAYS)`;
    document.getElementById('sim-banner-title').textContent = summary.total_project_delay_days > 0 
      ? `Project duration extended by +${summary.total_project_delay_days} working days`
      : `No overall project delay (absorbed by available schedule float).`;

    document.getElementById('sim-banner-finish').textContent = `${summary.baseline_finish_date} ➔ ${summary.simulated_finish_date}`;
    document.getElementById('sim-banner-deadline-status').innerHTML = summary.deadline_breached 
      ? `<span class="badge badge-delayed">BREACHED (+${summary.days_overdue}d Overdue)</span>`
      : `<span class="badge badge-completed">SAFE (${summary.simulated_slack_days}d Slack Buffer)</span>`;
    
    document.getElementById('sim-banner-affected-count').textContent = `${summary.total_affected_count} (${summary.direct_affected_count} direct, ${summary.indirect_affected_count} indirect)`;

    // 2. Schedule Comparison Table
    const compCard = document.getElementById('sim-results-card');
    compCard.style.display = 'block';

    const tbody = document.getElementById('sim-comparison-table-body');
    const baseDuration = summary.simulated_duration_days || 1;

    tbody.innerHTML = sim.task_comparisons.map(tc => {
      let badgeClass = 'badge-notstarted';
      if (tc.impact_type === 'Trigger') badgeClass = 'badge-delayed';
      else if (tc.impact_type === 'Direct') badgeClass = 'badge-atrisk';
      else if (tc.impact_type === 'Indirect') badgeClass = 'badge-inprogress';

      const slipText = tc.delay_experienced_days > 0 
        ? `<b style="color: #ef4444;">+${tc.delay_experienced_days}d</b>`
        : `<span style="color: var(--text-muted);">0d</span>`;

      return `
        <tr style="${tc.is_selected ? 'background: rgba(239, 68, 68, 0.08);' : (tc.is_affected ? 'background: rgba(245, 158, 11, 0.04);' : '')}">
          <td>
            <b style="color: #fff;">#${tc.task_id} ${this.escapeHtml(tc.name)}</b>
            ${tc.is_critical ? '<span class="badge badge-critical-path" style="font-size:9px; margin-left: 6px;">Critical</span>' : ''}
          </td>
          <td><span class="badge ${badgeClass}">${tc.impact_type}</span></td>
          <td style="font-size: 12px;">${tc.baseline_start} ➔ ${tc.baseline_end} (${tc.baseline_duration}d)</td>
          <td style="font-size: 12px;">${tc.simulated_start} ➔ ${tc.simulated_end} (${tc.simulated_duration}d)</td>
          <td>${slipText}</td>
          <td style="min-width: 140px;">
            <div class="schedule-comparison-bar">
              <div class="timeline-track" title="Baseline: ${tc.baseline_start} to ${tc.baseline_end}">
                <div class="timeline-fill-baseline" style="left: 0; width: 70%;"></div>
              </div>
              <div class="timeline-track" title="Simulated: ${tc.simulated_start} to ${tc.simulated_end}">
                <div class="timeline-fill-simulated" style="left: 0; width: ${tc.delay_experienced_days > 0 ? '95%' : '70%'};"></div>
              </div>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    // 3. Mini Propagation Graph
    const graphCard = document.getElementById('sim-graph-card');
    graphCard.style.display = 'block';
    this.renderSimulatorGraph(sim);
  },

  renderSimulatorGraph(sim) {
    const container = document.getElementById('simulator-graph-canvas');
    if (!container) return;

    const affectedSet = new Set(sim.affected_task_ids.all);
    const triggerId = sim.selected_task.id;

    // Build node datasets
    const nodes = this.tasks.map(t => {
      let bg = '#1E293B';
      let border = '#334155';
      let label = `${t.name}\n`;

      if (t.id === triggerId) {
        bg = '#7F1D1D';
        border = '#EF4444';
        label += `[DELAY TRIGGER +${sim.selected_task.delay_days}d]`;
      } else if (sim.affected_task_ids.direct.includes(t.id)) {
        bg = '#78350F';
        border = '#F59E0B';
        label += `[DIRECT DELAY SLIP]`;
      } else if (sim.affected_task_ids.indirect.includes(t.id)) {
        bg = '#4C1D95';
        border = '#8B5CF6';
        label += `[INDIRECT PROPAGATED]`;
      } else {
        bg = '#0F172A';
        border = '#1E293B';
        label += `[UNAFFECTED]`;
      }

      return {
        id: t.id,
        label: label,
        shape: 'box',
        color: { background: bg, border: border },
        font: { color: '#F8FAFC', size: 12, bold: true },
        borderWidth: (t.id === triggerId || affectedSet.has(t.id)) ? 3 : 1
      };
    });

    const edges = this.dependencies.map(d => {
      const isAffectedEdge = (d.predecessor_id === triggerId || affectedSet.has(d.predecessor_id)) && affectedSet.has(d.successor_id);
      return {
        from: d.predecessor_id,
        to: d.successor_id,
        arrows: 'to',
        color: { color: isAffectedEdge ? '#EF4444' : '#334155' },
        width: isAffectedEdge ? 3 : 1
      };
    });

    const options = {
      layout: {
        hierarchical: { direction: 'LR', levelSeparation: 180, nodeSpacing: 100 }
      },
      physics: { enabled: false }
    };

    if (this.simVisNetwork) this.simVisNetwork.destroy();
    this.simVisNetwork = new vis.Network(container, { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) }, options);
  },

  resetSimulation() {
    document.getElementById('sim-impact-banner').style.display = 'none';
    document.getElementById('sim-results-card').style.display = 'none';
    document.getElementById('sim-graph-card').style.display = 'none';
    this.showToast("Simulation cleared. Baseline schedule restored.", "info");
  },

  // --- MODULE 6 & 8: RISK & RECOVERY ---
  async loadRiskRecovery() {
    if (!this.activeProjectId) return;

    try {
      const [riskRes, recoveryRes] = await Promise.all([
        fetch(`/api/projects/${this.activeProjectId}/risk-analysis`).then(r => r.json()),
        fetch(`/api/projects/${this.activeProjectId}/recovery-suggestions`).then(r => r.json())
      ]);

      if (!riskRes.success) throw new Error(riskRes.error);
      const risk = riskRes.risk;
      const suggestions = recoveryRes.suggestions || [];

      // Update Risk Banner
      const banner = document.getElementById('risk-banner-card');
      const lvl = (risk.overall_risk_level || 'LOW').toLowerCase();
      banner.className = `risk-banner risk-${lvl}`;

      const badge = document.getElementById('risk-level-badge');
      badge.textContent = `${risk.overall_risk_level} RISK`;
      badge.className = `badge badge-${lvl === 'critical' ? 'delayed' : (lvl === 'high' ? 'delayed' : (lvl === 'medium' ? 'atrisk' : 'completed'))}`;

      document.getElementById('risk-score-text').textContent = `Risk Score: ${risk.risk_score} / 100`;
      document.getElementById('risk-explanation-text').textContent = risk.explanation;
      document.getElementById('risk-slack-days').textContent = risk.deadline_slack_days !== null ? `${risk.deadline_slack_days}d` : 'None';
      document.getElementById('risk-overdue-count').textContent = risk.overdue_tasks_count;
      document.getElementById('risk-critical-count').textContent = risk.critical_tasks_count;

      // Populate Reasons List directly under risk banner
      const reasonsList = document.getElementById('risk-reasons-list');
      if (reasonsList) {
        const factors = risk.risk_factors || [];
        if (factors.length === 0) {
          reasonsList.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="color: #34d399; font-weight: 600;">✓ Healthy Schedule:</span>
              <span>Project schedule is operating within safe buffers with zero overdue milestones and sufficient slack.</span>
            </div>
          `;
        } else {
          reasonsList.innerHTML = factors.map(rf => {
            const isCrit = rf.severity === 'CRITICAL';
            const isHigh = rf.severity === 'HIGH';
            const color = isCrit ? '#ef4444' : (isHigh ? '#f59e0b' : '#93c5fd');
            return `
              <div style="display: flex; align-items: flex-start; gap: 8px;">
                <span style="color: ${color}; font-weight: 700; flex-shrink: 0;">• ${this.escapeHtml(rf.factor)}:</span>
                <span style="color: #e2e8f0;">${this.escapeHtml(rf.description)}</span>
              </div>
            `;
          }).join('');
        }
      }

      // Render Risk Factors Table
      const factorsTbody = document.getElementById('risk-factors-table-body');
      if (risk.risk_factors.length === 0) {
        factorsTbody.innerHTML = `<tr><td colspan="3" style="text-align:center; padding: 16px; color: var(--text-muted);">No critical risk factors detected.</td></tr>`;
      } else {
        factorsTbody.innerHTML = risk.risk_factors.map(rf => {
          const sevClass = rf.severity === 'CRITICAL' ? 'badge-delayed' : (rf.severity === 'HIGH' ? 'badge-atrisk' : 'badge-completed');
          return `
            <tr>
              <td><b style="color: #fff;">${this.escapeHtml(rf.factor)}</b></td>
              <td><span class="badge ${sevClass}">${rf.severity}</span></td>
              <td>${this.escapeHtml(rf.description)}</td>
            </tr>
          `;
        }).join('');
      }

      // Render Recovery Suggestions
      const recContainer = document.getElementById('recovery-suggestions-container');
      if (suggestions.length === 0) {
        recContainer.innerHTML = `<div style="color: var(--text-muted); font-size: 13px;">No immediate recovery interventions needed.</div>`;
      } else {
        recContainer.innerHTML = suggestions.map(s => {
          const prioClass = s.priority === 'Critical' ? 'badge-delayed' : (s.priority === 'High' ? 'badge-atrisk' : 'badge-completed');
          return `
            <div class="recovery-card">
              <div class="recovery-header">
                <div>
                  <span style="font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 700;">${this.escapeHtml(s.type)}</span>
                  <div class="recovery-title">${this.escapeHtml(s.title)}</div>
                </div>
                <span class="badge ${prioClass}">${s.priority} Priority</span>
              </div>
              <div class="recovery-body">
                <b>Action:</b> ${this.escapeHtml(s.recommendation)}
              </div>
              <div class="recovery-meta">
                <div><b>Why:</b> ${this.escapeHtml(s.reason)}</div>
                <div style="color: #34D399; margin-top: 4px;"><b>Impact:</b> ${this.escapeHtml(s.expected_impact)}</div>
              </div>
            </div>
          `;
        }).join('');
      }

    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  // --- MODULE 7: WORKLOAD ANALYSIS ---
  async loadWorkload() {
    if (!this.activeProjectId) return;

    try {
      const res = await fetch(`/api/projects/${this.activeProjectId}/workload`);
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      const team = data.team_workload || [];
      const overloaded = data.overloaded_members || [];

      // Render Workload Chart
      this.renderWorkloadBarChart(team);

      // Render Overload Alert
      const alertContainer = document.getElementById('workload-alert-container');
      if (overloaded.length > 0) {
        alertContainer.innerHTML = `
          <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239,68,68,0.3); border-radius: var(--radius-sm); padding: 14px;">
            <div style="color: #F87171; font-weight: 700; font-size: 14px; display: flex; align-items: center; gap: 8px;">
              <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
              Workload Bottleneck Warning
            </div>
            <div style="font-size: 13px; color: var(--text-secondary); margin-top: 6px;">
              <b>${overloaded.join(', ')}</b> have exceeded sustainable workload thresholds (≥3 active tasks or ≥10 days duration).
              Redistribute tasks to balance velocity.
            </div>
          </div>
        `;
      } else {
        alertContainer.innerHTML = `
          <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: var(--radius-sm); padding: 14px;">
            <div style="color: #34D399; font-weight: 700; font-size: 14px;">Team Capacity Balanced</div>
            <div style="font-size: 13px; color: var(--text-secondary); margin-top: 6px;">
              Assignments are evenly distributed across available developers with no severe individual overload.
            </div>
          </div>
        `;
      }

      // Render Team Table
      const tbody = document.getElementById('workload-table-body');
      tbody.innerHTML = team.map(m => `
        <tr>
          <td>
            <div style="display: flex; align-items: center; gap: 10px;">
              <span class="avatar-circle" style="background: ${m.avatar_color || '#6366F1'};">
                ${this.getInitials(m.name)}
              </span>
              <div>
                <b style="color: #fff;">${this.escapeHtml(m.name)}</b>
                <div style="font-size: 11px; color: var(--text-muted);">${this.escapeHtml(m.email || '')}</div>
              </div>
            </div>
          </td>
          <td>${this.escapeHtml(m.role)}</td>
          <td><b>${m.total_tasks || 0}</b></td>
          <td><span style="color: #10B981; font-weight: 700;">${m.completed_tasks || 0}</span></td>
          <td><span style="color: #60A5FA; font-weight: 700;">${m.pending_tasks || 0}</span></td>
          <td><b>${m.total_duration_days || 0} Days</b></td>
          <td>
            ${m.is_overloaded 
              ? `<span class="badge badge-delayed">Overloaded</span>`
              : `<span class="badge badge-completed">Optimal Capacity</span>`}
          </td>
        </tr>
      `).join('');

    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  renderWorkloadBarChart(team) {
    const ctx = document.getElementById('workload-chart')?.getContext('2d');
    if (!ctx) return;

    if (this.workloadChart) this.workloadChart.destroy();

    const labels = team.map(m => m.name);
    const durationDays = team.map(m => m.total_duration_days || 0);
    const pendingTasks = team.map(m => m.pending_tasks || 0);

    this.workloadChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Total Working Days',
            data: durationDays,
            backgroundColor: '#6366F1',
            borderRadius: 6
          },
          {
            label: 'Pending Tasks',
            data: pendingTasks,
            backgroundColor: '#06B6D4',
            borderRadius: 6
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'top',
            labels: { color: '#94A3B8', font: { family: 'Inter', size: 11 } }
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: '#94A3B8', font: { family: 'Inter' } }
          },
          y: {
            grid: { color: 'rgba(255,255,255,0.06)' },
            ticks: { color: '#94A3B8', font: { family: 'Inter' } }
          }
        }
      }
    });
  },

  async loadTeamMembers() {
    try {
      const res = await fetch('/api/team');
      const data = await res.json();
      if (data.success) {
        this.teamMembers = data.team;
      }
    } catch (err) {
      console.error("Failed to load team:", err);
    }
  },

  openTeamModal() {
    document.getElementById('team-modal')?.classList.add('active');
  },

  closeTeamModal() {
    document.getElementById('team-modal')?.classList.remove('active');
  },

  async saveTeamMember() {
    const name = document.getElementById('team-form-name').value.trim();
    const role = document.getElementById('team-form-role').value.trim();
    const email = document.getElementById('team-form-email').value.trim();
    const avatar_color = document.getElementById('team-form-color').value;

    if (!name || !role) {
      this.showToast("Please provide member name and role.", "error");
      return;
    }

    try {
      const res = await fetch('/api/team', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, role, email, avatar_color })
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      this.showToast(data.message, 'success');
      this.closeTeamModal();
      await this.loadTeamMembers();
      if (this.currentView === 'workload') this.loadWorkload();
    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  // --- MODULE 10: HISTORY & REPORTS ---
  async loadReports() {
    if (!this.activeProjectId) return;

    try {
      const res = await fetch(`/api/projects/${this.activeProjectId}/simulations`);
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      const tbody = document.getElementById('sim-history-table-body');
      if (!tbody) return;

      const history = data.history || [];
      if (history.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 20px; color: var(--text-muted);">No simulation records stored yet. Run What-If delay simulations to populate audit history.</td></tr>`;
        return;
      }

      tbody.innerHTML = history.map(h => `
        <tr>
          <td><span style="font-size: 12px; color: var(--text-muted);">${h.simulated_at}</span></td>
          <td><b>${this.escapeHtml(h.project_name)}</b></td>
          <td><b>${this.escapeHtml(h.task_name)}</b></td>
          <td><span class="badge badge-delayed">+${h.delay_days} Days</span></td>
          <td><b>${h.total_affected_count}</b> (${h.direct_affected_count} direct, ${h.indirect_affected_count} indirect)</td>
          <td><b>+${h.project_delay_days} Days</b></td>
          <td>
            ${h.deadline_breached 
              ? `<span class="badge badge-delayed">Overdue</span>`
              : `<span class="badge badge-completed">Safe</span>`}
          </td>
          <td style="text-align: right;">
            <button class="quick-action-btn btn-danger" style="padding: 2px 8px; font-size: 11px; display: inline-flex;" onclick="App.deleteSimulationRecord(${h.id})">Delete</button>
          </td>
        </tr>
      `).join('');

    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  async deleteSimulationRecord(simId) {
    try {
      const res = await fetch(`/api/simulations/${simId}`, { method: 'DELETE' });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      this.showToast("Simulation entry removed.", "info");
      this.loadReports();
    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  downloadPDFReport() {
    if (!this.activeProjectId) {
      this.showToast("Please select an active project first.", "error");
      return;
    }
    this.showToast("Compiling 8-section executive PDF report...", "info");
    window.location.href = `/api/projects/${this.activeProjectId}/report/pdf`;
  },

  // --- SYSTEM DATABASE RESET ---
  async resetDatabase() {
    if (!confirm("Are you sure you want to reset the database? This restores the clean sample 'Software Development Project' and default team members.")) {
      return;
    }

    try {
      const res = await fetch('/api/system/reset', { method: 'POST' });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      this.showToast(data.message, 'success');
      this.activeProjectId = null;
      await this.loadTeamMembers();
      await this.loadProjects();
      this.switchView('dashboard');
    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },


  async loadComplexProject() {
    try {
      this.showToast('Loading complex parallel DAG project...', 'info');
      const res = await fetch('/api/projects/sample-complex', { method: 'POST' });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      this.showToast(data.message, 'success');
      await this.loadProjects();
      if (data.project_id) {
        this.setActiveProject(data.project_id);
      }
      this.switchView('dashboard');
    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  async resetSystem() {
    if (!confirm('Are you sure you want to reset the entire database? This will clear all data and reload the sample project.')) {
      return;
    }

    try {
      const res = await fetch('/api/system/reset', { method: 'POST' });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      this.showToast(data.message, 'success');
      this.activeProjectId = null;
      await this.loadTeamMembers();
      await this.loadProjects();
      this.switchView('dashboard');
    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  // ==========================================
  // VIEW: DAILY WORK UPDATES
  // ==========================================
  async loadDailyUpdates() {
    if (!this.activeProjectId) return;
    try {
      const uid = this.currentUser ? this.currentUser.id : 1;
      const [feedRes, sumRes] = await Promise.all([
        fetch(`/api/projects/${this.activeProjectId}/daily-updates?user_id=${uid}&role_filter=true`),
        fetch(`/api/projects/${this.activeProjectId}/daily-updates/summary`)
      ]);
      const feedData = await feedRes.json();
      const sumData = await sumRes.json();

      if (!feedData.success || !sumData.success) {
        throw new Error("Failed to load daily updates.");
      }

      // Update Daily Privacy Banner
      const dPrivBanner = document.getElementById('daily-privacy-banner');
      const dPrivText = document.getElementById('daily-privacy-text');
      const dPrivIcon = document.getElementById('daily-privacy-icon');
      if (dPrivBanner && dPrivText) {
        if (feedData.is_lead_view) {
          dPrivBanner.style.background = 'rgba(99, 102, 241, 0.15)';
          dPrivBanner.style.borderColor = 'rgba(99, 102, 241, 0.35)';
          dPrivBanner.style.color = '#c7d2fe';
          if (dPrivIcon) dPrivIcon.textContent = '👑';
          dPrivText.innerHTML = `<b>Project Lead Access (${this.escapeHtml(this.currentUser.full_name)}):</b> Full workspace visibility. Reviewing daily standups and blocker reports across all 5 team members.`;
        } else {
          dPrivBanner.style.background = 'rgba(245, 158, 11, 0.15)';
          dPrivBanner.style.borderColor = 'rgba(245, 158, 11, 0.35)';
          dPrivBanner.style.color = '#fde68a';
          if (dPrivIcon) dPrivIcon.textContent = '🔒';
          dPrivText.innerHTML = `<b>Private Member View (${this.escapeHtml(this.currentUser.full_name)} - ${this.escapeHtml(feedData.role_title)}):</b> Showing only your daily standups. Other team members' daily reports are private.`;
        }
      }

      // Update KPI Cards
      const kpiSub = document.getElementById('daily-kpi-submitted');
      if (kpiSub) kpiSub.innerText = sumData.today_submissions_count || 0;
      const kpiComp = document.getElementById('daily-kpi-compliance');
      if (kpiComp) kpiComp.innerText = `${sumData.compliance_rate_pct || 100}% compliance today`;
      const kpiPend = document.getElementById('daily-kpi-pending');
      if (kpiPend) kpiPend.innerText = sumData.pending_members_count || 0;
      const kpiStag = document.getElementById('daily-kpi-stagnant');
      if (kpiStag) kpiStag.innerText = sumData.stagnant_tasks_count || 0;

      const weeklyTotal = (sumData.weekly_trend || []).reduce((acc, curr) => acc + curr.count, 0);
      const kpiWeek = document.getElementById('daily-kpi-weekly-total');
      if (kpiWeek) kpiWeek.innerText = weeklyTotal;

      // Pending Members Alert Banner
      const pendingBanner = document.getElementById('daily-pending-banner');
      const pendingText = document.getElementById('daily-pending-text');
      if (pendingBanner && pendingText) {
        if (sumData.pending_members && sumData.pending_members.length > 0) {
          const names = sumData.pending_members.map(m => m.name).join(', ');
          pendingText.innerHTML = `<b>${sumData.pending_members.length} team members</b> have pending daily reports today: <span style="color:#fff;">${this.escapeHtml(names)}</span>`;
          pendingBanner.style.display = 'block';
        } else {
          pendingBanner.style.display = 'none';
        }
      }

      // Render Updates Feed Table
      const tbody = document.getElementById('daily-updates-tbody');
      const updates = feedData.updates || [];

      if (tbody) {
        if (updates.length === 0) {
          tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 30px;">No daily updates recorded yet. Click "+ Submit Daily Update" to add today\'s standup.</td></tr>';
        } else {
          tbody.innerHTML = updates.map(u => {
            const hasBlocker = u.problems_faced && u.problems_faced.trim().length > 0;
            return `
              <tr>
                <td>
                  <div style="display: flex; align-items: center; gap: 8px;">
                    <div class="avatar-circle" style="background-color: ${u.avatar_color || '#6366F1'}; width: 28px; height: 28px; font-size: 11px;">
                      ${this.getInitials(u.team_member_name)}
                    </div>
                    <div>
                      <div style="font-weight: 600; font-size: 13px;">${this.escapeHtml(u.team_member_name)}</div>
                      <div style="font-size: 11px; color: var(--text-muted);">${u.submission_date}</div>
                    </div>
                  </div>
                </td>
                <td>
                  <div style="font-weight: 600; font-size: 13px; color: #93c5fd;">${this.escapeHtml(u.task_name)}</div>
                  <div style="font-size: 11px; color: var(--text-muted);">Task #${u.task_id}</div>
                </td>
                <td>
                  <div style="font-size: 13px; color: var(--text-primary); margin-bottom: 4px;">${this.escapeHtml(u.work_description)}</div>
                  ${u.remaining_work ? `<div style="font-size: 11px; color: var(--text-muted);"><b>Remaining:</b> ${this.escapeHtml(u.remaining_work)}</div>` : ''}
                </td>
                <td>
                  <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="flex: 1; background: rgba(255,255,255,0.1); height: 6px; border-radius: 3px; overflow: hidden;">
                      <div style="width: ${u.progress_pct}%; background: ${u.progress_pct === 100 ? '#10b981' : '#6366f1'}; height: 100%;"></div>
                    </div>
                    <span style="font-size: 12px; font-weight: 700;">${u.progress_pct}%</span>
                  </div>
                </td>
                <td>
                  ${hasBlocker ? `
                    <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.35); border-radius: 4px; padding: 4px 8px; font-size: 11px; color: #fca5a5;">
                      ⚠️ ${this.escapeHtml(u.problems_faced)}
                    </div>
                  ` : '<span style="font-size: 12px; color: var(--text-muted);">No roadblocks</span>'}
                </td>
                <td>
                  <span class="badge" style="background: rgba(255,255,255,0.06); font-size: 11px;">${u.estimated_remaining_days} d</span>
                </td>
              </tr>
            `;
          }).join('');
        }
      }

      // Populate filter dropdown
      const memberSelect = document.getElementById('daily-filter-member');
      if (memberSelect) {
        memberSelect.innerHTML = '<option value="">All Team Members</option>' +
          this.teamMembers.map(m => `<option value="${m.id}">${this.escapeHtml(m.name)}</option>`).join('');
      }

    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  openDailyUpdateModal() {
    const memberSelect = document.getElementById('daily-form-member');
    const taskSelect = document.getElementById('daily-form-task');
    const dateInput = document.getElementById('daily-form-date');

    const activeUserSelect = document.getElementById('active-user-select');
    const activeUserId = activeUserSelect ? parseInt(activeUserSelect.value) : 1;

    if (memberSelect) {
      const isLead = this.isCurrentUserLead();
      if (!isLead && this.currentUser) {
        memberSelect.innerHTML = `<option value="${this.currentUser.id}" selected>${this.escapeHtml(this.currentUser.full_name)} (${this.escapeHtml(this.currentUser.roles?.[String(this.activeProjectId)]?.role_title || 'Member')})</option>`;
        memberSelect.disabled = true;
      } else {
        memberSelect.disabled = false;
        memberSelect.innerHTML = this.teamMembers.map(m =>
          `<option value="${m.id}" ${m.id === this.currentUser.id ? 'selected' : ''}>${this.escapeHtml(m.name)} (${this.escapeHtml(m.role)})</option>`
        ).join('');
      }
    }

    if (taskSelect) {
      taskSelect.innerHTML = this.tasks.map(t =>
        `<option value="${t.id}">${this.escapeHtml(t.name)} (Current: ${t.progress_pct || 0}%)</option>`
      ).join('');
    }

    if (dateInput) dateInput.value = new Date().toISOString().split('T')[0];
    const dw = document.getElementById('daily-form-work');
    if (dw) dw.value = '';
    const dp = document.getElementById('daily-form-progress');
    if (dp) dp.value = 50;
    const dpr = document.getElementById('daily-form-progress-range');
    if (dpr) dpr.value = 50;
    const drd = document.getElementById('daily-form-remaining-days');
    if (drd) drd.value = 1;
    const drw = document.getElementById('daily-form-remaining-work');
    if (drw) drw.value = '';
    const dprob = document.getElementById('daily-form-problems');
    if (dprob) dprob.value = '';

    document.getElementById('daily-update-modal')?.classList.add('active');
  },

  closeDailyUpdateModal() {
    document.getElementById('daily-update-modal')?.classList.remove('active');
  },

  async submitDailyUpdate() {
    if (!this.activeProjectId) return;
    const memberId = parseInt(document.getElementById('daily-form-member').value);
    const taskId = parseInt(document.getElementById('daily-form-task').value);
    const workDesc = document.getElementById('daily-form-work').value.trim();
    const progressPct = parseInt(document.getElementById('daily-form-progress').value);
    const remainingDays = parseInt(document.getElementById('daily-form-remaining-days').value);
    const remainingWork = document.getElementById('daily-form-remaining-work').value.trim();
    const problems = document.getElementById('daily-form-problems').value.trim();
    const subDate = document.getElementById('daily-form-date').value;

    if (!workDesc) {
      this.showToast("Please provide today's work deliverables.", "error");
      return;
    }

    try {
      const res = await fetch(`/api/projects/${this.activeProjectId}/daily-updates`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          team_member_id: memberId,
          task_id: taskId,
          work_description: workDesc,
          progress_pct: progressPct,
          estimated_remaining_days: remainingDays,
          remaining_work: remainingWork,
          problems_faced: problems,
          submission_date: subDate
        })
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      this.showToast('Daily update recorded & task progress synchronized!', 'success');
      this.closeDailyUpdateModal();
      await this.loadTasks();
      await this.loadDailyUpdates();
      if (this.currentView === 'team-progress') this.loadTeamProgress();
    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  // ==========================================
  // VIEW: TEAM PROGRESS TRACKING
  // ==========================================
  async loadTeamProgress() {
    if (!this.activeProjectId) return;
    try {
      const [metricsRes, tasksRes] = await Promise.all([
        fetch(`/api/projects/${this.activeProjectId}/progress-metrics`),
        fetch(`/api/projects/${this.activeProjectId}/tasks`)
      ]);
      const mData = await metricsRes.json();
      const tData = await tasksRes.json();

      if (!mData.success) throw new Error('Failed to load progress metrics.');

      const m = mData.metrics;
      const elProg = document.getElementById('prog-metric-overall');
      if (elProg) elProg.innerText = `${m.overall_progress_pct}%`;
      const elExp = document.getElementById('prog-metric-expected');
      if (elExp) elExp.innerText = `${m.expected_progress_pct}%`;
      
      const varElem = document.getElementById('prog-metric-variance');
      if (varElem) {
        if (m.progress_variance_pct >= 0) {
          varElem.innerText = `+${m.progress_variance_pct}% ahead of baseline`;
          varElem.style.color = '#10b981';
        } else {
          varElem.innerText = `${m.progress_variance_pct}% behind baseline`;
          varElem.style.color = '#ef4444';
        }
      }

      const elHours = document.getElementById('prog-metric-hours');
      if (elHours) elHours.innerText = `${m.total_spent_hours}h`;
      const elPlanned = document.getElementById('prog-metric-planned-hours');
      if (elPlanned) elPlanned.innerText = `of ${m.total_planned_hours}h planned`;
      const elComp = document.getElementById('prog-metric-completed');
      if (elComp) elComp.innerText = `${m.completed_tasks} / ${m.total_tasks}`;
      const elBrk = document.getElementById('prog-metric-breakdown');
      if (elBrk) elBrk.innerText = `${m.in_progress_tasks} in progress, ${m.stagnant_tasks_count} stagnant`;

      // Matrix Table
      const tbody = document.getElementById('team-progress-tbody');
      const tasks = tData.tasks || [];

      if (tbody) {
        tbody.innerHTML = tasks.map(t => `
          <tr>
            <td>
              <div style="font-weight: 700; font-size: 13px;">${this.escapeHtml(t.name)}</div>
              <div style="font-size: 11px; color: var(--text-muted);">${t.duration}d duration • ${t.complexity || 'Medium'} complexity</div>
            </td>
            <td>
              ${t.assignee_name ? `
                <div style="display: flex; align-items: center; gap: 6px;">
                  <div class="avatar-circle" style="background-color: ${t.assignee_color || '#6366F1'}; width: 24px; height: 24px; font-size: 10px;">
                    ${this.getInitials(t.assignee_name)}
                  </div>
                  <span style="font-size: 12px;">${this.escapeHtml(t.assignee_name)}</span>
                </div>
              ` : '<span style="font-size: 11px; color: var(--text-muted);">Unassigned</span>'}
            </td>
            <td>${this.renderStatusBadge(t.status)}</td>
            <td>
              <div style="display: flex; align-items: center; gap: 8px;">
                <div style="flex: 1; background: rgba(255,255,255,0.1); height: 8px; border-radius: 4px; overflow: hidden;">
                  <div style="width: ${t.progress_pct || 0}%; background: ${t.progress_pct === 100 ? '#10b981' : '#6366f1'}; height: 100%;"></div>
                </div>
                <span style="font-size: 12px; font-weight: 700; width: 35px; text-align: right;">${t.progress_pct || 0}%</span>
              </div>
            </td>
            <td>
              <span style="font-size: 12px; font-weight: 600;">${t.time_spent_hours || 0} hrs</span>
            </td>
            <td>
              <div style="font-size: 11px; color: var(--text-secondary);">
                <b>Start:</b> ${t.actual_start_date || 'Pending'}
              </div>
              <div style="font-size: 11px; color: var(--text-secondary);">
                <b>Done:</b> ${t.actual_completion_date || 'Pending'}
              </div>
            </td>
            <td style="text-align: right;">
              <button class="quick-action-btn btn-secondary" style="font-size: 11px; padding: 4px 8px;" onclick="App.openTaskProgressModal(${t.id})">
                Update Progress
              </button>
            </td>
          </tr>
        `).join('');
      }

    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  openTaskProgressModal(taskId) {
    const taskSelect = document.getElementById('prog-modal-task-select');
    if (taskSelect) {
      taskSelect.innerHTML = this.tasks.map(t =>
        `<option value="${t.id}" ${t.id === taskId ? 'selected' : ''}>${this.escapeHtml(t.name)}</option>`
      ).join('');
    }

    const targetId = taskId || (this.tasks[0] ? this.tasks[0].id : null);
    const hid = document.getElementById('prog-modal-task-id');
    if (hid) hid.value = targetId;

    this.onProgressModalTaskChange();
    document.getElementById('task-progress-modal')?.classList.add('active');
  },

  onProgressModalTaskChange() {
    const select = document.getElementById('prog-modal-task-select');
    if (!select) return;
    const selId = parseInt(select.value);
    const hid = document.getElementById('prog-modal-task-id');
    if (hid) hid.value = selId;
    const task = this.tasks.find(t => t.id === selId);
    if (task) {
      const prog = task.progress_pct || 0;
      const v = document.getElementById('prog-modal-val');
      if (v) v.value = prog;
      const r = document.getElementById('prog-modal-range');
      if (r) r.value = prog;
      const s = document.getElementById('prog-modal-status');
      if (s) s.value = task.status || 'In Progress';
      const h = document.getElementById('prog-modal-hours');
      if (h) h.value = 4.0;
      const c = document.getElementById('prog-modal-comments');
      if (c) c.value = '';
    }
  },

  closeTaskProgressModal() {
    document.getElementById('task-progress-modal')?.classList.remove('active');
  },

  async saveTaskProgress() {
    const taskId = parseInt(document.getElementById('prog-modal-task-id').value);
    const progressPct = parseInt(document.getElementById('prog-modal-val').value);
    const status = document.getElementById('prog-modal-status').value;
    const hours = parseFloat(document.getElementById('prog-modal-hours').value) || 0.0;
    const comments = document.getElementById('prog-modal-comments').value.trim();

    const activeUserSelect = document.getElementById('active-user-select');
    const memberId = activeUserSelect ? parseInt(activeUserSelect.value) : 1;

    try {
      const res = await fetch(`/api/tasks/${taskId}/progress`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          progress_pct: progressPct,
          status: status,
          hours_spent: hours,
          member_id: memberId,
          comments: comments
        })
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      this.showToast(`Task progress updated to ${progressPct}% (${data.new_status})`, 'success');
      this.closeTaskProgressModal();
      await this.loadTasks();
      this.loadTeamProgress();
    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  // ==========================================
  // VIEW: AI RISK PREDICTION
  // ==========================================
  async loadAIRisk() {
    if (!this.activeProjectId) return;
    try {
      const res = await fetch(`/api/projects/${this.activeProjectId}/ai-risk-prediction`);
      const data = await res.json();
      if (!data.success) throw new Error(data.error || 'Failed to run AI risk prediction.');

      // Model Header Banner
      const mStatus = data.model_status || {};
      const nameBanner = document.getElementById('ai-model-name-banner');
      const pill = document.getElementById('ai-model-status-pill');
      if (nameBanner && pill) {
        if (mStatus.is_trained) {
          nameBanner.innerText = mStatus.model_name || 'Scikit-Learn Random Forest (100 Trees)';
          pill.innerText = `Trained (${mStatus.accuracy}% Accuracy)`;
          pill.className = 'badge badge-success';
        } else {
          nameBanner.innerText = 'Rule-Based Calibrated Heuristic Engine';
          pill.innerText = 'ML Pending Training';
          pill.className = 'badge badge-warning';
        }
      }

      // Risk score & prob
      const riskBadge = document.getElementById('ai-overall-risk-badge');
      if (riskBadge) {
        riskBadge.innerText = data.overall_project_risk;
        if (data.overall_project_risk === 'CRITICAL RISK') {
          riskBadge.style.color = '#ef4444';
        } else if (data.overall_project_risk === 'HIGH RISK') {
          riskBadge.style.color = '#f59e0b';
        } else if (data.overall_project_risk === 'MEDIUM RISK') {
          riskBadge.style.color = '#3b82f6';
        } else {
          riskBadge.style.color = '#10b981';
        }
      }

      const probEl = document.getElementById('ai-overall-prob');
      if (probEl) probEl.innerText = `${data.project_delay_probability}%`;

      // High Risk Tasks Table
      const tbody = document.getElementById('ai-risk-tbody');
      const predictions = data.task_predictions || [];

      if (tbody) {
        tbody.innerHTML = predictions.map(p => {
          let tierColor = '#10b981';
          if (p.risk_tier.includes('CRITICAL')) tierColor = '#ef4444';
          else if (p.risk_tier.includes('HIGH')) tierColor = '#f59e0b';
          else if (p.risk_tier.includes('MEDIUM')) tierColor = '#3b82f6';

          return `
            <tr>
              <td>
                <div style="font-weight: 700; font-size: 13px;">${this.escapeHtml(p.name)}</div>
                <div style="font-size: 11px; color: var(--text-muted);">${p.is_critical ? '<span style="color:#ef4444; font-weight:700;">Critical Path</span> • ' : ''}${p.duration}d duration</div>
              </td>
              <td>
                <span style="font-size: 12px; color: var(--text-secondary);">${this.escapeHtml(p.assignee || 'Unassigned')}</span>
              </td>
              <td>
                <div style="display: flex; align-items: center; gap: 8px;">
                  <div style="flex: 1; background: rgba(255,255,255,0.1); height: 6px; border-radius: 3px; overflow: hidden;">
                    <div style="width: ${p.delay_probability}%; background: ${tierColor}; height: 100%;"></div>
                  </div>
                  <span style="font-size: 12px; font-weight: 700;">${p.delay_probability}%</span>
                </div>
              </td>
              <td>
                <span class="badge" style="background: rgba(255,255,255,0.06); color: ${tierColor}; border: 1px solid ${tierColor}40;">
                  ${p.risk_tier}
                </span>
              </td>
              <td>
                <span style="font-size: 12px; font-weight: 600;">${p.downstream_affected_count} tasks</span>
                <div style="font-size: 10px; color: var(--text-muted);">${p.direct_affected_ids.length} direct, ${p.indirect_affected_ids.length} indirect</div>
              </td>
              <td>
                <div style="font-size: 12px; font-weight: 600; color: #93c5fd;">${p.predicted_completion_date}</div>
                <div style="font-size: 10px; color: var(--text-muted);">Planned: ${p.planned_deadline}</div>
              </td>
              <td>
                <div style="display: flex; flex-direction: column; gap: 4px;">
                  ${(p.reasons || []).map(r => `<span style="font-size: 11px; color: var(--text-secondary);">• ${this.escapeHtml(r)}</span>`).join('')}
                </div>
              </td>
            </tr>
          `;
        }).join('');
      }

    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  async trainAIModel() {
    try {
      this.showToast('Training Scikit-Learn Random Forest on historical benchmarks...', 'info');
      const res = await fetch('/api/ai/train-model', { method: 'POST' });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      const acc = data.metadata ? data.metadata.accuracy : 93.8;
      this.showToast(`Random Forest Model successfully trained! Test Accuracy: ${acc}%`, 'success');

      if (this.currentView === 'ai-risk') this.loadAIRisk();
      if (this.currentView === 'dashboard') this.loadDashboard();
    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  // ==========================================
  // VIEW: TEAM PERFORMANCE
  // ==========================================
  async loadTeamPerformance() {
    if (!this.activeProjectId) return;
    try {
      const res = await fetch(`/api/projects/${this.activeProjectId}/team-performance`);
      const data = await res.json();
      if (!data.success) throw new Error('Failed to load team performance.');

      const tbody = document.getElementById('team-perf-tbody');
      const perf = data.team_performance || [];

      if (tbody) {
        tbody.innerHTML = perf.map(p => {
          let loadBadge = '<span class="badge badge-success">Balanced</span>';
          if (p.workload_status === 'Overloaded') loadBadge = '<span class="badge badge-delayed">Overloaded</span>';
          else if (p.workload_status === 'Available') loadBadge = '<span class="badge badge-info">Available</span>';

          return `
            <tr>
              <td>
                <div style="display: flex; align-items: center; gap: 10px;">
                  <div class="avatar-circle" style="background-color: ${p.avatar_color || '#6366F1'};">
                    ${this.getInitials(p.name)}
                  </div>
                  <div>
                    <div style="font-weight: 700; font-size: 13px;">${this.escapeHtml(p.name)}</div>
                    <div style="font-size: 11px; color: var(--text-muted);">${this.escapeHtml(p.email || '')}</div>
                  </div>
                </div>
              </td>
              <td>
                <div style="font-size: 13px; font-weight: 600;">${this.escapeHtml(p.role)}</div>
                <div style="font-size: 11px; color: var(--accent-purple);">${this.escapeHtml(p.role_type || 'Team Member')}</div>
              </td>
              <td><span style="font-weight: 700; font-size: 14px;">${p.assigned_tasks_count}</span></td>
              <td>
                <span style="font-weight: 700; color: #10b981;">${p.completed_tasks_count}</span>
                <span style="font-size: 11px; color: var(--text-muted);">(${p.completion_rate_pct}%)</span>
              </td>
              <td><span style="font-weight: 700;">${p.total_time_spent_hours} hrs</span></td>
              <td>
                <span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #34d399;">
                  ${p.daily_updates_count} updates (${p.compliance_pct}%)
                </span>
              </td>
              <td>${loadBadge}</td>
            </tr>
          `;
        }).join('');
      }

    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  // ==========================================
  // VIEW: AI RECOMMENDATIONS
  // ==========================================
  async loadAIRecommendations() {
    if (!this.activeProjectId) return;
    try {
      const res = await fetch(`/api/projects/${this.activeProjectId}/recovery-suggestions`);
      const data = await res.json();
      if (!data.success) throw new Error('Failed to load recovery suggestions.');

      // Render Executive AI Advisory Banner
      const advisory = data.executive_advisory || {};
      const advTextElem = document.getElementById('ai-advisory-text');
      const advBadge = document.getElementById('ai-advisory-mode-badge');
      const advLabel = document.getElementById('ai-advisory-provider-label');

      if (advTextElem) {
        advTextElem.innerHTML = advisory.text ? this.escapeHtml(advisory.text).replace(/\n/g, '<br>') : 'Synthesizing recommendations...';
      }

      if (advBadge) {
        if (advisory.is_online) {
          advBadge.textContent = advisory.status_badge || 'Cloud AI Active';
          advBadge.style.background = 'rgba(99, 102, 241, 0.2)';
          advBadge.style.color = '#a5b4fc';
          advBadge.style.border = '1px solid rgba(99, 102, 241, 0.5)';
        } else {
          advBadge.textContent = advisory.status_badge || 'Offline Mode Active';
          advBadge.style.background = 'rgba(16, 185, 129, 0.15)';
          advBadge.style.color = '#34d399';
          advBadge.style.border = '1px solid rgba(16, 185, 129, 0.3)';
        }
      }

      if (advLabel) {
        advLabel.textContent = `Engine: ${advisory.provider || 'Local Heuristic Engine'}`;
      }

      const container = document.getElementById('ai-recommendations-list');
      const suggs = data.suggestions || [];

      if (!container) return;

      if (suggs.length === 0) {
        container.innerHTML = '<div class="card"><div class="card-body" style="text-align: center; color: var(--text-muted);">No urgent recovery actions required. Project is currently on track.</div></div>';
        return;
      }

      container.innerHTML = suggs.map((s) => {
        let pColor = '#3b82f6';
        if (s.priority === 'CRITICAL' || s.priority === 'Critical') pColor = '#ef4444';
        else if (s.priority === 'HIGH' || s.priority === 'High') pColor = '#f59e0b';

        return `
          <div class="card" style="border-left: 4px solid ${pColor};">
            <div class="card-body">
              <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                <div style="display: flex; align-items: center; gap: 10px;">
                  <span class="badge" style="background: ${pColor}20; color: ${pColor}; border: 1px solid ${pColor}40; font-weight: 700;">
                    ${s.priority} PRIORITY
                  </span>
                  <h3 style="font-size: 15px; font-weight: 700; margin: 0; color: #fff;">${this.escapeHtml(s.title || s.recommendation)}</h3>
                </div>
                <span class="badge" style="background: rgba(255,255,255,0.06); font-size: 11px;">Impact: ${this.escapeHtml(s.expected_impact)}</span>
              </div>
              <p style="font-size: 13px; color: var(--text-secondary); margin: 6px 0 12px 0;">
                <b>Rationale:</b> ${this.escapeHtml(s.reason)}
              </p>
              <div style="background: rgba(0,0,0,0.25); border-radius: var(--radius-sm); padding: 10px 14px; font-size: 12px; color: #cbd5e1;">
                <b>Recommended Action:</b> ${this.escapeHtml(s.recommendation)}
              </div>
            </div>
          </div>
        `;
      }).join('');

    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  async openAIConfigModal() {
    try {
      const res = await fetch('/api/settings/ai-config');
      const data = await res.json();
      if (data.success) {
        const provSelect = document.getElementById('ai-config-provider');
        if (provSelect) provSelect.value = data.provider || 'gemini';
        const hint = document.getElementById('ai-config-key-hint');
        if (hint) {
          if (data.has_key) {
            hint.innerHTML = `<span style="color: #34d399;">Active Key: ${data.masked_key}</span> (Cloud AI enabled)`;
          } else {
            hint.textContent = 'No API key currently saved. The system is operating in Offline Local Mode.';
          }
        }
      }
    } catch (e) {
      console.warn("Could not load AI config:", e);
    }
    document.getElementById('ai-config-modal')?.classList.add('active');
  },

  closeAIConfigModal() {
    document.getElementById('ai-config-modal')?.classList.remove('active');
  },

  async saveAIConfig() {
    const provider = document.getElementById('ai-config-provider')?.value || 'gemini';
    const key = document.getElementById('ai-config-key')?.value.trim() || '';

    try {
      const res = await fetch('/api/settings/ai-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, api_key: key })
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      this.showToast(key ? 'Cloud AI enabled with offline fallback!' : 'Operating in 100% Offline Local Mode.', 'success');
      this.closeAIConfigModal();
      document.getElementById('ai-config-key').value = '';
      if (this.currentView === 'ai-recommendations') {
        this.loadAIRecommendations();
      }
    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  async clearAIKey() {
    try {
      await fetch('/api/settings/ai-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: 'gemini', api_key: '' })
      });
      this.showToast('Reset to 100% Offline Mode.', 'info');
      this.closeAIConfigModal();
      document.getElementById('ai-config-key').value = '';
      if (this.currentView === 'ai-recommendations') {
        this.loadAIRecommendations();
      }
    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  // --- HELPERS ---
  renderStatusBadge(status) {
    const s = (status || 'Not Started').toLowerCase().replace(' ', '');
    return `<span class="badge badge-${s}"><span class="badge-dot"></span>${status}</span>`;
  },

  getInitials(name) {
    if (!name) return 'U';
    const parts = name.trim().split(' ');
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return name.substring(0, 2).toUpperCase();
  },

  escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  },

  // ==========================================
  // USER AUTHENTICATION & SCOPED RBAC
  // ==========================================
  isCurrentUserLead() {
    if (!this.currentUser || !this.activeProjectId) return true;
    const pRole = (this.currentUser.roles || {})[String(this.activeProjectId)];
    if (!pRole) return true;
    return !!pRole.is_lead;
  },

  initNetworkDetector() {
    const updateStatus = (isOnline) => {
      const pill = document.getElementById('topbar-network-pill');
      const dot = document.getElementById('topbar-network-dot');
      const text = document.getElementById('topbar-network-text');
      if (!pill || !dot || !text) return;

      if (isOnline) {
        pill.style.background = 'rgba(16, 185, 129, 0.15)';
        pill.style.color = '#34d399';
        pill.style.borderColor = 'rgba(16, 185, 129, 0.3)';
        dot.style.background = '#10b981';
        text.textContent = 'Online';
      } else {
        pill.style.background = 'rgba(245, 158, 11, 0.15)';
        pill.style.color = '#fbbf24';
        pill.style.borderColor = 'rgba(245, 158, 11, 0.3)';
        dot.style.background = '#f59e0b';
        text.textContent = 'Offline Mode';
      }
    };

    // Check frontend browser online state + verify with backend ping
    fetch('/api/system/network-status')
      .then(r => r.json())
      .then(d => updateStatus(d.is_online))
      .catch(() => updateStatus(navigator.onLine));

    window.addEventListener('online', () => {
      updateStatus(true);
      this.showToast('Internet connected: Live cloud AI recommendations available.', 'info');
      if (this.currentView === 'ai-recommendations') this.loadAIRecommendations();
    });

    window.addEventListener('offline', () => {
      updateStatus(false);
      this.showToast('Internet offline: 100% Local Heuristic Engine active.', 'warning');
      if (this.currentView === 'ai-recommendations') this.loadAIRecommendations();
    });
  },

  updateUserSessionHeader() {
    if (!this.currentUser) return;
    const avatar = document.getElementById('topbar-user-avatar');
    const nameEl = document.getElementById('topbar-user-name');
    const roleBadge = document.getElementById('topbar-user-role-badge');
    if (!avatar || !nameEl || !roleBadge) return;

    avatar.textContent = this.getInitials(this.currentUser.full_name);
    avatar.style.background = this.currentUser.avatar_color || '#6366F1';
    nameEl.textContent = this.currentUser.full_name;

    const pRole = (this.currentUser.roles || {})[String(this.activeProjectId)];
    if (pRole) {
      if (pRole.is_lead) {
        roleBadge.textContent = `👑 ${pRole.role_title}`;
        roleBadge.style.color = '#34d399';
      } else {
        roleBadge.textContent = `🔒 ${pRole.role_title}`;
        roleBadge.style.color = '#fbbf24';
      }
    } else {
      roleBadge.textContent = `Contributor`;
      roleBadge.style.color = '#94a3b8';
    }

    const sel = document.getElementById('active-user-select');
    if (sel) sel.value = String(this.currentUser.id);
  },

  async loadAuthUsers() {
    try {
      const res = await fetch('/api/auth/users');
      const data = await res.json();
      if (data.success) {
        this.authUsers = data.users || [];
        this.renderQuickAccountsList();
      }
    } catch (e) {
      console.warn("Could not load auth users:", e);
    }
  },

  renderQuickAccountsList() {
    const container = document.getElementById('auth-quick-accounts-list');
    if (!container) return;

    container.innerHTML = this.authUsers.map(u => {
      const pRole = (u.roles || {})[String(this.activeProjectId)] || { role_title: 'Contributor', is_lead: false };
      const isLead = pRole.is_lead;
      const badgeClass = isLead ? 'badge-completed' : 'badge-atrisk';
      const badgeText = isLead ? `👑 Lead in Proj #${this.activeProjectId}` : `🔒 Member (${pRole.role_title})`;

      return `
        <div style="display: flex; align-items: center; justify-content: space-between; background: rgba(15, 23, 42, 0.6); padding: 8px 12px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.06);">
          <div style="display: flex; align-items: center; gap: 8px;">
            <div class="avatar-circle" style="width: 24px; height: 24px; font-size: 10px; background: ${u.avatar_color || '#6366f1'};">${this.getInitials(u.full_name)}</div>
            <div>
              <div style="font-size: 12px; font-weight: 700; color: #fff;">${this.escapeHtml(u.full_name)} <span style="font-size: 11px; color: var(--text-muted);">(@${u.username})</span></div>
              <span class="badge ${badgeClass}" style="font-size: 10px; padding: 1px 6px;">${badgeText}</span>
            </div>
          </div>
          <button class="quick-action-btn btn-secondary" style="padding: 3px 10px; font-size: 11px;" onclick="App.quickLogin(${u.id})">
            Select
          </button>
        </div>
      `;
    }).join('');
  },

  openAuthModal() {
    this.renderQuickAccountsList();
    document.getElementById('auth-modal')?.classList.add('active');
  },

  closeAuthModal() {
    document.getElementById('auth-modal')?.classList.remove('active');
  },

  switchAuthTab(tab) {
    const paneLogin = document.getElementById('auth-pane-login');
    const paneReg = document.getElementById('auth-pane-register');
    const tabLogin = document.getElementById('auth-tab-login');
    const tabReg = document.getElementById('auth-tab-register');

    if (tab === 'login') {
      if (paneLogin) paneLogin.style.display = 'block';
      if (paneReg) paneReg.style.display = 'none';
      if (tabLogin) tabLogin.className = 'quick-action-btn btn-primary';
      if (tabReg) tabReg.className = 'quick-action-btn btn-secondary';
    } else {
      if (paneLogin) paneLogin.style.display = 'none';
      if (paneReg) paneReg.style.display = 'block';
      if (tabLogin) tabLogin.className = 'quick-action-btn btn-secondary';
      if (tabReg) tabReg.className = 'quick-action-btn btn-primary';
    }
  },

  async quickLogin(userId) {
    const u = this.authUsers.find(x => x.id === userId);
    if (!u) return;

    this.currentUser = u;
    this.updateUserSessionHeader();
    this.closeAuthModal();

    const pRole = (u.roles || {})[String(this.activeProjectId)] || { role_title: 'Contributor', is_lead: false };
    const roleDesc = pRole.is_lead ? '👑 Project Lead (Full Workspace Access)' : `🔒 ${pRole.role_title} (Private Contributor View)`;
    this.showToast(`Switched account to ${u.full_name} — ${roleDesc}`, 'success');

    if (this.currentView === 'tasks') {
      await this.loadTasks();
    } else if (this.currentView === 'daily-updates') {
      await this.loadDailyUpdates();
    } else {
      this.switchView(this.currentView);
    }
  },

  async submitLogin() {
    const username = document.getElementById('auth-login-username')?.value.trim();
    const password = document.getElementById('auth-login-password')?.value.trim();

    if (!username || !password) {
      this.showToast("Please enter both username and password.", "error");
      return;
    }

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      this.currentUser = data.user;
      this.updateUserSessionHeader();
      this.closeAuthModal();
      const pwdEl = document.getElementById('auth-login-password');
      if (pwdEl) pwdEl.value = '';

      const pRole = (this.currentUser.roles || {})[String(this.activeProjectId)] || { role_title: 'Contributor', is_lead: false };
      const roleDesc = pRole.is_lead ? '👑 Project Lead (Full Access)' : `🔒 ${pRole.role_title} (Private Access)`;
      this.showToast(`Authenticated as ${this.currentUser.full_name} (${roleDesc})`, 'success');

      if (this.currentView === 'tasks') {
        await this.loadTasks();
      } else if (this.currentView === 'daily-updates') {
        await this.loadDailyUpdates();
      } else {
        this.switchView(this.currentView);
      }
    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

  async submitRegister() {
    const fullName = document.getElementById('auth-reg-fullname')?.value.trim();
    const username = document.getElementById('auth-reg-username')?.value.trim();
    const password = document.getElementById('auth-reg-password')?.value.trim();

    const role1Sel = document.getElementById('auth-reg-role-1');
    const role2Sel = document.getElementById('auth-reg-role-2');
    const role3Sel = document.getElementById('auth-reg-role-3');

    const role1 = role1Sel?.value || 'Developer';
    const isLead1 = parseInt(role1Sel?.options[role1Sel.selectedIndex]?.getAttribute('data-lead') || '0');
    const role2 = role2Sel?.value || 'Developer';
    const isLead2 = parseInt(role2Sel?.options[role2Sel.selectedIndex]?.getAttribute('data-lead') || '0');
    const role3 = role3Sel?.value || 'Developer';
    const isLead3 = parseInt(role3Sel?.options[role3Sel.selectedIndex]?.getAttribute('data-lead') || '0');

    if (!fullName || !username || !password) {
      this.showToast("Full name, username, and password are required.", "error");
      return;
    }

    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: fullName,
          username,
          password,
          roles: {
            "1": { role_title: role1, is_lead: isLead1 },
            "2": { role_title: role2, is_lead: isLead2 },
            "3": { role_title: role3, is_lead: isLead3 }
          }
        })
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      this.currentUser = data.user;
      this.updateUserSessionHeader();
      await this.loadAuthUsers();
      this.closeAuthModal();

      this.showToast(`Character profile created! Logged in as ${this.currentUser.full_name}`, 'success');

      if (this.currentView === 'tasks') {
        await this.loadTasks();
      } else if (this.currentView === 'daily-updates') {
        await this.loadDailyUpdates();
      } else {
        this.switchView(this.currentView);
      }
    } catch (err) {
      this.showToast(err.message, 'error');
    }
  },

};

// Bootstrap on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  App.init();
});
