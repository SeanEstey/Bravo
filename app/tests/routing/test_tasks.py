'''app.tests.routing.test_tasks'''
import unittest, json
from app.tests import *
from app.routing import tasks

class RoutingTasksTests(unittest.TestCase):
    def setUp(self):
        init_client(self)
        login(self.client)

    def tearDown(self):
        logout(self.client)

    def test_show_routing(self):
        rv = self.client.get('/routing')
        assert rv.status_code == 200

    '''def test_build_route(self):
        rv = self.client.get('/routing/build/fake_id')
    '''
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

    def test_build_routes_view(self):
        rv = self.client.get('/_build_routes')
        assert json.loads(rv.data)['state'] == 'SUCCESS'

if __name__ == '__main__':
    unittest.main()
