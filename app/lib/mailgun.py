'''app.mailgun'''
import json, logging, requests
from flask import g, current_app
from os import environ as env
#from app import db_client
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
def send(to, subject, body, conf, v=None):
    '''Send email via mailgun.
    @conf: db.agencies.mailgun
    @v: custom dict to included in webhooks
    Returns: mid string on success
    '''

    # Mailgun has no test API keys for use in test environment
    # If test mode enabled, re-route all emails to test address
    if env.get('BRV_SANDBOX') == 'True':
        test_db = current_app.db_client['test']
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
        g.group = g.db.agencies.find_one({'mailgun.from':conf['from']})
        log.exception('Mailgun error')
        raise

    if response.status_code == requests.codes.ok:
        return json.loads(response.text)['id']
    else:
        raise Exception('Error sending email to "%s"' % to)

#-------------------------------------------------------------------------------
def dump(form_values):
    form_values['message-headers'] = json.loads(form_values['message-headers'])
    log.debug(json.dumps(form_values, sort_keys=True, indent=4))

