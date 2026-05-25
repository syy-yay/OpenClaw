# -*- coding: utf-8 -*-
"""JWT 认证功能测试"""
import unittest
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import create_app
from models import db, User


class TestJWTAuth(unittest.TestCase):
    """JWT 认证 API 测试"""

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

    # ===== 注册 =====
    def test_register_success(self):
        rv = self.client.post('/api/auth/register', json={
            'username': 'newuser', 'email': 'new@test.com', 'password': 'Pass123',
        })
        data = rv.get_json()
        self.assertEqual(rv.status_code, 201)
        self.assertTrue(data['success'])
        self.assertIn('token', data)
        self.assertEqual(data['user']['username'], 'newuser')

    def test_register_missing_fields(self):
        rv = self.client.post('/api/auth/register', json={'username': 'x'})
        self.assertEqual(rv.status_code, 400)

    def test_register_duplicate(self):
        self.client.post('/api/auth/register', json={
            'username': 'dup', 'email': 'dup@test.com', 'password': 'Pass123',
        })
        rv = self.client.post('/api/auth/register', json={
            'username': 'dup', 'email': 'dup2@test.com', 'password': 'Pass123',
        })
        self.assertEqual(rv.status_code, 400)

    def test_register_invalid_email(self):
        rv = self.client.post('/api/auth/register', json={
            'username': 'test', 'email': 'bademail', 'password': 'Pass123',
        })
        self.assertEqual(rv.status_code, 400)

    # ===== 登录 =====
    def test_login_success(self):
        self.client.post('/api/auth/register', json={
            'username': 'logintest', 'email': 'lt@test.com', 'password': 'Pass123',
        })
        rv = self.client.post('/api/auth/login', json={
            'identity': 'logintest', 'password': 'Pass123',
        })
        data = rv.get_json()
        self.assertTrue(data['success'])
        self.assertIn('token', data)

    def test_login_by_email(self):
        self.client.post('/api/auth/register', json={
            'username': 'emuser', 'email': 'em@test.com', 'password': 'Pass123',
        })
        rv = self.client.post('/api/auth/login', json={
            'identity': 'em@test.com', 'password': 'Pass123',
        })
        self.assertTrue(rv.get_json()['success'])

    def test_login_wrong_password(self):
        self.client.post('/api/auth/register', json={
            'username': 'wp', 'email': 'wp@test.com', 'password': 'Pass123',
        })
        rv = self.client.post('/api/auth/login', json={
            'identity': 'wp', 'password': 'wrong',
        })
        self.assertFalse(rv.get_json()['success'])
        self.assertEqual(rv.status_code, 401)

    def test_login_nonexistent(self):
        rv = self.client.post('/api/auth/login', json={
            'identity': 'nobody', 'password': 'anything',
        })
        self.assertEqual(rv.status_code, 401)

    # ===== JWT 令牌验证 =====
    def test_token_valid(self):
        rv = self.client.post('/api/auth/register', json={
            'username': 'tok', 'email': 'tok@test.com', 'password': 'Pass123',
        })
        token = rv.get_json()['token']
        rv2 = self.client.get('/api/auth/me', headers={
            'Authorization': f'Bearer {token}'
        })
        data = rv2.get_json()
        self.assertTrue(data['authenticated'])
        self.assertEqual(data['user']['username'], 'tok')

    def test_token_missing(self):
        rv = self.client.get('/api/auth/me')
        self.assertEqual(rv.status_code, 401)

    def test_token_invalid(self):
        rv = self.client.get('/api/auth/me', headers={
            'Authorization': 'Bearer invalidtoken'
        })
        self.assertEqual(rv.status_code, 401)

    # ===== 退出登录 =====
    def test_logout(self):
        rv = self.client.post('/api/auth/logout')
        self.assertTrue(rv.get_json()['success'])

    # ===== admin 默认账户 =====
    def test_admin_login(self):
        rv = self.client.post('/api/auth/login', json={
            'identity': 'admin', 'password': 'admin123',
        })
        data = rv.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['user']['username'], 'admin')


if __name__ == '__main__':
    unittest.main()
