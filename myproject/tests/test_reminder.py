# -*- coding: utf-8 -*-
"""任务提醒与通知功能测试"""
import unittest, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import create_app
from models import db, Task, Notification
from datetime import date, timedelta


class TestReminderAndNotification(unittest.TestCase):
    """提醒与通知 API 测试"""

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

    def test_create_task_with_remind(self):
        rv = self.client.post('/api/tasks', json={
            'title': '带提醒', 'due_date': '2026-07-01',
            'remind_before_minutes': 1440,
        })
        d = rv.get_json()
        self.assertEqual(d['remind_before_minutes'], 1440)

    def test_update_remind(self):
        rv = self.client.post('/api/tasks', json={'title': '改提醒'})
        tid = rv.get_json()['id']
        rv2 = self.client.put(f'/api/tasks/{tid}', json={'remind_before_minutes': 60})
        self.assertEqual(rv2.get_json()['remind_before_minutes'], 60)

    def test_get_notifications_empty(self):
        rv = self.client.get('/api/notifications')
        self.assertEqual(len(rv.get_json()), 0)

    def test_unread_count(self):
        rv = self.client.get('/api/notifications/unread-count')
        self.assertEqual(rv.get_json()['count'], 0)

    def test_reminder_triggers(self):
        """过去日期的任务应触发提醒"""
        past = (date.today() - timedelta(days=1)).isoformat()
        self.client.post('/api/tasks', json={
            'title': '已到期', 'due_date': past,
            'remind_before_minutes': 60,
        })

        rv = self.client.get('/api/notifications/unread-count')
        count = rv.get_json()['count']
        self.assertGreater(count, 0)

    def test_reminder_generates_notification(self):
        past = (date.today() - timedelta(days=2)).isoformat()
        self.client.post('/api/tasks', json={
            'title': '已超期任务', 'due_date': past,
            'remind_before_minutes': 30,
        })

        rv = self.client.get('/api/notifications')
        notifs = rv.get_json()
        self.assertGreater(len(notifs), 0)
        self.assertIn('已超期任务', notifs[0]['message'])
        self.assertFalse(notifs[0]['is_read'])

    def test_mark_read(self):
        past = (date.today() - timedelta(days=1)).isoformat()
        self.client.post('/api/tasks', json={
            'title': '标记已读', 'due_date': past,
            'remind_before_minutes': 60,
        })
        rv = self.client.get('/api/notifications')
        nid = rv.get_json()[0]['id']

        rv2 = self.client.post(f'/api/notifications/{nid}/read')
        self.assertTrue(rv2.get_json()['success'])

        rv3 = self.client.get('/api/notifications/unread-count')
        self.assertEqual(rv3.get_json()['count'], 0)

    def test_mark_all_read(self):
        past = (date.today() - timedelta(days=1)).isoformat()
        self.client.post('/api/tasks', json={
            'title': 'A', 'due_date': past, 'remind_before_minutes': 60,
        })
        self.client.post('/api/tasks', json={
            'title': 'B', 'due_date': past, 'remind_before_minutes': 60,
        })
        self.client.get('/api/notifications')

        rv = self.client.post('/api/notifications/read-all')
        self.assertTrue(rv.get_json()['success'])

        rv2 = self.client.get('/api/notifications/unread-count')
        self.assertEqual(rv2.get_json()['count'], 0)

    def test_delete_notification(self):
        past = (date.today() - timedelta(days=1)).isoformat()
        self.client.post('/api/tasks', json={
            'title': '删我', 'due_date': past, 'remind_before_minutes': 60,
        })
        rv = self.client.get('/api/notifications')
        nid = rv.get_json()[0]['id']

        rv2 = self.client.delete(f'/api/notifications/{nid}')
        self.assertTrue(rv2.get_json()['success'])


if __name__ == '__main__':
    unittest.main()
