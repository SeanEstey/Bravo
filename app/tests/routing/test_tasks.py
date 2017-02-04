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

    def _test_discover_routes_task(self):
        try:
            tasks.discover_routes(kwargs={'days':5})
        except Exception as e:
            log.debug('exc=%s', str(e), exc_info=True)
            #assert isinstance(rv, celery.result.AsyncResult)

    def _test_build_route(self):
        try:
            route_id='587f605d06dc2a32aa714c62'
            tasks.build_route(route_id, job_id=None)
        except Exception as e:
            log.debug('exc=%s', str(e), exc_info=True)

    def test_build_scheduled_routes(self):
        try:
            tasks.build_scheduled_routes(agcy='vec')
        except Exception as e:
            log.debug('exc=%s', str(e), exc_info=True)

    def _test_build_scheduled_routes_celery(self):
        try:
            tasks.build_scheduled_routes.delay(agcy='vec')
        except Exception as e:
            log.debug('exc=%s', str(e), exc_info=True)

if __name__ == '__main__':
    unittest.main()
