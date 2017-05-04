'''app.tests.main.test_leaderboard'''
import logging, unittest, json
from flask import g
from app.tests.__init__ import *
from app import get_keys
from app.main import leaderboard
log = Loggy('test_leaderboard')

class LeaderboardTests(unittest.TestCase):
    def setUp(self):
        init(self)
        login_self(self)
        login_client(self.client)

    def tearDown(self):
        logout(self.client)

    def _test_get_all_ytd(self):
        leaderboard.get_all_ytd('vec')

    def test_get_rank(self):
        leaderboard.get_rank('Deer Ridge', 'vec')
        leaderboard.get_rank('Bowness', 'vec')
        leaderboard.get_rank('Citadel', 'vec')
        leaderboard.get_rank('Varsity', 'vec')
        leaderboard.get_rank('Hawkwood', 'vec')

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
