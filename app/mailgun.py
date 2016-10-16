'''app.mailgun'''

import requests
import json
import os
import logging

logger = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
def send(to, subject, body, conf):
    '''Send email via mailgun.
    @conf: db.agencies.mailgun
    @v: custom dict to included in webhooks
    Returns: mid string on success
    '''

    # Mailgun has no test API keys for use in test environment
    # If test mode enabled, re-route all emails to test address
    if os.environ.get('BRAVO_TEST_MODE') == 'True':
        to = 'estese@gmail.com'

    try:
        response = requests.post(
          'https://api.mailgun.net/v3/' + conf['domain'] + '/messages',
          auth=('api', conf['api_key']),
          data={
            'from': conf['from'],
            'to':  to,
            'subject': subject,
            'html': body,
            'v': json.dumps(v)
        })
    except requests.RequestException as e:
        logger.error('mailgun: %s ', str(e))
        pass

    logger.debug(response.text)

    return json.loads(response.text)['id']

