'''app.mailgun'''
import requests
import json
import os
import logging
from app import db_client
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def send(to, subject, body, conf, v=None):
    '''Send email via mailgun.
    @conf: db.agencies.mailgun
    @v: custom dict to included in webhooks
    Returns: mid string on success
    '''

    # Mailgun has no test API keys for use in test environment
    # If test mode enabled, re-route all emails to test address
    if os.environ.get('BRV_SANDBOX') == 'True':
        test_db = db_client['test']
        cred = test_db.credentials.find_one()['mailgun']
        conf = cred
        log.debug('sandbox mode. using domain="%s"', conf['domain'])
        to = conf['sandbox_to']

    data = {
        'from': conf['from'],
        'to':  to,
        'subject': subject,
        'html': body}

    if v:
        # Add custom vars: 'v:var:var_name:var_value'
        vars_ = {}
        for k in v:
            data['v:'+k] = v[k]

    try:
        response = requests.post(
          'https://api.mailgun.net/v3/' + conf['domain'] + '/messages',
          auth=('api', conf['api_key']),
          data=data)
    except requests.RequestException as e:
        log.error('mailgun: %s ', str(e))
        log.debug('', exc_info=True)
        raise

    #log.debug(response.text)

    return json.loads(response.text)['id']

#-------------------------------------------------------------------------------
def dump(form_values):
    form_values['message-headers'] = json.loads(form_values['message-headers'])
    log.debug(json.dumps(form_values, sort_keys=True, indent=4))

