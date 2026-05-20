# -*- coding: utf-8 -*-
"""首页功能测试"""
import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import create_app
from models import db, User


class TestHomepage(unittest.TestCase):
    """首页功能测试"""

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

    def test_homepage_accessible_to_everyone(self):
        """测试首页对所有人都可访问"""
        with self.app.app_context():
            # 未登录用户访问首页
            rv = self.client.get('/')
            self.assertEqual(rv.status_code, 200)
            # 应该看到登录/注册按钮
            self.assertIn('登录', rv.get_data(as_text=True))
            self.assertIn('注册', rv.get_data(as_text=True))
            # 不应该看到任务管理功能
            self.assertNotIn('创建新任务', rv.get_data(as_text=True))

    def test_homepage_for_authenticated_user(self):
        """测试登录用户访问首页"""
        with self.app.app_context():
            # 创建测试用户
            user = User(username='testuser', email='test@example.com')
            user.set_password('Test123456')
            db.session.add(user)
            db.session.commit()

            # 登录
            with self.client.session_transaction() as sess:
                sess['user_id'] = user.id
                sess['username'] = user.username

            # 登录用户访问首页
            rv = self.client.get('/')
            self.assertEqual(rv.status_code, 200)
            # 应该看到用户名和登出按钮
            self.assertIn('testuser', rv.get_data(as_text=True))
            self.assertIn('退出登录', rv.get_data(as_text=True))
            # 应该看到任务管理功能
            self.assertIn('创建新任务', rv.get_data(as_text=True))
            self.assertIn('任务列表', rv.get_data(as_text=True))

    def test_homepage_header_for_unauthenticated_user(self):
        """测试未登录用户的首页头部"""
        with self.app.app_context():
            rv = self.client.get('/')
            data = rv.get_data(as_text=True)
            self.assertEqual(rv.status_code, 200)
            # 应该有登录和注册按钮
            self.assertIn('href="/login"', data)
            self.assertIn('href="/register"', data)
            # 不应该有用户名显示
            self.assertNotIn('id="current-username"', data)

    def test_homepage_header_for_authenticated_user(self):
        """测试登录用户的首页头部"""
        with self.app.app_context():
            # 创建测试用户
            user = User(username='loggeduser', email='logged@example.com')
            user.set_password('Test123456')
            db.session.add(user)
            db.session.commit()

            # 登录
            with self.client.session_transaction() as sess:
                sess['user_id'] = user.id
                sess['username'] = user.username

            rv = self.client.get('/')
            data = rv.get_data(as_text=True)
            self.assertEqual(rv.status_code, 200)
            # 应该显示用户名
            self.assertIn('loggeduser', data)
            self.assertIn('id="current-username"', data)
            # 应该有登出按钮
            self.assertIn('id="logout-btn"', data)
            # 不应该有登录/注册按钮
            self.assertNotIn('href="/login"', data)
            self.assertNotIn('href="/register"', data)

    def test_logout_redirects_to_homepage(self):
        """测试登出后重定向到首页"""
        with self.app.app_context():
            # 创建测试用户并登录
            user = User(username='logouttest', email='logout@example.com')
            user.set_password('Test123456')
            db.session.add(user)
            db.session.commit()

            with self.client.session_transaction() as sess:
                sess['user_id'] = user.id
                sess['username'] = user.username

            # 登出
            rv = self.client.get('/logout', follow_redirects=True)
            self.assertEqual(rv.status_code, 200)
            # 应该重定向到首页，并显示登录/注册按钮
            data = rv.get_data(as_text=True)
            self.assertIn('登录', data)
            self.assertIn('注册', data)
            # 不应该显示用户名
            self.assertNotIn('logouttest', data)


if __name__ == '__main__':
    unittest.main()
