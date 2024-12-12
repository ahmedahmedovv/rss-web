import unittest
from app import app, init_db
import os

class TestApp(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        self.db_path = 'test_articles.db'
        
    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
            
    def test_index_route(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        
    def test_toggle_read(self):
        response = self.client.post('/toggle_read', 
                                  json={'link': 'https://example.com'})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('is_read', data)

if __name__ == '__main__':
    unittest.main() 