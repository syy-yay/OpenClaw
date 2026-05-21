# -*- coding: utf-8 -*-
"""任务优先级功能测试"""
import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import create_app
from models import db, User, Task


class TestTaskPriority(unittest.TestCase):
    """任务优先级 API 测试"""

    def setUp(self):
        self.app = create_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.user = User(username='priorityuser', email='p@e.com')
        self.user.set_password('Test123456')
        db.session.add(self.user)
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user.id
            sess['username'] = 'priorityuser'
            sess['user_role'] = 'user'

    def tearDown(self):
        db.drop_all()
        self.ctx.pop()

    # ========== 创建任务 ==========
    def test_create_task_default_priority(self):
        """创建任务时未指定优先级，默认为 medium"""
        rv = self.client.post('/api/tasks', json={'title': '默认优先级'})
        data = rv.get_json()
        self.assertEqual(rv.status_code, 201)
        self.assertEqual(data['priority'], 'medium')

    def test_create_task_high_priority(self):
        rv = self.client.post('/api/tasks', json={
            'title': '高优先级', 'priority': 'high',
        })
        self.assertEqual(rv.status_code, 201)
        self.assertEqual(rv.get_json()['priority'], 'high')

    def test_create_task_low_priority(self):
        rv = self.client.post('/api/tasks', json={
            'title': '低优先级', 'priority': 'low',
        })
        self.assertEqual(rv.status_code, 201)
        self.assertEqual(rv.get_json()['priority'], 'low')

    def test_create_task_invalid_priority(self):
        rv = self.client.post('/api/tasks', json={
            'title': '无效', 'priority': 'urgent',
        })
        self.assertEqual(rv.status_code, 400)

    # ========== 查看任务 ==========
    def test_get_task_includes_priority(self):
        rv = self.client.post('/api/tasks', json={
            'title': '测试', 'priority': 'high',
        })
        task_id = rv.get_json()['id']

        rv2 = self.client.get(f'/api/tasks')
        data = rv2.get_json()
        task = next(t for t in data if t['id'] == task_id)
        self.assertIn('priority', task)
        self.assertEqual(task['priority'], 'high')

    # ========== 排序 ==========
    def test_tasks_sorted_by_priority(self):
        self.client.post('/api/tasks', json={'title': '低', 'priority': 'low'})
        self.client.post('/api/tasks', json={'title': '高', 'priority': 'high'})
        self.client.post('/api/tasks', json={'title': '中', 'priority': 'medium'})

        rv = self.client.get('/api/tasks?sort=priority')
        data = rv.get_json()
        priorities = [t['priority'] for t in data]
        # 默认降序：high → medium → low
        self.assertEqual(priorities[0], 'high')
        self.assertEqual(priorities[1], 'medium')
        self.assertEqual(priorities[2], 'low')

    def test_tasks_sorted_by_priority_asc(self):
        self.client.post('/api/tasks', json={'title': '低', 'priority': 'low'})
        self.client.post('/api/tasks', json={'title': '高', 'priority': 'high'})

        rv = self.client.get('/api/tasks?sort=priority&order=asc')
        data = rv.get_json()
        self.assertEqual(data[0]['priority'], 'low')
        self.assertEqual(data[-1]['priority'], 'high')

    # ========== 修改任务优先级 ==========
    def test_update_priority(self):
        rv = self.client.post('/api/tasks', json={'title': '可改优先级'})
        task_id = rv.get_json()['id']

        rv2 = self.client.put(f'/api/tasks/{task_id}', json={
            'priority': 'high',
        })
        data = rv2.get_json()
        self.assertEqual(data['priority'], 'high')

    def test_update_priority_invalid(self):
        rv = self.client.post('/api/tasks', json={'title': '不改'})
        task_id = rv.get_json()['id']

        rv2 = self.client.put(f'/api/tasks/{task_id}', json={
            'priority': 'invalid',
        })
        self.assertEqual(rv2.status_code, 400)

    def test_update_not_affect_other_fields(self):
        """修改优先级不应改变其他字段"""
        rv = self.client.post('/api/tasks', json={
            'title': '原标题', 'status': 'pending',
        })
        task_id = rv.get_json()['id']

        self.client.put(f'/api/tasks/{task_id}', json={'priority': 'high'})
        rv2 = self.client.get('/api/tasks')
        task = next(t for t in rv2.get_json() if t['id'] == task_id)
        self.assertEqual(task['title'], '原标题')
        self.assertEqual(task['status'], 'pending')
        self.assertEqual(task['priority'], 'high')


if __name__ == '__main__':
    unittest.main()
