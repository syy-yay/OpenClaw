# -*- coding: utf-8 -*-
"""任务备注功能测试"""
import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import create_app
from models import db, User


class TestNoteAPI(unittest.TestCase):
    """任务备注 API 测试"""

    def setUp(self):
        self.app = create_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.user = User(username='noteuser', email='note@e.com')
        self.user.set_password('Test123456')
        db.session.add(self.user)

        self.other = User(username='otheruser', email='other@e.com')
        self.other.set_password('Test123456')
        db.session.add(self.other)

        self.admin = User(username='noteadmin', email='na@e.com', role='admin')
        self.admin.set_password('Admin123456')
        db.session.add(self.admin)
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user.id
            sess['username'] = 'noteuser'
            sess['user_role'] = 'user'
            sess['login_time'] = '2026-01-01T00:00:00'
            sess['login_ip'] = '127.0.0.1'

    def tearDown(self):
        db.drop_all()
        self.ctx.pop()

    def _create_task(self):
        rv = self.client.post('/api/tasks', json={'title': '可备注的任务'})
        return rv.get_json()['id']

    # ========== 创建备注 ==========
    def test_create_note(self):
        task_id = self._create_task()
        rv = self.client.post(f'/api/tasks/{task_id}/notes', json={
            'content': '这是一个备注',
        })
        data = rv.get_json()
        self.assertEqual(rv.status_code, 201)
        self.assertTrue(data['success'])
        self.assertEqual(data['note']['content'], '这是一个备注')
        self.assertEqual(data['note']['user']['username'], 'noteuser')

    def test_create_note_empty(self):
        task_id = self._create_task()
        rv = self.client.post(f'/api/tasks/{task_id}/notes', json={'content': ''})
        self.assertEqual(rv.status_code, 400)

    def test_create_note_too_long(self):
        task_id = self._create_task()
        rv = self.client.post(f'/api/tasks/{task_id}/notes', json={
            'content': 'a' * 10001,
        })
        self.assertEqual(rv.status_code, 400)

    # ========== 编辑备注 ==========
    def test_update_note(self):
        task_id = self._create_task()
        rv = self.client.post(f'/api/tasks/{task_id}/notes', json={'content': '原始内容'})
        note_id = rv.get_json()['note']['id']

        rv2 = self.client.put(f'/api/notes/{note_id}', json={'content': '编辑后的内容'})
        data = rv2.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['note']['content'], '编辑后的内容')

    def test_update_note_by_other_user(self):
        task_id = self._create_task()
        rv = self.client.post(f'/api/tasks/{task_id}/notes', json={'content': '别人的备注'})
        note_id = rv.get_json()['note']['id']

        with self.client.session_transaction() as sess:
            sess['user_id'] = self.other.id
            sess['username'] = 'otheruser'
            sess['user_role'] = 'user'

        rv2 = self.client.put(f'/api/notes/{note_id}', json={'content': '篡改内容'})
        self.assertEqual(rv2.status_code, 403)

    def test_update_note_empty(self):
        task_id = self._create_task()
        rv = self.client.post(f'/api/tasks/{task_id}/notes', json={'content': '内容'})
        note_id = rv.get_json()['note']['id']

        rv2 = self.client.put(f'/api/notes/{note_id}', json={'content': ''})
        self.assertEqual(rv2.status_code, 400)

    # ========== 删除备注 ==========
    def test_delete_note_by_author(self):
        task_id = self._create_task()
        rv = self.client.post(f'/api/tasks/{task_id}/notes', json={'content': '待删除'})
        note_id = rv.get_json()['note']['id']

        rv2 = self.client.delete(f'/api/notes/{note_id}')
        self.assertTrue(rv2.get_json()['success'])

    def test_delete_note_by_admin(self):
        task_id = self._create_task()
        rv = self.client.post(f'/api/tasks/{task_id}/notes', json={'content': '管理员可删'})
        note_id = rv.get_json()['note']['id']

        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin.id
            sess['username'] = 'noteadmin'
            sess['user_role'] = 'admin'

        rv2 = self.client.delete(f'/api/notes/{note_id}')
        self.assertTrue(rv2.get_json()['success'])

    def test_delete_note_by_other(self):
        task_id = self._create_task()
        rv = self.client.post(f'/api/tasks/{task_id}/notes', json={'content': '别人的'})
        note_id = rv.get_json()['note']['id']

        with self.client.session_transaction() as sess:
            sess['user_id'] = self.other.id
            sess['username'] = 'otheruser'
            sess['user_role'] = 'user'

        rv2 = self.client.delete(f'/api/notes/{note_id}')
        self.assertEqual(rv2.status_code, 403)

    # ========== 任务详情（含备注） ==========
    def test_task_detail_includes_notes(self):
        task_id = self._create_task()
        self.client.post(f'/api/tasks/{task_id}/notes', json={'content': '备注1'})
        self.client.post(f'/api/tasks/{task_id}/notes', json={'content': '备注2'})

        rv = self.client.get(f'/api/tasks/{task_id}')
        data = rv.get_json()
        self.assertIn('notes', data)
        self.assertEqual(len(data['notes']), 2)
        self.assertEqual(data['notes'][0]['content'], '备注1')
        self.assertEqual(data['notes'][1]['content'], '备注2')


if __name__ == '__main__':
    unittest.main()
