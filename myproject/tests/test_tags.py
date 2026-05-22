# -*- coding: utf-8 -*-
"""任务标签功能测试"""
import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import create_app
from models import db, User, Tag


class TestTagAPI(unittest.TestCase):
    """标签 API 测试"""

    def setUp(self):
        self.app = create_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.user = User(username='taguser', email='tag@e.com')
        self.user.set_password('Test123456')
        db.session.add(self.user)
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user.id
            sess['username'] = 'taguser'
            sess['user_role'] = 'user'

    def tearDown(self):
        db.drop_all()
        self.ctx.pop()

    # ========== 创建标签 ==========
    def test_create_tag(self):
        rv = self.client.post('/api/tags', json={'name': 'bug'})
        data = rv.get_json()
        self.assertEqual(rv.status_code, 201)
        self.assertEqual(data['tag']['name'], 'bug')

    def test_create_tag_with_color(self):
        rv = self.client.post('/api/tags', json={
            'name': 'urgent', 'color': '#e74c3c',
        })
        data = rv.get_json()
        self.assertEqual(data['tag']['color'], '#e74c3c')

    def test_create_tag_duplicate(self):
        self.client.post('/api/tags', json={'name': 'feature'})
        rv = self.client.post('/api/tags', json={'name': 'feature'})
        self.assertEqual(rv.status_code, 400)

    def test_create_tag_empty_name(self):
        rv = self.client.post('/api/tags', json={'name': ''})
        self.assertEqual(rv.status_code, 400)

    # ========== 获取标签 ==========
    def test_get_tags(self):
        self.client.post('/api/tags', json={'name': 'bug'})
        self.client.post('/api/tags', json={'name': 'feature'})
        rv = self.client.get('/api/tags')
        data = rv.get_json()
        self.assertEqual(len(data), 2)

    # ========== 删除标签 ==========
    def test_delete_tag(self):
        rv = self.client.post('/api/tags', json={'name': 'old'})
        tag_id = rv.get_json()['tag']['id']

        rv2 = self.client.delete(f'/api/tags/{tag_id}')
        self.assertTrue(rv2.get_json()['success'])

        rv3 = self.client.get('/api/tags')
        self.assertEqual(len(rv3.get_json()), 0)

    # ========== 为任务添加标签 ==========
    def test_create_task_with_tags(self):
        self.client.post('/api/tags', json={'name': 'bug'})
        rv = self.client.post('/api/tasks', json={
            'title': '带标签的任务',
            'tags': ['bug'],
        })
        data = rv.get_json()
        self.assertEqual(len(data['tags']), 1)
        self.assertEqual(data['tags'][0]['name'], 'bug')

    def test_add_tag_to_task(self):
        self.client.post('/api/tags', json={'name': 'bug'})
        rv = self.client.post('/api/tasks', json={'title': '任务'})
        task_id = rv.get_json()['id']

        rv2 = self.client.post(f'/api/tasks/{task_id}/tags', json={'tag': 'bug'})
        data = rv2.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['task']['tags']), 1)

    def test_add_nonexistent_tag(self):
        rv = self.client.post('/api/tasks', json={'title': '任务'})
        task_id = rv.get_json()['id']

        rv2 = self.client.post(f'/api/tasks/{task_id}/tags', json={'tag': '不存在'})
        self.assertEqual(rv2.status_code, 404)

    def test_add_duplicate_tag(self):
        self.client.post('/api/tags', json={'name': 'bug'})
        rv = self.client.post('/api/tasks', json={'title': '任务', 'tags': ['bug']})
        task_id = rv.get_json()['id']

        rv2 = self.client.post(f'/api/tasks/{task_id}/tags', json={'tag': 'bug'})
        self.assertEqual(rv2.status_code, 400)

    # ========== 移除任务标签 ==========
    def test_remove_tag_from_task(self):
        self.client.post('/api/tags', json={'name': 'bug'})
        rv = self.client.post('/api/tasks', json={'title': '任务', 'tags': ['bug']})
        task_id = rv.get_json()['id']
        tag_id = rv.get_json()['tags'][0]['id']

        rv2 = self.client.delete(f'/api/tasks/{task_id}/tags/{tag_id}')
        data = rv2.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['task']['tags']), 0)

    # ========== 按标签筛选 ==========
    def test_filter_tasks_by_tag(self):
        self.client.post('/api/tags', json={'name': 'bug'})
        self.client.post('/api/tags', json={'name': 'feature'})

        self.client.post('/api/tasks', json={'title': '修复', 'tags': ['bug']})
        self.client.post('/api/tasks', json={'title': '新功能', 'tags': ['feature']})
        self.client.post('/api/tasks', json={'title': '无标签'})

        rv = self.client.get('/api/tasks?tag=bug')
        data = rv.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['title'], '修复')

        rv2 = self.client.get('/api/tasks?tag=feature')
        self.assertEqual(len(rv2.get_json()), 1)

    def test_multiple_tags_on_task(self):
        self.client.post('/api/tags', json={'name': 'bug'})
        self.client.post('/api/tags', json={'name': 'urgent'})

        rv = self.client.post('/api/tasks', json={
            'title': '重要修复',
            'tags': ['bug', 'urgent'],
        })
        data = rv.get_json()
        self.assertEqual(len(data['tags']), 2)
        tag_names = [t['name'] for t in data['tags']]
        self.assertIn('bug', tag_names)
        self.assertIn('urgent', tag_names)


if __name__ == '__main__':
    unittest.main()
