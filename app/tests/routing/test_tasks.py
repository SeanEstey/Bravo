'''app.tests.routing.test_tasks'''
import logging, unittest, json
from flask import g
from app.tests import *
from app.routing import tasks
log = logging.getLogger(__name__)

class RoutingTasksTests(unittest.TestCase):
    def setUp(self):
        init(self)
        login_self(self)

    def tearDown(self):
        logout(self.client)

    '''
    def test_analyze_routes_task(self):
        try:
            tasks.analyze_routes(kwargs={'days':5})
        except Exception as e:
            log.debug('exc=%s', str(e), exc_info=True)
            #assert isinstance(rv, celery.result.AsyncResult)
    '''
    def test_build_route(self):
        try:
            route_id='587f605d06dc2a32aa714c62'
            tasks.build_route(route_id, job_id=None)
            #tasks.build_route(args=[route_id], kwargs={'job_id':None})
        except Exception as e:
            log.debug('exc=%s', str(e), exc_info=True)

if __name__ == '__main__':
    unittest.main()
