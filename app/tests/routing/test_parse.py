'''app.tests.routing.test_parse'''
import unittest
from flask import url_for
from app import create_app, gsheets
from app.tests import login, logout, get_db
from app.routing import parse

class RoutingParseTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app('app', testing=True)
        self.client = self.app.test_client()
        self._ctx = self.app.test_request_context()
        self._ctx.push()
        self.db = get_db()
        login(self.client)

    def tearDown(self):
        logout(self.client)

    def test_to_dict(self):
        ss_id = '1iRwY6tzKEM-M28yaKr5dvFgi5j2cjTr5su5YWJa28X4'
        parse.to_dict('vec', ss_id)

    def test_order_to_dict(self):
        print 'order_to_dict'
        ss_id = '1iRwY6tzKEM-M28yaKr5dvFgi5j2cjTr5su5YWJa28X4'
        conf = self.db.agencies.find_one({'name':'vec'})
        print conf
        service = gsheets.gauth(conf['google']['oauth'])
        rows = gsheets.get_values(service, ss_id, 'A:J')
        order = parse.row_to_dict('vec', ss_id, rows[0], rows[2])
        print order

if __name__ == '__main__':
    unittest.main()
