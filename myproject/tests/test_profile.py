# -*- coding: utf-8 -*-
"""用户个人资料 API 测试"""
import unittest
import os
import sys
import io
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import create_app
from models import db, User


class TestProfileAPI(unittest.TestCase):
    """个人资料查看/编辑 API 测试"""

    def setUp(self):
        self.app = create_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            user = User(username='profileuser', email='old@example.com')
            user.set_password('Test123456')
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id

    def tearDown(self):
        with self.app.app_context():
            db.drop_all()

    def _login(self):
        """辅助：以 profileuser 身份登录"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user_id
            sess['username'] = 'profileuser'
            sess['user_role'] = 'user'

    # ========== GET ==========
    def test_get_profile(self):
        with self.app.app_context():
            self._login()
            rv = self.client.get('/api/profile')
            data = rv.get_json()
            self.assertTrue(data['success'])
            self.assertEqual(data['user']['username'], 'profileuser')
            self.assertIn('avatar_url', data['user'])
            self.assertIn('email', data['user'])

    def test_get_profile_unauthenticated(self):
        rv = self.client.get('/api/profile')
        self.assertEqual(rv.status_code, 401)

    # ========== PUT 修改用户名 ==========
    def test_update_username_success(self):
        with self.app.app_context():
            self._login()
            rv = self.client.put('/api/profile', json={'username': 'newname'})
            data = rv.get_json()
            self.assertTrue(data['success'])
            self.assertEqual(data['user']['username'], 'newname')

    def test_update_username_too_short(self):
        with self.app.app_context():
            self._login()
            rv = self.client.put('/api/profile', json={'username': 'ab'})
            self.assertEqual(rv.status_code, 400)
            self.assertFalse(rv.get_json()['success'])

    def test_update_username_duplicate(self):
        with self.app.app_context():
            # 创建另一个用户
            other = User(username='existing', email='other@example.com')
            other.set_password('Test123456')
            db.session.add(other)
            db.session.commit()
            self._login()
            rv = self.client.put('/api/profile', json={'username': 'existing'})
            self.assertEqual(rv.status_code, 400)

    # ========== PUT 修改邮箱 ==========
    def test_update_email_success(self):
        with self.app.app_context():
            self._login()
            rv = self.client.put('/api/profile', json={'email': 'new@example.com'})
            data = rv.get_json()
            self.assertTrue(data['success'])
            self.assertEqual(data['user']['email'], 'new@example.com')

    def test_update_email_invalid(self):
        with self.app.app_context():
            self._login()
            rv = self.client.put('/api/profile', json={'email': 'not-an-email'})
            self.assertEqual(rv.status_code, 400)

    def test_update_email_duplicate(self):
        with self.app.app_context():
            other = User(username='otheruser', email='dup@example.com')
            other.set_password('Test123456')
            db.session.add(other)
            db.session.commit()
            self._login()
            rv = self.client.put('/api/profile', json={'email': 'dup@example.com'})
            self.assertEqual(rv.status_code, 400)

    # ========== PUT 修改头像 ==========
    def test_update_avatar_url(self):
        with self.app.app_context():
            self._login()
            rv = self.client.put('/api/profile', json={
                'avatar_url': 'https://example.com/avatar.png',
            })
            data = rv.get_json()
            self.assertTrue(data['success'])
            self.assertEqual(data['user']['avatar_url'], 'https://example.com/avatar.png')

    def test_update_avatar_url_clear(self):
        with self.app.app_context():
            self._login()
            # 先设置
            self.client.put('/api/profile', json={'avatar_url': 'https://ex.com/a.png'})
            # 再清空
            rv = self.client.put('/api/profile', json={'avatar_url': ''})
            data = rv.get_json()
            self.assertTrue(data['success'])
            self.assertIsNone(data['user']['avatar_url'])

    def test_update_avatar_url_invalid(self):
        with self.app.app_context():
            self._login()
            rv = self.client.put('/api/profile', json={
                'avatar_url': 'data:text/html,<script>',
            })
            self.assertEqual(rv.status_code, 400)

    # ========== PUT 修改密码 ==========
    def test_update_password_too_short(self):
        with self.app.app_context():
            self._login()
            rv = self.client.put('/api/profile', json={'password': '12345'})
            self.assertEqual(rv.status_code, 400)

    def test_update_password_success(self):
        with self.app.app_context():
            self._login()
            rv = self.client.put('/api/profile', json={'password': 'NewStrongPwd1'})
            self.assertTrue(rv.get_json()['success'])

    # ========== PUT 组合更新 ==========
    def test_update_multiple_fields(self):
        with self.app.app_context():
            self._login()
            rv = self.client.put('/api/profile', json={
                'username': 'newprofile',
                'email': 'newprofile@example.com',
                'avatar_url': 'https://example.com/avatar.png',
            })
            data = rv.get_json()
            self.assertTrue(data['success'])
            self.assertEqual(data['user']['username'], 'newprofile')
            self.assertEqual(data['user']['email'], 'newprofile@example.com')
            self.assertEqual(data['user']['avatar_url'], 'https://example.com/avatar.png')


class TestAvatarUpload(unittest.TestCase):
    """头像文件上传测试"""

    def setUp(self):
        self.app = create_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            user = User(username='avataruser', email='avatar@example.com')
            user.set_password('Test123456')
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id

    def tearDown(self):
        with self.app.app_context():
            db.drop_all()

    def _login(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user_id
            sess['username'] = 'avataruser'
            sess['user_role'] = 'user'

    def test_upload_avatar_no_file(self):
        with self.app.app_context():
            self._login()
            rv = self.client.post('/api/profile/avatar', data={},
                                  content_type='multipart/form-data')
            self.assertEqual(rv.status_code, 400)
            self.assertFalse(rv.get_json()['success'])

    def test_upload_avatar_disallowed_format(self):
        with self.app.app_context():
            self._login()
            data = {'avatar': (io.BytesIO(b'fake exe'), 'avatar.exe')}
            rv = self.client.post('/api/profile/avatar', data=data,
                                  content_type='multipart/form-data')
            self.assertEqual(rv.status_code, 400)

    def test_upload_avatar_success(self):
        with self.app.app_context():
            self._login()
            data = {'avatar': (io.BytesIO(b'fake png data'), 'avatar.png')}
            rv = self.client.post('/api/profile/avatar', data=data,
                                  content_type='multipart/form-data')
            result = rv.get_json()
            self.assertTrue(result['success'])
            self.assertIn('/static/avatars/', result['avatar_url'])
            self.assertEqual(result['user']['avatar_url'], result['avatar_url'])

    def test_upload_avatar_unauthenticated(self):
        rv = self.client.post('/api/profile/avatar')
        self.assertEqual(rv.status_code, 401)


if __name__ == '__main__':
    unittest.main()
