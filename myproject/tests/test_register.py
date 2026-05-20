# -*- coding: utf-8 -*-
"""用户注册功能测试"""
import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import create_app
from models import db, User


class TestRegisterAPI(unittest.TestCase):
    """注册API 测试"""

    def setUp(self):
        self.app = create_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.drop_all()

    # ---- 成功用例 ----
    def test_register_success(self):
        with self.app.app_context():
            rv = self.client.post('/register', json={
                'username': 'testuser',
                'email': 'test@example.com',
                'password': 'Pass123',
                'confirm_password': 'Pass123',
            })
            data = rv.get_json()
            self.assertTrue(data['success'])
            self.assertEqual(data['user']['username'], 'testuser')

    def test_register_auto_login(self):
        """注册成功后应自动登录，session 中包含用户信息"""
        with self.app.app_context():
            rv = self.client.post('/register', json={
                'username': 'autologin',
                'email': 'autologin@example.com',
                'password': 'Pass123456',
                'confirm_password': 'Pass123456',
            })
            self.assertTrue(rv.get_json()['success'])

            # 验证 session —— 应已自动登录
            rv2 = self.client.get('/api/check-session')
            data = rv2.get_json()
            self.assertTrue(data['authenticated'])
            self.assertEqual(data['user']['username'], 'autologin')
            self.assertIsNotNone(data['user']['id'])

    # ---- 参数缺失 ----
    def test_register_missing_username(self):
        with self.app.app_context():
            rv = self.client.post('/register', json={
                'email': 'a@b.com', 'password': '123456', 'confirm_password': '123456',
            })
            self.assertFalse(rv.get_json()['success'])

    def test_register_missing_password(self):
        with self.app.app_context():
            rv = self.client.post('/register', json={
                'username': 'bob', 'email': 'a@b.com',
            })
            self.assertFalse(rv.get_json()['success'])

    def test_register_missing_email(self):
        with self.app.app_context():
            rv = self.client.post('/register', json={
                'username': 'bob', 'password': '123456', 'confirm_password': '123456',
            })
            self.assertFalse(rv.get_json()['success'])

    # ---- 格式校验 ----
    def test_register_short_username(self):
        with self.app.app_context():
            rv = self.client.post('/register', json={
                'username': 'ab', 'email': 'a@b.com',
                'password': '123456', 'confirm_password': '123456',
            })
            self.assertFalse(rv.get_json()['success'])

    def test_register_long_username(self):
        with self.app.app_context():
            rv = self.client.post('/register', json={
                'username': 'a' * 21, 'email': 'a@b.com',
                'password': '123456', 'confirm_password': '123456',
            })
            self.assertFalse(rv.get_json()['success'])

    def test_register_short_password(self):
        with self.app.app_context():
            rv = self.client.post('/register', json={
                'username': 'validuser', 'email': 'a@b.com',
                'password': '12345', 'confirm_password': '12345',
            })
            self.assertFalse(rv.get_json()['success'])

    def test_register_invalid_email(self):
        with self.app.app_context():
            rv = self.client.post('/register', json={
                'username': 'validuser', 'email': 'not-email',
                'password': '123456', 'confirm_password': '123456',
            })
            self.assertFalse(rv.get_json()['success'])

    # ---- 密码确认 ----
    def test_register_password_mismatch(self):
        with self.app.app_context():
            rv = self.client.post('/register', json={
                'username': 'testuser', 'email': 'a@b.com',
                'password': 'Pass123', 'confirm_password': 'Different',
            })
            self.assertFalse(rv.get_json()['success'])
            self.assertIn('密码', rv.get_json()['message'])

    # ---- 重复注册 ----
    def test_register_duplicate_username(self):
        with self.app.app_context():
            self.client.post('/register', json={
                'username': 'dupuser', 'email': 'a@b.com',
                'password': 'Pass123', 'confirm_password': 'Pass123',
            })
            rv = self.client.post('/register', json={
                'username': 'dupuser', 'email': 'c@d.com',
                'password': 'Pass456', 'confirm_password': 'Pass456',
            })
            self.assertFalse(rv.get_json()['success'])

    def test_register_duplicate_email(self):
        with self.app.app_context():
            self.client.post('/register', json={
                'username': 'user1', 'email': 'same@b.com',
                'password': 'Pass123', 'confirm_password': 'Pass123',
            })
            rv = self.client.post('/register', json={
                'username': 'user2', 'email': 'same@b.com',
                'password': 'Pass456', 'confirm_password': 'Pass456',
            })
            self.assertFalse(rv.get_json()['success'])

    # ---- GET 页面 ----
    def test_register_page(self):
        rv = self.client.get('/register')
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b'register', rv.data.lower())


if __name__ == '__main__':
    unittest.main()
