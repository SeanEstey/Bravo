'''app.tests.???'''
import unittest
from flask import url_for
from app import create_app
from app.tests import login, logout, get_db

class TemplateTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app('app', testing=True)
        self.client = self.app.test_client()
        self._ctx = self.app.test_request_context()
        self._ctx.push()
        self.db = get_db()
        login(self.client)

    def tearDown(self):
        logout(self.client)

    def test_func(self):
        print 'write me'

if __name__ == '__main__':
    unittest.main()
