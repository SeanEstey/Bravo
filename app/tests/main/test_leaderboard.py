'''app.tests.main.test_leaderboard'''
import logging, unittest, json
from flask import g
from app.tests.__init__ import *
from app import get_keys, get_logger
from app.main import leaderboard
log = get_logger('test_leaderboard')

class LeaderboardTests(unittest.TestCase):
    def setUp(self):
        init(self)
        login_self(self)
        login_client(self.client)

    def tearDown(self):
        logout(self.client)

    def test_get_ytd_total(self):
        neighbhds = ['Tuscany', 'Royal Oak', 'Rocky Ridge', 'Bowness', 'Scenic Acres']

        for neighbhd in neighbhds:
            leaderboard.get_ytd_total(neighbhd, 'vec')

    def _test_update_accts(self):
        query = 'foo'
        agcy = 'foo'
        leaderboard.update_accts(query, agcy)

    def _test_update_leaderboard_task(self):
        from app.main import tasks
        try:
            tasks.update_leaderboard_accts.delay(agcy='vec')
        except Exception as e:
            log.debug('exc=%s', str(e), exc_info=True)

if __name__ == '__main__':
    unittest.main()
