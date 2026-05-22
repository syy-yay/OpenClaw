# -*- coding: utf-8 -*-
"""开放访问版功能冒烟测试"""
import unittest
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import create_app
from models import db, Task, Tag


class TestSmoke(unittest.TestCase):
    """功能冒烟测试"""

    def setUp(self):
        self.app = create_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.drop_all()
        self.ctx.pop()

    # ===== 首页 =====
    def test_homepage(self):
        rv = self.client.get('/')
        self.assertEqual(rv.status_code, 200)

    # ===== 任务 CRUD =====
    def test_create_task(self):
        rv = self.client.post('/api/tasks', json={'title': '测试任务'})
        self.assertEqual(rv.status_code, 201)
        self.assertEqual(rv.get_json()['title'], '测试任务')

    def test_create_task_default_priority(self):
        rv = self.client.post('/api/tasks', json={'title': '默认'})
        self.assertEqual(rv.get_json()['priority'], 'medium')

    def test_create_task_with_priority(self):
        rv = self.client.post('/api/tasks', json={'title': '高', 'priority': 'high'})
        self.assertEqual(rv.get_json()['priority'], 'high')

    def test_create_task_invalid_priority(self):
        rv = self.client.post('/api/tasks', json={'title': 'x', 'priority': 'x'})
        self.assertEqual(rv.status_code, 400)

    def test_get_tasks(self):
        self.client.post('/api/tasks', json={'title': 'A'})
        self.client.post('/api/tasks', json={'title': 'B'})
        rv = self.client.get('/api/tasks')
        self.assertEqual(len(rv.get_json()), 2)

    def test_get_task_detail(self):
        rv = self.client.post('/api/tasks', json={'title': '详情'})
        tid = rv.get_json()['id']
        rv2 = self.client.get(f'/api/tasks/{tid}')
        self.assertEqual(rv2.get_json()['title'], '详情')
        self.assertIn('notes', rv2.get_json())

    def test_update_task(self):
        rv = self.client.post('/api/tasks', json={'title': '旧标题'})
        tid = rv.get_json()['id']
        rv2 = self.client.put(f'/api/tasks/{tid}', json={'title': '新标题'})
        self.assertEqual(rv2.get_json()['title'], '新标题')

    def test_update_priority(self):
        rv = self.client.post('/api/tasks', json={'title': '改优先级'})
        tid = rv.get_json()['id']
        self.client.put(f'/api/tasks/{tid}', json={'priority': 'high'})
        rv2 = self.client.get('/api/tasks')
        self.assertEqual(rv2.get_json()[0]['priority'], 'high')

    def test_priority_sorting(self):
        self.client.post('/api/tasks', json={'title': '低', 'priority': 'low'})
        self.client.post('/api/tasks', json={'title': '高', 'priority': 'high'})
        rv = self.client.get('/api/tasks?sort=priority')
        data = rv.get_json()
        self.assertEqual(data[0]['priority'], 'high')
        self.assertEqual(data[1]['priority'], 'low')

    def test_get_task_progress(self):
        rv = self.client.post('/api/tasks', json={'title': 'P'})
        tid = rv.get_json()['id']
        rv2 = self.client.get(f'/api/tasks/{tid}/progress')
        self.assertIn('progress', rv2.get_json())

    # ===== 截止日期 =====
    def test_due_date(self):
        rv = self.client.post('/api/tasks', json={'title': 'D', 'due_date': '2026-12-31'})
        self.assertEqual(rv.get_json()['due_date'], '2026-12-31')

    def test_due_date_invalid(self):
        rv = self.client.post('/api/tasks', json={'title': 'D', 'due_date': 'bad'})
        self.assertEqual(rv.status_code, 400)

    # ===== 标签 =====
    def test_create_tag(self):
        rv = self.client.post('/api/tags', json={'name': 'bug'})
        self.assertEqual(rv.status_code, 201)
        self.assertEqual(rv.get_json()['tag']['name'], 'bug')

    def test_get_tags(self):
        self.client.post('/api/tags', json={'name': 'bug'})
        self.client.post('/api/tags', json={'name': 'feature'})
        rv = self.client.get('/api/tags')
        self.assertEqual(len(rv.get_json()), 2)

    def test_task_with_tags(self):
        self.client.post('/api/tags', json={'name': 'bug'})
        rv = self.client.post('/api/tasks', json={'title': 'T', 'tags': ['bug']})
        self.assertEqual(len(rv.get_json()['tags']), 1)
        self.assertEqual(rv.get_json()['tags'][0]['name'], 'bug')

    def test_filter_by_tag(self):
        self.client.post('/api/tags', json={'name': 'bug'})
        self.client.post('/api/tasks', json={'title': '修复', 'tags': ['bug']})
        self.client.post('/api/tasks', json={'title': '其他'})
        rv = self.client.get('/api/tasks?tag=bug')
        self.assertEqual(len(rv.get_json()), 1)

    def test_add_remove_tag(self):
        self.client.post('/api/tags', json={'name': 'bug'})
        rv = self.client.post('/api/tasks', json={'title': 'T'})
        tid = rv.get_json()['id']

        rv2 = self.client.post(f'/api/tasks/{tid}/tags', json={'tag': 'bug'})
        self.assertTrue(rv2.get_json()['success'])

        tag_id = Tag.query.filter_by(name='bug').first().id
        rv3 = self.client.delete(f'/api/tasks/{tid}/tags/{tag_id}')
        self.assertTrue(rv3.get_json()['success'])

    # ===== 评论 =====
    def test_create_comment(self):
        rv = self.client.post('/api/tasks', json={'title': 'T'})
        tid = rv.get_json()['id']
        rv2 = self.client.post(f'/api/tasks/{tid}/comments', json={'content': '评论内容'})
        self.assertEqual(rv2.status_code, 201)
        self.assertEqual(rv2.get_json()['comment']['content'], '评论内容')

    def test_get_comments(self):
        rv = self.client.post('/api/tasks', json={'title': 'T'})
        tid = rv.get_json()['id']
        self.client.post(f'/api/tasks/{tid}/comments', json={'content': 'C1'})
        self.client.post(f'/api/tasks/{tid}/comments', json={'content': 'C2'})
        rv2 = self.client.get(f'/api/tasks/{tid}/comments')
        self.assertEqual(len(rv2.get_json()), 2)

    def test_delete_comment(self):
        rv = self.client.post('/api/tasks', json={'title': 'T'})
        tid = rv.get_json()['id']
        rv2 = self.client.post(f'/api/tasks/{tid}/comments', json={'content': '删除'})
        cid = rv2.get_json()['comment']['id']
        rv3 = self.client.delete(f'/api/comments/{cid}')
        self.assertTrue(rv3.get_json()['success'])

    # ===== 备注 =====
    def test_create_note(self):
        rv = self.client.post('/api/tasks', json={'title': 'T'})
        tid = rv.get_json()['id']
        rv2 = self.client.post(f'/api/tasks/{tid}/notes', json={'content': '备注内容'})
        self.assertEqual(rv2.status_code, 201)
        self.assertEqual(rv2.get_json()['note']['content'], '备注内容')

    def test_update_note(self):
        rv = self.client.post('/api/tasks', json={'title': 'T'})
        tid = rv.get_json()['id']
        rv2 = self.client.post(f'/api/tasks/{tid}/notes', json={'content': '原始'})
        nid = rv2.get_json()['note']['id']
        rv3 = self.client.put(f'/api/notes/{nid}', json={'content': '修改后'})
        self.assertEqual(rv3.get_json()['note']['content'], '修改后')

    def test_delete_note(self):
        rv = self.client.post('/api/tasks', json={'title': 'T'})
        tid = rv.get_json()['id']
        rv2 = self.client.post(f'/api/tasks/{tid}/notes', json={'content': '删除'})
        nid = rv2.get_json()['note']['id']
        rv3 = self.client.delete(f'/api/notes/{nid}')
        self.assertTrue(rv3.get_json()['success'])

    # ===== 任务详情含备注 =====
    def test_task_detail_with_notes(self):
        rv = self.client.post('/api/tasks', json={'title': 'T'})
        tid = rv.get_json()['id']
        self.client.post(f'/api/tasks/{tid}/notes', json={'content': 'N1'})
        self.client.post(f'/api/tasks/{tid}/notes', json={'content': 'N2'})
        rv2 = self.client.get(f'/api/tasks/{tid}')
        self.assertEqual(len(rv2.get_json()['notes']), 2)


if __name__ == '__main__':
    unittest.main()
