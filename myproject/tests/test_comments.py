# -*- coding: utf-8 -*-
"""任务评论功能测试"""
import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import create_app
from models import db, User, Task, Comment


class TestCommentAPI(unittest.TestCase):
    """任务评论 API 测试"""

    def setUp(self):
        self.app = create_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        # 创建测试用户
        self.user = User(username='commenter', email='c@example.com')
        self.user.set_password('Test123456')
        db.session.add(self.user)

        self.admin = User(username='commentadmin', email='ca@example.com', role='admin')
        self.admin.set_password('Admin123456')
        db.session.add(self.admin)

        # 创建测试任务
        self.task = Task(title='测试任务', description='可评论的任务')
        db.session.add(self.task)
        db.session.commit()

        self.user_id = self.user.id
        self.admin_id = self.admin.id
        self.task_id = self.task.id

    def tearDown(self):
        db.drop_all()
        self.ctx.pop()

    def _login(self, user_id, username='commenter'):
        with self.client.session_transaction() as sess:
            sess['user_id'] = user_id
            sess['username'] = username
            sess['user_role'] = 'user'

    def _login_admin(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin_id
            sess['username'] = 'commentadmin'
            sess['user_role'] = 'admin'

    # ========== GET 评论列表 ==========
    def test_get_comments_empty(self):
        self._login(self.user_id)
        rv = self.client.get(f'/api/tasks/{self.task_id}/comments')
        data = rv.get_json()
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(len(data), 0)

    def test_get_comments_unauthenticated(self):
        rv = self.client.get(f'/api/tasks/{self.task_id}/comments')
        self.assertEqual(rv.status_code, 401)

    def test_get_comments_task_not_found(self):
        self._login(self.user_id)
        rv = self.client.get('/api/tasks/9999/comments')
        self.assertEqual(rv.status_code, 404)

    # ========== POST 发表评论 ==========
    def test_create_comment_success(self):
        self._login(self.user_id)
        rv = self.client.post(f'/api/tasks/{self.task_id}/comments', json={
            'content': '这是一个测试评论',
        })
        data = rv.get_json()
        self.assertEqual(rv.status_code, 201)
        self.assertTrue(data['success'])
        self.assertEqual(data['comment']['content'], '这是一个测试评论')
        self.assertEqual(data['comment']['task_id'], self.task_id)
        self.assertEqual(data['comment']['user']['username'], 'commenter')

    def test_create_comment_empty_content(self):
        self._login(self.user_id)
        rv = self.client.post(f'/api/tasks/{self.task_id}/comments', json={
            'content': '',
        })
        self.assertEqual(rv.status_code, 400)

    def test_create_comment_too_long(self):
        self._login(self.user_id)
        rv = self.client.post(f'/api/tasks/{self.task_id}/comments', json={
            'content': 'a' * 5001,
        })
        self.assertEqual(rv.status_code, 400)

    def test_create_comment_unauthenticated(self):
        rv = self.client.post(f'/api/tasks/{self.task_id}/comments', json={
            'content': 'test',
        })
        self.assertEqual(rv.status_code, 401)

    def test_create_comment_task_not_found(self):
        self._login(self.user_id)
        rv = self.client.post('/api/tasks/9999/comments', json={
            'content': 'test',
        })
        self.assertEqual(rv.status_code, 404)

    # ========== 获取非空评论列表 ==========
    def test_get_comments_with_data(self):
        self._login(self.user_id)
        self.client.post(f'/api/tasks/{self.task_id}/comments', json={
            'content': '第一条评论',
        })
        self.client.post(f'/api/tasks/{self.task_id}/comments', json={
            'content': '第二条评论',
        })
        rv = self.client.get(f'/api/tasks/{self.task_id}/comments')
        data = rv.get_json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['content'], '第一条评论')
        self.assertEqual(data[1]['content'], '第二条评论')

    def test_get_comments_multiple_tasks(self):
        self._login(self.user_id)
        task2 = Task(title='第二个任务')
        db.session.add(task2)
        db.session.commit()
        task2_id = task2.id

        self.client.post(f'/api/tasks/{self.task_id}/comments', json={'content': '任务1的评论'})
        self.client.post(f'/api/tasks/{task2_id}/comments', json={'content': '任务2的评论'})

        rv1 = self.client.get(f'/api/tasks/{self.task_id}/comments')
        self.assertEqual(len(rv1.get_json()), 1)

        rv2 = self.client.get(f'/api/tasks/{task2_id}/comments')
        self.assertEqual(len(rv2.get_json()), 1)

    # ========== DELETE 删除评论 ==========
    def test_delete_comment_by_author(self):
        self._login(self.user_id)
        rv = self.client.post(f'/api/tasks/{self.task_id}/comments', json={'content': '待删除'})
        comment_id = rv.get_json()['comment']['id']

        rv2 = self.client.delete(f'/api/comments/{comment_id}')
        self.assertTrue(rv2.get_json()['success'])

        # 验证软删除：GET 不再返回
        rv3 = self.client.get(f'/api/tasks/{self.task_id}/comments')
        self.assertEqual(len(rv3.get_json()), 0)

    def test_delete_comment_by_admin(self):
        self._login(self.user_id)
        rv = self.client.post(f'/api/tasks/{self.task_id}/comments', json={'content': '管理员可删'})
        comment_id = rv.get_json()['comment']['id']

        # 管理员登录
        self._login_admin()
        rv2 = self.client.delete(f'/api/comments/{comment_id}')
        self.assertTrue(rv2.get_json()['success'])

    def test_delete_comment_by_other_user(self):
        self._login(self.user_id)
        rv = self.client.post(f'/api/tasks/{self.task_id}/comments', json={'content': '别人的评论'})
        comment_id = rv.get_json()['comment']['id']

        # 其他用户尝试删除
        other = User(username='otheruser', email='other@example.com')
        other.set_password('Test123456')
        db.session.add(other)
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess['user_id'] = other.id
            sess['username'] = 'otheruser'
            sess['user_role'] = 'user'

        rv2 = self.client.delete(f'/api/comments/{comment_id}')
        self.assertEqual(rv2.status_code, 403)

    def test_delete_comment_not_found(self):
        self._login(self.user_id)
        rv = self.client.delete('/api/comments/9999')
        self.assertEqual(rv.status_code, 404)

    # ========== 评论含用户头像信息 ==========
    def test_comment_includes_user_info(self):
        self._login(self.user_id)
        # 设置用户头像
        self.user.avatar_url = '/static/avatars/test.png'
        db.session.commit()

        rv = self.client.post(f'/api/tasks/{self.task_id}/comments', json={'content': '测试头像'})
        data = rv.get_json()
        self.assertEqual(data['comment']['user']['avatar_url'], '/static/avatars/test.png')


if __name__ == '__main__':
    unittest.main()
