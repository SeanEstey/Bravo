'''app.mailgun'''
import requests
import json
import os
import logging
log = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def send(to, subject, body, conf, v=None):
    '''Send email via mailgun.
    @conf: db.agencies.mailgun
    @v: custom dict to included in webhooks
    Returns: mid string on success
    '''

    log.debug(conf)

    # Mailgun has no test API keys for use in test environment
    # If test mode enabled, re-route all emails to test address
    if os.environ.get('BRAVO_SANDBOX_MODE') == 'True':
        log.debug('sandbox mode enabled. rerouting email')
        to = conf['sandbox_to']

    data = {
        'from': conf['from'],
        'to':  to,
        'subject': subject,
        'html': body}

    # Add custom vars: 'v:var:var_name:var_value'
    vars_ = {}
    for k in v:
        data['v:'+k] = v[k]

    log.debug(data)

    try:
        response = requests.post(
          'https://api.mailgun.net/v3/' + conf['domain'] + '/messages',
          auth=('api', conf['api_key']),
          data=data)
    except requests.RequestException as e:
        log.error('mailgun: %s ', str(e))
        log.debug('', exc_info=True)
        pass

    log.debug(response.text)

    return 'ok' #json.loads(response.text)['id']

