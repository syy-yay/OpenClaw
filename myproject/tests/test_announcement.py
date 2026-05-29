# -*- coding: utf-8 -*-
"""团队公告功能测试（Session版）"""
import unittest, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import create_app
from models import db


class TestAnnouncement(unittest.TestCase):
    """公告 API 测试"""

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

    def _login_admin(self):
        self.client.post('/api/auth/login', json={
            'identity': 'admin', 'password': 'admin123',
        })

    def test_get_empty_list(self):
        rv = self.client.get('/api/announcements')
        self.assertEqual(len(rv.get_json()), 0)

    def test_create_without_login(self):
        rv = self.client.post('/api/announcements', json={
            'title': '公告', 'content': '内容',
        })
        self.assertEqual(rv.status_code, 403)

    def test_create_with_admin(self):
        self._login_admin()
        rv = self.client.post('/api/announcements', json={
            'title': '系统更新通知',
            'content': '系统将于今晚进行维护升级。',
        })
        self.assertEqual(rv.status_code, 201)
        self.assertEqual(rv.get_json()['title'], '系统更新通知')

    def test_create_empty_title(self):
        self._login_admin()
        rv = self.client.post('/api/announcements', json={
            'title': '', 'content': '内容',
        })
        self.assertEqual(rv.status_code, 400)

    def test_get_list(self):
        self._login_admin()
        self.client.post('/api/announcements', json={'title': '公告A', 'content': '内容A'})
        self.client.post('/api/announcements', json={'title': '公告B', 'content': '内容B'})
        rv = self.client.get('/api/announcements')
        data = rv.get_json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['title'], '公告B')

    def test_pinned_first(self):
        self._login_admin()
        self.client.post('/api/announcements', json={'title': '普通', 'content': '普通'})
        self.client.post('/api/announcements', json={'title': '置顶', 'content': '重要', 'is_pinned': True})
        rv = self.client.get('/api/announcements')
        data = rv.get_json()
        self.assertEqual(data[0]['title'], '置顶')
        self.assertTrue(data[0]['is_pinned'])

    def test_get_detail(self):
        self._login_admin()
        rv = self.client.post('/api/announcements', json={'title': '详情', 'content': '详情内容'})
        ann_id = rv.get_json()['id']
        rv2 = self.client.get(f'/api/announcements/{ann_id}')
        self.assertEqual(rv2.get_json()['title'], '详情')

    def test_delete_by_admin(self):
        self._login_admin()
        rv = self.client.post('/api/announcements', json={'title': '删我', 'content': '可删'})
        ann_id = rv.get_json()['id']
        rv2 = self.client.delete(f'/api/announcements/{ann_id}')
        self.assertTrue(rv2.get_json()['success'])

    def test_delete_without_login(self):
        rv = self.client.delete('/api/announcements/1')
        self.assertEqual(rv.status_code, 404)

    def test_toggle_pin(self):
        self._login_admin()
        rv = self.client.post('/api/announcements', json={'title': '可置顶', 'content': '测试'})
        ann_id = rv.get_json()['id']
        rv2 = self.client.post(f'/api/announcements/{ann_id}/pin')
        self.assertTrue(rv2.get_json()['success'])
        self.assertTrue(rv2.get_json()['announcement']['is_pinned'])

    def test_announcement_includes_author(self):
        self._login_admin()
        rv = self.client.post('/api/announcements', json={'title': '作者测试', 'content': '内容'})
        self.assertEqual(rv.get_json()['author'], 'admin')


if __name__ == '__main__':
    unittest.main()
