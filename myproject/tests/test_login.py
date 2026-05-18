# -*- coding: utf-8 -*-
"""用户登录功能测试"""
import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import create_app, rate_limiter
from models import db, User


class TestLoginAPI(unittest.TestCase):
    """登录API 测试"""

    def setUp(self):
        self.app = create_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            # create_app 已经创建了 admin，这里只添加测试用户
            db.create_all()
            user = User(username='testuser', email='test@example.com',
                        phone='13800138000', role='user')
            user.set_password('Test123456')
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id

    def tearDown(self):
        with self.app.app_context():
            db.drop_all()
        rate_limiter._failures.clear()

    # ---- 成功登录 ----
    def test_login_by_username(self):
        with self.app.app_context():
            rv = self.client.post('/login', json={
                'identity': 'testuser',
                'password': 'Test123456',
            })
            data = rv.get_json()
            self.assertTrue(data['success'])
            self.assertEqual(data['user']['username'], 'testuser')

    def test_login_by_email(self):
        with self.app.app_context():
            rv = self.client.post('/login', json={
                'identity': 'test@example.com',
                'password': 'Test123456',
            })
            self.assertTrue(rv.get_json()['success'])

    def test_login_by_phone(self):
        with self.app.app_context():
            rv = self.client.post('/login', json={
                'identity': '13800138000',
                'password': 'Test123456',
            })
            self.assertTrue(rv.get_json()['success'])

    # ---- 失败登录 ----
    def test_login_wrong_password(self):
        with self.app.app_context():
            rv = self.client.post('/login', json={
                'identity': 'testuser',
                'password': 'wrongpassword',
            })
            self.assertFalse(rv.get_json()['success'])
            self.assertEqual(rv.status_code, 401)

    def test_login_nonexistent_user(self):
        with self.app.app_context():
            rv = self.client.post('/login', json={
                'identity': 'nobody',
                'password': 'anything',
            })
            self.assertFalse(rv.get_json()['success'])

    def test_login_missing_fields(self):
        with self.app.app_context():
            rv = self.client.post('/login', json={'identity': 'testuser'})
            self.assertFalse(rv.get_json()['success'])
            self.assertEqual(rv.status_code, 400)

            rv = self.client.post('/login', json={'password': 'test'})
            self.assertFalse(rv.get_json()['success'])
            self.assertEqual(rv.status_code, 400)

    # ---- 暴力破解防护 ----
    def test_login_rate_limit(self):
        with self.app.app_context():
            for _ in range(5):
                self.client.post('/login', json={
                    'identity': 'testuser',
                    'password': 'wrong',
                })
            rv = self.client.post('/login', json={
                'identity': 'testuser',
                'password': 'Test123456',
            })
            data = rv.get_json()
            self.assertFalse(data['success'])
            self.assertEqual(rv.status_code, 429)
            self.assertIn('lockout_time', data)

    # ---- 会话管理 ----
    def test_login_sets_session(self):
        with self.app.app_context():
            with self.client as c:
                c.post('/login', json={
                    'identity': 'testuser',
                    'password': 'Test123456',
                })
                rv2 = c.get('/api/check-session')
                data = rv2.get_json()
                self.assertTrue(data['authenticated'])
                self.assertEqual(data['user']['username'], 'testuser')

    def test_login_page_redirect_when_authenticated(self):
        with self.app.app_context():
            with self.client as c:
                c.post('/login', json={
                    'identity': 'testuser',
                    'password': 'Test123456',
                })
                rv = c.get('/login', follow_redirects=False)
                self.assertEqual(rv.status_code, 302)

    def test_login_page_get(self):
        rv = self.client.get('/login')
        self.assertEqual(rv.status_code, 200)

    # ---- 权限控制 ----
    def test_unauthenticated_api_access(self):
        rv = self.client.get('/api/check-session')
        self.assertEqual(rv.status_code, 401)

    def test_unauthenticated_task_access(self):
        rv = self.client.get('/api/tasks')
        self.assertEqual(rv.status_code, 401)

    def test_logout(self):
        with self.app.app_context():
            with self.client as c:
                c.post('/login', json={
                    'identity': 'testuser',
                    'password': 'Test123456',
                })
                rv = c.get('/logout', follow_redirects=False)
                self.assertEqual(rv.status_code, 302)

                rv2 = c.get('/api/check-session')
                self.assertEqual(rv2.status_code, 401)


class TestRegisterWithPhone(unittest.TestCase):
    """注册功能测试（含手机号）"""

    def setUp(self):
        self.app = create_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.drop_all()

    def test_register_with_phone(self):
        with self.app.app_context():
            rv = self.client.post('/register', json={
                'username': 'phoneuser',
                'email': 'phone@example.com',
                'password': 'Pass123456',
                'confirm_password': 'Pass123456',
                'phone': '13900139000',
            })
            data = rv.get_json()
            self.assertTrue(data['success'])
            self.assertEqual(data['user']['username'], 'phoneuser')

    def test_register_invalid_phone(self):
        with self.app.app_context():
            rv = self.client.post('/register', json={
                'username': 'badphone',
                'email': 'bp@example.com',
                'password': 'Pass123',
                'confirm_password': 'Pass123',
                'phone': '12345',
            })
            self.assertFalse(rv.get_json()['success'])

    def test_register_duplicate_phone(self):
        with self.app.app_context():
            self.client.post('/register', json={
                'username': 'u1', 'email': 'a@b.com',
                'password': 'Pass123', 'confirm_password': 'Pass123',
                'phone': '13900139000',
            })
            rv = self.client.post('/register', json={
                'username': 'u2', 'email': 'c@d.com',
                'password': 'Pass456', 'confirm_password': 'Pass456',
                'phone': '13900139000',
            })
            self.assertFalse(rv.get_json()['success'])


class TestPermissionControl(unittest.TestCase):
    """权限控制测试"""

    def setUp(self):
        self.app = create_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.drop_all()

    def test_admin_can_list_users(self):
        with self.app.app_context():
            with self.client as c:
                c.post('/login', json={
                    'identity': 'admin', 'password': 'admin123',
                })
                rv = c.get('/api/users')
                self.assertEqual(rv.status_code, 200)

    def test_user_cannot_list_users(self):
        with self.app.app_context():
            user = User(username='normaluser', email='nu@example.com', role='user')
            user.set_password('Test123456')
            db.session.add(user)
            db.session.commit()
            with self.client as c:
                c.post('/login', json={
                    'identity': 'normaluser', 'password': 'Test123456',
                })
                rv = c.get('/api/users')
                self.assertEqual(rv.status_code, 403)

    def test_user_can_create_task(self):
        with self.app.app_context():
            user = User(username='tasker', email='tk@example.com', role='user')
            user.set_password('Test123456')
            db.session.add(user)
            db.session.commit()
            with self.client as c:
                c.post('/login', json={
                    'identity': 'tasker', 'password': 'Test123456',
                })
                rv = c.post('/api/tasks', json={'title': '测试任务'})
                self.assertEqual(rv.status_code, 201)

    def test_profile_update(self):
        with self.app.app_context():
            with self.client as c:
                c.post('/login', json={
                    'identity': 'admin', 'password': 'admin123',
                })
                rv = c.get('/api/profile')
                data = rv.get_json()
                self.assertTrue(data['success'])
                self.assertEqual(data['user']['role'], 'admin')


if __name__ == '__main__':
    unittest.main()
