# -*- coding: utf-8 -*-
"""任务截止日期功能测试"""
import unittest
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import create_app
from models import db, User, Task


class TestTaskDueDate(unittest.TestCase):
    """任务截止日期 API 测试"""

    def setUp(self):
        self.app = create_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.user = User(username='dueuser', email='due@e.com')
        self.user.set_password('Test123456')
        db.session.add(self.user)
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user.id
            sess['username'] = 'dueuser'
            sess['user_role'] = 'user'

    def tearDown(self):
        db.drop_all()
        self.ctx.pop()

    # ========== 创建任务 ==========
    def test_create_task_no_due_date(self):
        """不传 due_date 则为 None"""
        rv = self.client.post('/api/tasks', json={'title': '无截止日期'})
        data = rv.get_json()
        self.assertIsNone(data['due_date'])
        self.assertIsNone(data['days_remaining'])

    def test_create_task_with_due_date(self):
        today = date.today().isoformat()
        rv = self.client.post('/api/tasks', json={
            'title': '有截止日期', 'due_date': today,
        })
        data = rv.get_json()
        self.assertEqual(data['due_date'], today)
        self.assertEqual(data['days_remaining'], 0)

    def test_create_task_future_due_date(self):
        future = (date.today() + timedelta(days=5)).isoformat()
        rv = self.client.post('/api/tasks', json={
            'title': '未来截止', 'due_date': future,
        })
        data = rv.get_json()
        self.assertEqual(data['days_remaining'], 5)

    def test_create_task_past_due_date(self):
        past = (date.today() - timedelta(days=3)).isoformat()
        rv = self.client.post('/api/tasks', json={
            'title': '已过期', 'due_date': past,
        })
        data = rv.get_json()
        self.assertEqual(data['days_remaining'], -3)

    def test_create_task_invalid_date(self):
        rv = self.client.post('/api/tasks', json={
            'title': '无效日期', 'due_date': 'not-a-date',
        })
        self.assertEqual(rv.status_code, 400)

    # ========== 修改任务 ==========
    def test_update_due_date(self):
        rv = self.client.post('/api/tasks', json={'title': '改截止日'})
        task_id = rv.get_json()['id']

        future = (date.today() + timedelta(days=10)).isoformat()
        rv2 = self.client.put(f'/api/tasks/{task_id}', json={
            'due_date': future,
        })
        data = rv2.get_json()
        self.assertEqual(data['due_date'], future)
        self.assertEqual(data['days_remaining'], 10)

    def test_clear_due_date(self):
        today = date.today().isoformat()
        rv = self.client.post('/api/tasks', json={
            'title': '可清空', 'due_date': today,
        })
        task_id = rv.get_json()['id']

        rv2 = self.client.put(f'/api/tasks/{task_id}', json={'due_date': None})
        data = rv2.get_json()
        self.assertIsNone(data['due_date'])
        self.assertIsNone(data['days_remaining'])

    def test_update_invalid_date(self):
        rv = self.client.post('/api/tasks', json={'title': '改无效'})
        task_id = rv.get_json()['id']

        rv2 = self.client.put(f'/api/tasks/{task_id}', json={
            'due_date': 'bad-date',
        })
        self.assertEqual(rv2.status_code, 400)

    # ========== 查看任务 ==========
    def test_get_task_includes_due_date(self):
        today = date.today().isoformat()
        rv = self.client.post('/api/tasks', json={
            'title': '查看截止', 'due_date': today,
        })
        task_id = rv.get_json()['id']

        rv2 = self.client.get('/api/tasks')
        data = rv2.get_json()
        task = next(t for t in data if t['id'] == task_id)
        self.assertIn('due_date', task)
        self.assertIn('days_remaining', task)
        self.assertEqual(task['due_date'], today)


if __name__ == '__main__':
    unittest.main()
