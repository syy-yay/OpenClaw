# -*- coding: utf-8 -*-
"""第三方登录和登录日志测试"""
import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import create_app
from models import db, User, LoginLog


class TestOAuthAndLogging(unittest.TestCase):
    """OAuth 和登录日志测试"""

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

    def test_oauth_endpoints_exist(self):
        """测试 OAuth 路由是否存在"""
        with self.app.app_context():
            # 测试 OAuth 登录入口
            rv = self.client.get('/auth/github')
            self.assertEqual(rv.status_code, 200)
            
            rv = self.client.get('/auth/wechat')
            self.assertEqual(rv.status_code, 200)
            
            rv = self.client.get('/auth/qq')
            self.assertEqual(rv.status_code, 200)
            
            # 测试不支持的提供商
            rv = self.client.get('/auth/facebook')
            self.assertEqual(rv.status_code, 400)

    def test_oauth_callback_endpoints_exist(self):
        """测试 OAuth 回调路由是否存在"""
        with self.app.app_context():
            # 测试 OAuth 回调
            rv = self.client.get('/auth/github/callback')
            self.assertEqual(rv.status_code, 200)
            
            rv = self.client.get('/auth/wechat/callback')
            self.assertEqual(rv.status_code, 200)
            
            rv = self.client.get('/auth/qq/callback')
            self.assertEqual(rv.status_code, 200)
            
            # 测试不支持的提供商
            rv = self.client.get('/auth/facebook/callback')
            self.assertEqual(rv.status_code, 400)

    def test_login_logging_success(self):
        """测试登录成功日志记录"""
        with self.app.app_context():
            # 创建测试用户
            user = User(username='logger_test', email='log@test.com')
            user.set_password('Test123456')
            db.session.add(user)
            db.session.commit()
            
            # 登录
            rv = self.client.post('/login', json={
                'identity': 'logger_test',
                'password': 'Test123456',
            })
            self.assertTrue(rv.get_json()['success'])
            
            # 检查日志
            logs = LoginLog.query.all()
            self.assertEqual(len(logs), 1)
            log = logs[0]
            self.assertTrue(log.success)
            self.assertEqual(log.login_method, 'password')
            self.assertIsNotNone(log.ip_address)
            self.assertEqual(log.user_id, user.id)

    def test_login_logging_failure(self):
        """测试登录失败日志记录"""
        with self.app.app_context():
            # 登录失败
            rv = self.client.post('/login', json={
                'identity': 'nonexistent',
                'password': 'wrong',
            })
            self.assertFalse(rv.get_json()['success'])
            
            # 检查日志
            logs = LoginLog.query.all()
            self.assertEqual(len(logs), 1)
            log = logs[0]
            self.assertFalse(log.success)
            self.assertEqual(log.failure_reason, 'invalid_credentials')
            self.assertIsNone(log.user_id)
            self.assertEqual(log.username_attempted, 'nonexistent')

    def test_login_logging_missing_fields(self):
        """测试缺少字段的日志记录"""
        with self.app.app_context():
            # 登录缺少字段
            rv = self.client.post('/login', json={'identity': 'test'})
            self.assertEqual(rv.status_code, 400)
            
            # 检查日志
            logs = LoginLog.query.all()
            self.assertEqual(len(logs), 1)
            log = logs[0]
            self.assertFalse(log.success)
            self.assertEqual(log.failure_reason, 'missing_fields')

    def test_user_with_oauth_info(self):
        """测试带有 OAuth 信息的用户"""
        with self.app.app_context():
            # 创建 OAuth 用户
            user = User(
                username='oauth_user',
                email='oauth@test.com',
                oauth_provider='github',
                oauth_id='github_12345'
            )
            db.session.add(user)
            db.session.commit()
            
            # 检查用户信息
            retrieved_user = User.query.get(user.id)
            self.assertEqual(retrieved_user.oauth_provider, 'github')
            self.assertEqual(retrieved_user.oauth_id, 'github_12345')
            # OAuth 用户不应有密码
            self.assertIsNone(retrieved_user.password_hash)
            # 检查密码验证对 OAuth 用户应返回 False
            self.assertFalse(retrieved_user.check_password('any_password'))


if __name__ == '__main__':
    unittest.main()
