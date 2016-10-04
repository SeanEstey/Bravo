
    def test_many_calls(self):
        calls = []
        base = '780453'
        msg_document = {
        'job_id': self.job_id,
        'call_status': 'pending',
        'attempts': 0,
        'imported': {
          'event_date': parse('december 31, 2014'),
          'to': '780-863-5715',
          'name': 'NIS',
          'status': 'Active',
          'office_notes': ''
        }
        }

        for x in range(1000,1100):
          call = base + str(x)
          print call
          response = reminders.dial(call)
          #self.assertEquals(response['call_status'], 'queued', msg=response)
          sid = response['sid']
          msg_document['sid'] = sid
          msg_document['call_status'] = 'queued'
          msg_document['imported']['to'] = call
          print msg_document
          self.db['msgs'].insert(msg_document)
          payload = MultiDict([
          ('CallSid', response['sid']),
          ('To', call),
          ('CallStatus', 'in-progress'),
          ('AnsweredBy', 'human')
          ])
          del msg_document['_id']
          response = requests.post(PUB_URL+'/call/answer', data=payload)
          xml_response = xml.dom.minidom.parseString(response.text)
          # Test valid XML returned by reminders.get_speak()
          self.assertTrue(isinstance(xml_response, xml.dom.minidom.Document))

    def test_integration_dial_and_answer_call(self):
        call = reminders.dial(self.reminder['call']['to'])

        r = self.db['reminders'].update_one(
        {'_id':self.reminder['_id']},
        {'$set':{
          'call.sid':call.sid,
          'call.status': call.status
        }},
        )

        logger.info('SID: %s', call.sid)

        self.assertEquals(r.modified_count, 1)

        payload =  {
          'CallSid': call.sid,
          'To': self.reminder['call']['to'],
          'CallStatus': 'in-progress',
          'AnsweredBy': 'human'
        }

        r = self.app.post('/reminders/call.xml', data=dict(payload))

        xml_response = xml.dom.minidom.parseString(r.data)
        # Test valid XML returned by reminders.get_speak()
        self.assertTrue(isinstance(xml_response, xml.dom.minidom.Document))

        logger.info(r.data)
