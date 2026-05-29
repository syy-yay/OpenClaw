# -*- coding: utf-8 -*-
"""团队公告功能测试"""
import unittest, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import create_app
from models import db, User


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
        # create_app 已创建 admin 用户

    def tearDown(self):
        db.drop_all()
        self.ctx.pop()

    def _admin_token(self):
        rv = self.client.post('/api/auth/login', json={
            'identity': 'admin', 'password': 'admin123',
        })
        return rv.get_json()['token']

    def test_get_empty_list(self):
        rv = self.client.get('/api/announcements')
        self.assertEqual(len(rv.get_json()), 0)

    def test_create_without_token(self):
        rv = self.client.post('/api/announcements', json={
            'title': '公告', 'content': '内容',
        })
        self.assertEqual(rv.status_code, 403)

    def test_create_with_admin(self):
        token = self._admin_token()
        rv = self.client.post('/api/announcements', json={
            'title': '系统更新通知',
            'content': '系统将于今晚进行维护升级。',
        }, headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(rv.status_code, 201)
        self.assertEqual(rv.get_json()['title'], '系统更新通知')

    def test_create_empty_title(self):
        token = self._admin_token()
        rv = self.client.post('/api/announcements', json={
            'title': '', 'content': '内容',
        }, headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(rv.status_code, 400)

    def test_get_list(self):
        token = self._admin_token()
        self.client.post('/api/announcements', json={
            'title': '公告A', 'content': '内容A',
        }, headers={'Authorization': f'Bearer {token}'})
        self.client.post('/api/announcements', json={
            'title': '公告B', 'content': '内容B',
        }, headers={'Authorization': f'Bearer {token}'})

        rv = self.client.get('/api/announcements')
        data = rv.get_json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['title'], '公告B')  # 最新的在前

    def test_pinned_first(self):
        token = self._admin_token()
        self.client.post('/api/announcements', json={
            'title': '普通', 'content': '普通',
        }, headers={'Authorization': f'Bearer {token}'})
        self.client.post('/api/announcements', json={
            'title': '置顶', 'content': '重要', 'is_pinned': True,
        }, headers={'Authorization': f'Bearer {token}'})

        rv = self.client.get('/api/announcements')
        data = rv.get_json()
        self.assertEqual(data[0]['title'], '置顶')
        self.assertTrue(data[0]['is_pinned'])

    def test_get_detail(self):
        token = self._admin_token()
        rv = self.client.post('/api/announcements', json={
            'title': '详情', 'content': '详情内容',
        }, headers={'Authorization': f'Bearer {token}'})
        ann_id = rv.get_json()['id']

        rv2 = self.client.get(f'/api/announcements/{ann_id}')
        self.assertEqual(rv2.get_json()['title'], '详情')

    def test_delete_by_admin(self):
        token = self._admin_token()
        rv = self.client.post('/api/announcements', json={
            'title': '删我', 'content': '可删',
        }, headers={'Authorization': f'Bearer {token}'})
        ann_id = rv.get_json()['id']

        rv2 = self.client.delete(f'/api/announcements/{ann_id}',
                                 headers={'Authorization': f'Bearer {token}'})
        self.assertTrue(rv2.get_json()['success'])

    def test_delete_without_token(self):
        rv = self.client.delete('/api/announcements/1')
        self.assertEqual(rv.status_code, 404)

    def test_toggle_pin(self):
        token = self._admin_token()
        rv = self.client.post('/api/announcements', json={
            'title': '可置顶', 'content': '测试',
        }, headers={'Authorization': f'Bearer {token}'})
        ann_id = rv.get_json()['id']

        rv2 = self.client.post(f'/api/announcements/{ann_id}/pin',
                               headers={'Authorization': f'Bearer {token}'})
        self.assertTrue(rv2.get_json()['success'])
        self.assertTrue(rv2.get_json()['announcement']['is_pinned'])

    def test_announcement_includes_author(self):
        token = self._admin_token()
        rv = self.client.post('/api/announcements', json={
            'title': '作者测试', 'content': '内容',
        }, headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(rv.get_json()['author'], 'admin')


if __name__ == '__main__':
    unittest.main()
