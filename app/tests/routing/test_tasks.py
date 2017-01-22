'''app.tests.routing.test_tasks'''
import unittest, json
from flask import g, url_for
from app import create_app, init_celery
from app.tests import *
from app.routing import tasks

class RoutingTasksTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app('app', testing=True)
        self.celery = init_celery(__name__, self.app)
        self.client = self.app.test_client()
        self._ctx = self.app.test_request_context()
        self._ctx.push()
        self.db = g.db = get_db()
        login(self.client)

    def tearDown(self):
        logout(self.client)

    '''def test_show_routing(self):
        rv = self.client.get('/routing')
        assert rv.status_code == 200

    def test_build_route(self):
        rv = self.client.get('/routing/build/fake_id')

    def test_edit_route(self):
        rv = self.client.post('/routing/edit/fake_id', data={
            'field':'depot', 'value':'foobar'})

    def test_analyze_routes_task(self):
        import celery.result
        rv = tasks.analyze_routes.apply(kwargs={'days':1})
        assert isinstance(rv, celery.result.AsyncResult)

    def test_analyze_routes_view(self):
        rv = self.client.get('/_analyze_routes')
        assert json.loads(rv.data)['state'] == 'SUCCESS'
    '''

    def test_build_routes_view(self):
        rv = self.client.get('/_build_routes')
        assert json.loads(rv.data)['state'] == 'SUCCESS'

if __name__ == '__main__':
    unittest.main()
