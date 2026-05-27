# -*- coding: utf-8 -*-
"""搜索历史功能测试"""
import unittest, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import create_app
from models import db


class TestSearchHistory(unittest.TestCase):
    """搜索历史 API 测试"""

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

    def test_record_search(self):
        rv = self.client.post('/api/search-history', json={'keyword': 'bug修复'})
        self.assertEqual(rv.status_code, 201)
        self.assertEqual(rv.get_json()['search_history']['keyword'], 'bug修复')

    def test_get_empty_history(self):
        rv = self.client.get('/api/search-history')
        self.assertEqual(len(rv.get_json()), 0)

    def test_get_history(self):
        self.client.post('/api/search-history', json={'keyword': 'bug'})
        self.client.post('/api/search-history', json={'keyword': 'feature'})
        rv = self.client.get('/api/search-history')
        data = rv.get_json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['keyword'], 'feature')  # 最新的在前

    def test_deduplicate(self):
        self.client.post('/api/search-history', json={'keyword': 'bug'})
        self.client.post('/api/search-history', json={'keyword': 'feature'})
        self.client.post('/api/search-history', json={'keyword': 'bug'})  # 重复
        rv = self.client.get('/api/search-history')
        self.assertEqual(len(rv.get_json()), 2)  # 去重后只剩2条

    def test_max_history(self):
        # 插入 25 条
        for i in range(25):
            self.client.post('/api/search-history', json={'keyword': f'keyword{i}'})
        rv = self.client.get('/api/search-history')
        self.assertLessEqual(len(rv.get_json()), 20)

    def test_limit_10(self):
        for i in range(15):
            self.client.post('/api/search-history', json={'keyword': f'kw{i}'})
        rv = self.client.get('/api/search-history')
        self.assertLessEqual(len(rv.get_json()), 10)

    def test_empty_keyword(self):
        rv = self.client.post('/api/search-history', json={'keyword': ''})
        self.assertEqual(rv.status_code, 400)

    def test_clear_history(self):
        self.client.post('/api/search-history', json={'keyword': 'bug'})
        self.client.post('/api/search-history', json={'keyword': 'feature'})
        rv = self.client.delete('/api/search-history')
        self.assertTrue(rv.get_json()['success'])
        rv2 = self.client.get('/api/search-history')
        self.assertEqual(len(rv2.get_json()), 0)


if __name__ == '__main__':
    unittest.main()
