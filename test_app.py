import unittest
import json
from app import app
import database

class DependencyRescueTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        # Reset database to clean state
        with self.app.app_context():
            conn = database.get_db_connection()
            conn.executescript('''
                PRAGMA foreign_keys = OFF;
                DROP TABLE IF EXISTS ml_training_logs;
                DROP TABLE IF EXISTS ai_risk_predictions;
                DROP TABLE IF EXISTS task_activity_history;
                DROP TABLE IF EXISTS daily_work_updates;
                DROP TABLE IF EXISTS simulation_history;
                DROP TABLE IF EXISTS activity_logs;
                DROP TABLE IF EXISTS dependencies;
                DROP TABLE IF EXISTS tasks;
                DROP TABLE IF EXISTS projects;
                DROP TABLE IF EXISTS team_members;
                PRAGMA foreign_keys = ON;
            ''')
            conn.commit()
            conn.close()
            database.init_db()

    def test_01_sample_project_initialized(self):
        res = self.client.get('/api/projects')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertGreaterEqual(len(data['projects']), 1)
        p = [proj for proj in data['projects'] if proj['name'] == "Software Development Project"][0]
        self.assertEqual(p['name'], "Software Development Project")
        self.assertEqual(p['total_tasks'], 5)

    def test_02_project_crud(self):
        # Create
        res = self.client.post('/api/projects', json={
            "name": "Mobile App V2",
            "description": "Cross-platform mobile application",
            "start_date": "2026-11-10",
            "deadline": "2026-12-15",
            "status": "Active"
        })
        self.assertEqual(res.status_code, 201)
        pid = res.get_json()['project_id']

        # Read
        res = self.client.get(f'/api/projects/{pid}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()['project']['name'], "Mobile App V2")

        # Update
        res = self.client.put(f'/api/projects/{pid}', json={
            "name": "Mobile App V2 (Updated)",
            "description": "Updated description",
            "start_date": "2026-11-10",
            "deadline": "2026-12-20",
            "status": "On Track"
        })
        self.assertEqual(res.status_code, 200)

        # Delete
        res = self.client.delete(f'/api/projects/{pid}')
        self.assertEqual(res.status_code, 200)
        res = self.client.get(f'/api/projects/{pid}')
        self.assertEqual(res.status_code, 404)

    def test_03_task_crud_and_validation(self):
        # Valid task
        res = self.client.post('/api/projects/1/tasks', json={
            "name": "Documentation & User Manual",
            "description": "Write markdown guides",
            "duration": 2,
            "start_date": "2026-11-20",
            "deadline": "2026-11-22",
            "status": "Not Started",
            "priority": "Low",
            "predecessor_ids": [5]
        })
        self.assertEqual(res.status_code, 201)
        tid = res.get_json()['task_id']

        # Invalid task (duration <= 0)
        res = self.client.post('/api/projects/1/tasks', json={
            "name": "Invalid Task",
            "duration": 0,
            "start_date": "2026-11-20",
            "deadline": "2026-11-22"
        })
        # duration should be adjusted or error
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.get_json()['success'], True)

        # Delete task
        res = self.client.delete(f'/api/tasks/{tid}')
        self.assertEqual(res.status_code, 200)

    def test_04_circular_dependency_prevention(self):
        # Sample dependencies are: 1->2->3->4->5
        # Attempting to add 5 -> 1 must be rejected with HTTP 400
        res = self.client.post('/api/projects/1/dependencies', json={
            "predecessor_id": 5,
            "successor_id": 1
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn("Circular dependency detected", data['error'])

        # Self loop 3 -> 3 must also be rejected
        res = self.client.post('/api/projects/1/dependencies', json={
            "predecessor_id": 3,
            "successor_id": 3
        })
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.get_json()['success'])

    def test_05_bfs_and_dfs_analysis(self):
        # Analyze task 1 (Requirement Analysis):
        # Direct: 2 (UI/UX Design)
        # Indirect: 3, 4, 5
        res = self.client.get('/api/projects/1/dependency-analysis/1')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])

        bfs = data['bfs']
        self.assertEqual(bfs['direct_count'], 1)
        self.assertEqual(bfs['direct_dependents'][0]['id'], 2)
        self.assertEqual(bfs['indirect_count'], 3)
        self.assertEqual(bfs['total_count'], 4)

        dfs = data['dfs']
        self.assertGreaterEqual(dfs['chain_count'], 1)
        chain = dfs['chains'][0]
        self.assertEqual([node['id'] for node in chain], [1, 2, 3, 4, 5])

    def test_06_critical_path_analysis(self):
        res = self.client.get('/api/projects/1/critical-path')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        cpm = data['cpm']
        self.assertFalse(cpm['has_cycle'])
        # Total duration = 2 + 3 + 5 + 3 + 1 = 14 days
        self.assertEqual(cpm['project_duration_days'], 14)
        self.assertEqual(cpm['critical_task_ids'], [1, 2, 3, 4, 5])

    def test_07_what_if_delay_simulator_and_immutability(self):
        # 3-day delay on Task 2 (UI/UX Design)
        # Check original dates first
        res_before = self.client.get('/api/projects/1/tasks')
        tasks_before = {t['id']: t for t in res_before.get_json()['tasks']}

        res = self.client.post('/api/projects/1/simulate', json={
            "task_id": 2,
            "delay_days": 3,
            "save_history": True
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])

        sim = data['simulation']
        summary = sim['summary']
        # Project should be delayed by 3 days
        self.assertEqual(summary['total_project_delay_days'], 3)
        self.assertEqual(summary['simulated_duration_days'], 17)
        # Direct affected: Task 3 (Development)
        self.assertEqual(sim['affected_task_ids']['direct'], [3])
        # Indirect affected: Task 4, 5 (Testing, Deployment)
        self.assertEqual(sim['affected_task_ids']['indirect'], [4, 5])

        # CRITICAL TEST: Verify original database dates were NOT mutated
        res_after = self.client.get('/api/projects/1/tasks')
        tasks_after = {t['id']: t for t in res_after.get_json()['tasks']}
        for tid in tasks_before:
            self.assertEqual(tasks_before[tid]['duration'], tasks_after[tid]['duration'])
            self.assertEqual(tasks_before[tid]['start_date'], tasks_after[tid]['start_date'])
            self.assertEqual(tasks_before[tid]['deadline'], tasks_after[tid]['deadline'])

    def test_08_risk_and_recovery_suggestions(self):
        # Risk Analysis
        res = self.client.get('/api/projects/1/risk-analysis')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn(data['risk']['overall_risk_level'], ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'])

        # Recovery Suggestions
        res = self.client.get('/api/projects/1/recovery-suggestions')
        self.assertEqual(res.status_code, 200)
        suggs = res.get_json()['suggestions']
        self.assertGreaterEqual(len(suggs), 1)
        for s in suggs:
            self.assertIn('recommendation', s)
            self.assertIn('reason', s)
            self.assertIn('expected_impact', s)
            self.assertIn('priority', s)

    def test_09_workload_analysis(self):
        res = self.client.get('/api/projects/1/workload')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertGreaterEqual(len(data['team_workload']), 1)

    def test_10_pdf_report_generation(self):
        res = self.client.get('/api/projects/1/report/pdf')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers['Content-Type'], 'application/pdf')
        # Check PDF magic bytes '%PDF-'
        self.assertTrue(res.data.startswith(b'%PDF-'))
        self.assertGreater(len(res.data), 1000)

    def test_11_automatic_progress_tracking(self):
        # Update progress of Task 1 to 50%
        res = self.client.put('/api/tasks/1/progress', json={
            "progress_pct": 50,
            "status": "In Progress",
            "hours_spent": 8.0,
            "member_id": 1,
            "comments": "Completed initial draft specifications"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['new_progress'], 50)
        self.assertEqual(data['new_status'], "In Progress")

        # Verify activity history logged
        h_res = self.client.get('/api/tasks/1/history')
        self.assertEqual(h_res.status_code, 200)
        h_data = h_res.get_json()
        self.assertGreaterEqual(len(h_data['history']), 1)
        self.assertEqual(h_data['history'][0]['new_progress'], 50)

    def test_12_daily_work_updates(self):
        # Submit a daily work update for Task 2
        res = self.client.post('/api/projects/1/daily-updates', json={
            "task_id": 2,
            "team_member_id": 2,
            "work_description": "Created interactive wireframes in Figma",
            "progress_pct": 70,
            "remaining_work": "Mobile responsive screen mockups",
            "problems_faced": "Awaiting design token specs",
            "estimated_remaining_days": 1,
            "submission_date": "2026-11-10"
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('update_id', data)

        # Task 2 progress should automatically update to 70%
        t_res = self.client.get('/api/projects/1/tasks')
        tasks = {t['id']: t for t in t_res.get_json()['tasks']}
        self.assertEqual(tasks[2]['progress_pct'], 70)
        self.assertEqual(tasks[2]['status'], 'In Progress')

        # Check daily updates summary endpoint
        s_res = self.client.get('/api/projects/1/daily-updates/summary')
        self.assertEqual(s_res.status_code, 200)
        s_data = s_res.get_json()
        self.assertIn('compliance_rate_pct', s_data)
        self.assertIn('pending_members', s_data)

    def test_13_ai_risk_prediction_and_model_training(self):
        # AI Risk prediction endpoint
        res = self.client.get('/api/projects/1/ai-risk-prediction')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('overall_project_risk', data)
        self.assertIn('task_predictions', data)
        self.assertIn('high_risk_tasks', data)
        self.assertIn('project_delay_probability', data)

        # Scikit-learn model retraining
        train_res = self.client.post('/api/ai/train-model')
        self.assertEqual(train_res.status_code, 200)
        train_data = train_res.get_json()
        self.assertTrue(train_data['success'])
        self.assertIn('metadata', train_data)

    def test_14_smart_dashboard(self):
        res = self.client.get('/api/projects/1/smart-dashboard')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('summary_cards', data)
        self.assertIn('ai_insights', data)
        cards = data['summary_cards']
        self.assertIn('overall_project_progress', cards)
        self.assertIn('project_delay_probability', cards)

if __name__ == '__main__':
    unittest.main()

