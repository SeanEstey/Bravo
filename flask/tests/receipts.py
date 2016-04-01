import unittest
import requests
import json
import sys
import os
import time
import twilio
import pymongo
import json
import datetime
from dateutil.parser import parse
from werkzeug.datastructures import MultiDict
import xml.dom.minidom

#os.chdir('/home/sean/Bravo/flask')
#sys.path.insert(0, '/home/sean/Bravo/flask')

os.chdir('/root/bravo_dev/Bravo/flask')
sys.path.insert(0, '/root/bravo_dev/Bravo/flask')

from config import *
import views
import gsheets
import receipts
import views
from app import log_handler, flask_app, celery_app

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)
logger.addHandler(log_handler)

class BravoTestCase(unittest.TestCase):

  def setUp(self):
      flask_app.config['TESTING'] = True
      self.app = flask_app.test_client()
      celery_app.conf.CELERY_ALWAYS_EAGER = True

      mongo_client = pymongo.MongoClient(MONGO_URL, MONGO_PORT)
      self.db = mongo_client[DB_NAME]
      self.login('seane@wsaf.ca', 'wsf')

      self.zero_gift = {
        "account_number": 57515, # Test Res
        "date": "04/06/2016",
        "amount": 0.00,
        "status": "Active",
        "next_pickup": "21/06/2016",
        "from": {
            "sheet": "Routes",
            "row": 2,
            "upload_status": "Success"
        }
      }



      self.gift = {
        "account_number": 57515, # Test Res
        "date": "04/06/2016",
        "amount": 10.00,
        "status": "Active",
        "next_pickup": "21/06/2016",
        "from": {
            "sheet": "Routes",
            "row": 3,
            "upload_status": "Success"
        }
      }

      self.gift_cancelled_act = {
        "account_number": 71675, # Cancelled Status
        "date": "04/06/2016",
        "amount": 0.00,
        "status": "Cancelled",
        "next_pickup": "21/06/2016",
        "from": {
            "sheet": "Routes",
            "row": 4,
            "upload_status": "Success"
        }
      }

      self.gift_no_email_act = self.gift.copy()
      self.gift_no_email_act['account_number'] = 67590
      self.gift_no_email_act['from']['row'] = 5

      self.zero_gift_bus = {
        "account_number": 57516, # Test Business
        "date": "04/06/2016",
        "amount": 5.00,
        "status": "Call-in",
        "next_pickup": "21/06/2016",
        "from": {
            "sheet": "Routes",
            "row": 6,
            "upload_status": "Success"
        }
      }

      self.etap_test_res_acct = {
          'id': 57515,
          'email': 'estese@gmail.com',
          'name': 'Sean Estey',
          'address': '7408 102 Ave NW',
          'postal': 'T6A 0P1',
          'gift_history': [
            { 'amount': '16.00', 'date': '1/3/2016' },
            { 'amount': '8.00', 'date': '2/3/2016' }
          ]
      }

  def tearDown(self):
      # Remove job record created by setUp
      foo = 'bar'

  def login(self, username, password):
      return self.app.post('/login', data=dict(
          username=username,
          password=password
      ), follow_redirects=True)


  def logout(self):
      return self.app.get('/logout', follow_redirects=True)

  #'''
  def test_send_zero_receipt(self):
      r = self.app.post(
        '/email/send',
        data=json.dumps({
          "recipient": self.etap_test_res_acct['email'],
          "subject": receipts.ZERO_COLLECTION_EMAIL_SUBJECT,
          "template": 'email/zero_collection_receipt.html',
          "data": {
            "entry": self.zero_gift,
            "account": self.etap_test_res_acct,
            "from": {}
          }
        }),
        content_type='application/json'
      )

      self.assertEquals(r.status_code, 200)
  #'''
  '''
  def test_send_gift_receipt(self):
      r = self.app.post(
        '/email/send',
        data=json.dumps({
          "recipient": self.etap_test_res_acct['email'],
          "subject": receipts.GIFT_RECEIPT_EMAIL_SUBJECT,
          "template": 'email/collection_receipt.html',
          "data": {
            "entry": self.gift,
            "account": self.etap_test_res_acct,
            "from": {'worksheet': 'foo'}
          }
        }),
        content_type='application/json'
      )

      self.assertEquals(r.status_code, 200)
  '''
  '''
  def test_process_receipts(self):
      # Hard to unit test because this function calls
      # /email/send from the live server.

      try:
          r = receipts.process.apply_async(
            args=([
                self.zero_gift,
                self.gift,
                self.gift_cancelled_act,
                self.gift_no_email_act,
                self.zero_gift_bus],
                ETAP_WRAPPER_KEYS),
            queue=DB_NAME
          )
      except Exception as e:
          logger.error(str(e))

      #logger.info(r.__dict__)
      self.assertEquals(r._state, 'SUCCESS')
  '''
  """
  def test_send_receipt(self):
      receipts.send(
        self.etap_test_res_acct,
        self.zero_gift,
        "email_zero_collection.html",
        receipts.ZERO_COLLECTION_EMAIL_SUBJECT
      )
  """

if __name__ == '__main__':
    logger.info('********** begin receipts.py unittest **********')
    unittest.main()
