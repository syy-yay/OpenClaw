# -*- coding: utf-8 -*-
"""任务统计 API 测试"""
import unittest, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import create_app
from models import db
from datetime import date, timedelta


class TestTaskStats(unittest.TestCase):
    """任务统计 API 测试"""

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.drop_all()
        self.ctx.pop()

    def test_stats_empty(self):
        rv = self.client.get('/api/tasks/stats')
        data = rv.get_json()
        self.assertEqual(data['total'], 0)
        self.assertEqual(data['completion_rate'], 0)

    def test_stats_by_status(self):
        self.client.post('/api/tasks', json={'title': '待办'})
        self.client.post('/api/tasks', json={'title': '进行中', 'status': 'in-progress'})
        self.client.post('/api/tasks', json={'title': '已完成', 'status': 'completed'})

        rv = self.client.get('/api/tasks/stats')
        data = rv.get_json()
        self.assertEqual(data['total'], 3)
        self.assertEqual(data['by_status']['pending'], 1)
        self.assertEqual(data['by_status']['in-progress'], 1)
        self.assertEqual(data['by_status']['completed'], 1)

    def test_stats_by_priority(self):
        self.client.post('/api/tasks', json={'title': '高', 'priority': 'high'})
        self.client.post('/api/tasks', json={'title': '高2', 'priority': 'high'})
        self.client.post('/api/tasks', json={'title': '中', 'priority': 'medium'})

        rv = self.client.get('/api/tasks/stats')
        data = rv.get_json()
        self.assertEqual(data['by_priority']['high'], 2)
        self.assertEqual(data['by_priority']['medium'], 1)

    def test_completion_rate(self):
        self.client.post('/api/tasks', json={'title': '完成', 'status': 'completed'})
        self.client.post('/api/tasks', json={'title': '待办'})
        self.client.post('/api/tasks', json={'title': '待办2'})
        self.client.post('/api/tasks', json={'title': '待办3'})

        rv = self.client.get('/api/tasks/stats')
        data = rv.get_json()
        self.assertEqual(data['total'], 4)
        self.assertEqual(data['by_status']['completed'], 1)
        self.assertEqual(data['by_status']['pending'], 3)
        self.assertEqual(data['completion_rate'], 25.0)

    def test_due_date_stats(self):
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        far = (date.today() + timedelta(days=10)).isoformat()

        self.client.post('/api/tasks', json={'title': '已过期', 'due_date': yesterday})
        self.client.post('/api/tasks', json={'title': '今天', 'due_date': today})
        self.client.post('/api/tasks', json={'title': '明天', 'due_date': tomorrow})
        self.client.post('/api/tasks', json={'title': '未来', 'due_date': far})
        self.client.post('/api/tasks', json={'title': '无截止'})

        rv = self.client.get('/api/tasks/stats')
        data = rv.get_json()
        self.assertEqual(data['due_date']['overdue'], 1)
        self.assertEqual(data['due_date']['today'], 1)
        self.assertEqual(data['due_date']['soon'], 1)
        self.assertEqual(data['due_date']['with_due_date'], 4)
        self.assertEqual(data['due_date']['without_due_date'], 1)

    def test_stats_by_tag(self):
        self.client.post('/api/tags', json={'name': 'bug'})
        self.client.post('/api/tags', json={'name': 'feature'})
        self.client.post('/api/tasks', json={'title': '修复', 'tags': ['bug']})
        self.client.post('/api/tasks', json={'title': '功能', 'tags': ['feature']})

        rv = self.client.get('/api/tasks/stats')
        data = rv.get_json()
        self.assertEqual(len(data['by_tag']), 2)
        tag_names = [t['name'] for t in data['by_tag']]
        self.assertIn('bug', tag_names)
        self.assertIn('feature', tag_names)


if __name__ == '__main__':
    unittest.main()
