'''app.tests.main.test_etap'''
import logging, unittest, json
from flask import g
from app.tests import *
from app.main.tasks import process_entries
log = logging.getLogger(__name__)


class EtapApiTests(unittest.TestCase):
    def setUp(self):
        init(self)
        login_self(self)

    def tearDown(self):
        logout(self.client)

    def test_process_entries(self):
        entry = {
		    'acct_id': 269,
		    'row': None,
		    'udf': {
			    'Status': 'Active',
			    'Neighborhood': 'Tuscany',
                'Block': 'R1Z',
                'Driver Notes': 'new driver_notes',
                'Office Notes': 'new office notes',
                'Next Pickup Date': '25/04/2017'},
		    'gift': {
                'amount': 0.00,
                'fund': 'General Operating',
                'campaign': 'Annual/General',
                'approach': 'Beverage Container Pick Up',
                'date': '20/04/2017',
                'note': 'Driver: Stew\n 1vb'}}

        import copy
        entries = [copy.deepcopy(entry) for i in range(11)]
        for i in range(0,len(entries)):
            entries[i]['row'] = i+2

        entries[5]['acct_id'] = 500000

        try:
            process_entries(entries=entries)
        except Exception as e:
            log.debug('exc=%s', str(e), exc_info=True)

if __name__ == '__main__':
    unittest.main()
