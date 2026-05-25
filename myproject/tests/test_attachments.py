# -*- coding: utf-8 -*-
"""任务附件功能测试"""
import unittest, os, sys, io
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import create_app
from models import db, User, Attachment


class TestAttachmentAPI(unittest.TestCase):
    """附件 API 测试"""

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        # Create a task
        rv = self.client.post('/api/tasks', json={'title': '附件测试任务'})
        self.task_id = rv.get_json()['id']

    def tearDown(self):
        db.drop_all()
        self.ctx.pop()

    def test_upload_file(self):
        data = {'files': (io.BytesIO(b'test content'), 'test.txt')}
        rv = self.client.post(f'/api/tasks/{self.task_id}/attachments',
                              data=data, content_type='multipart/form-data')
        result = rv.get_json()
        self.assertEqual(rv.status_code, 201)
        self.assertEqual(len(result['uploaded']), 1)
        self.assertEqual(result['uploaded'][0]['original_name'], 'test.txt')

    def test_upload_multiple_files(self):
        data = {'files': [
            (io.BytesIO(b'content1'), 'a.txt'),
            (io.BytesIO(b'content2'), 'b.txt'),
        ]}
        rv = self.client.post(f'/api/tasks/{self.task_id}/attachments',
                              data=data, content_type='multipart/form-data')
        result = rv.get_json()
        self.assertEqual(len(result['uploaded']), 2)

    def test_upload_disallowed_type(self):
        data = {'files': (io.BytesIO(b'exe'), 'test.exe')}
        rv = self.client.post(f'/api/tasks/{self.task_id}/attachments',
                              data=data, content_type='multipart/form-data')
        result = rv.get_json()
        self.assertGreater(len(result['errors']), 0)

    def test_get_attachments(self):
        data = {'files': (io.BytesIO(b'test'), 'test.txt')}
        self.client.post(f'/api/tasks/{self.task_id}/attachments',
                         data=data, content_type='multipart/form-data')
        rv = self.client.get(f'/api/tasks/{self.task_id}/attachments')
        data = rv.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['original_name'], 'test.txt')
        self.assertIn('download_url', data[0])

    def test_download_attachment(self):
        data = {'files': (io.BytesIO(b'hello world'), 'hello.txt')}
        rv = self.client.post(f'/api/tasks/{self.task_id}/attachments',
                              data=data, content_type='multipart/form-data')
        att_id = rv.get_json()['uploaded'][0]['id']

        rv2 = self.client.get(f'/api/attachments/{att_id}/download')
        self.assertEqual(rv2.status_code, 200)
        self.assertEqual(rv2.data, b'hello world')

    def test_delete_attachment(self):
        data = {'files': (io.BytesIO(b'delete me'), 'del.txt')}
        rv = self.client.post(f'/api/tasks/{self.task_id}/attachments',
                              data=data, content_type='multipart/form-data')
        att_id = rv.get_json()['uploaded'][0]['id']

        rv2 = self.client.delete(f'/api/attachments/{att_id}')
        self.assertTrue(rv2.get_json()['success'])

        rv3 = self.client.get(f'/api/tasks/{self.task_id}/attachments')
        self.assertEqual(len(rv3.get_json()), 0)

    def test_attachment_info(self):
        data = {'files': (io.BytesIO(b'info'), 'info.txt')}
        rv = self.client.post(f'/api/tasks/{self.task_id}/attachments',
                              data=data, content_type='multipart/form-data')
        att_id = rv.get_json()['uploaded'][0]['id']

        rv2 = self.client.get(f'/api/attachments/{att_id}/info')
        self.assertEqual(rv2.get_json()['original_name'], 'info.txt')


if __name__ == '__main__':
    unittest.main()
